import frappe

DOCTYPE = "FR GL Account Creation Request"
STATES = ("Request For Creation", "Account Created", "Rejected")


def execute():
	"""Backfill workflow_state on existing FR GL Account Creation Requests.

	Fixtures (the Workflow) sync after post_model_sync patches, and the Workflow's own
	default-state update would otherwise mark every existing request, including those
	already created, as 'Request For Creation'.
	"""
	if not frappe.db.has_column(DOCTYPE, "workflow_state"):
		return

	for name in STATES:
		if not frappe.db.exists("Workflow State", name):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": name}).insert(
				ignore_permissions=True
			)

	for status, state in (
		("Account Created", "Account Created"),
		("Requested", "Request For Creation"),
		("Rejected", "Rejected"),
	):
		frappe.db.sql(
			f"""UPDATE `tab{DOCTYPE}` SET workflow_state = %s
			WHERE ifnull(workflow_state, '') = '' AND status = %s""",
			(state, status),
		)
