# Copyright (c) 2026, Hybrowlabs and contributors
# For license information, please see license.txt
"""Server API for the "Consolidated Financial Statement" desk page.

Shows the face of the Balance Sheet / Profit & Loss for every domestic company
(functional currency == DOMESTIC_CURRENCY) as a single columnar statement:

    Particular | Consolidate | <Company 1> | <Company 2> | ...

`Consolidate` is the arithmetic total of the domestic companies shown (a simple
sum per line item, not an eliminations-based consolidation). Values are read
from the structured `table_data` of already-generated Financial Report
documents, so this page never triggers a fresh report generation.
"""

import difflib
import json
from collections import Counter

import frappe
from frappe.utils import flt

# Companies shown on this page are chosen explicitly via a checkbox on the Company
# master ("Include in Consolidated Financials") rather than inferred from currency.
INCLUDE_FIELD = "custom_include_in_consolidated_financials"

BALANCE_SHEET = "Balance Sheet"
PROFIT_AND_LOSS = "Profit & Loss"
STATEMENTS = (BALANCE_SHEET, PROFIT_AND_LOSS)


def _storage_report_type(report_type):
	"""Report Type as stored on Financial Report.

	"FTM" is not a stored report type — it is a presentation of the Monthly
	reports showing only the For-The-Month (movement) column, so it maps to the
	stored "Monthly" reports.
	"""
	return "Monthly" if report_type in ("Monthly", "FTM") else report_type


def _is_monthly_like(report_type):
	"""True when the view is driven by Monthly reports (Monthly or FTM)."""
	return _storage_report_type(report_type) == "Monthly"

# Indian fiscal year runs April -> March; present months in that order.
FISCAL_MONTH_ORDER = [
	"April", "May", "June", "July", "August", "September",
	"October", "November", "December", "January", "February", "March",
]


def _month_sort_key(m):
	try:
		return FISCAL_MONTH_ORDER.index(m)
	except ValueError:
		return 99


CALENDAR_MONTHS = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]


def _prev_month(m):
	"""Calendar month before `m` (e.g. April -> March, January -> December)."""
	if m not in CALENDAR_MONTHS:
		return None
	return CALENDAR_MONTHS[(CALENDAR_MONTHS.index(m) - 1) % 12]


def _fiscal_months_upto(end_month):
	"""Fiscal-order months from April up to and including `end_month`.

	Used by the "All FTM" view to show every month's movement from the start of
	the fiscal year through the selected month. Falls back to the full fiscal
	year when `end_month` is missing or unrecognised.
	"""
	if end_month in FISCAL_MONTH_ORDER:
		return FISCAL_MONTH_ORDER[: FISCAL_MONTH_ORDER.index(end_month) + 1]
	return list(FISCAL_MONTH_ORDER)


def _company_order():
	"""Return the user-configured company display order from FR Financial Settings.

	[{name -> ordinal}] built from the "Company Order" child table; companies not
	listed there sort after the listed ones, alphabetically.
	"""
	rows = frappe.get_all(
		"FR Company Order",
		filters={"parent": "FR Financial Settings"},
		fields=["company"],
		order_by="idx asc",
	)
	return {r.company: i for i, r in enumerate(rows)}


def _domestic_companies():
	"""Return the companies flagged for this statement as [{name, currency}].

	Selection is the "Include in Consolidated Financials" checkbox on the Company
	master (falls back to nothing if the field is not installed yet). Display
	order follows FR Financial Settings' "Company Order" table when set, with
	unlisted companies sorted alphabetically after the listed ones.
	"""
	if not frappe.db.has_column("Company", INCLUDE_FIELD):
		return []
	companies = frappe.get_all(
		"Company",
		filters={INCLUDE_FIELD: 1},
		fields=["name", "default_currency as currency"],
		order_by="name asc",
	)
	order = _company_order()
	if not order:
		return companies
	companies.sort(key=lambda c: (order.get(c.name, len(order)), c.name))
	return companies


def _strategic_companies():
	"""Companies offered on the Strategic Expense tab, as [{name, currency}].

	Exactly the companies listed in FR Financial Settings -> Company Order, in
	that order (still limited to those flagged "Include in Consolidated
	Financials", which is what the statements show). While the table is empty
	every flagged company is returned so the tab is not left blank.
	"""
	companies = _domestic_companies()
	order = _company_order()
	if not order:
		return companies
	return [c for c in companies if c.name in order]


def _pick_report(company, report_type, fiscal_year=None, month=None):
	"""Return the best Financial Report row for a company.

	Preference: matching fiscal year / month (when given) -> Successful status
	-> most recently modified.
	"""
	filters = {"company": company, "report_type": report_type}
	if fiscal_year:
		filters["fiscal_year"] = fiscal_year
	if month and report_type == "Monthly":
		filters["current_month"] = month

	rows = frappe.get_all(
		"FR Financial Report",
		filters=filters,
		fields=["name", "fiscal_year", "previous_fiscal_year", "report_status", "report_generated_on"],
		order_by="modified desc",
	)
	if not rows:
		return None
	for r in rows:
		if r.report_status == "Successful":
			return r
	return rows[0]


def _statement_rows(report_name, section_type):
	"""Return the structured line-item rows (from table_data) for a section."""
	detail = frappe.get_all(
		"FR Financial Report Details",
		filters={
			"parent": report_name,
			"parenttype": "FR Financial Report",
			"section_type": section_type,
		},
		fields=["table_data"],
		order_by="idx asc",
		limit=1,
	)
	if not detail or not (detail[0].table_data or "").strip():
		return None
	try:
		rows = json.loads(detail[0].table_data)
	except (ValueError, TypeError):
		return None
	return rows or None


# "Revenue from operations" and "Other expenses" are bifurcated from the GL
# grouping: accounts mapped under a primary group, split by secondary group.
# Revenue uses a fixed two-way split (in this order); Other expenses shows
# every secondary group configured for it (the set varies per company, so it
# is derived per request rather than hardcoded).
REVENUE_PRIMARY_GROUP = "Revenue from Operations"
REVENUE_SECONDARY_GROUPS = ["Domestic Sales", "Export Sales"]
OTHER_EXPENSES_PRIMARY_GROUP = "Other expenses"
# Trial-balance amounts are raw rupees; Income carries a credit (negative) sign
# and Expense carries a debit (positive) sign. The page shows positive ₹ Lacs,
# so display = sign * amount / LACS (sign -1 for income groups, +1 for expense).
LACS = 100000.0

# User-entered "Strategic Expense" figures (per company / primary group / secondary
# group / fiscal year / month). Each amount is reclassified out of that secondary
# group of its primary group's P&L face row into the Strategic Expense line.
STRATEGIC_DOCTYPE = "FR Strategic Expense Entry"
EMPLOYEE_EMOLUMENTS_PRIMARY_GROUP = "Employee Emoluments"
# Primary groups a Strategic Expense can come out of -> prefix of the (normalised)
# P&L face row that group's amounts reduce.
STRATEGIC_PRIMARY_GROUPS = {
	OTHER_EXPENSES_PRIMARY_GROUP: "other expenses",
	EMPLOYEE_EMOLUMENTS_PRIMARY_GROUP: "employee benefit",
}


def _fetch_strategic(companies, fiscal_years):
	"""Return {primary_group: {(company, secondary_group, fiscal_year, month): amount}}."""
	companies = [c for c in (companies or [])]
	fiscal_years = [y for y in (fiscal_years or []) if y]
	if not companies or not fiscal_years:
		return {}
	if not frappe.db.exists("DocType", STRATEGIC_DOCTYPE):
		return {}  # DocType not installed yet — treat as no data
	rows = frappe.get_all(
		STRATEGIC_DOCTYPE,
		filters={
			"company": ["in", companies],
			"fiscal_year": ["in", fiscal_years],
			"secondary_group": ["is", "set"],
		},
		fields=["company", "primary_group", "secondary_group", "fiscal_year", "month", "amount"],
		limit_page_length=0,
	)
	agg = {}
	for r in rows:
		# Entries saved before primary_group existed were all Other expenses.
		per_primary = agg.setdefault(r.primary_group or OTHER_EXPENSES_PRIMARY_GROUP, {})
		key = (r.company, r.secondary_group, r.fiscal_year, r.month)
		per_primary[key] = per_primary.get(key, 0.0) + flt(r.amount)
	return agg


def _strategic_amounts(
	company_names, report_type, fiscal_year, month, previous_fiscal_year,
	primary_group=OTHER_EXPENSES_PRIMARY_GROUP, fetched=None,
):
	"""{company: {secondary_group: {measure_key: amount}}} for one primary group.

	Entries are monthly amounts, so: Yearly sums the fiscal year; Monthly gives
	the cumulative-to-month (cm), the month itself (ftm) and cumulative-to-prev
	(pm); FTM gives the single month. `fetched` is a prior `_fetch_strategic`
	result, to avoid re-querying when several primary groups are needed.
	"""
	if fetched is None:
		fetched = _fetch_strategic(company_names, [fiscal_year, previous_fiscal_year])
	raw = fetched.get(primary_group, {})
	groups = sorted({g for (_c, g, _fy, _m) in raw})

	def m_amt(c, g, fy, m):
		return raw.get((c, g, fy, m), 0.0)

	def cum(c, g, fy, upto):
		return sum(m_amt(c, g, fy, m) for m in _fiscal_months_upto(upto))

	def year_total(c, g, fy):
		return sum(m_amt(c, g, fy, m) for m in FISCAL_MONTH_ORDER) if fy else 0.0

	out = {}
	for c in company_names:
		out[c] = {}
		for g in groups:
			if report_type == "FTM":
				out[c][g] = {"ftm": m_amt(c, g, fiscal_year, month)}
			elif report_type == "Monthly":
				months_up = _fiscal_months_upto(month)
				out[c][g] = {
					"cm": cum(c, g, fiscal_year, month),
					"ftm": m_amt(c, g, fiscal_year, month),
					"pm": sum(m_amt(c, g, fiscal_year, m) for m in months_up[:-1]),
				}
			else:  # Yearly
				out[c][g] = {
					"cy": year_total(c, g, fiscal_year),
					"py": year_total(c, g, previous_fiscal_year),
				}
	return out


