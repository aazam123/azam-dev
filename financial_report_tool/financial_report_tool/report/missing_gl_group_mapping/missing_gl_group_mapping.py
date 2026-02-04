# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "GL Account", "fieldname": "gl_account", "fieldtype": "Link", "options": "Account", "width": 300},
        {"label": "Report Type", "fieldname": "report_type", "fieldtype": "Data", "width": 120},
        {"label": "Primary Group", "fieldname": "primary_group", "fieldtype": "Link", "options": "Standalone Group", "width": 200, "editable": 1},
        {"label": "Secondary Group", "fieldname": "secondary_group", "fieldtype": "Link", "options": "Standalone Group", "width": 200, "editable": 1},
        {"label": "Higher Secondary Group", "fieldname": "higher_secondary_group", "fieldtype": "Link", "options": "Standalone Group", "width": 200, "editable": 1},
    ]


def get_data(filters):
    company = filters.get("company")
    report_type = filters.get("report_type")

    if not company:
        return []

    # Get all GL accounts from Trial Balance Entry
    trial_gls = frappe.get_all(
        "FR Trial Balance Entry",
        filters={"company": company},
        pluck="gl_account",
        distinct=True
    )

    if not trial_gls:
        return []

    # Build filter for mapped GLs
    mapped_filters = {"company": company}
    if report_type:
        mapped_filters["report_type"] = report_type

    # Get all mapped GL accounts
    mapped_gls = frappe.get_all(
        "GL Group Mapping",
        filters=mapped_filters,
        pluck="gl_account",
        distinct=True
    )

    # Find missing GLs
    missing_gls = list(set(trial_gls) - set(mapped_gls))

    if not missing_gls:
        return []

    # Get account details for missing GLs
    data = []
    for gl in missing_gls:
        account = frappe.db.get_value(
            "Account",
            gl,
            ["name", "account_name", "report_type", "root_type", "parent_account"],
            as_dict=True
        )
        if account:
            data.append({
                "gl_account": account.name,
                "account_name": account.account_name,
                "report_type": account.report_type,
                "root_type": account.root_type,
                "parent_account": account.parent_account,
                "primary_group": "",
                "secondary_group": "",
                "higher_secondary_group": "",
            })

    # Sort by account name
    data.sort(key=lambda x: x.get("account_name") or "")

    return data


@frappe.whitelist()
def create_gl_group_mapping(gl_account, company, report_type, primary_group, secondary_group, higher_secondary_group=None):
    """Create a new GL Group Mapping document"""
    if frappe.db.exists("GL Group Mapping", {"gl_account": gl_account, "company": company, "report_type": report_type}):
        frappe.throw(f"GL Group Mapping already exists for {gl_account} with report type {report_type}")

    doc = frappe.new_doc("GL Group Mapping")
    doc.gl_account = gl_account
    doc.company = company
    doc.report_type = report_type
    doc.primary_group = primary_group
    doc.secondary_group = secondary_group
    if higher_secondary_group:
        doc.higher_secondary_group = higher_secondary_group
    doc.insert()

    return doc.name


@frappe.whitelist()
def create_bulk_gl_group_mappings(mappings, company, report_type):
    """Create multiple GL Group Mapping documents from report data"""
    import json
    if isinstance(mappings, str):
        mappings = json.loads(mappings)

    created = []
    errors = []

    for mapping in mappings:
        gl_account = mapping.get("gl_account")
        primary_group = mapping.get("primary_group")
        secondary_group = mapping.get("secondary_group")
        higher_secondary_group = mapping.get("higher_secondary_group")

        if not gl_account or not primary_group or not secondary_group:
            errors.append({"gl_account": gl_account, "error": "Missing required fields"})
            continue

        try:
            if frappe.db.exists("GL Group Mapping", {"gl_account": gl_account, "company": company, "report_type": report_type}):
                errors.append({"gl_account": gl_account, "error": "Mapping already exists"})
                continue

            doc = frappe.new_doc("GL Group Mapping")
            doc.gl_account = gl_account
            doc.company = company
            doc.report_type = report_type
            doc.primary_group = primary_group
            doc.secondary_group = secondary_group
            if higher_secondary_group:
                doc.higher_secondary_group = higher_secondary_group
            doc.insert()
            created.append(gl_account)
        except Exception as e:
            errors.append({"gl_account": gl_account, "error": str(e)})

    frappe.db.commit()
    return {"created": created, "errors": errors}


