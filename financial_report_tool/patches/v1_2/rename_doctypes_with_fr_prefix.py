import re

import frappe

# Every DocType of this app now starts with "FR ". Old name -> new name.
RENAMES = {
	"Balance Sheet Template": "FR Balance Sheet Template",
	"Balance Sheet Template Details": "FR Balance Sheet Template Details",
	"Cash Flow Template": "FR Cash Flow Template",
	"Cash Flow Template Details": "FR Cash Flow Template Details",
	"Company Hierarchy": "FR Company Hierarchy",
	"Company Hierarchy Relation": "FR Company Hierarchy Relation",
	"Consol Adjustment Entry": "FR Console Adjustment Entry",
	"Equity Template": "FR Equity Template",
	"Financial Report": "FR Financial Report",
	"Financial Report Comments": "FR Financial Report Comments",
	"Financial Report Details": "FR Financial Report Details",
	"Financial Report Template": "FR Financial Report Template",
	"Financial Report Template Details": "FR Financial Report Template Details",
	"Financial Report Version Control": "FR Financial Report Version Control",
	"Financial Report Version Control Details": "FR Financial Report Version Control Details",
	"GL Account Company Assignee": "FR GL Account Company Assignee",
	"GL Account Creation Request": "FR GL Account Creation Request",
	"GL Account For Grouping": "FR GL Account For Grouping",
	"GL Account Request Settings": "FR GL Account Request Settings",
	"GL Group Mapping": "FR GL Group Mapping",
	"Other Equity Opening Entry": "FR Other Equity Opening Entry",
	"Profit And Loss Template": "FR Profit And Loss Template",
	"Profit And Loss Template Details": "FR Profit And Loss Template Details",
	"Purchase Order Series For Grouping": "FR Purchase Order Series For Grouping",
	"SAP Company Mapping": "FR SAP Company Mapping",
	"Schedule Reorder": "FR Schedule Reorder",
	"Schedule Reorder Details": "FR Schedule Reorder Details",
	"Special GL Indicator Grouping": "FR Special GL Indicator Grouping",
	"Standalone Group": "FR Standalone Group",
	"Strategic Expense Entry": "FR Strategic Expense Entry",
	"Sync SAP": "FR Sync SAP",
	"Sync SAP Missing Account": "FR Sync SAP Missing Account",
	"Sync SAP Trial Balance": "FR Sync SAP Trial Balance",
	"Sync SAP Trial Balance Details": "FR Sync SAP Trial Balance Details",
	"Trade Payables Turnover Ratio Grouping": "FR Trade Payables Turnover Ratio Grouping",
	"Vendor Series For Nature": "FR Vendor Series For Nature",
}

# Quoted occurrences of a DocType name inside stored Client / Server Scripts.
_QUOTED = re.compile(
	r"([\"'])(" + "|".join(re.escape(o) for o in sorted(RENAMES, key=len, reverse=True)) + r")\1"
)


def execute():
	"""Rename the DocTypes in place so records, permissions, links, versions and
	attachments follow them; nothing is deleted. Runs before model sync, which
	then loads the renamed JSON from the renamed folders."""
	_rename_doctypes()
	_fix_template_doctype_names()
	_fix_list_view_state()
	_fix_plain_text_references()
	_fix_stored_scripts()
	frappe.clear_cache()


def _rename_doctypes():
	# With developer_mode on, frappe re-saves (and re-exports) every DocType that
	# links to the one being renamed; their controller folders are already moved,
	# so that would fail or write stray files. The SQL updates are all that is needed.
	dev_mode = frappe.conf.get("developer_mode")
	frappe.conf.developer_mode = 0
	try:
		for old, new in RENAMES.items():
			old_exists, new_exists = frappe.db.exists("DocType", old), frappe.db.exists("DocType", new)
			if old_exists and new_exists:
				frappe.throw(f"Cannot rename DocType {old} to {new}: both already exist.")
			if old_exists:
				frappe.rename_doc("DocType", old, new, force=True, show_alert=False, rebuild_search=False)
				frappe.db.commit()
	finally:
		frappe.conf.developer_mode = dev_mode


def _fix_template_doctype_names():
	"""`doctype_name` holds the DocType of the template picked on each row
	(Dynamic Link target); it is plain text, so frappe's rename does not touch it."""
	templates = [
		"Profit And Loss Template", "Balance Sheet Template", "Cash Flow Template", "Equity Template",
	]
	for table in ("FR Financial Report Details", "FR Financial Report Template Details"):
		if not frappe.db.table_exists(table):
			continue
		for old in templates:
			frappe.db.sql(f"update `tab{table}` set doctype_name=%s where doctype_name=%s", (RENAMES[old], old))


def _fix_plain_text_references():
	"""Columns that hold a DocType name as plain Data (not a Link), so frappe's
	rename leaves them behind."""
	for table, column in (("Notification Log", "document_type"), ("Email Queue", "reference_doctype")):
		if not frappe.db.table_exists(table) or not frappe.db.has_column(table, column):
			continue
		for old, new in RENAMES.items():
			frappe.db.sql(f"update `tab{table}` set `{column}`=%s where `{column}`=%s", (new, old))


def _fix_list_view_state():
	for old, new in RENAMES.items():
		if frappe.db.exists("List View Settings", old) and not frappe.db.exists("List View Settings", new):
			frappe.db.sql("update `tabList View Settings` set name=%s where name=%s", (new, old))
		frappe.db.sql("update ignore `__UserSettings` set doctype=%s where doctype=%s", (new, old))


def _fix_stored_scripts():
	for doctype in ("Client Script", "Server Script"):
		for row in frappe.get_all(doctype, fields=["name", "script"]):
			script = row.script or ""
			updated = _QUOTED.sub(lambda m: m.group(1) + RENAMES[m.group(2)] + m.group(1), script)
			if updated != script:
				frappe.db.set_value(doctype, row.name, "script", updated, update_modified=False)
