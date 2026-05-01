import base64
import json
import os

import frappe
from frappe.utils.file_manager import save_file

from financial_report_tool.financial_report_tool.doctype.sync_sap.sync_sap import (
	ALLOWED_DOCUMENT_TYPES,
)


def _upload_for_type(document_type, file_name=None, file_content=None, preview_only=0):
	"""Shared logic: parse uploaded CSV/JSON and create a Sync SAP record."""
	if document_type not in ALLOWED_DOCUMENT_TYPES:
		frappe.throw(
			f"Invalid document_type. Allowed: {', '.join(ALLOWED_DOCUMENT_TYPES)}"
		)

	uploaded = frappe.request.files.get("file") if frappe.request else None

	if uploaded is not None:
		file_name = file_name or uploaded.filename
		raw_bytes = uploaded.stream.read()
	elif file_content:
		if not file_name:
			frappe.throw("file_name is required when sending file_content")
		try:
			raw_bytes = base64.b64decode(file_content)
		except (ValueError, TypeError) as e:
			frappe.throw(f"file_content must be valid base64: {e}")
	else:
		frappe.throw("Provide either a multipart 'file' or base64 'file_content'")

	ext = os.path.splitext(file_name)[1].lower()
	if ext not in (".csv", ".json"):
		frappe.throw("Only .csv and .json files are supported")

	preview_only = int(preview_only or 0)

	if preview_only:
		json_data = _parse_bytes(raw_bytes, ext)
		return {
			"document_type": document_type,
			"file_name": file_name,
			"json_data": json.loads(json_data),
		}

	saved = save_file(
		fname=file_name,
		content=raw_bytes,
		dt=None,
		dn=None,
		decode=False,
		is_private=1,
	)

	doc = frappe.new_doc("Sync SAP")
	doc.document_type = document_type
	doc.file = saved.file_url
	doc.insert(ignore_permissions=False)

	frappe.db.set_value("File", saved.name, {
		"attached_to_doctype": "Sync SAP",
		"attached_to_name": doc.name,
	})
	frappe.db.commit()

	return {
		"name": doc.name,
		"document_type": doc.document_type,
		"file_url": doc.file,
		"json_data": json.loads(doc.json_data) if doc.json_data else None,
	}


@frappe.whitelist()
def upload_sales_register(file_name=None, file_content=None, preview_only=0):
	"""Upload CSV/JSON for Sales Register."""
	return _upload_for_type("Sales Register", file_name, file_content, preview_only)


@frappe.whitelist()
def upload_purchase_register(file_name=None, file_content=None, preview_only=0):
	"""Upload CSV/JSON for Purchase Register."""
	return _upload_for_type("Purchase Register", file_name, file_content, preview_only)


@frappe.whitelist()
def upload_far_entry(file_name=None, file_content=None, preview_only=0):
	"""Upload CSV/JSON for FAR Entry."""
	return _upload_for_type("FAR Entry", file_name, file_content, preview_only)


@frappe.whitelist()
def upload_account_payable_entry(file_name=None, file_content=None, preview_only=0):
	"""Upload CSV/JSON for Account Payable Entry."""
	return _upload_for_type("Account Payable Entry", file_name, file_content, preview_only)


@frappe.whitelist()
def upload_account_receivable_entry(file_name=None, file_content=None, preview_only=0):
	"""Upload CSV/JSON for Account Receivable Entry."""
	return _upload_for_type("Account Receivable Entry", file_name, file_content, preview_only)


@frappe.whitelist()
def upload_asset_register_entry(file_name=None, file_content=None, preview_only=0):
	"""Upload CSV/JSON for Asset Register Entry."""
	return _upload_for_type("Asset Register Entry", file_name, file_content, preview_only)


def _parse_bytes(raw_bytes, ext):
	import csv
	import io

	try:
		content = raw_bytes.decode("utf-8-sig")
	except UnicodeDecodeError:
		content = raw_bytes.decode("latin-1")

	if ext == ".json":
		try:
			data = json.loads(content)
		except ValueError as e:
			frappe.throw(f"Invalid JSON file: {e}")
	else:
		reader = csv.DictReader(io.StringIO(content))
		data = [row for row in reader]

	return json.dumps(data, ensure_ascii=False, indent=2)


@frappe.whitelist()
def create_gl_group_mapping(gl_account, company, report_type, primary_group, secondary_group, higher_secondary_group=None, update_existing=0):

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


@frappe.whitelist()
def bulk_update_gl_group_mappings(items, report_type, primary_group=None, secondary_group=None, higher_secondary_group=None):
    if isinstance(items, str):
        items = json.loads(items)

    updated = []
    errors = []

    for item in items:
        try:
            gl_account = item.get("gl_account")
            company = item.get("company")

            if not gl_account or not company:
                continue

            filters = {
                "gl_account": gl_account,
                "company": company,
                "report_type": report_type
            }

            update_values = {}

            if primary_group:
                update_values["primary_group"] = primary_group
            if secondary_group:
                update_values["secondary_group"] = secondary_group
            if higher_secondary_group:
                update_values["higher_secondary_group"] = higher_secondary_group

            if update_values:
                frappe.db.set_value("GL Group Mapping", filters, update_values)
                updated.append(gl_account)

        except Exception as e:
            errors.append({
                "gl_account": item.get("gl_account"),
                "error": str(e)
            })

    frappe.db.commit()

    return {
        "updated": updated,
        "errors": errors
    }