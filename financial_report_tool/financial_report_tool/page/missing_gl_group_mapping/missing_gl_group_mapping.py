# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def get_missing_gl_accounts(company, report_type):
    """Get GL accounts from Trial Balance that don't have group mapping"""
    if not company:
        return {"data": [], "primary_groups": [], "secondary_groups": []}

    # Get all GL accounts from Trial Balance Entry
    trial_gls = frappe.get_all(
        "FR Trial Balance Entry",
        filters={"company": company},
        pluck="gl_account",
        distinct=True
    )

    if not trial_gls:
        return {"data": [], "primary_groups": [], "secondary_groups": []}

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
        return {"data": [], "primary_groups": [], "secondary_groups": []}

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
                "primary_group": "",
                "secondary_group": "",
                "higher_secondary_group": "",
            })

    # Sort by account name
    data.sort(key=lambda x: x.get("account_name") or "")

    # Get standalone groups for dropdowns
    primary_groups = frappe.get_all(
        "Standalone Group",
        filters={"is_primary_group": 1, "disable": 0},
        fields=["name", "standalone_group_name"],
        order_by="standalone_group_name"
    )

    secondary_groups = frappe.get_all(
        "Standalone Group",
        filters={"is_group": 0, "is_primary_group": 0, "disable": 0},
        fields=["name", "standalone_group_name", "parent_standalone_group"],
        order_by="standalone_group_name"
    )

    return {
        "data": data,
        "primary_groups": primary_groups,
        "secondary_groups": secondary_groups
    }


@frappe.whitelist()
def create_bulk_gl_group_mappings(mappings, company, report_type):
    """Create multiple GL Group Mapping documents"""
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


@frappe.whitelist()
def create_single_gl_group_mapping(gl_account, company, report_type, primary_group, secondary_group, higher_secondary_group=None):
    """Create a single GL Group Mapping document automatically"""
    try:
        if not gl_account or not primary_group or not secondary_group:
            return {"success": False, "error": "Missing required fields"}

        if frappe.db.exists("GL Group Mapping", {"gl_account": gl_account, "company": company, "report_type": report_type}):
            return {"success": False, "error": "Mapping already exists"}

        doc = frappe.new_doc("GL Group Mapping")
        doc.gl_account = gl_account
        doc.company = company
        doc.report_type = report_type
        doc.primary_group = primary_group
        doc.secondary_group = secondary_group
        if higher_secondary_group:
            doc.higher_secondary_group = higher_secondary_group
        doc.insert()
        frappe.db.commit()

        return {"success": True, "name": doc.name}
    except Exception as e:
        return {"success": False, "error": str(e)}
