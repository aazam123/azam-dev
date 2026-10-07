# Copyright (c) 2026, Hybrowlabs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FRStrategicExpenseEntry(Document):
	def validate(self):
		# One amount per company / primary group / secondary group / fiscal year / month.
		dup = frappe.db.exists(
			"FR Strategic Expense Entry",
			{
				"company": self.company,
				"primary_group": self.primary_group,
				"secondary_group": self.secondary_group,
				"fiscal_year": self.fiscal_year,
				"month": self.month,
				"name": ["!=", self.name],
			},
		)
		if dup:
			frappe.throw(
				f"A Strategic Expense entry already exists for {self.company} — "
				f"{self.primary_group} — {self.secondary_group} — {self.fiscal_year} {self.month} ({dup})."
			)
