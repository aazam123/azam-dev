import frappe

REQUESTOR = "FR GL Requestor"
MAKER = "FR GL Maker"


def execute():
	"""FR GL Account Creation Request now has two roles instead of Accounts User /
	Accounts Manager: FR GL Requestor (raises the request) and FR GL Maker (sets the
	GL number and grouping, creates the account).

	- Every user who could raise a request before (Accounts User / Accounts Manager)
	  keeps that ability through FR GL Requestor.
	- Every assignee in FR GL Account Request Settings becomes a Maker, otherwise they
	  could no longer see the Maker section or action their requests.
	"""
	for role in (REQUESTOR, MAKER):
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)

	requestors = frappe.get_all(
		"Has Role",
		filters={"role": ["in", ["Accounts User", "Accounts Manager"]], "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
	for user in requestors:
		_grant(user, REQUESTOR)

	if frappe.db.exists("DocType", "FR GL Account Company Assignee"):
		for user in frappe.get_all("FR GL Account Company Assignee", pluck="assignee", distinct=True):
			_grant(user, MAKER)

	frappe.clear_cache()


def _grant(user, role):
	if user in ("Administrator", "Guest") or not frappe.db.exists("User", user):
		return
	if frappe.db.exists("Has Role", {"parent": user, "parenttype": "User", "role": role}):
		return
	doc = frappe.get_doc("User", user)
	doc.append("roles", {"role": role})
	doc.flags.ignore_permissions = True
	doc.save()
