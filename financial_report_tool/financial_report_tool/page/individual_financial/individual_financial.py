# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

"""Excel export of one Financial Report for the "individual-financial" page.

The page sends what is on screen (every section's tables and text, including the FTM / Previous FTM columns it adds), because those
extra columns exist only in the browser. The server adds what must come from the database and be permission-checked: the report's
details, the review state, and every comment with its files. Everything is written to one .xlsx.
"""

import io
import json
import re

import frappe
import pytz
from frappe import _
from frappe.utils import cint, format_datetime, get_datetime, now_datetime
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from financial_report_tool.financial_report_tool.doctype.fr_financial_report_review.fr_financial_report_review import (
	REVIEW_ROLES,
	_state,
)

MAX_SECTIONS = 300
MAX_CELL = 32000                                   # Excel allows 32767 characters in a cell
INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
NUMBER = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
FORMULA_START = ("=", "+", "-", "@")

BRAND = "2F5D50"
HEAD_FILL = PatternFill("solid", fgColor=BRAND)
GROUP_FILL = PatternFill("solid", fgColor="E7EFEA")
TOTAL_FILL = PatternFill("solid", fgColor="F3F6F4")
THIN = Side(style="thin", color="B8C4BE")


def _text(value) -> str:
	return ILLEGAL_CHARACTERS_RE.sub("", str(value if value is not None else "")).replace("\u00a0", " ").strip()[:MAX_CELL]


def _number(text: str):
	"""A figure as a float ("1,234.5", "(12)", "-12") or None when the text is not a plain number."""
	t = text.replace(",", "").strip()
	neg = t.startswith("(") and t.endswith(")")
	if neg:
		t = t[1:-1].strip()
	if not NUMBER.match(t):
		return None, 0
	decimals = len(t.split(".")[1]) if "." in t else 0
	return (-float(t) if neg else float(t)), decimals


def _put(cell, text: str):
	"""Write a cell: numbers stay numbers (so Excel can add them up), everything else is literal text (never a formula)."""
	value, decimals = _number(text)
	if value is not None:
		cell.value = value
		cell.number_format = "#,##0" + ("." + "0" * decimals if decimals else "")
		cell.alignment = Alignment(horizontal="right", vertical="top")
		return
	cell.value = text
	if text.startswith(FORMULA_START):
		cell.data_type = "s"
	cell.alignment = Alignment(vertical="top", wrap_text=len(text) > 60)


def _user_zone():
	user_tz = frappe.db.get_value("User", frappe.session.user, "time_zone")
	return pytz.timezone(user_tz or frappe.utils.get_system_timezone())


def _when(value) -> str:
	"""A stored time (system time zone) written in the user's time zone and the System Settings date / time format."""
	if not value:
		return ""
	system = pytz.timezone(frappe.utils.get_system_timezone())
	stamp = system.localize(get_datetime(value)) if get_datetime(value).tzinfo is None else get_datetime(value)
	local = stamp.astimezone(_user_zone()).replace(tzinfo=None)
	date_fmt = (frappe.get_system_settings("date_format") or "yyyy-mm-dd").replace("mm", "MM")
	time_fmt = (frappe.get_system_settings("time_format") or "HH:mm:ss").replace(":ss", "")
	return format_datetime(local, f"{date_fmt} {time_fmt}")


def _sheet_name(used: set, wanted: str) -> str:
	base = INVALID_SHEET_CHARS.sub(" ", _text(wanted) or "Sheet").strip("' ")[:31] or "Sheet"
	name, n = base, 2
	while name.lower() in used:
		suffix = f" ({n})"
		name, n = base[: 31 - len(suffix)] + suffix, n + 1
	used.add(name.lower())
	return name


def _title(ws, row: int, text: str, size=13):
	ws.cell(row=row, column=1, value=text).font = Font(bold=True, size=size, color=BRAND)


