# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FRAccountPayableSettings(Document):
	def before_save(self):
		for i in self.special_gl_indicator_grouping:
			if not i.e_ne:
				i.currency = ""