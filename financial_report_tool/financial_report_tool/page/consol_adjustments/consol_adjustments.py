# Copyright (c) 2026, Hybrowlabs and contributors
# For license information, please see license.txt
"""Server API for the "Consolidation Adjustments" desk page.

Captures elimination and regrouping entries against the group's own Company
and Standalone Group masters (the same masters GL Group Mapping and the
Consolidated Financial Statement page use) and derives four reports from
them: Adjustment TB, company-to-company matrix, inter-company reconciliation
and entity-wise summary. Each entry carries exactly one of Debit/Credit;
`net = debit - credit`.
"""

import io
import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.xlsxutils import make_xlsx, read_xlsx_file_from_attached_file

DOCTYPE = "Consol Adjustment Entry"
TYPES = ("Elimination", "Regrouping")
# Indian fiscal year runs April -> March; present months in that order.
MONTHS = (
	"April", "May", "June", "July", "August", "September",
	"October", "November", "December", "January", "February", "March",
)


def _label(t):
	prefix = "RGP-" if t.get("adj_type") == "Regrouping" else "ELM-"
	no = (t.get("name") or "").split("-")[-1]
	return prefix + no.zfill(4) if no.isdigit() else t.get("name")


def _out(r):
	"""DB row (frappe._dict) -> API shape used by the front-end."""
	return {
		"id": r.name,
		"no": _label(r),
		"from": r.from_company,
		"to": r.to_company or "",
		"pg": r.primary_group,
		"sg": r.secondary_group,
		"fy": r.fiscal_year,
		"month": r.month or "",
		"debit": flt(r.debit),
		"credit": flt(r.credit),
		"net": flt(r.debit) - flt(r.credit),
		"type": r.adj_type,
		"narration": r.narration or "",
		"ref": r.reference or "",
		"createdAt": r.get("creation"),
		"updatedAt": r.get("modified"),
	}


ROW_FIELDS = [
	"name", "from_company", "to_company", "primary_group", "secondary_group",
	"fiscal_year", "month", "debit", "credit", "adj_type", "narration", "reference",
	"creation", "modified",
]


def _clean(b):
	num = lambda v: flt(v) if v not in (None, "") else 0.0
	return {
		"from_company": (b.get("from") or "").strip(),
		"to_company": (b.get("to") or "").strip(),
		"primary_group": (b.get("pg") or "").strip(),
		"secondary_group": (b.get("sg") or "").strip(),
		"fiscal_year": (b.get("fy") or "").strip(),
		"month": (b.get("month") or "").strip(),
		"debit": num(b.get("debit")),
		"credit": num(b.get("credit")),
		"adj_type": (b.get("type") or "").strip(),
		"narration": (b.get("narration") or "").strip(),
		"reference": (b.get("ref") or "").strip(),
	}


def _validate(t, companies, group_subs, fiscal_years):
	"""Same rules as the doctype controller, re-checked here so bulk import
	can report every failing row instead of stopping at the first insert."""
	e = []
	if not t["from_company"]:
		e.append(_("From company is required."))
	elif t["from_company"] not in companies:
		e.append(_('From company "{0}" is not in the master.').format(t["from_company"]))
	if t["to_company"] and t["to_company"] not in companies:
		e.append(_('To company "{0}" is not in the master.').format(t["to_company"]))
	if t["to_company"] and t["to_company"] == t["from_company"]:
		e.append(_("From and To company cannot be the same."))
	if not t["fiscal_year"]:
		e.append(_("Fiscal Year is required."))
	elif t["fiscal_year"] not in fiscal_years:
		e.append(_('Fiscal Year "{0}" is not valid.').format(t["fiscal_year"]))
	if not t["month"]:
		e.append(_("Month is required."))
	elif t["month"] not in MONTHS:
		e.append(_('Month "{0}" is not valid.').format(t["month"]))
	subs = group_subs.get(t["primary_group"])
	if subs is None:
		e.append(_('Primary group "{0}" is not in the master.').format(t["primary_group"]))
	elif t["secondary_group"] not in subs:
		e.append(_('"{0}" is not a secondary group under {1}.').format(t["secondary_group"], t["primary_group"]))
	if t["debit"] < 0 or t["credit"] < 0:
		e.append(_("Amounts must be positive."))
	elif t["debit"] > 0 and t["credit"] > 0:
		e.append(_("Enter either a debit or a credit, not both."))
	elif not (t["debit"] > 0) and not (t["credit"] > 0):
		e.append(_("Enter a debit or a credit amount."))
	if t["adj_type"] not in TYPES:
		e.append(_("Adjustment type must be Elimination or Regrouping."))
	return e


