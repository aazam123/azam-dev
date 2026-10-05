# Copyright (c) 2026, Hybrowlabs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ConsolAdjustmentEntry(Document):
	def before_insert(self):
		# Naming series must be set before set_new_name() runs, so the ELM-/RGP-
		# prefix follows the chosen Adjustment Type on create.
		self.naming_series = "RGP-.####" if self.adj_type == "Regrouping" else "ELM-.####"

	def validate(self):
		self.narration = (self.narration or "").strip()
		self.reference = (self.reference or "").strip()

		if self.to_company and self.to_company == self.from_company:
			frappe.throw(_("From Company and To Company cannot be the same entity."))

		debit, credit = flt(self.debit), flt(self.credit)
		if debit < 0 or credit < 0:
			frappe.throw(_("Debit and Credit must be positive amounts."))
		if debit > 0 and credit > 0:
			frappe.throw(_("Enter either a Debit or a Credit, not both."))
		if not debit and not credit:
			frappe.throw(_("Enter a Debit or a Credit amount."))

		if self.primary_group:
			if not frappe.db.get_value("Standalone Group", self.primary_group, "is_primary_group"):
				frappe.throw(_("{0} is not a Primary Group.").format(self.primary_group))
			if (
				self.secondary_group
				and self.secondary_group != self.primary_group
				and frappe.db.get_value("Standalone Group", self.secondary_group, "parent_standalone_group")
				!= self.primary_group
			):
				frappe.throw(
					_("{0} is not a secondary group under {1}.").format(self.secondary_group, self.primary_group)
				)

		self.net = debit - credit