def _strategic_amounts_all_ftm(
	company_names, month_range, fiscal_year,
	primary_group=OTHER_EXPENSES_PRIMARY_GROUP, fetched=None,
):
	"""All-FTM Strategic Expense per company/group: one month's amount per month column."""
	if fetched is None:
		fetched = _fetch_strategic(company_names, [fiscal_year])
	raw = fetched.get(primary_group, {})
	groups = sorted({g for (_c, g, _fy, _m) in raw})
	return {
		c: {g: {m.lower(): raw.get((c, g, fiscal_year, m), 0.0) for m in month_range} for g in groups}
		for c in company_names
	}


def _strategic_company_totals(by_group):
	"""Collapse {company: {group: {k: v}}} to {company: {k: sum over groups}}."""
	out = {}
	for c, groups in by_group.items():
		tot = {}
		for cells in groups.values():
			for k, v in cells.items():
				tot[k] = tot.get(k, 0.0) + v
		out[c] = tot
	return out


def _subtract_strategic_from_split(split, groups, by_group):
	"""Subtract Strategic Expense from the matching secondary-group cells of an
	Other-expenses split (in place). Groups that only appear in the entries are
	added so the breakdown always foots to the reduced face row. Returns the
	(sorted) group list."""
	groups = set(groups)
	for c, per_group in by_group.items():
		for g, cells in per_group.items():
			groups.add(g)
			cell = split.setdefault(c, {}).setdefault(g, {})
			for k, v in cells.items():
				cell[k] = round((cell.get(k) or 0.0) - v, 2)
	return sorted(groups)


def _adjust_row(row, company_names, measure_keys, strategic, sign):
	"""Add (sign=+1) or subtract (sign=-1) Strategic Expense from an existing row."""
	consol = row.get("consolidate")
	if consol:
		for k in measure_keys:
			delta = sign * sum(strategic.get(c, {}).get(k, 0.0) for c in company_names)
			consol[k] = round((consol.get(k) or 0) + delta, 2)
	for i, c in enumerate(company_names):
		cell = row["values"][i]
		if cell is None:
			continue
		for k in measure_keys:
			if cell.get(k) is not None:
				cell[k] = round((cell.get(k) or 0) + sign * strategic.get(c, {}).get(k, 0.0), 2)


def _strategic_total(by_primary):
	"""Collapse {primary_group: {company: {k: v}}} to {company: {k: v}} (sum over primaries)."""
	out = {}
	for per_company in by_primary.values():
		for c, cells in per_company.items():
			tot = out.setdefault(c, {})
			for k, v in cells.items():
				tot[k] = tot.get(k, 0.0) + v
	return out


def _strategic_by_primary(company_names, report_type, fiscal_year, month, previous_fiscal_year):
	"""{primary_group: {company: {measure_key: amount}}} for the Statement view."""
	fetched = _fetch_strategic(company_names, [fiscal_year, previous_fiscal_year])
	return {
		pg: _strategic_company_totals(
			_strategic_amounts(
				company_names, report_type, fiscal_year, month, previous_fiscal_year, pg, fetched
			)
		)
		for pg in STRATEGIC_PRIMARY_GROUPS
	}


def _strategic_by_primary_all_ftm(company_names, month_range, fiscal_year):
	"""{primary_group: {company: {month_key: amount}}} for the All-FTM Statement view."""
	fetched = _fetch_strategic(company_names, [fiscal_year])
	return {
		pg: _strategic_company_totals(
			_strategic_amounts_all_ftm(company_names, month_range, fiscal_year, pg, fetched)
		)
		for pg in STRATEGIC_PRIMARY_GROUPS
	}


def _reclassify_strategic(out_rows, company_names, measure_keys, by_primary, sign):
	"""Take Strategic Expense out of each primary group's face row and "Total Expenses".

	Each primary group in `by_primary` reduces its own P&L row (Other expenses,
	Employee benefit expenses); Total Expenses is reduced once by what was
	actually applied. sign=-1 subtracts (run before the EBITDA block is computed,
	so EBITDA is struck on the reduced expenses); sign=+1 reverses that.

	Primary groups whose face row is absent are skipped. Returns the
	{primary_group: ...} subset that was applied (empty when nothing was, or when
	Total Expenses is absent) so the caller adds back exactly that amount.
	"""
	te = _find_row(out_rows, lambda n: n.startswith("total exp"))
	if te < 0:
		return {}
	applied = {}
	for pg, per_company in by_primary.items():
		prefix = STRATEGIC_PRIMARY_GROUPS.get(pg)
		idx = _find_row(out_rows, lambda n, p=prefix: n.startswith(p)) if prefix else -1
		if idx < 0:
			continue
		_adjust_row(out_rows[idx], company_names, measure_keys, per_company, sign)
		applied[pg] = per_company
	if applied:
		_adjust_row(out_rows[te], company_names, measure_keys, _strategic_total(applied), sign)
	return applied


def _insert_strategic_expense(out_rows, company_names, measure_keys, applied):
	"""Insert the "Strategic Expense" row below Litigation Exp and add it back to
	Total Expenses. Returns False (no-op) when Litigation Exp is absent.

	`applied` is what `_reclassify_strategic` took out of the face rows. It was
	already removed from Total Expenses before EBITDA was computed, so EBITDA
	reflects the reduced expenses. Adding it back to Total Expenses here restores
	the reported total, leaving Profit before tax / for the year unchanged.
	Tagged into the EBITDA collapse group since it sits inside that block.
	"""
	lit = _find_row(out_rows, lambda n: n.startswith("litigation exp"))
	if lit < 0:
		return False

	strategic = _strategic_total(applied)
	consol = {
		k: round(sum(strategic.get(c, {}).get(k, 0.0) for c in company_names), 2) for k in measure_keys
	}
	values = [
		{k: round(strategic.get(c, {}).get(k, 0.0), 2) for k in measure_keys} for c in company_names
	]
	row = {
		"particular": "Strategic Expense",
		"indent": 0,
		"is_bold": 0,
		"is_header": 0,
		"kind": "derived",
		"collapse_member": "ebitda",
		"consolidate": consol,
		"values": values,
	}
	out_rows[lit + 1 : lit + 1] = [row]

	te = _find_row(out_rows, lambda n: n.startswith("total exp"))
	if te >= 0:
		_adjust_row(out_rows[te], company_names, measure_keys, strategic, sign=+1)
	return True


def _strategic_groups(companies, primary_group=OTHER_EXPENSES_PRIMARY_GROUP):
	"""Secondary groups configured under `primary_group` for these companies (sorted)."""
	if not companies:
		return []
	groups = frappe.get_all(
		"FR GL Group Mapping",
		filters={
			"company": ["in", companies],
			"primary_group": primary_group,
			"report_type": ["in", ["Monthly", "Yearly"]],
		},
		pluck="secondary_group",
		group_by="secondary_group",
		limit_page_length=0,
	)
	return sorted(g for g in groups if g)


@frappe.whitelist()
def get_strategic_entries(fiscal_year=None, month=None):
	"""Existing Strategic Expense amounts for a fiscal year + month.

	Powers the Strategic Expense tab grid: returns the domestic companies (grid
	columns), one section per primary group (Other expenses, Employee Emoluments)
	listing its secondary groups (grid rows), and the current
	{company: {primary_group: {secondary_group: amount}}} so the inputs can be
	pre-filled.
	"""
	frappe.has_permission(STRATEGIC_DOCTYPE, "read", throw=True)
	companies = [c.name for c in _strategic_companies()]
	sections = [
		{"primary_group": pg, "groups": _strategic_groups(companies, pg)}
		for pg in STRATEGIC_PRIMARY_GROUPS
	]
	amounts = {}
	if fiscal_year and month and companies:
		rows = frappe.get_all(
			STRATEGIC_DOCTYPE,
			filters={
				"fiscal_year": fiscal_year,
				"month": month,
				"company": ["in", companies],
				"secondary_group": ["is", "set"],
			},
			fields=["company", "primary_group", "secondary_group", "amount"],
			limit_page_length=0,
		)
		for r in rows:
			# Entries saved before primary_group existed were all Other expenses.
			pg = r.primary_group or OTHER_EXPENSES_PRIMARY_GROUP
			amounts.setdefault(r.company, {}).setdefault(pg, {})[r.secondary_group] = flt(r.amount)
	return {"companies": companies, "sections": sections, "amounts": amounts}


