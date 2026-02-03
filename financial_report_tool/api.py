import frappe

@frappe.whitelist()
def create_gl_group_mapping(gl_account, company, report_type, primary_group, secondary_group, higher_secondary_group=None, update_existing=0):
	"""Create GL Group Mapping entry with duplicate check"""

	# Check for duplicate entry
	filters = {
		"gl_account": gl_account,
		"company": company,
		"report_type": report_type,
	}

	existing = frappe.db.exists("GL Group Mapping", filters)

	if existing:
		if update_existing == 1:
			# Update existing entry
			doc = frappe.get_doc("GL Group Mapping", existing)
			doc.primary_group = primary_group
			doc.secondary_group = secondary_group
			doc.higher_secondary_group = higher_secondary_group or ""
			doc.save()
			return {"success": True, "name": doc.name, "updated": True}
		else:
			# Return existing info for confirmation
			existing_doc = frappe.get_doc("GL Group Mapping", existing)
			return {
				"success": False,
				"exists": True,
				"existing_name": existing,
				"existing_data": {
					"primary_group": existing_doc.primary_group,
					"secondary_group": existing_doc.secondary_group,
					"higher_secondary_group": existing_doc.higher_secondary_group or ""
				}
			}

	# Create new entry
	doc = frappe.get_doc({
		"doctype": "GL Group Mapping",
		"gl_account": gl_account,
		"company": company,
		"report_type": report_type,
		"primary_group": primary_group,
		"secondary_group": secondary_group,
		"higher_secondary_group": higher_secondary_group or ""
	})
	doc.insert()

	return {"success": True, "name": doc.name, "created": True}
