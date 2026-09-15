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
import re
from collections import Counter

import frappe
from frappe.utils import flt

# A "domestic" company is one whose functional/default currency matches the
# group's reporting currency. For this deployment that is INR.
DOMESTIC_CURRENCY = "INR"

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


def _domestic_companies():
	"""Return domestic companies as [{name, currency}], ordered by name."""
	return frappe.get_all(
		"Company",
		filters={"default_currency": DOMESTIC_CURRENCY},
		fields=["name", "default_currency as currency"],
		order_by="name asc",
	)


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
		"Financial Report",
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
		"Financial Report Details",
		filters={
			"parent": report_name,
			"parenttype": "Financial Report",
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


# Section name of the note that bifurcates "Revenue from operations".
REVENUE_NOTE_SECTION = "Revenue from operations"

# User-entered "Strategic Expense" figures (per company / fiscal year / month).
STRATEGIC_DOCTYPE = "Strategic Expense Entry"


def _fetch_strategic(companies, fiscal_years):
	"""Return {(company, fiscal_year, month): amount} summed from user entries."""
	companies = [c for c in (companies or [])]
	fiscal_years = [y for y in (fiscal_years or []) if y]
	if not companies or not fiscal_years:
		return {}
	if not frappe.db.exists("DocType", STRATEGIC_DOCTYPE):
		return {}  # DocType not installed yet — treat as no data
	rows = frappe.get_all(
		STRATEGIC_DOCTYPE,
		filters={"company": ["in", companies], "fiscal_year": ["in", fiscal_years]},
		fields=["company", "fiscal_year", "month", "amount"],
	)
	agg = {}
	for r in rows:
		key = (r.company, r.fiscal_year, r.month)
		agg[key] = agg.get(key, 0.0) + flt(r.amount)
	return agg


def _strategic_amounts(company_names, report_type, fiscal_year, month, previous_fiscal_year):
	"""Per-company Strategic Expense mapped onto the P&L measures for this view.

	Entries are monthly amounts, so: Yearly sums the fiscal year; Monthly gives
	the cumulative-to-month (cm), the month itself (ftm) and cumulative-to-prev
	(pm); FTM gives the single month.
	"""
	raw = _fetch_strategic(company_names, [fiscal_year, previous_fiscal_year])

	def m_amt(c, fy, m):
		return raw.get((c, fy, m), 0.0)

	def cum(c, fy, upto):
		return sum(m_amt(c, fy, m) for m in _fiscal_months_upto(upto))

	def year_total(c, fy):
		return sum(m_amt(c, fy, m) for m in FISCAL_MONTH_ORDER) if fy else 0.0

	out = {}
	for c in company_names:
		if report_type == "FTM":
			out[c] = {"ftm": m_amt(c, fiscal_year, month)}
		elif report_type == "Monthly":
			months_up = _fiscal_months_upto(month)
			out[c] = {
				"cm": cum(c, fiscal_year, month),
				"ftm": m_amt(c, fiscal_year, month),
				"pm": sum(m_amt(c, fiscal_year, m) for m in months_up[:-1]),
			}
		else:  # Yearly
			out[c] = {
				"cy": year_total(c, fiscal_year),
				"py": year_total(c, previous_fiscal_year),
			}
	return out


def _strategic_amounts_all_ftm(company_names, month_range, fiscal_year):
	"""All-FTM Strategic Expense: one month's amount per month column."""
	raw = _fetch_strategic(company_names, [fiscal_year])
	return {
		c: {m.lower(): raw.get((c, fiscal_year, m), 0.0) for m in month_range}
		for c in company_names
	}


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


def _insert_strategic_expense(out_rows, company_names, measure_keys, strategic):
	"""Insert the "Strategic Expense" row below Finance costs and deduct from profit.

	The amount is added into Total Expenses and subtracted from the profit rows
	(Profit before tax / Profit for the year / Total comprehensive income), so the
	statement still foots. EBITDA is computed earlier from the pre-Strategic Total
	Expenses, so it is intentionally left unchanged (Strategic is a below-EBITDA,
	strategic-in-nature deduction). No-op when Finance costs is absent.
	"""
	fin = _find_row(out_rows, lambda n: n.startswith("finance cost"))
	if fin < 0:
		return

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
		"consolidate": consol,
		"values": values,
	}
	out_rows[fin + 1 : fin + 1] = [row]

	te = _find_row(out_rows, lambda n: n.startswith("total exp"))
	if te >= 0:
		_adjust_row(out_rows[te], company_names, measure_keys, strategic, sign=+1)
	for r in out_rows:
		n = _norm(r.get("particular"))
		if (
			n.startswith("profit before tax")
			or n.startswith("profit for the")
			or n.startswith("total comprehensive")
		):
			_adjust_row(r, company_names, measure_keys, strategic, sign=-1)