@frappe.whitelist()
def save_strategic_entries(fiscal_year=None, month=None, amounts=None):
	"""Upsert Strategic Expense amounts for a fiscal year + month.

	`amounts` is a {company: {primary_group: {secondary_group: amount}}} map
	covering only the companies the user is editing. A zero/blank amount deletes
	any existing entry for that company/primary group/group/period; a non-zero
	one creates or updates it. Returns counts so the caller can confirm.
	"""
	frappe.has_permission(STRATEGIC_DOCTYPE, "create", throw=True)
	if not fiscal_year or not month:
		frappe.throw("Fiscal Year and Month are required.")
	if isinstance(amounts, str):
		try:
			amounts = json.loads(amounts)
		except (ValueError, TypeError):
			amounts = {}
	valid_companies = {c.name for c in _strategic_companies()}
	valid_groups = {
		pg: set(_strategic_groups(list(valid_companies), pg)) for pg in STRATEGIC_PRIMARY_GROUPS
	}

	saved = deleted = 0
	for company, per_primary in (amounts or {}).items():
		if company not in valid_companies or not isinstance(per_primary, dict):
			continue
		for primary, per_group in per_primary.items():
			if primary not in valid_groups or not isinstance(per_group, dict):
				continue
			for group, amt in per_group.items():
				if group not in valid_groups[primary]:
					continue
				# Match legacy rows (blank primary group) as Other expenses.
				match = {
					"company": company,
					"fiscal_year": fiscal_year,
					"month": month,
					"secondary_group": group,
					"primary_group": primary,
				}
				existing = frappe.db.get_value(STRATEGIC_DOCTYPE, match, "name")
				if not existing and primary == OTHER_EXPENSES_PRIMARY_GROUP:
					existing = frappe.db.get_value(
						STRATEGIC_DOCTYPE, {**match, "primary_group": ["in", ["", None]]}, "name"
					)
				val = flt(amt)
				if not val:
					if existing:
						frappe.delete_doc(STRATEGIC_DOCTYPE, existing)
						deleted += 1
					continue
				if existing:
					doc = frappe.get_doc(STRATEGIC_DOCTYPE, existing)
					doc.primary_group = primary
					doc.amount = val
					doc.save()
				else:
					frappe.get_doc({"doctype": STRATEGIC_DOCTYPE, **match, "amount": val}).insert()
				saved += 1
	frappe.db.commit()
	return {"saved": saved, "deleted": deleted}


def _grouping_report_type(report_type):
	"""domestic-financials report type -> GL Group Mapping report_type."""
	return "Monthly" if report_type in ("Monthly", "FTM") else "Yearly"


def _gl_split_accounts(companies, map_report_type, primary_group, secondary_groups=None):
	"""{company: {gl_account: secondary_group}} for accounts under `primary_group`.

	Reads GL Group Mapping for the given companies where the primary group matches
	and, when `secondary_groups` is given, the secondary group is one of those
	(otherwise every secondary group configured under the primary group is
	included). Falls back to the other mapping report type if nothing is
	configured for the requested one.
	"""
	def _query(rt):
		filters = {
			"company": ["in", companies],
			"report_type": rt,
			"primary_group": primary_group,
		}
		if secondary_groups:
			filters["secondary_group"] = ["in", secondary_groups]
		return frappe.get_all(
			"FR GL Group Mapping",
			filters=filters,
			fields=["company", "gl_account", "secondary_group"],
		)

	rows = _query(map_report_type)
	if not rows:
		rows = _query("Yearly" if map_report_type != "Yearly" else "Monthly")
	out = {}
	for r in rows:
		out.setdefault(r.company, {})[r.gl_account] = r.secondary_group
	return out


def _gl_split_grouped(companies, acct_map, fiscal_years):
	"""{(company, secondary_group, fiscal_year, month): raw_amount} from trial balance."""
	accounts = {a for m in acct_map.values() for a in m}
	fiscal_years = [y for y in fiscal_years if y]
	if not accounts or not fiscal_years:
		return {}
	rows = frappe.get_all(
		"FR Trial Balance Entry",
		filters={
			"company": ["in", companies],
			"fiscal_year": ["in", fiscal_years],
			"gl_account": ["in", list(accounts)],
		},
		fields=["company", "gl_account", "fiscal_year", "month", "amount"],
		limit_page_length=0,
	)
	grouped = {}
	for r in rows:
		grp = acct_map.get(r.company, {}).get(r.gl_account)
		if not grp:
			continue
		key = (r.company, grp, r.fiscal_year, r.month)
		grouped[key] = grouped.get(key, 0.0) + flt(r.amount)
	return grouped


def _gl_split_amounts(
	company_names, report_type, fiscal_year, month, previous_fiscal_year,
	primary_group, secondary_groups, sign,
):
	"""({company: {secondary_group: {measure_key: value}}}, groups) in signed Rs Lacs.

	Trial-balance amounts are monthly deltas (raw rupees, credit sign for income,
	debit sign for expense), so the display value is sign * sum / LACS (-1 for
	income groups, +1 for expense groups). Measures follow the P&L view: Yearly
	sums the fiscal year (cy/py); Monthly gives cumulative-to-month, month,
	cumulative-to-prev; FTM gives the single month. `groups` is `secondary_groups`
	when given, otherwise every secondary group actually configured (sorted).
	"""
	acct_map = _gl_split_accounts(
		company_names, _grouping_report_type(report_type), primary_group, secondary_groups
	)
	groups = secondary_groups or sorted({g for m in acct_map.values() for g in m.values()})
	grouped = _gl_split_grouped(company_names, acct_map, [fiscal_year, previous_fiscal_year])

	def disp(c, g, fy, months):
		return round(sign * sum(grouped.get((c, g, fy, m), 0.0) for m in months) / LACS, 2)

	out = {}
	for c in company_names:
		out[c] = {}
		for g in groups:
			if report_type == "FTM":
				out[c][g] = {"ftm": disp(c, g, fiscal_year, [month])}
			elif report_type == "Monthly":
				up = _fiscal_months_upto(month)
				out[c][g] = {
					"cm": disp(c, g, fiscal_year, up),
					"ftm": disp(c, g, fiscal_year, [month]),
					"pm": disp(c, g, fiscal_year, up[:-1]),
				}
			else:  # Yearly
				out[c][g] = {
					"cy": disp(c, g, fiscal_year, FISCAL_MONTH_ORDER),
					"py": disp(c, g, previous_fiscal_year, FISCAL_MONTH_ORDER)
					if previous_fiscal_year
					else 0.0,
				}
	return out, groups


def _bif_measures(report_type, fiscal_year, month, previous_fiscal_year):
	"""Breakdown columns (key, label) -- mirror the P&L face for this view."""
	if report_type == "FTM":
		return [("ftm", "FTM")]
	if report_type == "Monthly":
		return [
			("cm", month or "Current Month"),
			("ftm", "FTM"),
			("pm", _prev_month(month) or "Previous Month"),
		]
	return [
		("cy", fiscal_year or "Current Year"),
		("py", previous_fiscal_year or "Previous Year"),
	]


# --- Consolidation adjustments (Elimination / Regrouping) ------------------
# FR Console Adjustment Entry rows are shown as two extra columns after Consolidate.
# They are NOT netted into Consolidate. Entries are fetched by fiscal year and month
# only (plus the primary / secondary group where a line needs them) -- never by
# company -- and are monthly amounts: Yearly sums the fiscal year, Monthly gives
# cumulative-to-month / the month / cumulative-to-prev, FTM the month.
#   net = Debit - Credit
#   Income line   = Debit - Credit
#   Expense line  = Credit - Debit
# The line type is the FR Particular's "particular_type" (Income / Expenses).
ADJUSTMENT_DOCTYPE = "FR Console Adjustment Entry"
ADJUSTMENT_TYPES = {"Elimination": "elimination", "Regrouping": "regrouping"}
ADJUSTMENT_FIELDS = tuple(ADJUSTMENT_TYPES.values())
ADJUSTMENT_PREFIX = "__adj__"  # pseudo-company names used while building rows

# Statement rows that pool every primary group of one Standalone Group type on
# the face. For adjustments each row takes only primaries of its OWN type, so an
# entry is never counted on both the Other Income and Other Expense rows.
POOLED_GROUP_TYPES = ("Other Income", "Other Expense", "Current Tax Liabilities", "Income Tax Assets")

# Lines the face derives by formula from several groups (or whose own group map points
# at a group with no GL mappings). For adjustments they are fetched purely by grouping:
# an entry whose (primary, secondary) group is listed here lands on that schedule's P&L
# line. Keyed by the line's schedule (FR Section) note type -> [(primary, secondary|None)];
# None means any secondary group. "Inventories" is also a Balance Sheet group, so only the
# secondary groups the Changes-in-inventories note itself sums are taken.
ADJUSTMENT_NOTE_GROUPS = {
	"Cost of Materials Consumed": [("Material consumed", None)],
	"Purchases of Stock in Trade": [("Purchases of Stock in Trade", None)],
	"Changes in inventories of Finished Goods and Work-In-Progress": [
		("Inventories", "Finished Goods"),
		("Inventories", "Work in Progress"),
		("Inventories", "Stock In Trade"),
	],
}


def _adjustment_periods(report_type, fiscal_year, month, previous_fiscal_year, month_range=None):
	"""{measure_key: (fiscal_year, [months])} -- which entry months feed each column."""
	if month_range is not None:  # All-FTM: one month per column
		return {m.lower(): (fiscal_year, [m]) for m in month_range}
	if report_type == "FTM":
		return {"ftm": (fiscal_year, [month])}
	if report_type == "Monthly":
		up = _fiscal_months_upto(month)
		return {"cm": (fiscal_year, up), "ftm": (fiscal_year, [month]), "pm": (fiscal_year, up[:-1])}
	return {
		"cy": (fiscal_year, FISCAL_MONTH_ORDER),
		"py": (previous_fiscal_year, FISCAL_MONTH_ORDER) if previous_fiscal_year else (None, []),
	}


