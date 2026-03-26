# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _


@frappe.whitelist()
def get_companies_with_tb(fiscal_year, month):
    """Get all companies that have FR Trial Balance Entry for the given fiscal year and month."""
    if not fiscal_year or not month:
        return []

    companies = frappe.db.sql("""
        SELECT DISTINCT tbe.company, c.default_currency
        FROM `tabFR Trial Balance Entry` tbe
        LEFT JOIN `tabCompany` c ON c.name = tbe.company
        WHERE tbe.fiscal_year = %s AND tbe.month = %s
        ORDER BY tbe.company
    """, (fiscal_year, month), as_dict=True)

    return companies


@frappe.whitelist()
def validate_before_import(fiscal_year, month, companies):
    """Validate all pre-conditions before importing.

    Checks:
    1. FR Trial Balance Entry exists for each company
    2. Company not already imported to FR Console Trial Balance
    3. FR Foreign Exchange Rate exists from company currency to INR
    """
    if isinstance(companies, str):
        companies = frappe.parse_json(companies)

    if not companies:
        frappe.throw(_("Please select at least one company."))

    results = []

    for company in companies:
        status = {"company": company, "valid": True, "errors": [], "tb_count": 0}

        # 1. Check FR Trial Balance Entry exists
        tb_count = frappe.db.count("FR Trial Balance Entry", {
            "fiscal_year": fiscal_year,
            "month": month,
            "company": company
        })
        status["tb_count"] = tb_count

        if tb_count == 0:
            status["valid"] = False
            status["errors"].append(
                _("No FR Trial Balance Entry found for {0} - {1} - {2}").format(company, fiscal_year, month)
            )

        # 2. Check if already imported
        already_imported = frappe.db.exists("FR Console Trial Balance", {
            "fiscal_year": fiscal_year,
            "month": month,
            "company": company
        })
        if already_imported:
            status["valid"] = False
            status["errors"].append(
                _("Company {0} is already imported for {1} - {2}").format(company, fiscal_year, month)
            )

        # 3. Check FR Foreign Exchange Rate exists (currency to INR)
        company_currency = frappe.db.get_value("Company", company, "default_currency")
        status["currency"] = company_currency

        if company_currency and company_currency != "INR":
            fx_rates = frappe.db.get_value("FR Foreign Exchange Rate", {
                "fiscal_year": fiscal_year,
                "month": month,
                "from_currency": company_currency,
                "to_currency": "INR"
            }, ["closing_rate", "average_rate"], as_dict=True)

            if not fx_rates or not fx_rates.closing_rate:
                status["valid"] = False
                status["errors"].append(
                    _("FR Foreign Exchange Rate missing: {0} to INR for {1} - {2}").format(
                        company_currency, fiscal_year, month
                    )
                )
            else:
                status["closing_rate"] = fx_rates.closing_rate
                status["average_rate"] = fx_rates.average_rate or fx_rates.closing_rate
        else:
            status["closing_rate"] = 1
            status["average_rate"] = 1

        results.append(status)

    return results


@frappe.whitelist()
def get_preview_data(fiscal_year, month, companies):
    """Return TB entries with computed exchange rates for preview table."""
    if isinstance(companies, str):
        companies = frappe.parse_json(companies)

    if not companies:
        return []

    # Build FX rate lookup per company
    fx_map = {}
    for company in companies:
        company_currency = frappe.db.get_value("Company", company, "default_currency")
        closing_rate = 1
        average_rate = 1
        if company_currency and company_currency != "INR":
            fx_rates = frappe.db.get_value("FR Foreign Exchange Rate", {
                "fiscal_year": fiscal_year,
                "month": month,
                "from_currency": company_currency,
                "to_currency": "INR"
            }, ["closing_rate", "average_rate"], as_dict=True)
            if fx_rates:
                closing_rate = fx_rates.closing_rate or 0
                average_rate = fx_rates.average_rate or closing_rate
        fx_map[company] = {"closing_rate": closing_rate, "average_rate": average_rate}

    # Fetch all TB entries for valid companies
    tb_entries = frappe.get_all("FR Trial Balance Entry",
        filters={
            "fiscal_year": fiscal_year,
            "month": month,
            "company": ["in", companies]
        },
        fields=["company", "gl_account", "report_type", "currency", "amount"],
        order_by="company, gl_account"
    )

    threshold = frappe.db.get_single_value("FR Financial Settings", "console_tb_threshold_amount") or 0

    rows = []
    for entry in tb_entries:
        rates = fx_map.get(entry.company, {"closing_rate": 1, "average_rate": 1})
        if entry.report_type == "Balance Sheet":
            exchange_rate = rates["closing_rate"]
        else:
            exchange_rate = rates["average_rate"]

        amount = entry.amount or 0
        amount_inr = amount * exchange_rate

        rows.append({
            "company": entry.company,
            "gl_account": entry.gl_account,
            "report_type": entry.report_type or "",
            "exchange_rate": exchange_rate,
            "amount": amount,
            "amount_inr": round(amount_inr, 2)
        })

    return {"rows": rows, "threshold": threshold}


