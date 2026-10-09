# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

"""Whole-report review sign-off.

One record per (Financial Report, role) means "the user who holds that role has reviewed this report". The record is
named "<report>-<role>", so the same role can never review the same report twice. Taking the review back deletes the record.
Page users have no direct permission on this doctype: they go through get_review_state / set_review, which check the role.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

from financial_report_tool.financial_report_tool.doctype.financial_report_comments.financial_report_comments import (
	PREPARE_ROLE,
	REVIEW1_ROLE,
	REVIEW2_ROLE,
)

DOCTYPE = "Financial Report Review"
REVIEW_ROLES = (("prepare", PREPARE_ROLE), ("review1", REVIEW1_ROLE), ("review2", REVIEW2_ROLE))


class FinancialReportReview(Document):
	def before_insert(self):
		# who and when always come from the server, never from the client
		self.reviewed_by = frappe.session.user
		self.reviewed_on = now_datetime()

	def validate(self):
		if self.review_role not in {role for _key, role in REVIEW_ROLES}:
			frappe.throw(_("{0} is not a review role").format(self.review_role))


def _holders(role: str) -> list[str]:
	users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	if not users:
		return []
	return sorted(frappe.get_all("User", filters={"name": ["in", users], "enabled": 1}, pluck="name"))


def _state(report: str) -> dict:
	done = {
		r.review_role: r
		for r in frappe.get_all(
			DOCTYPE, filters={"financial_report": report}, fields=["review_role", "reviewed_by", "reviewed_on"]
		)
	}
	me = frappe.session.user
	cards = []
	for key, role in REVIEW_ROLES:
		holders = _holders(role)
		row = done.get(role)
		cards.append(
			{
				"key": key,
				"holders": holders,
				"can": me in holders,
				"reviewed_by": row.reviewed_by if row else None,
				"reviewed_on": row.reviewed_on if row else None,
			}
		)
	return {"report": report, "cards": cards}


@frappe.whitelist()
def get_review_state(report: str):
	"""Review cards of a report: for each role the users who hold it, whether the caller may act, and who reviewed when."""
	frappe.get_doc("Financial Report", report).check_permission("read")
	return _state(report)


@frappe.whitelist(methods=["POST"])
def set_review(report: str, key: str, reviewed=1):
	"""Mark the report as reviewed (reviewed=1) or take the review back (reviewed=0) for one role.

	Only a user who holds that role can change that role's card.
	"""
	role = dict(REVIEW_ROLES).get(key)
	if not role:
		frappe.throw(_("Unknown review"))
	frappe.get_doc("Financial Report", report).check_permission("read")

	user = frappe.session.user
	if user not in _holders(role):
		frappe.throw(_("Only the user assigned to this review can change it"), frappe.PermissionError)

	name = f"{report}-{role}"
	if cint(reviewed):
		if not frappe.db.exists(DOCTYPE, name):
			try:
				frappe.get_doc({"doctype": DOCTYPE, "financial_report": report, "review_role": role}).insert(
					ignore_permissions=True
				)
			except frappe.DuplicateEntryError:
				pass  # a second click / second tab got there first: it is reviewed either way
	elif frappe.db.exists(DOCTYPE, name):
		frappe.delete_doc(DOCTYPE, name, ignore_permissions=True, force=True)
	return _state(report)