# ---------------------------------------------------------------- masters --
@frappe.whitelist()
def get_masters():
	"""Company list and Primary -> [Secondary] group hierarchy, sourced from
	the existing Company and Standalone Group masters (the same ones GL Group
	Mapping and the Consolidated Financial Statement page use)."""
	frappe.has_permission(DOCTYPE, "read", throw=True)
	companies = frappe.get_all("Company", fields=["name"], order_by="name asc", pluck="name")
	primaries = frappe.get_all(
		"Standalone Group",
		filters={"is_primary_group": 1},
		fields=["name", "report_type"],
		order_by="name asc",
	)
	subs = frappe.get_all(
		"Standalone Group",
		filters={"parent_standalone_group": ["in", [p.name for p in primaries]]} if primaries else {"name": ("=", "")},
		fields=["name", "parent_standalone_group"],
		order_by="name asc",
	)
	by_parent = defaultdict(list)
	for s in subs:
		by_parent[s.parent_standalone_group].append(s.name)
	groups = [
		{"name": p.name, "st": p.report_type or "Unmapped", "subs": by_parent.get(p.name, [])}
		for p in primaries
	]
	fiscal_years = frappe.get_all("Fiscal Year", fields=["name"], order_by="year_start_date desc", pluck="name")
	return {"companies": companies, "groups": groups, "fiscal_years": fiscal_years, "months": list(MONTHS)}


def _get_masters_maps():
	m = get_masters()
	return set(m["companies"]), {g["name"]: set(g["subs"]) for g in m["groups"]}, set(m["fiscal_years"])


# ------------------------------------------------------------ transactions --
@frappe.whitelist()
def list_transactions(adj_type=None, from_company=None, primary_group=None, fiscal_year=None, month=None):
	frappe.has_permission(DOCTYPE, "read", throw=True)
	filters = {}
	if adj_type:
		filters["adj_type"] = adj_type
	if from_company:
		filters["from_company"] = from_company
	if primary_group:
		filters["primary_group"] = primary_group
	if fiscal_year:
		filters["fiscal_year"] = fiscal_year
	if month:
		filters["month"] = month
	rows = frappe.get_all(DOCTYPE, filters=filters, fields=ROW_FIELDS, order_by="creation asc")
	return [_out(r) for r in rows]


@frappe.whitelist()
def create_transaction(txn=None, **kwargs):
	frappe.has_permission(DOCTYPE, "create", throw=True)
	body = json.loads(txn) if isinstance(txn, str) else (txn or kwargs)
	t = _clean(body)
	companies, group_subs, fiscal_years = _get_masters_maps()
	errors = _validate(t, companies, group_subs, fiscal_years)
	if errors:
		frappe.throw("<br>".join(errors), title=_("Could not save"))
	doc = frappe.get_doc({"doctype": DOCTYPE, **t})
	doc.insert()
	return _out(frappe.get_all(DOCTYPE, filters={"name": doc.name}, fields=ROW_FIELDS)[0])


@frappe.whitelist()
def update_transaction(id, txn=None, **kwargs):
	frappe.has_permission(DOCTYPE, "write", throw=True)
	if not frappe.db.exists(DOCTYPE, id):
		frappe.throw(_("Transaction not found."), frappe.DoesNotExistError)
	body = json.loads(txn) if isinstance(txn, str) else (txn or kwargs)
	t = _clean(body)
	companies, group_subs, fiscal_years = _get_masters_maps()
	errors = _validate(t, companies, group_subs, fiscal_years)
	if errors:
		frappe.throw("<br>".join(errors), title=_("Could not save"))
	doc = frappe.get_doc(DOCTYPE, id)
	doc.update(t)
	doc.save()
	return _out(frappe.get_all(DOCTYPE, filters={"name": doc.name}, fields=ROW_FIELDS)[0])


