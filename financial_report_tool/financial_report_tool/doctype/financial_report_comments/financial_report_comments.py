# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

DELETE_FIELDS = ("is_deleted", "deleted_by", "deleted_on")
PRIVILEGED_ROLES = {"System Manager", "Financial Report Manager"}
PREPARE_ROLE = "Comment finance Prepare"      # avatar turns yellow
REVIEW1_ROLE = "Reviewer Level 1"             # avatar turns green
REVIEW2_ROLE = "Reviewer Level 2"             # avatar turns red


class FinancialReportComments(Document):
	def validate(self):
		# The deletion trail is written only by delete_comment(), so nobody can fake "deleted by".
		if self.flags.deleting_comment:
			return
		if self.is_new():
			if any(self.get(f) for f in DELETE_FIELDS):
				frappe.throw(_("A new comment cannot be created as deleted"))
		elif any(self.has_value_changed(f) for f in DELETE_FIELDS):
			frappe.throw(_("Use Delete on the comment to remove it. Deletion details cannot be edited."))


@frappe.whitelist(methods=["POST"])
def delete_comment(name: str):
	"""Soft-delete a comment: keep the row, record who deleted it and when.

	Allowed for the comment's author and for Financial Report Manager / System Manager.
	"""
	doc = frappe.get_doc("Financial Report Comments", name)
	doc.check_permission("write")

	user = frappe.session.user
	if doc.comment_added_by != user and not PRIVILEGED_ROLES.intersection(frappe.get_roles(user)):
		frappe.throw(_("You can delete only your own comments"), frappe.PermissionError)

	if doc.is_deleted:
		return {"is_deleted": 1, "deleted_by": doc.deleted_by, "deleted_on": str(doc.deleted_on)}

	doc.flags.deleting_comment = True
	doc.is_deleted = 1
	doc.deleted_by = user
	doc.deleted_on = now_datetime()
	doc.save()
	return {"is_deleted": 1, "deleted_by": doc.deleted_by, "deleted_on": str(doc.deleted_on)}


@frappe.whitelist()
def get_role_users():
	"""Which commenters get a role colour on the Financial Report page: {user: "prepare" | "review1" | "review2"}.

	Only user ids and the colour key are returned (no role names), so any logged-in user of the page can read it.
	If someone holds more than one of these roles, "prepare" is used first, then "review2", then "review1".
	"""
	out = {}
	for key, role in (("review1", REVIEW1_ROLE), ("review2", REVIEW2_ROLE), ("prepare", PREPARE_ROLE)):       # last one wins
		for user in frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"):
			out[user] = key
	return out
