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

# A "domestic" company is one whose functional/default currency matches the
# group's reporting currency. For this deployment that is INR.
DOMESTIC_CURRENCY = "INR"

BALANCE_SHEET = "Balance Sheet"
PROFIT_AND_LOSS = "Profit & Loss"
STATEMENTS = (BALANCE_SHEET, PROFIT_AND_LOSS)

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


def _find_row(rows, pred):
	"""Index of the first out-row whose (normalised) particular matches `pred`."""
	for i, r in enumerate(rows):
		if pred(_norm(r.get("particular"))):
			return i
	return -1


def _insert_gross_margin(out_rows, measure_keys):
	"""Insert derived Gross Margin / Gross Margin (%) rows into a P&L statement.

	Placed directly below "Changes in inventories …". Computed per column
	(company + Consolidate) and per measure from existing line items:

	    Gross Margin      = Total Income - Cost of materials consumed
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
	rev = _find_row(out_rows, lambda n: n.startswith("revenue from operation"))
	inv = _find_row(out_rows, lambda n: n.startswith("changes in inventor"))
	if min(ti, cost, rev, inv) < 0:
		return  # not the expected P&L structure

	ncomp = len(out_rows[ti]["values"])

	def _obj(idx, i):
		"""Cell dict for row `idx`; i < 0 selects the Consolidate column."""
		return out_rows[idx]["consolidate"] if i < 0 else out_rows[idx]["values"][i]

	def _diff(i, k):
		"""Gross Margin (amount) for column i, measure k; None when both absent."""
		tv = (_obj(ti, i) or {}).get(k)
		cv = (_obj(cost, i) or {}).get(k)
		if tv is None and cv is None:
			return None
		return round((tv or 0) - (cv or 0), 2)

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

	gm_consol, gm_values = _build(_diff)
	pct_consol, pct_values = _build(_pct)

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
	out_rows[inv + 1 : inv + 1] = [gross_margin, gross_margin_pct]


@frappe.whitelist()
def get_context(report_type="Yearly", fiscal_year=None):
	"""Filter metadata: available fiscal years (and months for Monthly).

	Resolves the fiscal year server-side (the passed one if valid, else the
	default) so the returned months always match the year the page will show.
	"""
	frappe.has_permission("Financial Report", "read", throw=True)

	companies = [c.name for c in _domestic_companies()]
	empty = {
		"fiscal_years": [],
		"default_fiscal_year": None,
		"resolved_fiscal_year": None,
		"months": [],
		"default_month": None,
		"company_count": 0,
	}
	if not companies:
		return empty

	years = frappe.get_all(
		"Financial Report",
		filters={"company": ["in", companies], "report_type": report_type},
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
				"report_type": report_type,
				"fiscal_year": y,
				"report_status": "Successful",
			},
		):
			default_year = y
			break
	if not default_year and years:
		default_year = years[0]

	resolved_year = fiscal_year if fiscal_year in years else default_year

	# Months only apply to Monthly reports.
	months, default_month = [], None
	if report_type == "Monthly" and resolved_year:
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
	}


@frappe.whitelist()
def get_consolidated_statement(
	fiscal_year=None, report_type="Yearly", statement=BALANCE_SHEET, month=None
):
	"""Return one statement as a Particular | Consolidate | <company> matrix.

	Rows follow the canonical (most complete) template structure; each company's
	line items are aligned to it by particular so figures land in the right row
	even when a company omits a line. Amounts are the current-year figures.
	For Monthly reports, `month` selects the report month.
	"""
	frappe.has_permission("Financial Report", "read", throw=True)
	if statement not in STATEMENTS:
		statement = BALANCE_SHEET
	if report_type != "Monthly":
		month = None

	# Gather each domestic company's rows for this statement.
	with_data, missing = [], []
	for c in _domestic_companies():
		report = _pick_report(c.name, report_type, fiscal_year, month)
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
	if report_type == "Monthly":
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
	out_rows = []
	for idx, r in enumerate(canonical):
		is_header = bool(r.get("header") or r.get("group"))
		values, totals, has_value = [], {k: 0.0 for k in measure_keys}, False
		for cn in company_names:
			cell = aligned[cn][idx]
			if cell is None:
				values.append({k: None for k in measure_keys})
			else:
				values.append({k: round(cell[k], 2) for k in measure_keys})
				for k in measure_keys:
					totals[k] += cell[k]
				# A row carries figures if any measure is non-zero. This keeps
				# grouped total rows (e.g. "Profit for the year") — which are
				# flagged group=1 but hold real amounts — from being blanked,
				# while genuine section headers (all-zero) stay blank.
				if any(abs(cell[k]) > 1e-6 for k in measure_keys):
					has_value = True
		blank = not has_value
		out_rows.append(
			{
				"particular": r.get("account") or "",
				"indent": int(r.get("indent") or 0),
				"is_bold": 1 if r.get("is_bold") else 0,
				"is_header": 1 if is_header else 0,
				"consolidate": None if blank else {k: round(totals[k], 2) for k in measure_keys},
				"values": values,
			}
		)

	# Derived KPIs (Gross Margin, Gross Margin %) — P&L only; no-op elsewhere.
	if statement == PROFIT_AND_LOSS:
		_insert_gross_margin(out_rows, measure_keys)

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
	}