@frappe.whitelist()
def delete_transaction(id):
	frappe.has_permission(DOCTYPE, "delete", throw=True)
	if not frappe.db.exists(DOCTYPE, id):
		frappe.throw(_("Transaction not found."), frappe.DoesNotExistError)
	frappe.delete_doc(DOCTYPE, id)
	return {"deleted": 1}


@frappe.whitelist()
def bulk_create(rows):
	"""All-or-nothing import: `rows` is a JSON list of the same shape as
	create_transaction's body. Every row is validated before anything is
	inserted; on any failure, nothing is saved and every failing row is
	reported."""
	frappe.has_permission(DOCTYPE, "create", throw=True)
	rows = json.loads(rows) if isinstance(rows, str) else (rows or [])
	if not rows:
		frappe.throw(_("No rows to import."))
	companies, group_subs, fiscal_years = _get_masters_maps()
	cleaned = [_clean(r) for r in rows]
	errors = []
	for i, t in enumerate(cleaned):
		e = _validate(t, companies, group_subs, fiscal_years)
		if e:
			errors.append(_("Row {0}: {1}").format(i + 1, e[0]))
	if errors:
		frappe.throw("<br>".join(errors[:50]), title=_("{0} rows failed validation").format(len(errors)))
	for t in cleaned:
		frappe.get_doc({"doctype": DOCTYPE, **t}).insert()
	return {"inserted": len(cleaned)}


# ----------------------------------------------------------------- reports --
def _base_filters(adj_type=None, primary_group=None, fiscal_year=None, month=None):
	f = {}
	if adj_type:
		f["adj_type"] = adj_type
	if primary_group:
		f["primary_group"] = primary_group
	if fiscal_year:
		f["fiscal_year"] = fiscal_year
	if month:
		f["month"] = month
	return f


@frappe.whitelist()
def report_adjustment_tb(adj_type=None, fiscal_year=None, month=None):
	"""Totals by statement (P&L, then BS), primary group, secondary group and
	type, in master order -- mirrors the P&L/BS face layout."""
	frappe.has_permission(DOCTYPE, "read", throw=True)
	rows = frappe.get_all(
		DOCTYPE, filters=_base_filters(adj_type, None, fiscal_year, month),
		fields=["primary_group", "secondary_group", "adj_type", "debit", "credit"],
	)
	masters = get_masters()
	statement_of = {g["name"]: g["st"] for g in masters["groups"]}
	order = {g["name"]: i for i, g in enumerate(masters["groups"])}
	sub_order = {g["name"]: {s: i for i, s in enumerate(g["subs"])} for g in masters["groups"]}

	by = defaultdict(lambda: {"entries": 0, "debit": 0.0, "credit": 0.0})
	for r in rows:
		k = (r.primary_group, r.secondary_group, r.adj_type)
		c = by[k]
		c["entries"] += 1
		c["debit"] += flt(r.debit)
		c["credit"] += flt(r.credit)

	pgs = sorted({k[0] for k in by}, key=lambda p: (order.get(p, 999), p))
	out = []
	for pg in pgs:
		st = statement_of.get(pg, "Unmapped")
		sgs = sorted(
			{k[1] for k in by if k[0] == pg},
			key=lambda s: (sub_order.get(pg, {}).get(s, 999), s),
		)
		for sg in sgs:
			for ty in TYPES:
				c = by.get((pg, sg, ty))
				if not c:
					continue
				out.append({
					"statement": st, "pg": pg, "sg": sg, "type": ty,
					"entries": c["entries"], "debit": round(c["debit"], 2), "credit": round(c["credit"], 2),
					"net": round(c["debit"] - c["credit"], 2),
				})
	return out


@frappe.whitelist()
def report_company_matrix(adj_type=None, primary_group=None, fiscal_year=None, month=None):
	"""Net by From x To company; only entries with a To company are included."""
	frappe.has_permission(DOCTYPE, "read", throw=True)
	rows = frappe.get_all(
		DOCTYPE, filters={**_base_filters(adj_type, primary_group, fiscal_year, month), "to_company": ["!=", ""]},
		fields=["from_company", "to_company", "debit", "credit"],
	)
	by = defaultdict(float)
	for r in rows:
		by[(r.from_company, r.to_company)] += flt(r.debit) - flt(r.credit)
	return [
		{"from": f, "to": t, "net": round(n, 2)}
		for (f, t), n in sorted(by.items())
	]


