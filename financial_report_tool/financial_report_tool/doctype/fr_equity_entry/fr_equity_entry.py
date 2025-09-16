# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime
from frappe.model.document import Document

class FREquityEntry(Document):
	def before_save(self):
		if self.posting_date:
			if isinstance(self.posting_date, str):
				date_obj = datetime.strptime(self.posting_date, "%Y-%m-%d")
			else:
				date_obj = self.posting_date
			self.month = date_obj.strftime("%B")
		self.investment_value = round(self.exchanges_rate * self.investment_value_fc)