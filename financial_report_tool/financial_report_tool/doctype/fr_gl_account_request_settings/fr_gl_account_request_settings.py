# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FRGLAccountRequestSettings(Document):
	def validate(self):
		seen = set()
		for row in self.company_assignments:
			if row.company in seen:
				frappe.throw(
					f"Company '{row.company}' is listed more than once in Company Assignments."
				)
			seen.add(row.company)

	def on_update(self):
		"""Whoever is assigned to a company is the Maker for its GL requests, so give
		them the FR GL Maker role (the Maker section is permission-gated by that role)."""
		for assignee in {row.assignee for row in self.company_assignments if row.assignee}:
			if assignee in ("Administrator", "Guest") or not frappe.db.exists("User", assignee):
				continue
			if frappe.db.exists("Has Role", {"parent": assignee, "parenttype": "User", "role": "FR GL Maker"}):
				continue
			user = frappe.get_doc("User", assignee)
			user.append("roles", {"role": "FR GL Maker"})
			user.flags.ignore_permissions = True
			user.save()


def get_company_assignee(company):
	"""Return (assignee, default_report_type, default_parent_account) for a company."""
	settings = frappe.get_single("FR GL Account Request Settings")
	for row in settings.company_assignments:
		if row.company == company:
			return row.assignee, row.default_report_type, row.default_parent_account
	return None, None, None