@frappe.whitelist()
def report_ic_reconciliation(adj_type=None, primary_group=None, fiscal_year=None, month=None):
	"""Company-pair reconciliation: for each {A, B} (A < B alphabetically),
	A->B net + B->A net should be zero."""
	frappe.has_permission(DOCTYPE, "read", throw=True)
	rows = frappe.get_all(
		DOCTYPE, filters={**_base_filters(adj_type, primary_group, fiscal_year, month), "to_company": ["!=", ""]},
		fields=["from_company", "to_company", "debit", "credit"],
	)
	pairs = defaultdict(lambda: {"ab": 0.0, "ba": 0.0, "entries": 0})
	for r in rows:
		a, b = sorted([r.from_company, r.to_company])
		p = pairs[(a, b)]
		net = flt(r.debit) - flt(r.credit)
		if r.from_company == a:
			p["ab"] += net
		else:
			p["ba"] += net
		p["entries"] += 1
	out = []
	for (a, b), p in pairs.items():
		diff = p["ab"] + p["ba"]
		out.append({
			"a": a, "b": b, "entries": p["entries"],
			"ab": round(p["ab"], 2), "ba": round(p["ba"], 2), "diff": round(diff, 2),
		})
	out.sort(key=lambda r: abs(r["diff"]), reverse=True)
	return out


@frappe.whitelist()
def report_entity_summary(adj_type=None, primary_group=None, fiscal_year=None, month=None):
	"""Per company: entries, Dr, Cr and net as originator, plus the net that
	counterparties recorded against it."""
	frappe.has_permission(DOCTYPE, "read", throw=True)
	rows = frappe.get_all(
		DOCTYPE, filters=_base_filters(adj_type, primary_group, fiscal_year, month),
		fields=["from_company", "to_company", "debit", "credit"],
	)
	by = defaultdict(lambda: {"entries": 0, "debit": 0.0, "credit": 0.0, "counterparty_net": 0.0})
	for r in rows:
		f = by[r.from_company]
		f["entries"] += 1
		f["debit"] += flt(r.debit)
		f["credit"] += flt(r.credit)
		if r.to_company:
			by[r.to_company]["counterparty_net"] += flt(r.debit) - flt(r.credit)
	return [
		{
			"company": c, "entries": v["entries"],
			"debit": round(v["debit"], 2), "credit": round(v["credit"], 2),
			"net": round(v["debit"] - v["credit"], 2),
			"counterparty_net": round(v["counterparty_net"], 2),
		}
		for c, v in sorted(by.items())
	]


# ------------------------------------------------------------------ import --
HEADER_ALIASES = {
	"from": ["from company", "from", "of", "company from", "originating company"],
	"to": ["to company", "to", "company", "counterparty", "counterparty company"],
	"pg": ["primary group", "primary grouping", "primary"],
	"sg": ["secondary group", "secondary grouping", "secondary"],
	"fy": ["fiscal year", "fy"],
	"month": ["month"],
	"debit": ["debit", "dr", "debit amount"],
	"credit": ["credit", "cr", "credit amount"],
	"amount": ["amount", "net", "net impact"],
	"type": ["adjustment type", "type", "category"],
	"narration": ["description / narration", "description", "narration", "description/narration"],
	"ref": ["reference", "ref"],
}


def _norm(s):
	return " ".join(str(s or "").strip().lower().split())


def _match_in(options, value):
	n = _norm(value)
	for o in options:
		if _norm(o) == n:
			return o
	return None


