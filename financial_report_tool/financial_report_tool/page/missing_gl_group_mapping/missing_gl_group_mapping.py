# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def get_missing_gl_accounts(company, report_type):
    """Get GL accounts from Trial Balance that don't have group mapping"""
    if not company:
        return {"data": [], "primary_groups": [], "secondary_groups": []}

    # Determine source table based on report type
    if report_type in ("Console Monthly", "Console Yearly"):
        source_doctype = "FR Console Trial Balance"
    else:
        source_doctype = "FR Trial Balance Entry"

    # Get all GL accounts from the appropriate Trial Balance
    trial_gls = frappe.get_all(
        source_doctype,
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
            ["name", "account_name", "account_number", "report_type", "root_type", "parent_account"],
            as_dict=True
        )
        if account:
            data.append({
                "gl_account": account.name,
                "account_number": account.account_number or "",
                "primary_group": "",
                "secondary_group": "",
                "higher_secondary_group": "",
            })
        else:
            # For Console TB entries where GL account may not exist as an Account doc
            data.append({
                "gl_account": gl,
                "account_number": "",
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

        # Handle multi-select arrays - join with comma
        if isinstance(primary_group, list):
            primary_group = ", ".join(primary_group) if primary_group else ""
        if isinstance(secondary_group, list):
            secondary_group = ", ".join(secondary_group) if secondary_group else ""
        if isinstance(higher_secondary_group, list):
            higher_secondary_group = ", ".join(higher_secondary_group) if higher_secondary_group else ""

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


@frappe.whitelist()
def parse_excel_mappings(file_url):
    """Parse Excel file and return mappings data without creating entries"""
    from frappe.utils.file_manager import get_file
    from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

    try:
        # Read the uploaded file
        fcontent = get_file(file_url)
        rows = read_xlsx_file_from_attached_file(fcontent=fcontent[1])

        if not rows or len(rows) < 2:
            return {"success": False, "error": "Empty file or no data rows"}

        # Skip header row
        data_rows = rows[1:]

        mappings = []
        errors = []

        for row_idx, row in enumerate(data_rows, start=2):
            if len(row) < 4:
                errors.append({"row": row_idx, "error": "Insufficient columns"})
                continue

            # Column mapping: Account Number, GL Account, Primary Group, Secondary Group, Higher Secondary Group
            gl_account = str(row[1]).strip() if row[1] else ""
            primary_group = str(row[2]).strip() if row[2] else ""
            secondary_group = str(row[3]).strip() if row[3] else ""
            higher_secondary_group = str(row[4]).strip() if len(row) > 4 and row[4] else ""

            if not gl_account:
                continue  # Skip empty rows

            # Validate Primary Group exists (if provided)
            if primary_group and not frappe.db.exists("Standalone Group", primary_group):
                errors.append({"row": row_idx, "gl_account": gl_account, "error": f"Primary Group '{primary_group}' not found"})
                continue

            # Validate Secondary Group exists (if provided)
            if secondary_group and not frappe.db.exists("Standalone Group", secondary_group):
                errors.append({"row": row_idx, "gl_account": gl_account, "error": f"Secondary Group '{secondary_group}' not found"})
                continue

            # Validate Higher Secondary Group exists (if provided)
            if higher_secondary_group and not frappe.db.exists("Standalone Group", higher_secondary_group):
                errors.append({"row": row_idx, "gl_account": gl_account, "error": f"Higher Secondary Group '{higher_secondary_group}' not found"})
                higher_secondary_group = ""  # Clear invalid value but continue

            mappings.append({
                "gl_account": gl_account,
                "primary_group": primary_group,
                "secondary_group": secondary_group,
                "higher_secondary_group": higher_secondary_group
            })

        return {
            "success": True,
            "mappings": mappings,
            "errors": errors
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def download_template(company, report_type):
    """Download Excel template with missing GL accounts"""
    import io
    from frappe.utils.xlsxutils import make_xlsx

    result = get_missing_gl_accounts(company, report_type)
    data = result.get("data", [])

    # Prepare Excel data
    header = ["Account Number", "GL Account", "Primary Group", "Secondary Group", "Higher Secondary Group"]
    rows = [header]

    for row in data:
        gl_account = row.get("gl_account", "")
        # Extract account number from GL account name
        account_number = ""
        if gl_account:
            account_doc = frappe.db.get_value("Account", gl_account, ["account_number"], as_dict=True)
            if account_doc:
                account_number = account_doc.get("account_number") or ""

        rows.append([
            account_number,
            gl_account,
            "",  # Primary Group - to be filled
            "",  # Secondary Group - to be filled
            ""   # Higher Secondary Group - optional
        ])

    # Create Excel file
    xlsx_file = make_xlsx(rows, "Missing GL Mappings")

    # Set response headers for download
    frappe.response["filename"] = f"missing_gl_mappings_{company}_{report_type}.xlsx"
    frappe.response["filecontent"] = xlsx_file.getvalue()
    frappe.response["type"] = "binary"


@frappe.whitelist()
def upload_mappings(file_url, company, report_type):
    """Upload Excel file and create mappings"""
    import json
    from frappe.utils.file_manager import get_file
    from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

    try:
        # Read the uploaded file
        fcontent = get_file(file_url)
        rows = read_xlsx_file_from_attached_file(fcontent=fcontent[1])

        if not rows or len(rows) < 2:
            return {"success": False, "error": "Empty file or no data rows"}

        # Skip header row
        header = rows[0]
        data_rows = rows[1:]

        created = []
        errors = []
        skipped = []

        for row_idx, row in enumerate(data_rows, start=2):
            if len(row) < 4:
                errors.append({"row": row_idx, "error": "Insufficient columns"})
                continue

            # Column mapping: Account Number, GL Account, Primary Group, Secondary Group, Higher Secondary Group
            gl_account = str(row[1]).strip() if row[1] else ""
            primary_group = str(row[2]).strip() if row[2] else ""
            secondary_group = str(row[3]).strip() if row[3] else ""
            higher_secondary_group = str(row[4]).strip() if len(row) > 4 and row[4] else ""

            if not gl_account:
                continue  # Skip empty rows

            if not primary_group or not secondary_group:
                skipped.append({"row": row_idx, "gl_account": gl_account, "reason": "Missing Primary or Secondary Group"})
                continue

            # Validate GL Account exists
            if not frappe.db.exists("Account", gl_account):
                errors.append({"row": row_idx, "gl_account": gl_account, "error": "GL Account not found"})
                continue

            # Validate Primary Group exists
            if not frappe.db.exists("Standalone Group", primary_group):
                errors.append({"row": row_idx, "gl_account": gl_account, "error": f"Primary Group '{primary_group}' not found"})
                continue

            # Validate Secondary Group exists
            if not frappe.db.exists("Standalone Group", secondary_group):
                errors.append({"row": row_idx, "gl_account": gl_account, "error": f"Secondary Group '{secondary_group}' not found"})
                continue

            # Check if mapping already exists
            if frappe.db.exists("GL Group Mapping", {"gl_account": gl_account, "company": company, "report_type": report_type}):
                skipped.append({"row": row_idx, "gl_account": gl_account, "reason": "Mapping already exists"})
                continue

            try:
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
                errors.append({"row": row_idx, "gl_account": gl_account, "error": str(e)})

        frappe.db.commit()

        return {
            "success": True,
            "created": created,
            "errors": errors,
            "skipped": skipped
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
