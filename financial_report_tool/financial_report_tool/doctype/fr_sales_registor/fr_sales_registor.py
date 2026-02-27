# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FRSalesRegistor(Document):
	def validate(self):
		if self.ship_to_country == "IN":
			self.nature = "Domestic"
		else:
			self.nature = "Foreign"

		settings = frappe.db.exists("FR RPT Master", self.company)
		if not settings:
			frappe.throw("Please set the Related and Internal Customer List in FR RPT Master")

		settings = frappe.get_doc("FR RPT Master", self.company)
		related_customers = {row.customer_code for row in settings.related_customer_list}
		internal_customers = {row.customer_code for row in settings.internal_customer_list}

		if self.ship_to_party in related_customers:
			self.party_type = "Related Party"
		elif self.ship_to_party in internal_customers:
			self.party_type = "Branch Transfer"
		else:
			self.party_type = "Unrelated Party"