@frappe.whitelist()
def preview_import(file_url):
	"""Parse an uploaded Excel/CSV file into validated rows, without saving.
	Returns `{ok: [...], errors: [...], skipped}` so the client can show a
	confirmation before importing."""
	frappe.has_permission(DOCTYPE, "create", throw=True)
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()
	is_xlsx = file_url.lower().endswith((".xlsx", ".xls"))
	rows = read_xlsx_file_from_attached_file(fcontent=content) if is_xlsx else _read_csv(content)

	hi, colmap = -1, {}
	for r in range(min(15, len(rows))):
		m = {}
		for ci, cell in enumerate(rows[r]):
			n = _norm(cell)
			for key, aliases in HEADER_ALIASES.items():
				if key not in m and n in aliases:
					m[key] = ci
		if m.get("from") is not None and (m.get("debit") is not None or m.get("credit") is not None or m.get("amount") is not None):
			hi, colmap = r, m
			break
	if hi < 0:
		frappe.throw(
			_("Could not find a header row. It needs at least a From Company column and Debit/Credit (or Amount) columns.")
		)

	companies, group_subs, fiscal_years = _get_masters_maps()
	ok, errors, skipped = [], [], 0

	def cell(row, key):
		idx = colmap.get(key)
		return row[idx] if idx is not None and idx < len(row) else ""

	for r in range(hi + 1, len(rows)):
		row = rows[r]
		if not row or all(c in (None, "") for c in row):
			continue
		dr = flt(cell(row, "debit"))
		cr = flt(cell(row, "credit"))
		if colmap.get("debit") is None and colmap.get("credit") is None:
			amt = flt(cell(row, "amount"))
			dr, cr = (amt, 0.0) if amt > 0 else (0.0, -amt if amt < 0 else 0.0)
		if not dr and not cr:
			skipped += 1
			continue
		if dr < 0 and not cr:
			dr, cr = 0.0, -dr
		if cr < 0 and not dr:
			dr, cr = -cr, 0.0

		pg_raw = cell(row, "pg")
		pg = _match_in(group_subs.keys(), pg_raw) or str(pg_raw).strip()
		subs = group_subs.get(pg, set())
		sg_raw = cell(row, "sg")
		sg = _match_in(subs, sg_raw) or str(sg_raw).strip()
		ty_raw = _norm(cell(row, "type"))
		to_raw = str(cell(row, "to")).strip()
		if _norm(to_raw) in ("n/a", "na", "-", "not applicable", ""):
			to_raw = ""
		else:
			to_raw = _match_in(companies, to_raw) or to_raw
		from_raw = str(cell(row, "from")).strip()
		from_raw = _match_in(companies, from_raw) or from_raw
		fy_raw = str(cell(row, "fy")).strip()
		fy_raw = _match_in(fiscal_years, fy_raw) or fy_raw
		month_raw = str(cell(row, "month")).strip()
		month_raw = _match_in(MONTHS, month_raw) or month_raw

		t = {
			"from_company": from_raw, "to_company": to_raw, "primary_group": pg, "secondary_group": sg,
			"fiscal_year": fy_raw, "month": month_raw, "debit": dr, "credit": cr,
			"adj_type": "Regrouping" if ty_raw.startswith("reg") else "Elimination",
			"narration": str(cell(row, "narration")).strip(), "reference": str(cell(row, "ref")).strip(),
		}
		e = _validate(t, companies, group_subs, fiscal_years)
		if e:
			errors.append(_("Row {0}: {1}").format(r + 1, e[0]))
		else:
			ok.append({
				"from": t["from_company"], "to": t["to_company"], "pg": t["primary_group"], "sg": t["secondary_group"],
				"fy": t["fiscal_year"], "month": t["month"], "debit": t["debit"], "credit": t["credit"], "type": t["adj_type"],
				"narration": t["narration"], "ref": t["reference"] or "Imported",
			})
	return {"ok": ok, "errors": errors, "skipped": skipped}


def _read_csv(content):
	import csv
	import io as _io

	text = content.decode("utf-8-sig") if isinstance(content, (bytes, bytearray)) else content
	return [row for row in csv.reader(_io.StringIO(text))]


