# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.core.api.file import get_max_file_size
from frappe.model.document import Document
from frappe.utils import cint, now_datetime
from frappe.utils.file_manager import save_file

DELETE_FIELDS = ("is_deleted", "deleted_by", "deleted_on")
PRIVILEGED_ROLES = {"System Manager", "Financial Report Manager"}
PREPARE_ROLE = "Comment finance Prepare"      # avatar turns yellow
REVIEW1_ROLE = "Reviewer Level 1"             # avatar turns green
REVIEW2_ROLE = "Reviewer Level 2"             # avatar turns red


class FRFinancialReportComments(Document):
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
	doc = frappe.get_doc("FR Financial Report Comments", name)
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


MAX_FILES = 5                                  # attachments on one comment
FILE_FIELDS = ["name", "file_name", "file_url", "file_size", "attached_to_name"]


def _file_row(f) -> dict:
	return {"name": f.get("name"), "file_name": f.get("file_name"), "file_url": f.get("file_url"), "file_size": f.get("file_size") or 0}


def _uploaded_files() -> list:
	"""The files sent with this request as [(name, bytes)]; empty uploads are rejected."""
	request = getattr(frappe.local, "request", None)
	out = []
	for f in (request.files.getlist("files") if request is not None and getattr(request, "files", None) else []):
		if not f or not f.filename:
			continue
		content = f.stream.read()
		name = os.path.basename(f.filename.replace("\\", "/"))
		if not content:
			frappe.throw(_("{0} is empty").format(name))
		out.append((name, content))
	return out


@frappe.whitelist(methods=["POST"])
def add_comment(report: str, note_no: str = "", section_type: str = "", row_index=0, row_label: str = "", comment: str = ""):
	"""Save a comment on one row of a report, with up to MAX_FILES attachments, in one request (all or nothing).

	The author is always the logged-in user. Files are attached to the comment as private files, so they can be opened only by
	users who may read that comment. Files are read from the request's multipart field "files".
	"""
	comment = (comment or "").strip()
	files = _uploaded_files()
	if not comment and not files:
		frappe.throw(_("Write a comment or attach a file"))
	if len(files) > MAX_FILES:
		frappe.throw(_("You can attach up to {0} files to one comment").format(MAX_FILES))
	limit = get_max_file_size()
	for name, content in files:
		if len(content) > limit:
			frappe.throw(_("{0} is larger than the allowed {1} MB").format(name, round(limit / 1048576, 1)))

	frappe.get_doc("FR Financial Report", report).check_permission("read")
	doc = frappe.get_doc(
		{
			"doctype": "FR Financial Report Comments",
			"financial_report": report,
			"comment_added_by": frappe.session.user,
			"note_no": note_no or "",
			"section_type": section_type or "",
			"row_index": cint(row_index),
			"row_label": (row_label or "")[:140],
			"comment": comment,
		}
	).insert()
	try:
		saved = [save_file(name, content, "FR Financial Report Comments", doc.name, is_private=1) for name, content in files]
	except frappe.ValidationError:
		raise
	except Exception:
		# a file Frappe cannot store (for example a damaged PDF): say which one, and nothing is saved (the request rolls back)
		frappe.log_error(title="Financial Report comment attachment failed")
		frappe.throw(_("One of the files could not be saved. Check that {0} are not damaged and try again.").format(", ".join(n for n, _c in files)))
	return {"name": doc.name, "creation": str(doc.creation), "files": [_file_row(f) for f in saved]}


@frappe.whitelist()
def get_thread(report: str, note_no: str = "", section_type: str = "", row_index=0):
	"""All comments of one row (deleted ones too, they show as notes), oldest first, each with its attached files."""
	rows = frappe.get_list(
		"FR Financial Report Comments",
		filters={"financial_report": report, "note_no": note_no or "", "row_index": cint(row_index), "section_type": section_type or ""},
		fields=["name", "comment", "comment_added_by", "creation", "is_deleted", "deleted_by", "deleted_on"],
		order_by="creation asc",
		limit_page_length=0,
	)
	by_comment = {}
	if rows:
		for f in frappe.get_all(
			"File",
			filters={"attached_to_doctype": "FR Financial Report Comments", "attached_to_name": ["in", [r.name for r in rows]], "is_folder": 0},
			fields=FILE_FIELDS,
			order_by="creation asc",
		):
			by_comment.setdefault(f.attached_to_name, []).append(_file_row(f))
	for r in rows:
		r["files"] = [] if r.is_deleted else by_comment.get(r.name, [])
	return rows
