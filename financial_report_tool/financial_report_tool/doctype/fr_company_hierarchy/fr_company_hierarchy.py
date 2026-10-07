# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe.utils.nestedset import NestedSet


class FRCompanyHierarchy(NestedSet):
	RELATION_SORT_ORDER = {
		"Ultimate Holding Company": 0,
		"Holding Company": 1,
		"Subsidiary Company": 2,
		"Fellow Subsidiary of Holding Company": 3,
		"Fellow Subsidiary": 4,
		"Subsidiary of Fellow Subsidiary": 5,
	}

	@frappe.whitelist()
	def fetch_all_companies(self):
		"""Classify all companies relative to this node and populate company_hierarchy_relation."""
		all_nodes = frappe.get_all(
			"FR Company Hierarchy",
			fields=["name", "company", "parent_company", "parent_company_tree"],
			order_by="creation asc"
		)

		node_map = {n.name: n for n in all_nodes}

		# Build children map from parent_company (the field that actually has data)
		children_map = defaultdict(list)
		for n in all_nodes:
			parent = n.parent_company_tree or n.parent_company
			if parent:
				children_map[parent].append(n.name)

		# Get all ancestors (walk up via parent_company)
		def get_ancestors(name):
			ancestors = []
			current = name
			while current:
				node = node_map.get(current)
				if not node:
					break
				parent = node.parent_company_tree or node.parent_company
				if parent and parent in node_map:
					ancestors.append(parent)
					current = parent
				else:
					break
			return ancestors

		# Get all descendants (walk down via children_map)
		def get_descendants(name):
			descendants = []
			stack = list(children_map.get(name, []))
			while stack:
				child = stack.pop()
				descendants.append(child)
				stack.extend(children_map.get(child, []))
			return descendants

		my_name = self.name
		direct_parent = self.parent_company_tree or self.parent_company

		# 1. Ancestors: walk up the parent chain
		ancestor_list = get_ancestors(my_name)
		ancestor_set = set(ancestor_list)

		# 2. Descendants: all children recursively
		descendant_set = set(get_descendants(my_name))

		# 3. Fellow subsidiaries: other children of my direct parent
		fellow_sub_set = set()
		if direct_parent:
			for child in children_map.get(direct_parent, []):
				if child != my_name:
					fellow_sub_set.add(child)

		subsidiary_of_fellow_set = set()
		for fellow in fellow_sub_set:
			subsidiary_of_fellow_set.update(get_descendants(fellow))

		# 4. Fellow Subsidiary of Holding Company: children of any ancestor
		#    (excluding self, our ancestors, our descendants, and our fellow subsidiaries)
		holding_children_set = set()
		for a_name in ancestor_set:
			for desc in get_descendants(a_name):
				holding_children_set.add(desc)
		# Remove self, ancestors, descendants, and fellow subsidiaries
		holding_children_set -= ancestor_set
		holding_children_set -= descendant_set
		holding_children_set -= fellow_sub_set
		holding_children_set -= subsidiary_of_fellow_set
		holding_children_set.discard(my_name)

		results = []
		for n in all_nodes:
			if n.name == my_name:
				continue

			if n.name in ancestor_set:
				if n.name == direct_parent:
					relation = "Holding Company"
				else:
					relation = "Ultimate Holding Company"
			elif n.name in descendant_set:
				relation = "Subsidiary Company"
			elif n.name in fellow_sub_set:
				relation = "Fellow Subsidiary"
			elif n.name in subsidiary_of_fellow_set:
				relation = "Subsidiary of Fellow Subsidiary"
			elif n.name in holding_children_set:
				relation = "Fellow Subsidiary of Holding Company"
			else:
				relation = "Fellow Subsidiary"

			results.append({"company": n.company, "relation": relation})

		# Sort: first by relation sequence, then by Company creation date within each group
		company_names = [r["company"] for r in results]
		creation_map = {}
		if company_names:
			creation_data = frappe.get_all(
				"Company",
				filters={"name": ["in", company_names]},
				fields=["name", "creation"]
			)
			creation_map = {c.name: c.creation for c in creation_data}

		results.sort(key=lambda x: (
			self.RELATION_SORT_ORDER.get(x["relation"], 99),
			creation_map.get(x["company"], frappe.utils.now_datetime())
		))

		# Populate child table
		self.company_hierarchy_relation = []
		for r in results:
			self.append("company_hierarchy_relation", {
				"company": r["company"],
				"relation": r["relation"]
			})


	def before_save(self):
		if not self.company_hierarchy_relation:
			return

		# Bulk-fetch all company names in one query
		company_names = [
			i.company for i in self.company_hierarchy_relation
			if i.relation != "Key Managerial Personnel" and i.company
		]

		existing_companies = set()
		if company_names:
			existing_companies = set(
				frappe.get_all("Company", filters={"name": ["in", company_names]}, pluck="name")
			)

		invalid = []
		for i in self.company_hierarchy_relation:
			if i.relation == "Key Managerial Personnel" or not i.company:
				continue
			if i.company not in existing_companies:
				invalid.append(f"Row {i.idx}: {i.company}")

		if invalid:
			frappe.throw(
				f"The following companies do not exist in the Company master:<br>{'<br>'.join(invalid)}",
				title="Invalid Companies"
			)