@frappe.whitelist()
def get_strategic_entries(fiscal_year=None, month=None):
	"""Existing Strategic Expense amounts for a fiscal year + month, per company.

	Powers the in-page entry grid: returns the domestic company list plus the
	current amount for each (0 when none), so the dialog can pre-fill inputs.
	"""
	frappe.has_permission(STRATEGIC_DOCTYPE, "read", throw=True)
	companies = [c.name for c in _domestic_companies()]
	amounts = {}
	if fiscal_year and month:
		rows = frappe.get_all(
			STRATEGIC_DOCTYPE,
			filters={"fiscal_year": fiscal_year, "month": month, "company": ["in", companies]},
			fields=["company", "amount"],
		)
		amounts = {r.company: flt(r.amount) for r in rows}
	return {"companies": companies, "amounts": amounts}


@frappe.whitelist()
def save_strategic_entries(fiscal_year=None, month=None, amounts=None):
	"""Upsert Strategic Expense amounts for a fiscal year + month.

	`amounts` is a {company: amount} map. A zero/blank amount deletes any existing
	entry for that company/period; a non-zero one creates or updates it. Returns
	counts so the caller can confirm.
	"""
	frappe.has_permission(STRATEGIC_DOCTYPE, "create", throw=True)
	if not fiscal_year or not month:
		frappe.throw("Fiscal Year and Month are required.")
	if isinstance(amounts, str):
		try:
			amounts = json.loads(amounts)
		except (ValueError, TypeError):
			amounts = {}
	valid = {c.name for c in _domestic_companies()}

	saved = deleted = 0
	for company, amt in (amounts or {}).items():
		if company not in valid:
			continue
		existing = frappe.db.get_value(
			STRATEGIC_DOCTYPE,
			{"company": company, "fiscal_year": fiscal_year, "month": month},
			"name",
		)
		val = flt(amt)
		if not val:
			if existing:
				frappe.delete_doc(STRATEGIC_DOCTYPE, existing)
				deleted += 1
			continue
		if existing:
			doc = frappe.get_doc(STRATEGIC_DOCTYPE, existing)
			doc.amount = val
			doc.save()
		else:
			frappe.get_doc(
				{
					"doctype": STRATEGIC_DOCTYPE,
					"company": company,
					"fiscal_year": fiscal_year,
					"month": month,
					"amount": val,
				}
			).insert()
		saved += 1
	frappe.db.commit()
	return {"saved": saved, "deleted": deleted}


def _note_html(report_name, section):
	"""Return the rendered `table_data` HTML for a Consolidation Note section."""
	detail = frappe.get_all(
		"Financial Report Details",
		filters={
			"parent": report_name,
			"parenttype": "Financial Report",
			"section_type": "Consolidation Note",
			"section": section,
		},
		fields=["table_data"],
		order_by="idx asc",
		limit=1,
	)
	if not detail:
		return None
	return (detail[0].table_data or "").strip() or None


def _num(text):
	"""Parse a numeric cell; returns None when it is not a number."""
	t = re.sub(r"<[^>]+>", "", text or "")
	t = t.replace("&nbsp;", "").replace(" ", "").replace(",", "").strip()
	if t in ("", "-"):
		return None
	try:
		return float(t)
	except ValueError:
		return None


def _parse_note_html(html):
	"""Parse a note's HTML table into structured line items.

	Returns a list of {particular, indent, is_bold, nums:[...]} — one per body
	row, in document order, excluding the "Particulars" header row. Indentation
	is inferred from leading &nbsp; in the label cell (4 per level), matching how
	the note tables are rendered. `nums` holds the numeric columns left-to-right.
	"""
	if not html:
		return None
	rows = []
	for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
		cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
		if not cells:
			continue
		if re.search(r"<th", tr, re.I):
			continue  # header row ("Particulars | <dates>")
		raw = cells[0]
		lead = re.match(r"((?:&nbsp;| |\s)*)", raw).group(1)
		indent = (lead.count("&nbsp;") + lead.count(" ")) // 4
		label = re.sub(r"<[^>]+>", "", raw).replace("&nbsp;", " ").replace(" ", " ").strip()
		if not label:
			continue
		is_bold = bool(re.search(r"font-weight:\s*bold", tr, re.I))
		nums = [_num(c) for c in cells[1:]]
		rows.append({"particular": label, "indent": indent, "is_bold": 1 if is_bold else 0, "nums": nums})
	return rows or None


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
	out_rows[te + 1 : te + 1] = block


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


