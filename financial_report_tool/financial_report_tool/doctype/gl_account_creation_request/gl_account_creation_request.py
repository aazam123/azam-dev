# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_fullname, get_url_to_form

from financial_report_tool.financial_report_tool.doctype.gl_account_request_settings.gl_account_request_settings import (
	get_company_assignee,
)


class GLAccountCreationRequest(Document):
	def validate(self):
		if not self.requested_by:
			self.requested_by = frappe.session.user
		if not self.status:
			self.status = "Requested"
		# Route to the user responsible for this company (from Settings).
		if self.company and not self.assigned_to:
			assignee, def_report_type, def_parent = get_company_assignee(self.company)
			self.assigned_to = assignee
			if def_report_type and not self.report_type:
				self.report_type = def_report_type
			if def_parent and not self.parent_account:
				self.parent_account = def_parent

	def after_insert(self):
		self.notify_assignee()

	# ------------------------------------------------------------------ emails
	def notify_assignee(self):
		if not self.assigned_to:
			frappe.msgprint(
				_("No assignee is configured for {0}. Set one in GL Account Request Settings.").format(
					self.company
				),
				indicator="orange",
				alert=True,
			)
			return
		url = get_url_to_form(self.doctype, self.name)
		self._safe_sendmail(
			recipients=[self.assigned_to],
			subject=_("GL Account creation requested for {0} ({1})").format(self.company, self.name),
			message=_(
				"<p>{requester} has requested a new GL Account for <b>{company}</b>.</p>"
				"<table cellpadding='4'>"
				"<tr><td><b>Proposed account</b></td><td>{account}</td></tr>"
				"<tr><td><b>Account number</b></td><td>{number}</td></tr>"
				"<tr><td><b>Root type</b></td><td>{root}</td></tr>"
				"<tr><td><b>Reason</b></td><td>{reason}</td></tr>"
				"</table>"
				"<p>Please open the request, set the <b>Primary</b> and <b>Secondary</b> grouping, "
				"and click <b>Create Account &amp; Grouping</b>:</p>"
				"<p><a href='{url}'>{name}</a></p>"
			).format(
				requester=get_fullname(self.requested_by),
				company=self.company,
				account=frappe.utils.escape_html(self.account_name or "-"),
				number=frappe.utils.escape_html(self.account_number or "-"),
				root=self.root_type or "-",
				reason=frappe.utils.escape_html(self.reason or "-"),
				url=url,
				name=self.name,
			),
		)

	def notify_requester(self, created=True):
		if not self.requested_by:
			return
		if created and not frappe.db.get_single_value(
			"GL Account Request Settings", "notify_requester_on_completion"
		):
			return
		url = get_url_to_form(self.doctype, self.name)
		if created:
			subject = _("GL Account created for {0} ({1})").format(self.company, self.name)
			body = _(
				"<p>Your GL Account request <b>{name}</b> has been actioned.</p>"
				"<p><b>Account:</b> {account}<br><b>Grouping:</b> {primary} / {secondary}</p>"
				"<p><a href='{url}'>{name}</a></p>"
			).format(
				name=self.name,
				account=self.created_account,
				primary=self.primary_group or "-",
				secondary=self.secondary_group or "-",
				url=url,
			)
		else:
			subject = _("GL Account request rejected ({0})").format(self.name)
			body = _(
				"<p>Your GL Account request <b>{name}</b> was rejected.</p>"
				"<p><b>Reason:</b> {reason}</p>"
				"<p><a href='{url}'>{name}</a></p>"
			).format(name=self.name, reason=self.rejection_reason or "-", url=url)
		self._safe_sendmail(recipients=[self.requested_by], subject=subject, message=body)

	def _safe_sendmail(self, **kwargs):
		"""Send mail without letting a mail-config error block the workflow."""
		kwargs.setdefault("reference_doctype", self.doctype)
		kwargs.setdefault("reference_name", self.name)
		try:
			frappe.sendmail(**kwargs)
		except Exception:
			frappe.log_error(
				title="GL Account Creation Request: email failed",
				message=frappe.get_traceback(),
			)

	# --------------------------------------------------------------- actions
	@frappe.whitelist()
	def create_account_and_grouping(self):
		self._check_assignee()
		if self.status == "Account Created":
			frappe.throw(_("An account has already been created for this request."))
		if self.status == "Rejected":
			frappe.throw(_("This request was rejected and cannot be actioned."))
		if not (self.primary_group and self.secondary_group):
			frappe.throw(_("Set both Primary Group and Secondary Group before creating the account."))

		account = self._create_account()
		mapping = self._create_group_mapping(account.name)

		self.created_account = account.name
		self.gl_group_mapping = mapping.name
		self.status = "Account Created"
		self.save(ignore_permissions=True)
		self.notify_requester(created=True)
		frappe.msgprint(
			_("Account {0} created and mapped to {1} / {2}.").format(
				account.name, self.primary_group, self.secondary_group
			),
			indicator="green",
			alert=True,
		)
		return {"account": account.name, "gl_group_mapping": mapping.name}

	@frappe.whitelist()
	def reject(self, reason=None):
		self._check_assignee()
		if self.status == "Account Created":
			frappe.throw(_("This request already has an account and cannot be rejected."))
		self.status = "Rejected"
		if reason:
			self.rejection_reason = reason
		self.save(ignore_permissions=True)
		self.notify_requester(created=False)

	# ---------------------------------------------------------------- helpers
	def _check_assignee(self):
		user = frappe.session.user
		if user == "Administrator" or "System Manager" in frappe.get_roles(user):
			return
		if self.assigned_to and user == self.assigned_to:
			return
		frappe.throw(
			_("Only the assigned user ({0}) can action this request.").format(
				self.assigned_to or _("unassigned")
			),
			frappe.PermissionError,
		)

	def _create_account(self):
		if frappe.db.exists(
			"Account", {"account_name": self.account_name, "company": self.company}
		):
			frappe.throw(
				_("An Account named '{0}' already exists for {1}.").format(
					self.account_name, self.company
				)
			)
		account = frappe.new_doc("Account")
		account.account_name = self.account_name
		account.company = self.company
		account.is_group = self.is_group or 0
		if self.account_number:
			account.account_number = self.account_number
		if self.parent_account:
			account.parent_account = self.parent_account
		if self.root_type:
			account.root_type = self.root_type
		account.insert(ignore_permissions=True)
		return account

	def _create_group_mapping(self, account_name):
		mapping = frappe.new_doc("GL Group Mapping")
		mapping.company = self.company
		mapping.gl_account = account_name
		mapping.report_type = self.report_type or "Monthly"
		mapping.primary_group = self.primary_group
		mapping.secondary_group = self.secondary_group
		mapping.higher_secondary_group = self.higher_secondary_group
		mapping.insert(ignore_permissions=True)
		return mapping