def _write_table(ws, top: int, rows: list, widths: dict) -> int:
	"""Write one table starting at row `top`; returns the next free row. Merged cells (colspan / rowspan) are kept."""
	taken = set()                                   # (row, col) already covered by a merged cell
	r = top
	for row in rows:
		col = 1
		kind = row.get("kind") or ""
		for cell in row.get("cells") or []:
			while (r, col) in taken:
				col += 1
			text = _text(cell.get("t"))
			cs, rs = max(1, cint(cell.get("cs"))), max(1, cint(cell.get("rs")))
			c = ws.cell(row=r, column=col)
			_put(c, text)
			if kind == "head" or cell.get("th"):
				c.font = Font(bold=True, color="FFFFFF")
				c.fill = HEAD_FILL
				c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
			elif kind in ("group", "result"):
				c.font = Font(bold=True)
				c.fill = GROUP_FILL
			elif kind == "total":
				c.font = Font(bold=True)
				c.fill = TOTAL_FILL
				c.border = Border(top=THIN)
			if cs > 1 or rs > 1:
				ws.merge_cells(start_row=r, start_column=col, end_row=r + rs - 1, end_column=col + cs - 1)
				for dr in range(rs):
					for dc in range(cs):
						taken.add((r + dr, col + dc))
			elif text:
				widths[col] = max(widths.get(col, 0), len(text))
			col += cs
		r += 1
	return r


def _write_section(wb, used: set, index: dict, sec: dict):
	title = _text(sec.get("title")) or _text(sec.get("kicker")) or "Section"
	label = f"Note {_text(sec.get('note'))} {title}" if _text(sec.get("note")) else title
	ws = wb.create_sheet(_sheet_name(used, label))
	index.append((ws.title, _text(sec.get("kicker")), title))

	_title(ws, 1, title)
	ws.cell(row=2, column=1, value=_text(sec.get("kicker"))).font = Font(italic=True, color="66756F")
	r, widths, tables, first_head = 4, {}, 0, None
	for block in sec.get("blocks") or []:
		if block.get("type") == "text":
			text = _text(block.get("text"))
			if text:
				c = ws.cell(row=r, column=1, value=text)
				c.alignment = Alignment(vertical="top", wrap_text=False)
				r += 1
		elif block.get("type") == "table":
			rows = [x for x in (block.get("rows") or []) if x.get("cells")]
			if not rows:
				continue
			if first_head is None:
				first_head = r + sum(1 for x in rows if x.get("kind") == "head")
			r = _write_table(ws, r, rows, widths) + 1
			tables += 1
	for col, longest in widths.items():
		ws.column_dimensions[get_column_letter(col)].width = min(max(longest + 2, 11), 60)
	if tables == 1 and first_head:
		ws.freeze_panes = ws.cell(row=first_head, column=2)


def _write_summary(wb, doc, period: str, sheets: list, comments: list, review: dict):
	ws = wb.active
	ws.title = "Summary"
	_title(ws, 1, "Financial Report", 15)
	facts = [
		("Report", doc.name),
		("Company", doc.company),
		("Period", period or doc.current_month),
		("Fiscal Year", doc.fiscal_year),
		("Report Type", doc.report_type),
		("Currency", doc.currency),
		("Status", doc.workflow_state),
		("Approved By", doc.approved_by),
		("Approved On", _when(doc.approved_on)),
		("Comments (not deleted)", sum(1 for c in comments if not c["is_deleted"])),
		("Exported By", frappe.utils.get_fullname(frappe.session.user)),
		("Exported On", _when(now_datetime())),
	]
	r = 3
	for key, value in facts:
		ws.cell(row=r, column=1, value=key).font = Font(bold=True)
		c = ws.cell(row=r, column=2)
		_put(c, _text(value))
		c.alignment = Alignment(horizontal="left", vertical="top")
		r += 1

	r += 1
	_title(ws, r, "Review", 12)
	r += 1
	for col, head in enumerate(("Reviewer", "Reviewed", "Reviewed On"), 1):
		h = ws.cell(row=r, column=col, value=head)
		h.font, h.fill = Font(bold=True, color="FFFFFF"), HEAD_FILL
	for card in review["cards"]:
		r += 1
		who = card["reviewed_by"] or ", ".join(card["holders"]) or "Nobody assigned"
		ws.cell(row=r, column=1, value=", ".join(frappe.utils.get_fullname(u) for u in who.split(", ")) if card["holders"] or card["reviewed_by"] else who)
		ws.cell(row=r, column=2, value="Yes" if card["reviewed_by"] else "No")
		ws.cell(row=r, column=3, value=_when(card["reviewed_on"]))

	r += 2
	_title(ws, r, "Sheets", 12)
	for name, kicker, title in sheets:
		r += 1
		c = ws.cell(row=r, column=1, value=name)
		c.hyperlink = f"#'{name}'!A1"
		c.font = Font(color="0563C1", underline="single")
		ws.cell(row=r, column=2, value=kicker)
		ws.cell(row=r, column=3, value=title if title != name else "")
	ws.column_dimensions["A"].width = 34
	ws.column_dimensions["B"].width = 38
	ws.column_dimensions["C"].width = 40


