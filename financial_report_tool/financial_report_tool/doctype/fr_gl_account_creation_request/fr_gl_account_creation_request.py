# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_fullname, get_url_to_form

from financial_report_tool.financial_report_tool.doctype.fr_gl_account_request_settings.fr_gl_account_request_settings import (
	get_company_assignee,
)


MAKER_ROLE = "FR GL Maker"
REQUESTOR_ROLE = "FR GL Requestor"
MAKER_FIELDS = ("new_gl", "primary_group", "secondary_group", "pattern_account")
STATE_ACCOUNT_CREATED = "Account Created"
STATE_REJECTED = "Rejected"
STATE_OPEN = "Request For Creation"


def _is_maker(doc, user=None):
	"""True for the Maker assigned to this request, and for System Manager / Administrator."""
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True
	return bool(doc.assigned_to and user == doc.assigned_to)


class FRGLAccountCreationRequest(Document):
	def validate(self):
		if not self.requested_by:
			self.requested_by = frappe.session.user
		if not self.status:
			self.status = "Requested"
		self.set_receiver_from_company()
		self.guard_maker_fields()
		if self.workflow_state == STATE_ACCOUNT_CREATED and not self.created_account:
			self.check_ready_for_creation()
		elif self.workflow_state == STATE_REJECTED and self.status != "Rejected":
			self.mark_rejected()

	def mark_rejected(self):
		"""Reject action (Request For Creation -> Rejected): needs a reason, keeps the
		status field in step with the workflow state and notifies the requester."""
		self._check_assignee()
		if self.status == "Account Created" or self.created_account:
			frappe.throw(_("This request already has an account and cannot be rejected."))
		if not self.rejection_reason:
			frappe.throw(_("Enter a Rejection Reason before rejecting the request."))
		self.status = "Rejected"
		self.flags.notify_rejected = True

	def guard_maker_fields(self):
		"""Maker fields (New GL, Primary / Secondary Grouping) sit at permlevel 1, which
		only FR GL Maker (and System Manager) can write; Frappe strips them from anyone
		else's save. On top of that, an *existing* request's Maker fields may be changed
		only by the Maker assigned to its company (or an admin), so one Maker cannot
		edit another company's request. New documents are left to the permlevel check,
		which runs after validate and blanks any value a Requestor supplied."""
		if self.is_new() or self.flags.ignore_permissions:
			return
		if not any(self.has_value_changed(f) for f in MAKER_FIELDS):
			return
		if _is_maker(self):
			return
		frappe.throw(
			_("Only the Maker assigned to {0} ({1}) can set New GL and the Primary / Secondary Grouping.").format(
				self.company or "", self.assigned_to or _("unassigned")
			),
			frappe.PermissionError,
		)

	def set_receiver_from_company(self):
		"""Assign the request and its notification to the Receiver's Mail ID
		configured for this Company in GL Account Request Settings."""
		if not self.company:
			self.assigned_to = None
			self.receiver_email = None
			return
		assignee, def_report_type, def_parent = get_company_assignee(self.company)
		self.assigned_to = assignee
		self.receiver_email = frappe.db.get_value("User", assignee, "email") if assignee else None
		if def_report_type and not self.report_type:
			self.report_type = def_report_type
		if def_parent and not self.parent_account:
			self.parent_account = def_parent

	def after_insert(self):
		self.notify_assignee()

	# ------------------------------------------------------------------ emails
	def notify_assignee(self):
		if not self.receiver_email:
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
			recipients=[self.receiver_email],
			subject=_("GL Account creation requested for {0} ({1})").format(self.company, self.name),
			message=_(
				"<p>{requester} has requested a new GL Account for <b>{company}</b>.</p>"
				"<table cellpadding='4'>"
				"<tr><td><b>Proposed account</b></td><td>{account}</td></tr>"
				"<tr><td><b>Reference GL</b></td><td>{reference}</td></tr>"
				"</table>"
				"<p>Please open the request, set the <b>New GL</b> and the <b>Primary</b> and <b>Secondary</b> grouping, "
				"and click <b>Create Account &amp; Grouping</b>:</p>"
				"<p><a href='{url}'>{name}</a></p>"
			).format(
				requester=get_fullname(self.requested_by),
				company=self.company,
				account=frappe.utils.escape_html(self.account_name or "-"),
				reference=frappe.utils.escape_html(self.reference_gl or "-"),
				url=url,
				name=self.name,
			),
		)

	def notify_requester(self, created=True):
		if not self.requested_by:
			return
		if created and not frappe.db.get_single_value(
			"FR GL Account Request Settings", "notify_requester_on_completion"
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
	def on_update(self):
		if self.workflow_state == STATE_ACCOUNT_CREATED and not self.created_account:
			self.create_account_and_grouping()
		if self.flags.notify_rejected:
			self.notify_requester(created=False)

	def check_ready_for_creation(self):
		"""Pre-flight for the Approve action (Request For Creation -> Account Created).
		Runs in validate, i.e. before the workflow transition is committed."""
		self._check_assignee()
		if self.status == "Rejected":
			frappe.throw(_("This request was rejected and cannot be actioned."))
		missing = [
			label
			for field, label in (
				("new_gl", _("New GL")),
				("primary_group", _("Primary Grouping")),
				("secondary_group", _("Secondary Grouping")),
				("pattern_account", _("Pattern Account")),
			)
			if not self.get(field)
		]
		if missing:
			frappe.throw(
				_("Set {0} before approving the request.").format(", ".join(missing)),
				frappe.MandatoryError,
			)
		self.validate_pattern_account()
		self.validate_account_number()

	def validate_account_number(self):
		"""Same rule and message as ERPNext's Account.validate_account_number: a GL code
		is unique within a company. ERPNext's own method cannot be called here, it
		excludes `name != self.name` and an unsaved Account has no name yet. Because an
		Account is named '<code> - <name> - <abbr>', this also covers code + name + company."""
		existing = frappe.db.get_value(
			"Account", {"account_number": self.new_gl, "company": self.company}
		)
		if existing:
			frappe.throw(
				_("Account Number {0} already used in account {1}").format(self.new_gl, existing)
			)

	def validate_pattern_account(self):
		"""The Pattern Account is the parent group the new account is created under."""
		is_group, company = frappe.db.get_value(
			"Account", self.pattern_account, ["is_group", "company"]
		) or (0, None)
		if not is_group or company != self.company:
			frappe.throw(
				_("Pattern Account {0} must be a group account of {1}.").format(
					self.pattern_account, self.company
				)
			)

	def create_account_and_grouping(self):
		"""Runs when the workflow action Approve moves the request to Account Created.
		Any failure here aborts the save and rolls the transition back."""
		account = self._create_account()
		mapping = self._create_group_mapping(account.name)

		self.db_set(
			{
				"created_account": account.name,
				"gl_group_mapping": mapping.name,
				"status": "Account Created",
			}
		)
		self.notify_requester(created=True)
		frappe.msgprint(
			_("Account {0} created and mapped to {1} / {2}.").format(
				account.name, self.primary_group, self.secondary_group
			),
			indicator="green",
			alert=True,
		)

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
		account = frappe.new_doc("Account")
		account.account_name = self.account_name
		account.account_number = self.new_gl
		account.company = self.company
		account.parent_account = self.pattern_account
		account.insert(ignore_permissions=True)
		return account

	def _create_group_mapping(self, account_name):
		mapping = frappe.new_doc("FR GL Group Mapping")
		mapping.company = self.company
		mapping.gl_account = account_name
		mapping.report_type = self.report_type or "Monthly"
		mapping.primary_group = self.primary_group
		mapping.secondary_group = self.secondary_group
		mapping.insert(ignore_permissions=True)
		return mapping


@frappe.whitelist()
def get_receiver_for_company(company):
	"""Return {assigned_to, receiver_email} for the given Company, so the
	client can preview it immediately on selecting Company. `validate()`
	re-derives the same values authoritatively on save regardless."""
	assignee, _report_type, _parent = get_company_assignee(company)
	email = frappe.db.get_value("User", assignee, "email") if assignee else None
	return {"assigned_to": assignee, "receiver_email": email}


@frappe.whitelist()
def approve_request(name, new_gl, account_name, primary_group, secondary_group, pattern_account):
	"""Approve popup: store the Maker's entries, then run the Approve workflow action.

	One request, one transaction: the save and the action (account creation, GL Group
	Mapping, state change) succeed or fail together, so a failure leaves nothing behind
	and the popup can show the error."""
	return _save_and_apply(
		name,
		"Approve",
		{
			"new_gl": new_gl,
			"account_name": account_name,
			"primary_group": primary_group,
			"secondary_group": secondary_group,
			"pattern_account": pattern_account,
		},
	)


@frappe.whitelist()
def reject_request(name, remark):
	"""Reject popup: store the remark as the Rejection Reason, then run the Reject
	workflow action (state -> Rejected, requester notified)."""
	return _save_and_apply(name, "Reject", {"rejection_reason": remark})


def _save_and_apply(name, action, values):
	from frappe.model.workflow import apply_workflow

	doc = frappe.get_doc("FR GL Account Creation Request", name)
	doc.check_permission("write")
	doc._check_assignee()
	if doc.workflow_state != STATE_OPEN:
		frappe.throw(_("Only a request in '{0}' can be actioned.").format(STATE_OPEN))
	doc.update(values)
	doc.save()
	return apply_workflow(doc, action).as_dict()
