import json
import os

import frappe


FIXTURE_PATH = os.path.join(
	os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
	"fixtures",
	"cost_center.json",
)


def create_root_cost_centers():
	"""Create root (parent) cost centers from the fixture file.

	Root cost centers have no parent, which fails the standard mandatory
	check on `parent_cost_center`. We insert them with `ignore_mandatory`
	so they can act as parents for the rest of the cost-center tree.
	"""
	if not os.path.exists(FIXTURE_PATH):
		return

	with open(FIXTURE_PATH) as f:
		entries = json.load(f)

	for entry in entries:
		name = entry.get("name")
		company = entry.get("company")

		if not name or not company:
			continue

		if not frappe.db.exists("Company", company):
			continue

		if frappe.db.exists("Cost Center", name):
			continue

		doc = frappe.new_doc("Cost Center")
		doc.update({
			"cost_center_name": entry.get("cost_center_name"),
			"company": company,
			"is_group": entry.get("is_group", 1),
			"disabled": entry.get("disabled", 0),
			"parent_cost_center": None,
		})
		doc.flags.ignore_mandatory = True
		doc.flags.ignore_permissions = True
		doc.flags.ignore_links = True

		try:
			doc.insert()
		except Exception:
			frappe.log_error(
				title="Root Cost Center creation failed",
				message=frappe.get_traceback(),
			)
			continue

	frappe.db.commit()
