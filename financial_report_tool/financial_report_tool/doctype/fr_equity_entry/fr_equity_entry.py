# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class FREquityEntry(Document):
	def before_save(self):
		self.investment_value = round(self.exchanges_rate * self.investment_value_fc)