@frappe.whitelist()
def get_context(report_type="Yearly", fiscal_year=None):
	"""Filter metadata: available fiscal years (and months for Monthly).

	Resolves the fiscal year server-side (the passed one if valid, else the
	default) so the returned months always match the year the page will show.
	"""
	frappe.has_permission("Financial Report", "read", throw=True)

	# FTM reads the Monthly reports (only its For-The-Month column differs).
	storage_type = _storage_report_type(report_type)

	companies = [c.name for c in _domestic_companies()]
	empty = {
		"fiscal_years": [],
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
		"Financial Report",
		filters={"company": ["in", companies], "report_type": storage_type},
		distinct=True,
		pluck="fiscal_year",
		order_by="fiscal_year desc",
	)
	years = [y for y in years if y]

	default_year = None
	for y in years:
		if frappe.db.exists(
			"Financial Report",
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
			"Financial Report",
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
				"Financial Report",
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
	frappe.has_permission("Financial Report", "read", throw=True)
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
		_strategic_amounts(company_names, report_type, fiscal_year, month, previous_fiscal_year)
		if statement == PROFIT_AND_LOSS
		else None
	)
	out_rows = _build_out_rows(canonical, company_names, aligned, measure_keys, statement, strategic)

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
	}


@frappe.whitelist()
def get_revenue_bifurcation(
	fiscal_year=None, report_type="Yearly", month=None,
	exclude_companies=None, all_ftm=None,
):
	"""Breakdown ("bifurcation") of Revenue from operations, per company.

	Read from each domestic company's "Revenue from operations" note and aligned
	into the same Particular | Consolidate | <company> shape the P&L face uses, so
	the page can expand the Revenue row inline. Columns mirror the P&L face for
	the same filters.
	"""
	frappe.has_permission("Financial Report", "read", throw=True)
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
		return _revenue_bifurcation_all_ftm(fiscal_year, month, excluded)

	# Parse each visible company's revenue note.
	parsed, missing = [], []
	for c in _domestic_companies():
		if c.name in excluded:
			continue
		report = _pick_report(c.name, storage_type, fiscal_year, month)
		rows = _parse_note_html(_note_html(report.name, REVENUE_NOTE_SECTION)) if report else None
		if rows:
			parsed.append({"company": c.name, "rows": rows, "report": report})
		else:
			missing.append(c.name)

	if not parsed:
		return {"columns": [], "companies": [], "rows": [], "missing_companies": missing}

	prev_years = [p["report"].get("previous_fiscal_year") for p in parsed]
	prev_years = [y for y in prev_years if y]
	previous_fiscal_year = Counter(prev_years).most_common(1)[0][0] if prev_years else None

	# (measure_key, label, note_column_index): the note's numeric columns map onto
	# the same measures the P&L face shows for this report type. The Monthly note
	# also carries a trailing previous-year column, which the face omits.
	if report_type == "FTM":
		measures = [("ftm", "FTM", 1)]
	elif report_type == "Monthly":
		measures = [
			("cm", month or "Current Month", 0),
			("ftm", "FTM", 1),
			("pm", _prev_month(month) or "Previous Month", 2),
		]
	else:
		measures = [
			("cy", fiscal_year or "Current Year", 0),
			("py", previous_fiscal_year or "Previous Year", 1),
		]

	company_names = [p["company"] for p in parsed]
	# Canonical line-item order = the company with the most note rows.
	canonical = max(parsed, key=lambda p: len(p["rows"]))["rows"]
	lookups = {p["company"]: {_norm(r["particular"]): r for r in p["rows"]} for p in parsed}

	out_rows = _build_bifurcation_rows(canonical, company_names, lookups, measures)
	return {
		"columns": [{"key": k, "label": lbl} for k, lbl, _ci in measures],
		"companies": company_names,
		"rows": out_rows,
		"missing_companies": missing,
	}