# ------------------------------------------------------------------ export --
@frappe.whitelist()
def export_transactions():
	"""Transactions, Adjustment TB, IC Reconciliation and Company Matrix, as
	an .xlsx workbook (one sheet each)."""
	frappe.has_permission(DOCTYPE, "read", throw=True)
	masters = get_masters()
	statement_of = {g["name"]: g["st"] for g in masters["groups"]}
	txns = list_transactions()

	import openpyxl

	wb = openpyxl.Workbook()
	wb.remove(wb.active)

	tx_rows = [[
		"Transaction ID", "From Company", "To Company", "Fiscal Year", "Month", "Primary Group", "Secondary Group",
		"Statement", "Adjustment Type", "Debit", "Credit", "Net Impact", "Description / Narration", "Reference", "Created",
	]]
	for t in txns:
		tx_rows.append([
			t["no"], t["from"], t["to"] or "N/A", t["fy"], t["month"], t["pg"], t["sg"], statement_of.get(t["pg"], ""),
			t["type"], t["debit"], t["credit"], t["net"], t["narration"], t["ref"], t["createdAt"],
		])
	make_xlsx(tx_rows, "Transactions", wb=wb)

	tb = report_adjustment_tb()
	tb_rows = [["Statement", "Primary Group", "Secondary Group", "Adjustment Type", "Debit", "Credit", "Net"]]
	for r in tb:
		tb_rows.append([r["statement"], r["pg"], r["sg"], r["type"], r["debit"], r["credit"], r["net"]])
	make_xlsx(tb_rows, "Adjustment TB", wb=wb)

	recon = report_ic_reconciliation()
	recon_rows = [["Entity A", "Entity B", "A to B net", "B to A net", "Difference", "Status"]]
	for r in recon:
		recon_rows.append([r["a"], r["b"], r["ab"], r["ba"], r["diff"], "Matched" if abs(r["diff"]) < 1 else "Difference"])
	make_xlsx(recon_rows, "IC Reconciliation", wb=wb)

	matrix = report_company_matrix()
	froms = sorted({r["from"] for r in matrix})
	tos = sorted({r["to"] for r in matrix})
	cell = {(r["from"], r["to"]): r["net"] for r in matrix}
	matrix_rows = [["From \\ To", *tos]]
	for f in froms:
		matrix_rows.append([f, *[cell.get((f, c), 0) for c in tos]])
	make_xlsx(matrix_rows, "Company Matrix", wb=wb)

	buf = io.BytesIO()
	wb.save(buf)
	frappe.response["filename"] = f"Consolidation_Adjustments_{frappe.utils.nowdate()}.xlsx"
	frappe.response["filecontent"] = buf.getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def export_template():
	"""Downloadable import template: one example transaction row plus the
	current Company, Standalone Group and Month masters for reference."""
	frappe.has_permission(DOCTYPE, "read", throw=True)
	masters = get_masters()

	wb_rows = [
		["From Company", "To Company", "Fiscal Year", "Month", "Primary Group", "Secondary Group", "Debit", "Credit", "Adjustment Type", "Description / Narration", "Reference"],
	]
	if masters["companies"]:
		c0 = masters["companies"][0]
		c1 = masters["companies"][1] if len(masters["companies"]) > 1 else ""
		fy0 = masters["fiscal_years"][0] if masters["fiscal_years"] else ""
		month0 = masters["months"][0] if masters["months"] else ""
		pg0 = masters["groups"][0]["name"] if masters["groups"] else ""
		sg0 = masters["groups"][0]["subs"][0] if masters["groups"] and masters["groups"][0]["subs"] else ""
		wb_rows.append([c0, c1, fy0, month0, pg0, sg0, 0, 1000000, "Elimination", "Example: sales eliminated", "Elimination sheet"])

	import openpyxl

	wb = openpyxl.Workbook()
	wb.remove(wb.active)
	make_xlsx(wb_rows, "Transactions", wb=wb)

	group_rows = [["Primary Group", "Statement", "Secondary Group"]]
	for g in masters["groups"]:
		for s in g["subs"]:
			group_rows.append([g["name"], g["st"], s])
	make_xlsx(group_rows, "Group master", wb=wb)

	co_rows = [["Company"], *[[c] for c in masters["companies"]]]
	make_xlsx(co_rows, "Company master", wb=wb)

	month_rows = [["Month"], *[[m] for m in masters["months"]]]
	make_xlsx(month_rows, "Month master", wb=wb)

	buf = io.BytesIO()
	wb.save(buf)
	frappe.response["filename"] = "Consolidation_Import_Template.xlsx"
	frappe.response["filecontent"] = buf.getvalue()
	frappe.response["type"] = "binary"
