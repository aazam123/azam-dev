# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.utils.nestedset import NestedSet


class ConsolidationGroup(NestedSet):
	def autoname(self):
		name = ""
		if self.consolidation_group_number:
			name = f"{self.consolidation_group_number} - "

		name += f"{self.consolidation_group_name}"
		self.name = name
