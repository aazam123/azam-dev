# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FRParticular(Document):
	def validate(self):
		"""Validate the document before saving"""
		self.validate_duplicate_primary_secondary_combinations()
	
	def validate_duplicate_primary_secondary_combinations(self):
		"""Validate that there are no duplicate combinations of primary and secondary groups"""
		if not self.primary_and_secondary_group_mapping:
			return
		
		combinations = []
		duplicates = []
		
		for row in self.primary_and_secondary_group_mapping:
			if not row.primary_group or not row.secondary_group:
				continue
			
			combination = (row.primary_group, row.secondary_group)
			
			if combination in combinations:
				duplicates.append(f"{row.primary_group} - {row.secondary_group}")
			else:
				combinations.append(combination)
		
		if duplicates:
			duplicate_list = ", ".join(duplicates)
			frappe.throw(
				f"Duplicate primary-secondary group combinations found: {duplicate_list}. "
				"Each combination of primary and secondary group should be unique."
			)
