# Copyright (c) 2026, Hybrowlabs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


def secondary_groups_by_primary(primaries=None):
	"""{primary_group: [secondary_group, ...]} allowed on an adjustment entry.

	A primary group's secondary groups are the union of:
	  * every descendant of it in the FR Standalone Group tree (children, grandchildren ...), and
	  * every secondary group mapped to it in FR GL Group Mapping (any company, any report type).
	Names are matched to FR Standalone Group case-insensitively and returned in that
	record's spelling (GL mappings sometimes differ only in case). A secondary already
	used by a saved entry for that primary stays valid so existing entries remain editable.
	The primary group itself is not listed here; callers add it.
	"""
	groups = frappe.get_all("FR Standalone Group", fields=["name", "parent_standalone_group", "is_primary_group"], limit_page_length=0)
	canon = {g.name.lower(): g.name for g in groups}
	children = {}
	for g in groups:
		if g.parent_standalone_group:
			children.setdefault(g.parent_standalone_group, []).append(g.name)
	allowed = {}

	def add(primary, secondary):
		if primary and secondary:
			allowed.setdefault(primary, set()).add(canon.get(secondary.lower(), secondary))

	for primary in [g.name for g in groups if g.is_primary_group] if primaries is None else primaries:
		seen, stack = {primary}, list(children.get(primary, []))
		while stack:
			node = stack.pop()
			if node in seen:
				continue
			seen.add(node)
			add(primary, node)
			stack.extend(children.get(node, []))

	filters = {"secondary_group": ["is", "set"]}
	if primaries is not None:
		filters["primary_group"] = ["in", list(primaries)] if primaries else ["in", [""]]
	for r in frappe.get_all("FR GL Group Mapping", filters=filters, fields=["primary_group", "secondary_group"], group_by="primary_group, secondary_group", limit_page_length=0):
		add(r.primary_group, r.secondary_group)
	for r in frappe.get_all("FR Console Adjustment Entry", filters={"secondary_group": ["is", "set"]}, fields=["primary_group", "secondary_group"], group_by="primary_group, secondary_group", limit_page_length=0):
		add(r.primary_group, r.secondary_group)
	return {p: sorted(s, key=str.lower) for p, s in allowed.items()}


class FRConsoleAdjustmentEntry(Document):
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
			if not frappe.db.get_value("FR Standalone Group", self.primary_group, "is_primary_group"):
				frappe.throw(_("{0} is not a Primary Group.").format(self.primary_group))
			if self.secondary_group and self.secondary_group != self.primary_group:
				allowed = secondary_groups_by_primary([self.primary_group]).get(self.primary_group, [])
				match = {s.lower(): s for s in allowed}.get(self.secondary_group.lower())
				if not match:
					frappe.throw(
						_("{0} is not a secondary group of {1} in GL Group Mapping.").format(
							self.secondary_group, self.primary_group
						)
					)
				self.secondary_group = match

		self.net = debit - credit
