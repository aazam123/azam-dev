# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FRRPTEntry(Document):
	pass


@frappe.whitelist()
def fetch_companies_for_table(company, table_type):
	if not company:
		frappe.throw("Please select a Company first.")

	hierarchy_name = frappe.db.exists("Company Hierarchy", {"company": company})
	if not hierarchy_name:
		frappe.throw(f"No Company Hierarchy entry found for {company}")

	results = []

	# First check if the reporting company's hierarchy node has pre-defined relations
	hierarchy_doc = frappe.get_doc("Company Hierarchy", hierarchy_name)
	if hierarchy_doc.company_hierarchy_relation:
		for row in hierarchy_doc.company_hierarchy_relation:
			results.append({"company": row.company, "relation": row.relation})
	else:
		frappe.throw("Fill the Company Hierarchy Relation at Company Hierarchy")

	return results
