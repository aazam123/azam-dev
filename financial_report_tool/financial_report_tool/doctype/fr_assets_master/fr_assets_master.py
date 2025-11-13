# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_years, getdate

class FRAssetsMaster(Document):
	def before_save(self):
		if self.capitalisation_date and self.life_years:
			self.end_date = add_years(self.capitalisation_date, self.life_years)
			self.life_days = (getdate(self.end_date) - getdate(self.capitalisation_date)).days