def _load_adjustments(periods, primary_group=None):
	"""{"elimination"|"regrouping": {(primary, secondary, fiscal_year, month): Debit - Credit}}.

	Filters: fiscal_year and month (from the column `periods`), and `primary_group`
	when the caller needs a single group. Company is deliberately not a filter.
	"""
	book = {f: {} for f in ADJUSTMENT_FIELDS}
	fiscal_years = sorted({fy for fy, _months in periods.values() if fy})
	months = sorted({m for fy, ms in periods.values() if fy for m in ms})
	if not fiscal_years or not months or not frappe.db.exists("DocType", ADJUSTMENT_DOCTYPE):
		return book
	if not frappe.has_permission(ADJUSTMENT_DOCTYPE, "read"):
		return book
	filters = {"fiscal_year": ["in", fiscal_years], "month": ["in", months]}
	if primary_group:
		filters["primary_group"] = primary_group
	rows = frappe.get_all(
		ADJUSTMENT_DOCTYPE,
		filters=filters,
		fields=["adj_type", "primary_group", "secondary_group", "fiscal_year", "month", "debit", "credit"],
		limit_page_length=0,
	)
	for r in rows:
		field = ADJUSTMENT_TYPES.get(r.adj_type)
		if not field:
			continue
		key = (r.primary_group, r.secondary_group, r.fiscal_year, r.month)
		book[field][key] = book[field].get(key, 0.0) + flt(r.debit) - flt(r.credit)
	return book


class _AdjustmentResolver:
	"""Maps adjustment entries onto statement line items (FR Particulars).

	A leaf line takes the entries whose (primary, secondary) group feeds it --
	its FR Particular's group mapping, or, for a "fetch from trial balance"
	schedule, every secondary group under the schedule's primary group. A total
	line is rebuilt from its children, exactly as the face builds it.
	"""

	def __init__(self, statement, book, periods):
		self.statement = statement
		self.book = book
		self.periods = periods
		self._memo = {}
		self._leaf_cache = {}
		self._particulars = {}
		self.selectors_seen = set()

	def _leaf(self, p):
		"""(selectors, sign): selectors are (primary, secondary|None-for-any) pairs."""
		if p.name in self._leaf_cache:
			return self._leaf_cache[p.name]
		sels = set()
		note_type = frappe.db.get_value("FR Section", p.schedule, "note_type") if p.schedule else None
		note_group = ADJUSTMENT_NOTE_GROUPS.get(note_type)
		if note_group:
			sels = set(note_group)  # fetched by grouping alone
		elif p.fetch_from_schedule and not p.is_purchase_of_stock_in_trade:
			pass  # sourced from FAR / other schedules, not from GL groups
		else:
			section = frappe.get_cached_doc("FR Section", p.schedule) if p.schedule else None
			if section and section.fetch_data_from_trial_balance:
				pg = section.primary_consolidation_group
				gtype = frappe.get_cached_value("FR Standalone Group", pg, "group_type") if pg else None
				if gtype in POOLED_GROUP_TYPES:
					pgs = set(
						frappe.get_all(
							"FR Standalone Group",
							filters={"is_primary_group": 1, "group_type": gtype},
							pluck="name",
						)
					)
				else:
					pgs = {pg} if pg else set()
				sels = {(g, None) for g in pgs}
			else:
				sels = {
					(m.primary_group, m.secondary_group or "")
					for m in (p.get("primary_and_secondary_group_mapping") or [])
					if m.primary_group
				}
		# Sign of the line's value against net = Debit - Credit:
		#   Income line   -> Debit - Credit   (+1)
		#   Expense line  -> Credit - Debit   (-1)
		# Other lines (balance sheet etc.) keep the face rule: flipped by "Show Reversed Value".
		ptype = p.get("particular_type")
		if ptype == "Income":
			sign = 1.0
		elif ptype == "Expenses":
			sign = -1.0
		else:
			sign = -1.0 if p.show_reversed_value else 1.0
		out = (frozenset(sels), sign)
		self.selectors_seen |= sels
		self._leaf_cache[p.name] = out
		return out

	def amount(self, pid, field, key):
		"""Adjustment for particular `pid` in display units (Rs Lacs)."""
		if not pid:
			return 0.0
		ck = (pid, field, key)
		if ck in self._memo:
			return self._memo[ck]
		# Stored table_data can reference a deleted FR Particular. Check existence
		# first: get_cached_doc would queue a "not found" message for the user.
		if pid not in self._particulars:
			self._particulars[pid] = (
				frappe.get_cached_doc("FR Particular", pid) if frappe.db.exists("FR Particular", pid) else None
			)
		p = self._particulars[pid]
		if p is None:
			self._memo[ck] = 0.0
			return 0.0

		if p.is_total:
			total = 0.0
			for idx, c in enumerate(p.get("particulars") or []):
				child = self.amount(c.particular, field, key)
				# Only the P&L face honours "To Subtract" (first child minus the rest).
				if self.statement == PROFIT_AND_LOSS and p.to_subtract:
					total = child if idx == 0 else total - child
				else:
					total += child
			val = -total if p.show_reversed_value else total  # the face reverses totals too
		else:
			sels, sign = self._leaf(p)
			fy, months = self.periods[key]
			net = 0.0
			for (pg, sg, efy, em), amt in self.book[field].items():
				if efy == fy and em in months and any(
					spg == pg and (ssg is None or ssg == (sg or "")) for spg, ssg in sels
				):
					net += amt
			val = sign * net / LACS
		val = round(val, 2)
		self._memo[ck] = val
		return val

	def unmapped(self):
		"""Entry groups of this statement that no line item picks up (sorted labels)."""
		out = set()
		for entries in self.book.values():
			for pg, sg, _fy, _m in entries:
				if frappe.get_cached_value("FR Standalone Group", pg, "report_type") != self.statement:
					continue
				if not any(
					spg == pg and (ssg is None or ssg == (sg or "")) for spg, ssg in self.selectors_seen
				):
					out.add(f"{pg} > {sg}")
		return sorted(out)


def _statement_adjustments(statement, canonical, periods):
	"""({pseudo_company: per-canonical-row cells}, unmapped_labels) for a statement.

	The pseudo columns are fed through `_build_out_rows` alongside the companies
	so totals and derived KPI rows (Gross Margin, EBITDA ...) follow the same
	arithmetic for Elimination / Regrouping as for every other column.
	"""
	resolver = _AdjustmentResolver(statement, _load_adjustments(periods), periods)
	aligned = {
		ADJUSTMENT_PREFIX + f: [
			{k: resolver.amount(r.get("id"), f, k) for k in periods} for r in canonical
		]
		for f in ADJUSTMENT_FIELDS
	}
	return aligned, resolver.unmapped()


def _adjustment_split(periods, primary_group, sign):
	"""{field: {secondary_group: {measure_key: value}}} for one primary group (Rs Lacs).

	`sign` multiplies Debit - Credit: +1 for an income group, -1 for an expense group.
	"""
	out = {}
	for field, entries in _load_adjustments(periods, primary_group).items():
		per = {}
		for (pg, sg, efy, em), net in entries.items():
			for key, (fy, months) in periods.items():
				if efy == fy and em in months:
					cell = per.setdefault(sg, {k: 0.0 for k in periods})
					cell[key] += sign * net / LACS
		out[field] = {sg: {k: round(v, 2) for k, v in cell.items()} for sg, cell in per.items()}
	return out


def _with_adjustment_groups(groups, adj_split):
	"""`groups` plus any secondary group that only appears in adjustments, so the
	breakdown still foots to the face row."""
	extra = {g for cells in adj_split.values() for g in cells} - set(groups)
	return list(groups) + sorted(extra)


def _build_split_rows(company_names, measures, split, groups, drop_zero_groups=False, adj_split=None):
	"""One row per secondary group, aligned + consolidated.

	When `drop_zero_groups` is set, a secondary group whose Consolidate value is
	zero (or absent) across every measure column -- and that carries no
	Elimination / Regrouping -- is left out entirely: used for Other expenses,
	where the configured secondary-group set is large and mostly zero for any
	given company/period; Revenue keeps its fixed two rows regardless.

	`adj_split` ({field: {group: {measure_key: value}}}) fills each row's
	Elimination / Regrouping cells.
	"""
	measure_keys = [m[0] for m in measures]
	adj_split = adj_split or {}
	rows = []
	for g in groups:
		values, totals = [], {k: 0.0 for k in measure_keys}
		for c in company_names:
			cell = (split.get(c) or {}).get(g) or {}
			vv = {}
			for k in measure_keys:
				v = cell.get(k)
				vv[k] = v
				if v is not None:
					totals[k] += v
			values.append(vv)
		adj = {
			f: {k: (adj_split.get(f, {}).get(g) or {}).get(k, 0.0) for k in measure_keys}
			for f in ADJUSTMENT_FIELDS
		}
		if (
			drop_zero_groups
			and all(abs(totals[k]) < 1e-6 for k in measure_keys)
			and all(abs(v) < 1e-6 for cell in adj.values() for v in cell.values())
		):
			continue
		rows.append(
			{
				"particular": g,
				"indent": 0,
				"is_bold": 0,
				"is_header": 0,
				"consolidate": {k: round(totals[k], 2) for k in measure_keys},
				"values": values,
				**adj,
			}
		)
	return rows