def _build_bifurcation_rows(canonical, company_names, lookups, measures):
	"""Align parsed note line items across companies onto the canonical order."""
	measure_keys = [m[0] for m in measures]
	out = []
	for cr in canonical:
		key = _norm(cr["particular"])
		values, totals, has_value = [], {k: 0.0 for k in measure_keys}, False
		for cn in company_names:
			src = lookups[cn].get(key)
			if not src:
				values.append({k: None for k in measure_keys})
				continue
			cell = {}
			for mk, _lbl, ci in measures:
				v = src["nums"][ci] if ci < len(src["nums"]) else None
				cell[mk] = round(v, 2) if v is not None else None
				if v is not None:
					totals[mk] += v
					if abs(v) > 1e-6:
						has_value = True
			values.append(cell)
		blank = not has_value
		out.append(
			{
				"particular": cr["particular"],
				"indent": int(cr.get("indent") or 0),
				"is_bold": int(cr.get("is_bold") or 0),
				"is_header": 1 if blank else 0,
				"consolidate": None if blank else {k: round(totals[k], 2) for k in measure_keys},
				"values": values,
			}
		)
	return out


def _revenue_bifurcation_all_ftm(fiscal_year, month, excluded):
	"""All-FTM view of the Revenue breakdown: one FTM column per month."""
	month_range = list(reversed(_fiscal_months_upto(month)))
	measures = [(m.lower(), m, 1) for m in month_range]  # note FTM column = index 1
	measure_keys = [k for k, _l, _c in measures]

	company_month_rows, missing, row_sets = {}, [], []
	for c in _domestic_companies():
		if c.name in excluded:
			continue
		per_month = {}
		for m in month_range:
			report = _pick_report(c.name, "Monthly", fiscal_year, m)
			rows = _parse_note_html(_note_html(report.name, REVENUE_NOTE_SECTION)) if report else None
			if rows:
				per_month[m] = rows
				row_sets.append(rows)
		if per_month:
			company_month_rows[c.name] = per_month
		else:
			missing.append(c.name)

	if not row_sets:
		return {"columns": [], "companies": [], "rows": [], "missing_companies": missing}

	canonical = max(row_sets, key=len)
	company_names = list(company_month_rows.keys())

	out = []
	for cr in canonical:
		key = _norm(cr["particular"])
		values, totals, has_value = [], {k: 0.0 for k in measure_keys}, False
		for cn in company_names:
			cell = {k: None for k in measure_keys}
			for m, rows in company_month_rows[cn].items():
				src = next((r for r in rows if _norm(r["particular"]) == key), None)
				v = src["nums"][1] if src and len(src["nums"]) > 1 else None
				if v is not None:
					cell[m.lower()] = round(v, 2)
					totals[m.lower()] += v
					if abs(v) > 1e-6:
						has_value = True
			values.append(cell)
		blank = not has_value
		out.append(
			{
				"particular": cr["particular"],
				"indent": int(cr.get("indent") or 0),
				"is_bold": int(cr.get("is_bold") or 0),
				"is_header": 1 if blank else 0,
				"consolidate": None if blank else {k: round(totals[k], 2) for k in measure_keys},
				"values": values,
			}
		)
	return {
		"columns": [{"key": k, "label": lbl} for k, lbl, _c in measures],
		"companies": company_names,
		"rows": out,
		"missing_companies": missing,
	}


def _build_out_rows(canonical, company_names, aligned, measure_keys, statement, strategic=None):
	"""Assemble the Particular | Consolidate | <company> rows from aligned data.

	`aligned[company][idx]` is either None (row absent for that company) or a
	dict of per-measure figures; a figure may itself be None when only some
	measures apply to a company/row (e.g. a month missing in the All-FTM view).
	Totals ignore Nones, and a row is blank only when every measure is empty.
	"""
	out_rows = []
	for idx, r in enumerate(canonical):
		is_header = bool(r.get("header") or r.get("group"))
		values, totals, has_value = [], {k: 0.0 for k in measure_keys}, False
		for cn in company_names:
			cell = aligned[cn][idx]
			if cell is None:
				values.append({k: None for k in measure_keys})
			else:
				values.append(
					{k: (round(cell[k], 2) if cell[k] is not None else None) for k in measure_keys}
				)
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
		_insert_ebitda(out_rows, measure_keys)
		_reorder_pbt_drivers(out_rows)
		# Strategic Expense (user-entered) goes below Finance costs and deducts from
		# profit — done last so EBITDA above keeps its pre-Strategic figures.
		if strategic:
			_insert_strategic_expense(out_rows, company_names, measure_keys, strategic)
	return out_rows


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
		_strategic_amounts_all_ftm(company_names, month_range, fiscal_year)
		if statement == PROFIT_AND_LOSS
		else None
	)
	out_rows = _build_out_rows(canonical, company_names, aligned, measure_keys, statement, strategic)

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
	}
