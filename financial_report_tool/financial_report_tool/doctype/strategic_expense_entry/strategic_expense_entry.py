# Copyright (c) 2026, Hybrowlabs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StrategicExpenseEntry(Document):
	def validate(self):
		# One amount per company / fiscal year / month.
		dup = frappe.db.exists(
			"Strategic Expense Entry",
			{
				"company": self.company,
				"fiscal_year": self.fiscal_year,
				"month": self.month,
				"name": ["!=", self.name],
			},
		)
		if dup:
			frappe.throw(
				f"A Strategic Expense entry already exists for {self.company} — "
				f"{self.fiscal_year} {self.month} ({dup})."
			)