def _token(r):
	"""Identity of a line item, used to align rows across companies."""
	return (
		(r.get("account") or "").strip(),
		int(r.get("indent") or 0),
		int(r.get("is_bold") or 0),
		int(r.get("header") or 0),
		int(r.get("group") or 0),
	)


def _norm(s):
	return (s or "").strip().lower()


# Source line-item labels (frequently OCR-derived from the uploaded statements)
# mapped to the clean particulars used in the Excel statutory P&L / Balance
# Sheet. Keyed by the normalised source label so whitespace/case never matter.
# This is presentation-only — the underlying report data is left untouched.
PARTICULAR_FIXES = {
	"total lncome (l+ ll)": "Total Income (I + II)",
	"total income (i+ ii)": "Total Income (I + II)",
	"total income (i + ii)": "Total Income (I + II)",
	"purchases of stock in trade": "Purchase of Stock-in-trade",
	"employee benefits expenses": "Employee benefit expenses",
	"depreciation and amortisation expenses": "Depreciation and amortisation expense",
	"total expenses": "Total Expenses",
	"excess provision for tax relating to prior years": "Short/(Excess) provision for tax relating to prior years",
	"basic and diluted (in ruppe)": "Basic and diluted (in ₹)",
	# Balance Sheet
	"lnventories": "Inventories",
	"capital work-in-progress": "Capital work-in-progress",
	"financial assets": "Financial assets",
	"trade payables": "Trade payables",
	"deferred tax liabilities (net)": "Deferred tax liabilities (net)",
}


def _clean_particular(name):
	"""Return the Excel-aligned particular for a (possibly OCR-garbled) label."""
	return PARTICULAR_FIXES.get(_norm(name), name or "")


def _find_row(rows, pred):
	"""Index of the first out-row whose (normalised) particular matches `pred`."""
	for i, r in enumerate(rows):
		if pred(_norm(r.get("particular"))):
			return i
	return -1


def _insert_gross_margin(out_rows, measure_keys):
	"""Insert derived Total RMC / Gross Margin / Gross Margin (%) rows into a P&L.

	Placed directly below "Changes in inventories …". Computed per column
	(company + Consolidate) and per measure from existing line items, matching the
	Excel model (Summary!RMC = SUM('Profit & Loss'!row 13:15)):

	    Total RMC         = Cost of materials consumed
	                        + Purchases of Stock-in-Trade
	                        + Changes in inventories of finished goods & WIP
	    Gross Margin      = Total Income - Total RMC
	    Gross Margin (%)  = Gross Margin / Revenue from operations * 100

	No-ops (returns unchanged) when the expected P&L rows are absent, so it is
	safe to call for any statement.
	"""
	ti = _find_row(
		out_rows,
		lambda n: n.startswith("total")
		and ("income" in n or "lncome" in n)  # OCR sometimes renders "Income" as "lncome"
		and "comprehensive" not in n,
	)
	cost = _find_row(out_rows, lambda n: n.startswith("cost of material"))
	purch = _find_row(out_rows, lambda n: n.startswith("purchase") and "stock" in n)
	rev = _find_row(out_rows, lambda n: n.startswith("revenue from operation"))
	inv = _find_row(out_rows, lambda n: n.startswith("changes in inventor"))
	# Purchases of Stock-in-Trade is optional (some companies omit it); the other
	# three rows define the expected P&L structure.
	if min(ti, cost, rev, inv) < 0:
		return  # not the expected P&L structure

	# Rows summed into RMC — mirrors the Excel SUM over the three material lines.
	rmc_rows = [cost, inv] + ([purch] if purch >= 0 else [])

	ncomp = len(out_rows[ti]["values"])

	def _obj(idx, i):
		"""Cell dict for row `idx`; i < 0 selects the Consolidate column."""
		return out_rows[idx]["consolidate"] if i < 0 else out_rows[idx]["values"][i]

	def _rmc(i, k):
		"""Total RMC for column i, measure k; None only when every source is absent."""
		cells = [(_obj(idx, i) or {}).get(k) for idx in rmc_rows]
		if all(v is None for v in cells):
			return None
		return round(sum(v or 0 for v in cells), 2)

	def _diff(i, k):
		"""Gross Margin (amount) for column i, measure k; None when both absent."""
		tv = (_obj(ti, i) or {}).get(k)
		rmc = _rmc(i, k)
		if tv is None and rmc is None:
			return None
		return round((tv or 0) - (rmc or 0), 2)

	def _pct(i, k):
		gm = _diff(i, k)
		rv = (_obj(rev, i) or {}).get(k)
		if gm is None or not rv:
			return None
		return round(gm / rv * 100, 2)

	def _build(compute):
		return {k: compute(-1, k) for k in measure_keys}, [
			{k: compute(i, k) for k in measure_keys} for i in range(ncomp)
		]

	rmc_consol, rmc_values = _build(_rmc)
	gm_consol, gm_values = _build(_diff)
	pct_consol, pct_values = _build(_pct)

	total_rmc = {
		"particular": "Total RMC",
		"indent": 0,
		"is_bold": 1,
		"is_header": 0,
		"kind": "derived",
		"consolidate": rmc_consol,
		"values": rmc_values,
	}
	gross_margin = {
		"particular": "Gross Margin",
		"indent": 0,
		"is_bold": 1,
		"is_header": 0,
		"kind": "derived",
		"consolidate": gm_consol,
		"values": gm_values,
	}
	gross_margin_pct = {
		"particular": "Gross Margin (%)",
		"indent": 0,
		"is_bold": 1,
		"is_header": 0,
		"kind": "derived",
		"value_format": "percent",
		"consolidate": pct_consol,
		"values": pct_values,
	}
	out_rows[inv + 1 : inv + 1] = [total_rmc, gross_margin, gross_margin_pct]


def _insert_ebitda(out_rows, measure_keys):
	"""Insert the EBITDA / Litigation KPI block into a P&L statement.

	Placed directly below "Total Expenses". Computed per column (each company +
	Consolidate) and per measure from the statutory P&L line items, matching the
	Excel "Dom" summary definitions:

	    EBITDA Pre-Litigation      = Total Income - Total Expenses
	                                 + Finance costs + Depreciation & amortisation
	    EBITDA (%) Pre-Litigation  = EBITDA Pre-Litigation / Revenue from operations * 100
	    Litigation Exp             = 0  (no per-company litigation source yet)
	    EBITDA Post-Litigation     = EBITDA Pre-Litigation - Litigation Exp
	    EBITDA (%) Post-Litigation = EBITDA Post-Litigation / Revenue from operations * 100

	No-op (returns unchanged) when the expected P&L rows are absent, so it is safe
	to call for any statement.
	"""
	ti = _find_row(
		out_rows,
		lambda n: n.startswith("total")
		and ("income" in n or "lncome" in n)
		and "comprehensive" not in n,
	)
	te = _find_row(out_rows, lambda n: n.startswith("total exp"))
	fin = _find_row(out_rows, lambda n: n.startswith("finance cost"))
	dep = _find_row(out_rows, lambda n: n.startswith("depreciation"))
	rev = _find_row(out_rows, lambda n: n.startswith("revenue from operation"))
	if min(ti, te, fin, dep, rev) < 0:
		return  # not the expected P&L structure

	ncomp = len(out_rows[ti]["values"])

	def _obj(idx, i):
		"""Cell dict for row `idx`; i < 0 selects the Consolidate column."""
		return out_rows[idx]["consolidate"] if i < 0 else out_rows[idx]["values"][i]

	def _cell(idx, i, k):
		return (_obj(idx, i) or {}).get(k)

	def _pre(i, k):
		"""EBITDA (Pre-Litigation) for column i, measure k; None when all absent."""
		parts = [_cell(ti, i, k), _cell(te, i, k), _cell(fin, i, k), _cell(dep, i, k)]
		if all(v is None for v in parts):
			return None
		tiv, tev, finv, depv = (v or 0 for v in parts)
		return round(tiv - tev + finv + depv, 2)

	def _litigation(i, k):
		# No per-company litigation figure in the source reports yet — keep the
		# row (value 0) so it is visible and ready to be wired up later.
		return 0.0

	def _post(i, k):
		pre = _pre(i, k)
		if pre is None:
			return None
		return round(pre - (_litigation(i, k) or 0), 2)

	def _pct(amount_fn, i, k):
		amt = amount_fn(i, k)
		rv = _cell(rev, i, k)
		if amt is None or not rv:
			return None
		return round(amt / rv * 100, 2)

	def _build(fn):
		return {k: fn(-1, k) for k in measure_keys}, [
			{k: fn(i, k) for k in measure_keys} for i in range(ncomp)
		]

	pre_consol, pre_values = _build(_pre)
	pre_pct_consol, pre_pct_values = _build(lambda i, k: _pct(_pre, i, k))
	lit_consol, lit_values = _build(_litigation)
	post_consol, post_values = _build(_post)
	post_pct_consol, post_pct_values = _build(lambda i, k: _pct(_post, i, k))

	def _row(particular, consol, values, fmt=None):
		row = {
			"particular": particular,
			"indent": 0,
			"is_bold": 1,
			"is_header": 0,
			"kind": "derived",
			"consolidate": consol,
			"values": values,
		}
		if fmt:
			row["value_format"] = fmt
		return row

	block = [
		_row("EBITDA Pre-Litigation", pre_consol, pre_values),
		_row("EBITDA (%) Pre-Litigation", pre_pct_consol, pre_pct_values, "percent"),
		_row("Litigation Exp", lit_consol, lit_values),
		_row("EBITDA Post-Litigation", post_consol, post_values),
		_row("EBITDA (%) Post-Litigation", post_pct_consol, post_pct_values, "percent"),
	]
	# Collapsible "EBITDA" header above the block: a "+" hides/shows the KPI lines.
	# Kept KPI-gated (kind=derived) like the rows it groups, and blank so it reads
	# as a section header. The five KPI rows collapse under it.
	for r in block:
		r["collapse_member"] = "ebitda"
	ebitda_header = {
		"particular": "EBITDA",
		"indent": 0,
		"is_bold": 1,
		"is_header": 1,
		"kind": "derived",
		"collapse_id": "ebitda",
		"consolidate": None,
		"values": [{k: None for k in measure_keys} for _ in range(ncomp)],
	}
	out_rows[te + 1 : te + 1] = [ebitda_header] + block


