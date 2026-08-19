# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class GLAccountRequestSettings(Document):
	def validate(self):
		seen = set()
		for row in self.company_assignments:
			if row.company in seen:
				frappe.throw(
					f"Company '{row.company}' is listed more than once in Company Assignments."
				)
			seen.add(row.company)


def get_company_assignee(company):
	"""Return (assignee, default_report_type, default_parent_account) for a company."""
	settings = frappe.get_single("GL Account Request Settings")
	for row in settings.company_assignments:
		if row.company == company:
			return row.assignee, row.default_report_type, row.default_parent_account
	return None, None, None
