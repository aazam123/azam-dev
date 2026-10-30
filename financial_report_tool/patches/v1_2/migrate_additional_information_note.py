import frappe

from financial_report_tool.financial_report_tool.additional_information_note import parse_note_html

DOCTYPE = "FR Additional Information Schedule III"
ROW_DOCTYPE = "FR Additional Information Row"


def execute():
	"""Bring every Note 60 master to header fields + table rows; each step skips what is already done."""
	split_note_content_into_fields()
	copy_amount_label_into_column_labels()
	for name in frappe.get_all(DOCTYPE, pluck="name"):
		doc = frappe.get_doc(DOCTYPE, name)
		doc.flags.ignore_permissions = True
		doc.save()  # refreshes the section_description of generated reports


def split_note_content_into_fields():
	"""The stored Note 60 HTML of a master without rows is split into header fields and table rows."""
	if not frappe.db.has_column(DOCTYPE, "note_content"):
		return
	for name, content in frappe.db.sql(f"select name, note_content from `tab{DOCTYPE}`"):
		parsed = parse_note_html(content)
		if not parsed or frappe.db.exists(ROW_DOCTYPE, {"parent": name, "parenttype": DOCTYPE}):
			continue
		doc = frappe.get_doc(DOCTYPE, name)
		for fieldname, value in parsed["texts"].items():
			doc.set(fieldname, value)
		for row in parsed["rows"]:
			doc.append("rows", row)
		doc.flags.ignore_permissions = True
		doc.save()


def copy_amount_label_into_column_labels():
	"""The old single `amount_label` is copied into the four per-column amount labels."""
	if not frappe.db.has_column(DOCTYPE, "amount_label"):
		return
	frappe.db.sql(
		f"""update `tab{DOCTYPE}`
		set net_assets_amount_label = amount_label, profit_amount_label = amount_label,
			oci_amount_label = amount_label, tci_amount_label = amount_label
		where ifnull(net_assets_amount_label, '') = '' and ifnull(amount_label, '') != ''"""
	)