def _reorder_pbt_drivers(out_rows):
	"""Move Depreciation and Finance costs to just below the EBITDA block.

	Mirrors the Excel "Summary" layout, where EBITDA is struck first and then
	Depreciation (r21) and Finance Cost (r22) are deducted to reach Profit before
	tax. Purely positional: the rows keep their figures, Total Expenses still
	sums them, and EBITDA still adds them back — only their display position
	changes. No-op when the EBITDA block or either row is absent.
	"""
	# Anchor = last row of the EBITDA block (its rows all start with "ebitda").
	anchor = -1
	for i, r in enumerate(out_rows):
		if _norm(r.get("particular")).startswith("ebitda"):
			anchor = i
	if anchor < 0:
		return  # EBITDA block absent — leave the statutory layout untouched

	fin = _find_row(out_rows, lambda n: n.startswith("finance cost"))
	dep = _find_row(out_rows, lambda n: n.startswith("depreciation"))
	if fin < 0 or dep < 0:
		return

	dep_row, fin_row = out_rows[dep], out_rows[fin]
	# Remove both (highest index first so the other index stays valid), tracking
	# how the anchor shifts as earlier rows are pulled out.
	for i in sorted([fin, dep], reverse=True):
		out_rows.pop(i)
		if i <= anchor:
			anchor -= 1
	# Re-insert below the EBITDA block in Excel order: Depreciation, then Finance.
	out_rows[anchor + 1 : anchor + 1] = [dep_row, fin_row]


def _move_total_expenses_after_finance_costs(out_rows):
	"""Move Total Expenses to sit directly below Finance costs.

	Purely positional, run after the collapsible-section tagging so the
	"expenses" section's detail-line tags (computed from the original
	Expenses -> Total Expenses adjacency) are unaffected; only the Total
	Expenses row itself — untagged, since it's the section's total marker —
	relocates. No-op when either row is absent.
	"""
	te = _find_row(out_rows, lambda n: n.startswith("total exp"))
	if te < 0:
		return
	te_row = out_rows.pop(te)
	fin = _find_row(out_rows, lambda n: n.startswith("finance cost"))
	if fin < 0:
		out_rows.insert(te, te_row)  # Finance costs absent — restore original spot
		return
	out_rows.insert(fin + 1, te_row)


def _report_fiscal_years():
	"""Fiscal Years that have a Financial Report created (newest first).

	Feeds the Strategic Expense tab. Unlike the statements' own Fiscal Year
	filter it is not tied to one Report Type: a year counts when a Yearly *or*
	Monthly report exists for any of the tab's companies, in any status.
	"""
	companies = [c.name for c in _strategic_companies()]
	if not companies:
		return []
	years = frappe.get_all(
		"FR Financial Report",
		filters={"company": ["in", companies], "fiscal_year": ["is", "set"]},
		distinct=True,
		pluck="fiscal_year",
	)
	start = dict(frappe.get_all("Fiscal Year", fields=["name", "year_start_date"], as_list=True))
	return sorted(years, key=lambda y: str(start.get(y) or ""), reverse=True)


@frappe.whitelist()
def get_context(report_type="Yearly", fiscal_year=None):
	"""Filter metadata: available fiscal years (and months for Monthly).

	Resolves the fiscal year server-side (the passed one if valid, else the
	default) so the returned months always match the year the page will show.
	"""
	frappe.has_permission("FR Financial Report", "read", throw=True)

	# FTM reads the Monthly reports (only its For-The-Month column differs).
	storage_type = _storage_report_type(report_type)

	companies = [c.name for c in _domestic_companies()]
	empty = {
		"fiscal_years": [],
		"strategic_fiscal_years": _report_fiscal_years(),
		"default_fiscal_year": None,
		"resolved_fiscal_year": None,
		"months": [],
		"default_month": None,
		"company_count": 0,
		"companies": [],
	}
	if not companies:
		return empty

	years = frappe.get_all(
		"FR Financial Report",
		filters={"company": ["in", companies], "report_type": storage_type},
		distinct=True,
		pluck="fiscal_year",
		order_by="fiscal_year desc",
	)
	years = [y for y in years if y]

	default_year = None
	for y in years:
		if frappe.db.exists(
			"FR Financial Report",
			{
				"company": ["in", companies],
				"report_type": storage_type,
				"fiscal_year": y,
				"report_status": "Successful",
			},
		):
			default_year = y
			break
	if not default_year and years:
		default_year = years[0]

	resolved_year = fiscal_year if fiscal_year in years else default_year

	# Months apply to the Monthly-driven views (Monthly and FTM).
	months, default_month = [], None
	if _is_monthly_like(report_type) and resolved_year:
		months = frappe.get_all(
			"FR Financial Report",
			filters={
				"company": ["in", companies],
				"report_type": "Monthly",
				"fiscal_year": resolved_year,
			},
			distinct=True,
			pluck="current_month",
		)
		months = sorted({m for m in months if m}, key=_month_sort_key)

		# Prefer the latest (fiscal order) month with a Successful report.
		for m in reversed(months):
			if frappe.db.exists(
				"FR Financial Report",
				{
					"company": ["in", companies],
					"report_type": "Monthly",
					"fiscal_year": resolved_year,
					"current_month": m,
					"report_status": "Successful",
				},
			):
				default_month = m
				break
		if not default_month and months:
			default_month = months[-1]

	return {
		"fiscal_years": years,
		"strategic_fiscal_years": _report_fiscal_years(),
		"default_fiscal_year": default_year,
		"resolved_fiscal_year": resolved_year,
		"months": months,
		"default_month": default_month,
		"company_count": len(companies),
		"companies": companies,
	}


@frappe.whitelist()
def get_consolidated_statement(
	fiscal_year=None, report_type="Yearly", statement=BALANCE_SHEET, month=None,
	exclude_companies=None, all_ftm=None,
):
	"""Return one statement as a Particular | Consolidate | <company> matrix.

	Rows follow the canonical (most complete) template structure; each company's
	line items are aligned to it by particular so figures land in the right row
	even when a company omits a line. Amounts are the current-year figures.
	For Monthly reports, `month` selects the report month.

	`exclude_companies` (JSON list or list) drops those companies from the matrix
	entirely, so the Consolidate total and the derived Gross Margin rows are
	recomputed over only the remaining (visible) companies.
	"""
	frappe.has_permission("FR Financial Report", "read", throw=True)
	if statement not in STATEMENTS:
		statement = BALANCE_SHEET
	# FTM is served from the Monthly reports; only its column set differs.
	storage_type = _storage_report_type(report_type)
	if not _is_monthly_like(report_type):
		month = None

	if isinstance(exclude_companies, str):
		try:
			exclude_companies = json.loads(exclude_companies)
		except (ValueError, TypeError):
			exclude_companies = []
	excluded = set(exclude_companies or [])

	# "All FTM" is an FTM-only view: instead of one For-The-Month column per
	# company, it shows one FTM column per month from April up to the selected
	# month, for every company.
	all_ftm = str(all_ftm).lower() in ("1", "true", "yes") and report_type == "FTM"

	if all_ftm:
		return _all_ftm_statement(statement, fiscal_year, month, excluded)

	# Gather each domestic company's rows for this statement.
	with_data, missing = [], []
	for c in _domestic_companies():
		if c.name in excluded:
			continue  # hidden by the user — leave out of the matrix and totals
		report = _pick_report(c.name, storage_type, fiscal_year, month)
		rows = _statement_rows(report.name, statement) if report else None
		if rows:
			with_data.append(
				{"company": c.name, "currency": c.currency, "rows": rows, "report": report}
			)
		else:
			missing.append(c.name)

	if not with_data:
		return {
			"statement": statement,
			"fiscal_year": fiscal_year,
			"previous_fiscal_year": None,
			"report_type": report_type,
			"month": month,
			"columns": [],
			"companies": [],
			"rows": [],
			"missing_companies": missing,
		}

	# Representative previous-year label (most common across the picked reports).
	prev_years = [p["report"].get("previous_fiscal_year") for p in with_data]
	prev_years = [y for y in prev_years if y]
	previous_fiscal_year = (
		Counter(prev_years).most_common(1)[0][0] if prev_years else None
	)

	# Sub-columns (measures) per company depend on the report type.
	#   Yearly  -> Current Year, Previous Year
	#   Monthly -> Current Month, FTM, Previous Month  (no previous year)
	#   FTM     -> For-The-Month only (single movement column per company)
	if report_type == "FTM":
		measures = [("ftm", "ftm_amount", "FTM")]
	elif report_type == "Monthly":
		measures = [
			("cm", "current_month_amount", month or "Current Month"),
			("ftm", "ftm_amount", "FTM"),
			("pm", "previous_month_amount", _prev_month(month) or "Previous Month"),
		]
	else:
		measures = [
			("cy", "current_month_amount", fiscal_year or "Current Year"),
			("py", "previous_year", previous_fiscal_year or "Previous Year"),
		]
	measure_keys = [m[0] for m in measures]

	# Canonical structure = the company with the most rows (the fullest template).
	canonical = max(with_data, key=lambda p: len(p["rows"]))["rows"]
	canon_tokens = [_token(r) for r in canonical]

	# Align every company's rows onto the canonical indices, keeping each
	# measure's figure per row.
	aligned = {}
	for p in with_data:
		comp_tokens = [_token(r) for r in p["rows"]]
		vals = [None] * len(canonical)
		matcher = difflib.SequenceMatcher(None, canon_tokens, comp_tokens, autojunk=False)
		for tag, i1, i2, j1, j2 in matcher.get_opcodes():
			if tag == "equal":
				for off in range(i2 - i1):
					src = p["rows"][j1 + off]
					vals[i1 + off] = {key: flt(src.get(field) or 0) for key, field, _lbl in measures}
		aligned[p["company"]] = vals

	company_names = [p["company"] for p in with_data]
	strategic = (
		_strategic_by_primary(company_names, report_type, fiscal_year, month, previous_fiscal_year)
		if statement == PROFIT_AND_LOSS
		else None
	)
	adj_aligned, adj_unmapped = _statement_adjustments(
		statement, canonical,
		_adjustment_periods(report_type, fiscal_year, month, previous_fiscal_year),
	)
	aligned.update(adj_aligned)
	out_rows = _build_out_rows(
		canonical, company_names, aligned, measure_keys, statement, strategic, adjustments=True
	)

	return {
		"statement": statement,
		"fiscal_year": fiscal_year,
		"previous_fiscal_year": previous_fiscal_year,
		"report_type": report_type,
		"month": month,
		"columns": [{"key": key, "label": lbl} for key, _f, lbl in measures],
		"companies": company_names,
		"rows": out_rows,
		"missing_companies": missing,
		"excluded_companies": sorted(excluded),
		"adjustment_unmapped": adj_unmapped,
	}


