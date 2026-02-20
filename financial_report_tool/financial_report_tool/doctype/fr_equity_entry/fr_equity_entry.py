# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FREquityEntry(Document):
	def before_save(self):
		if self.currency and self.currency == "INR":
			self.exchange_rate = 1
		self.investment_inr = round((self.investment_value or 0) * (self.exchange_rate or 0), 4)
