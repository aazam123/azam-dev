# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FRGLGroupMapping(Document):
	def before_insert(self):
		exists = frappe.db.exists("FR GL Group Mapping", {
			"company": self.company,
			"gl_account": self.gl_account,
			"report_type": self.report_type
		})
		if exists:
			frappe.throw(f"GL Group Mapping for GL Account '{self.gl_account}' in Company '{self.company}' for {self.report_type} already exists.")