@frappe.whitelist()
def get_revenue_bifurcation(
	fiscal_year=None, report_type="Yearly", month=None,
	exclude_companies=None, all_ftm=None,
):
	"""Breakdown ("bifurcation") of Revenue from operations, per company.

	Sourced from the GL grouping: accounts mapped under the revenue primary group,
	split by the Domestic Sales / Export Sales secondary groups, summed from the
	trial balance. Returned in the Particular | Consolidate | <company> shape the
	P&L face uses, with columns mirroring the face for the same filters.
	"""
	frappe.has_permission("FR Financial Report", "read", throw=True)
	storage_type = _storage_report_type(report_type)
	if not _is_monthly_like(report_type):
		month = None

	if isinstance(exclude_companies, str):
		try:
			exclude_companies = json.loads(exclude_companies)
		except (ValueError, TypeError):
			exclude_companies = []
	excluded = set(exclude_companies or [])

	all_ftm = str(all_ftm).lower() in ("1", "true", "yes") and report_type == "FTM"
	if all_ftm:
		return _gl_bifurcation_all_ftm(
			fiscal_year, month, excluded, REVENUE_PRIMARY_GROUP, REVENUE_SECONDARY_GROUPS, sign=-1,
		)

	# Visible domestic companies, in the same order as the P&L face.
	company_names = [c.name for c in _domestic_companies() if c.name not in excluded]
	if not company_names:
		return {"columns": [], "companies": [], "rows": [], "missing_companies": []}

	# Previous fiscal year (for the Yearly py column) resolved like the face does.
	previous_fiscal_year = _previous_fiscal_year(company_names, storage_type, fiscal_year, month)

	measures = _bif_measures(report_type, fiscal_year, month, previous_fiscal_year)
	split, groups = _gl_split_amounts(
		company_names, report_type, fiscal_year, month, previous_fiscal_year,
		REVENUE_PRIMARY_GROUP, REVENUE_SECONDARY_GROUPS, sign=-1,
	)
	adj_split = _adjustment_split(
		_adjustment_periods(report_type, fiscal_year, month, previous_fiscal_year),
		REVENUE_PRIMARY_GROUP,
		sign=1,  # income: Debit - Credit
	)
	groups = _with_adjustment_groups(groups, adj_split)
	rows = _build_split_rows(company_names, measures, split, groups, adj_split=adj_split)
	return {
		"columns": [{"key": k, "label": lbl} for k, lbl in measures],
		"companies": company_names,
		"rows": rows,
		"missing_companies": [],
	}


@frappe.whitelist()
def get_other_expenses_bifurcation(
	fiscal_year=None, report_type="Yearly", month=None,
	exclude_companies=None, all_ftm=None,
):
	"""Breakdown ("bifurcation") of Other expenses, per company.

	Sourced from the GL grouping: accounts mapped under the "Other expenses"
	primary group, split by whichever secondary groups are configured for it
	(the set varies per company -- unlike Revenue's fixed Domestic/Export split,
	every configured secondary group is shown), summed from the trial balance.
	Returned in the Particular | Consolidate | <company> shape the P&L face
	uses, with columns mirroring the face for the same filters.
	"""
	frappe.has_permission("FR Financial Report", "read", throw=True)
	storage_type = _storage_report_type(report_type)
	if not _is_monthly_like(report_type):
		month = None

	if isinstance(exclude_companies, str):
		try:
			exclude_companies = json.loads(exclude_companies)
		except (ValueError, TypeError):
			exclude_companies = []
	excluded = set(exclude_companies or [])

	all_ftm = str(all_ftm).lower() in ("1", "true", "yes") and report_type == "FTM"
	if all_ftm:
		return _gl_bifurcation_all_ftm(
			fiscal_year, month, excluded, OTHER_EXPENSES_PRIMARY_GROUP, None, sign=1,
			drop_zero_groups=True, subtract_strategic=True,
		)

	company_names = [c.name for c in _domestic_companies() if c.name not in excluded]
	if not company_names:
		return {"columns": [], "companies": [], "rows": [], "missing_companies": []}

	previous_fiscal_year = _previous_fiscal_year(company_names, storage_type, fiscal_year, month)

	measures = _bif_measures(report_type, fiscal_year, month, previous_fiscal_year)
	split, groups = _gl_split_amounts(
		company_names, report_type, fiscal_year, month, previous_fiscal_year,
		OTHER_EXPENSES_PRIMARY_GROUP, None, sign=1,
	)
	# Strategic Expense is reclassified out of Other expenses, per secondary group.
	groups = _subtract_strategic_from_split(
		split,
		groups,
		_strategic_amounts(company_names, report_type, fiscal_year, month, previous_fiscal_year),
	)
	adj_split = _adjustment_split(
		_adjustment_periods(report_type, fiscal_year, month, previous_fiscal_year),
		OTHER_EXPENSES_PRIMARY_GROUP,
		sign=-1,  # expense: Credit - Debit
	)
	groups = _with_adjustment_groups(groups, adj_split)
	rows = _build_split_rows(company_names, measures, split, groups, drop_zero_groups=True, adj_split=adj_split)
	return {
		"columns": [{"key": k, "label": lbl} for k, lbl in measures],
		"companies": company_names,
		"rows": rows,
		"missing_companies": [],
	}


def _previous_fiscal_year(company_names, storage_type, fiscal_year, month):
	"""Most common previous_fiscal_year across the companies' picked reports."""
	prevs = []
	for c in company_names:
		rep = _pick_report(c, storage_type, fiscal_year, month)
		if rep and rep.get("previous_fiscal_year"):
			prevs.append(rep["previous_fiscal_year"])
	return Counter(prevs).most_common(1)[0][0] if prevs else None


def _gl_bifurcation_all_ftm(
	fiscal_year, month, excluded, primary_group, secondary_groups, sign, drop_zero_groups=False,
	subtract_strategic=False,
):
	"""All-FTM GL split: one For-The-Month column per month (April -> selected)."""
	company_names = [c.name for c in _domestic_companies() if c.name not in excluded]
	if not company_names:
		return {"columns": [], "companies": [], "rows": [], "missing_companies": []}

	month_range = list(reversed(_fiscal_months_upto(month)))
	measures = [(m.lower(), m) for m in month_range]

	acct_map = _gl_split_accounts(company_names, "Monthly", primary_group, secondary_groups)
	groups = secondary_groups or sorted({g for m in acct_map.values() for g in m.values()})
	grouped = _gl_split_grouped(company_names, acct_map, [fiscal_year])
	split = {
		c: {
			g: {
				m.lower(): round(sign * grouped.get((c, g, fiscal_year, m), 0.0) / LACS, 2)
				for m in month_range
			}
			for g in groups
		}
		for c in company_names
	}
	if subtract_strategic:
		groups = _subtract_strategic_from_split(
			split, groups, _strategic_amounts_all_ftm(company_names, month_range, fiscal_year)
		)
	adj_split = _adjustment_split(
		_adjustment_periods("FTM", fiscal_year, month, None, month_range),
		primary_group,
		-sign,  # GL sign is -1 for income / +1 for expense; adjustments are the opposite
	)
	groups = _with_adjustment_groups(groups, adj_split)
	rows = _build_split_rows(
		company_names, measures, split, groups, drop_zero_groups=drop_zero_groups, adj_split=adj_split
	)
	return {
		"columns": [{"key": k, "label": lbl} for k, lbl in measures],
		"companies": company_names,
		"rows": rows,
		"missing_companies": [],
	}