def _comments(report: str) -> list:
	rows = frappe.get_list(
		"FR Financial Report Comments",
		filters={"financial_report": report},
		fields=["name", "section_type", "note_no", "row_label", "comment", "comment_added_by", "creation", "is_deleted", "deleted_by", "deleted_on"],
		order_by="section_type asc, note_no asc, row_index asc, creation asc",
		limit_page_length=0,
	)
	files = {}
	if rows:
		for f in frappe.get_all(
			"File",
			filters={"attached_to_doctype": "FR Financial Report Comments", "attached_to_name": ["in", [r.name for r in rows]], "is_folder": 0},
			fields=["attached_to_name", "file_name"],
			order_by="creation asc",
		):
			files.setdefault(f.attached_to_name, []).append(f.file_name)
	for r in rows:
		r["files"] = [] if r.is_deleted else files.get(r.name, [])
	return rows


def _write_comments(wb, used: set, comments: list):
	ws = wb.create_sheet(_sheet_name(used, "Comments"))
	_title(ws, 1, "Comments")
	heads = ("Section", "Note", "Row", "Comment", "By", "Date", "Attachments", "Status")
	for col, head in enumerate(heads, 1):
		h = ws.cell(row=3, column=col, value=head)
		h.font, h.fill = Font(bold=True, color="FFFFFF"), HEAD_FILL
		h.alignment = Alignment(horizontal="center", vertical="center")
	widths = {i: len(h) for i, h in enumerate(heads, 1)}
	for r, c in enumerate(comments, 4):
		deleted = bool(c.is_deleted)
		values = (
			c.section_type,
			c.note_no,
			_text(c.row_label),
			"" if deleted else _text(c.comment),                       # a deleted comment's text is never exported
			frappe.utils.get_fullname(c.comment_added_by),
			_when(c.creation),
			", ".join(c["files"]),
			f"Deleted by {frappe.utils.get_fullname(c.deleted_by)} on {_when(c.deleted_on)}" if deleted else "",
		)
		for col, value in enumerate(values, 1):
			cell = ws.cell(row=r, column=col)
			cell.value = _text(value)
			if cell.value.startswith(FORMULA_START):
				cell.data_type = "s"
			cell.alignment = Alignment(vertical="top", wrap_text=col in (3, 4, 7, 8))
			widths[col] = max(widths[col], min(len(cell.value), 70))
	for col, longest in widths.items():
		ws.column_dimensions[get_column_letter(col)].width = min(max(longest + 2, 10), 70)
	ws.freeze_panes = "A4"


@frappe.whitelist(methods=["POST"])
def export_report(report: str, sections: str = "[]", period: str = ""):
	"""Build the Excel file of one report and send it as a download.

	`sections` is the JSON the page collects from its own tables. Everything about who commented, who reviewed and what the report
	record says is read here, with the caller's permissions.
	"""
	doc = frappe.get_doc("FR Financial Report", report)
	doc.check_permission("read")
	doc.check_permission("export")

	try:
		data = json.loads(sections or "[]")
	except ValueError:
		frappe.throw(_("The report data could not be read"))
	if not isinstance(data, list) or len(data) > MAX_SECTIONS:
		frappe.throw(_("The report data is not valid"))

	comments = _comments(report)
	review = _state(report)

	wb = Workbook()
	used, index = {"summary"}, []
	for sec in data:
		if isinstance(sec, dict):
			_write_section(wb, used, index, sec)
	_write_comments(wb, used, comments)
	_write_summary(wb, doc, _text(period), index, comments, review)

	out = io.BytesIO()
	wb.save(out)
	name = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{report}_{_text(period)}").strip("_") or "financial_report"
	frappe.response["type"] = "binary"
	frappe.response["filecontent"] = out.getvalue()
	frappe.response["filename"] = f"{name}.xlsx"
