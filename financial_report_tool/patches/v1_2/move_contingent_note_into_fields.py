import re

import frappe
from frappe.utils import flt

from financial_report_tool.financial_report_tool.contingent_note import ROWS

DOCTYPE = "FR Contingent Liabilities"
CHILD = "FR Contingent Liability Row"
OLD_COLUMNS = (
	"cl_combined_layout",
	"cl_combined_particulars",
	"cl_label_a",
	"cl_label_b",
	"cl_label_d",
	"company_imported_label",
	"bank_guarantees",
	"disputed_custom_duty_matters",
	"company_imported",
	"claim_against",
	"cl_note_head",
	"cl_note_i",
	"cl_note_ii",
	"cl_head_asat",
)


def child_lines(name):
	"""[(particulars, amount)] of a record whose lines were moved into the child table."""
	rows = frappe.db.sql(
		f"select particulars, current_amount, line_key from `tab{CHILD}` where parent=%s and parenttype=%s order by idx",
		(name, DOCTYPE),
		as_dict=True,
	)
	lines = [(row.particulars, row.current_amount) for row in rows if not row.line_key.startswith("note_")]
	return lines or [(row.particulars, row.current_amount) for row in rows]


def column_lines(name):
	"""[(particulars, amount)] of a record still holding the original flat fields."""
	old = frappe.db.get_value(DOCTYPE, name, list(OLD_COLUMNS[:10]), as_dict=True)
	if old.cl_combined_layout:
		parts = [part.strip() for part in re.split(r"\n\s*\n", old.cl_combined_particulars or "") if part.strip()]
		return [(text, 0) for text in parts]
	lines = [
		(old.cl_label_a or "a) Bank guarantees given to excise authorities and other institutions", old.bank_guarantees),
		(old.cl_label_b or "b) Disputed Custom duty matters", old.disputed_custom_duty_matters),
	]
	if old.company_imported_label or flt(old.company_imported):
		lines.append((f"c) {old.company_imported_label or ''}", old.company_imported))
	return lines


def execute():
	"""Note 50 keeps three rows (label, current, previous amount) as fields of the master; the child table and old columns go."""
	has_child = frappe.db.table_exists(CHILD)
	names = frappe.get_all(DOCTYPE, pluck="name")
	for name in names:
		if has_child and frappe.db.sql(f"select 1 from `tab{CHILD}` where parent=%s limit 1", name):
			lines = child_lines(name)
		elif frappe.db.has_column(DOCTYPE, "bank_guarantees"):
			lines = column_lines(name)
		else:
			continue
		values = {}
		for (suffix, _), (text, amount) in zip(ROWS, lines):
			values[f"cl_{suffix}_label"] = text
			values[f"cl_{suffix}_current"] = flt(amount)
		frappe.db.set_value(DOCTYPE, name, values, update_modified=False)
	# every master has its rows now, so a save can also fill the previous-year amounts from the earlier master
	for name in names:
		doc = frappe.get_doc(DOCTYPE, name)
		doc.flags.ignore_permissions = True
		doc.save()
	if has_child:
		frappe.delete_doc("DocType", CHILD, force=True, ignore_missing=True)
		frappe.db.sql_ddl(f"drop table if exists `tab{CHILD}`")
	for column in OLD_COLUMNS:
		if frappe.db.has_column(DOCTYPE, column):
			frappe.db.sql_ddl(f"alter table `tab{DOCTYPE}` drop column `{column}`")