@frappe.whitelist()
def import_console_trial_balance(fiscal_year, month, companies):
    """Pull data from FR Trial Balance Entry and create FR Console Trial Balance records."""
    if isinstance(companies, str):
        companies = frappe.parse_json(companies)

    if not companies:
        frappe.throw(_("Please select at least one company."))

    # Re-validate before import
    validation = validate_before_import(fiscal_year, month, companies)
    invalid = [v for v in validation if not v["valid"]]
    if invalid:
        error_msgs = []
        for v in invalid:
            error_msgs.extend(v["errors"])
        frappe.throw("<br>".join(error_msgs))

    total_created = 0

    threshold = frappe.get_value("FR Financial Settings", None, "console_tb_threshold_amount")
    if threshold:
        for company in companies:
            result = frappe.db.sql("""
                SELECT SUM(uploaded_amount) FROM `tabFR Trial Balance Entry`
                WHERE fiscal_year = %s AND month = %s AND company = %s
            """, (fiscal_year, month, company))

            amount = result[0][0] or 0
            if abs(amount) > int(threshold):
                frappe.throw(_("Threshold exceeded for company {0}. Total Amount: {1}, Threshold: {2}").format(company, amount, threshold))

    for company in companies:
        company_currency = frappe.db.get_value("Company", company, "default_currency")
        closing_rate = 1
        average_rate = 1
        if company_currency and company_currency != "INR":
            fx_rates = frappe.db.get_value("FR Foreign Exchange Rate", {
                "fiscal_year": fiscal_year,
                "month": month,
                "from_currency": company_currency,
                "to_currency": "INR"
            }, ["closing_rate", "average_rate"], as_dict=True)

            if fx_rates:
                closing_rate = fx_rates.closing_rate or 0
                average_rate = fx_rates.average_rate or closing_rate

        # Fetch all TB entries for this company/FY/month
        tb_entries = frappe.get_all("FR Trial Balance Entry",
            filters={
                "fiscal_year": fiscal_year,
                "month": month,
                "company": company
            },
            fields=["gl_account", "report_type", "currency", "amount", "date"]
        )

        for entry in tb_entries:
            amount = entry.amount or 0

            # Balance Sheet → closing_rate, Profit and Loss → average_rate
            if entry.report_type == "Balance Sheet":
                exchange_rate = closing_rate
            else:
                exchange_rate = average_rate

            amount_inr = amount * exchange_rate

            fctb = frappe.get_doc({
                "doctype": "FR Console Trial Balance",
                "fiscal_year": fiscal_year,
                "month": month,
                "posting_date": entry.date,
                "company": company,
                "gl_account": entry.gl_account,
                "report_type": entry.report_type,
                "currency": entry.currency or company_currency,
                "exchange_rate": exchange_rate,
                "amount": amount,
                "amount_inr": amount_inr
            })
            fctb.insert(ignore_permissions=True)
            total_created += 1

    frappe.db.commit()

    return {
        "success": True,
        "message": _("{0} Console Trial Balance entries created successfully.").format(total_created),
        "total_created": total_created
    }
