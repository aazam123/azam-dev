# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.utils.nestedset import NestedSet


class StandaloneGroup(NestedSet):
	pass
	# def autoname(self):
	# 	name = ""
	# 	if self.standalone_group_number:
	# 		name = f"{self.standalone_group_number} - "

	# 	name += f"{self.standalone_group_name}"
	# 	self.name = name