def _build_out_rows(
	canonical, company_names, aligned, measure_keys, statement, strategic=None, adjustments=False
):
	"""Assemble the Particular | Consolidate | <company> rows from aligned data.

	`aligned[company][idx]` is either None (row absent for that company) or a
	dict of per-measure figures; a figure may itself be None when only some
	measures apply to a company/row (e.g. a month missing in the All-FTM view).
	Totals ignore Nones, and a row is blank only when every measure is empty.

	With `adjustments`, `aligned` also carries one pseudo-company per
	ADJUSTMENT_FIELDS entry (prefixed ADJUSTMENT_PREFIX). They run through the
	same derived-row logic as the companies but are left out of the Consolidate
	total, and come back on each row as `row["elimination"]` / `row["regrouping"]`
	instead of in `row["values"]`.
	"""
	ncomp = len(company_names)
	adj_names = [ADJUSTMENT_PREFIX + f for f in ADJUSTMENT_FIELDS] if adjustments else []
	company_names = list(company_names) + adj_names
	out_rows = []
	for idx, r in enumerate(canonical):
		is_header = bool(r.get("header") or r.get("group"))
		values, totals, has_value = [], {k: 0.0 for k in measure_keys}, False
		for j, cn in enumerate(company_names):
			cell = aligned[cn][idx]
			if cell is None:
				values.append({k: None for k in measure_keys})
			else:
				values.append(
					{k: (round(cell[k], 2) if cell[k] is not None else None) for k in measure_keys}
				)
				if j >= ncomp:
					continue  # adjustment column: never part of Consolidate
				for k in measure_keys:
					if cell[k] is not None:
						totals[k] += cell[k]
				# A row carries figures if any measure is non-zero. This keeps
				# grouped total rows (e.g. "Profit for the year") — which are
				# flagged group=1 but hold real amounts — from being blanked,
				# while genuine section headers (all-zero) stay blank.
				if any(cell[k] is not None and abs(cell[k]) > 1e-6 for k in measure_keys):
					has_value = True
		blank = not has_value
		out_rows.append(
			{
				"particular": _clean_particular(r.get("account")),
				"indent": int(r.get("indent") or 0),
				"is_bold": 1 if r.get("is_bold") else 0,
				"is_header": 1 if is_header else 0,
				"consolidate": None if blank else {k: round(totals[k], 2) for k in measure_keys},
				"values": values,
			}
		)

	# Derived KPIs — P&L only; no-ops elsewhere. Gross Margin first (it sits high
	# in the statement), then the EBITDA / Litigation block below Total Expenses.
	if statement == PROFIT_AND_LOSS:
		_insert_gross_margin(out_rows, measure_keys)
		# Strategic Expense (user-entered) is reclassified out of its primary group's
		# face row (Other expenses / Employee benefit expenses) *before* EBITDA is
		# struck, so EBITDA reflects the reduced expenses; the Strategic Expense row
		# below Litigation Exp then adds it back to Total Expenses, leaving profit
		# unchanged.
		applied = (
			_reclassify_strategic(out_rows, company_names, measure_keys, strategic, sign=-1)
			if strategic
			else {}
		)
		_insert_ebitda(out_rows, measure_keys)
		_reorder_pbt_drivers(out_rows)
		if applied and not _insert_strategic_expense(out_rows, company_names, measure_keys, applied):
			# No EBITDA block to host the row — undo so the statement still foots.
			_reclassify_strategic(out_rows, company_names, measure_keys, applied, sign=+1)
		# Drop the Earnings-per-share block — not shown on this consolidated face.
		out_rows[:] = [
			r for r in out_rows
			if not _norm(r.get("particular")).startswith(DROP_PARTICULARS)
		]
		# Mark the collapsible sections (Expenses / Tax expense / OCI) so the page can
		# hide their detail lines behind a "+" and show only the section total, then
		# relocate Total Expenses below Finance costs (purely positional; the
		# "expenses" section's tagged detail lines are unaffected).
		_mark_collapsible_sections(out_rows)
		_move_total_expenses_after_finance_costs(out_rows)
	if adj_names:
		for r in out_rows:
			cells = r["values"][ncomp:]
			r["values"] = r["values"][:ncomp]
			for field, cell in zip(ADJUSTMENT_FIELDS, cells):
				# A ratio of adjustment columns is meaningless -- leave it blank.
				if r.get("value_format") == "percent":
					cell = {k: None for k in cell}
				r[field] = cell
	return out_rows


# P&L rows hidden from the consolidated face (matched by normalised label prefix).
DROP_PARTICULARS = ("earnings per equity share", "basic and diluted")


# Sections whose detail lines collapse behind a "+" on the desk page, leaving only
# the section header (with the toggle) and its total row visible. Each entry is
# (group-id, header-match, total-match); both matchers take a normalised label.
# Header labels are matched exactly so "Expenses" never catches "Other expenses"
# or "Total Expenses"; the total is the first matching bold-style row after it.
COLLAPSIBLE_SECTIONS = [
	("income", lambda n: n == "income", lambda n: n.startswith("total income") or n.startswith("total lncome")),
	("expenses", lambda n: n == "expenses", lambda n: n.startswith("total exp")),
	("tax-expense", lambda n: n == "tax expense", lambda n: n.startswith("total tax")),
	(
		"oci",
		lambda n: n == "other comprehensive income",
		lambda n: n.startswith("total other comprehensive"),
	),
]


def _mark_collapsible_sections(out_rows):
	"""Tag each collapsible section's header (collapse_id) and its detail rows
	(collapse_member) so the client can toggle them. The header and total rows
	stay visible; only the lines strictly between them collapse. No-op for any
	section whose header or total is absent."""
	for gid, is_head, is_total in COLLAPSIBLE_SECTIONS:
		head = _find_row(out_rows, is_head)
		if head < 0:
			continue
		total = -1
		for j in range(head + 1, len(out_rows)):
			if is_total(_norm(out_rows[j].get("particular"))):
				total = j
				break
		if total < 0:
			continue
		out_rows[head]["collapse_id"] = gid
		for j in range(head + 1, total):
			out_rows[j]["collapse_member"] = gid


def _all_ftm_statement(statement, fiscal_year, month, excluded):
	"""All-FTM view: one For-The-Month column per month (April -> selected month)
	for every domestic company, served from that month's Monthly report.
	"""
	# Columns run most-recent first: selected month -> April.
	month_range = list(reversed(_fiscal_months_upto(month)))
	measures = [(m.lower(), "ftm_amount", m) for m in month_range]
	measure_keys = [k for k, _f, _l in measures]

	# Per company, gather each month's rows (only months that have a report).
	company_month_rows, missing, row_sets = {}, [], []
	for c in _domestic_companies():
		if c.name in excluded:
			continue
		per_month = {}
		for m in month_range:
			report = _pick_report(c.name, "Monthly", fiscal_year, m)
			rows = _statement_rows(report.name, statement) if report else None
			if rows:
				per_month[m] = rows
				row_sets.append(rows)
		if per_month:
			company_month_rows[c.name] = per_month
		else:
			missing.append(c.name)

	if not row_sets:
		return {
			"statement": statement,
			"fiscal_year": fiscal_year,
			"previous_fiscal_year": None,
			"report_type": "FTM",
			"month": month,
			"all_ftm": 1,
			"columns": [],
			"companies": [],
			"rows": [],
			"missing_companies": missing,
		}

	# Canonical structure = the fullest row set across all companies/months.
	canonical = max(row_sets, key=len)
	canon_tokens = [_token(r) for r in canonical]

	# Align each company's per-month rows onto the canonical indices, filling
	# that month's measure with its For-The-Month figure.
	aligned = {}
	for cn, per_month in company_month_rows.items():
		vals = [{k: None for k in measure_keys} for _ in canonical]
		for m, rows in per_month.items():
			mk = m.lower()
			comp_tokens = [_token(r) for r in rows]
			matcher = difflib.SequenceMatcher(None, canon_tokens, comp_tokens, autojunk=False)
			for tag, i1, i2, j1, j2 in matcher.get_opcodes():
				if tag == "equal":
					for off in range(i2 - i1):
						src = rows[j1 + off]
						vals[i1 + off][mk] = flt(src.get("ftm_amount") or 0)
		aligned[cn] = vals

	company_names = list(company_month_rows.keys())
	strategic = (
		_strategic_by_primary_all_ftm(company_names, month_range, fiscal_year)
		if statement == PROFIT_AND_LOSS
		else None
	)
	adj_aligned, adj_unmapped = _statement_adjustments(
		statement, canonical,
		_adjustment_periods("FTM", fiscal_year, month, None, month_range),
	)
	aligned.update(adj_aligned)
	out_rows = _build_out_rows(
		canonical, company_names, aligned, measure_keys, statement, strategic, adjustments=True
	)

	return {
		"statement": statement,
		"fiscal_year": fiscal_year,
		"previous_fiscal_year": None,
		"report_type": "FTM",
		"month": month,
		"all_ftm": 1,
		"columns": [{"key": key, "label": lbl} for key, _f, lbl in measures],
		"companies": company_names,
		"rows": out_rows,
		"missing_companies": missing,
		"excluded_companies": sorted(excluded),
		"adjustment_unmapped": adj_unmapped,
	}
