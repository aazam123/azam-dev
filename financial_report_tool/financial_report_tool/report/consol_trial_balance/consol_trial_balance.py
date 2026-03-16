# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils.xlsxutils import make_xlsx


def execute(filters=None):
    if not filters:
        filters = {}

    validate_filters(filters)
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def validate_filters(filters):
    if not filters.get("fiscal_year"):
        frappe.throw(_("Fiscal Year is required"))
    if filters.get("report_type") == "Consol Monthly" and not filters.get("month"):
        frappe.throw(_("Month is required"))


def get_columns():
    return [
        {
            "label": _("Account Number"),
            "fieldname": "account_number",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("GL Account"),
            "fieldname": "gl_account",
            "fieldtype": "Link",
            "options": "Account",
            "width": 430
        },
        {
            "label": _("Amount"),
            "fieldname": "amount_df_currency",
            "fieldtype": "Currency",
            "width": 200,
            "options": "Company:company:default_currency"
        },
        {
            "label": _("Company Currency"),
            "fieldname": "currency",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "label": _("Exchange Rate"),
            "fieldname": "exchange_rate",
            "fieldtype": "Float",
            "precision": 3,
            "width": 140
        },
        {
            "label": _("Amount (In INR)"),
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 200,
            "options": "INR"
        },
        {
            "label": _("Primary Group"),
            "fieldname": "primary_group",
            "fieldtype": "Link",
            "options": "Standalone Group",
            "width": 240
        },
        {
            "label": _("Secondary Group"),
            "fieldname": "secondary_group",
            "fieldtype": "Link",
            "options": "Standalone Group",
            "width": 240
        },
        {
            "label": _("Higher Secondary Group"),
            "fieldname": "higher_secondary_group",
            "fieldtype": "Link",
            "options": "Standalone Group",
            "width": 200
        },
        {
            "label": _("Report Type"),
            "fieldname": "report_type",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 180
        }
    ]


def get_data(filters):
    conditions = get_conditions(filters)

    data = frappe.db.sql("""
        SELECT
            acc.report_type AS report_type,
            t.gl_account AS gl_account,
            acc.account_number AS account_number,
            gm.primary_group AS primary_group,
            gm.secondary_group AS secondary_group,
            gm.higher_secondary_group AS higher_secondary_group,
            SUM(t.uploaded_amount) AS amount,
            t.month AS month,
            t.fiscal_year AS fiscal_year,
            t.company AS company,
            t.currency
        FROM `tabFR Trial Balance Entry` t
        INNER JOIN `tabGL Group Mapping` gm
            ON t.gl_account = gm.gl_account
            AND t.company = gm.company
        INNER JOIN `tabAccount` acc
            ON t.gl_account = acc.name
            AND t.company = acc.company
        WHERE t.fiscal_year = %(fiscal_year)s
            AND gm.report_type = %(report_type)s
            {conditions}
        GROUP BY
            acc.report_type,
            t.gl_account,
            acc.account_number,
            gm.primary_group,
            gm.secondary_group,
            gm.higher_secondary_group,
            t.month,
            t.fiscal_year,
            t.company
    """.format(conditions=conditions), filters, as_dict=True)

    logger = frappe.logger("currency_conversion", allow_site=True)

    for row in data:

        company_currency = frappe.get_value(
            "Company", row.company, "default_currency"
        )

        original_amount = row.amount
        row.amount_df_currency = original_amount

        # If company currency already INR
        if company_currency == "INR":
            row.exchange_rate = 1
            row.amount = original_amount

            logger.warning(
                f"{row.company} | {row.gl_account} | INR | "
                f"{original_amount} | 1 | {original_amount}"
            )

            continue

        rate_doc = frappe.db.get_value(
            "FR Foreign Exchange Rate",
            {
                "from_currency": company_currency,
                "to_currency": "INR",
                "fiscal_year": row.fiscal_year,
                "month": row.month
            },
            ["closing_rate", "average_rate"],
            as_dict=True
        )

        if not rate_doc:
            rate = 0
        else:
            if row.report_type == "Balance Sheet":
                rate = rate_doc.closing_rate or 0
            else:
                rate = rate_doc.average_rate or 0

        converted_amount = original_amount * rate

        row.exchange_rate = rate
        row.amount = converted_amount

        logger.warning(
            f"{row.company} | {row.gl_account} | {company_currency} | "
            f"{original_amount} | {rate} | {converted_amount}"
        )

    # ------------------------------
    # Calculate CTA Difference
    # ------------------------------

    total_converted = sum(d.amount for d in data)

    # If difference exists add CTA row
    if abs(total_converted) > 0.5:

        data.append({
            "account_number": "",
            "gl_account": "Foreign Currency Translation Reserve",
            "primary_group": "Equity",
            "secondary_group": "",
            "higher_secondary_group": "",
            "report_type": "Balance Sheet",
            "amount_df_currency": "",
            "exchange_rate": "",
            "amount": -total_converted,
            "month": "",
            "fiscal_year": filters.get("fiscal_year"),
            "company": "Consolidated",
            "currency": "INR"
        })

        logger.warning(
            f"CTA Adjustment Added | Difference: {total_converted}"
        )

    return data

def get_conditions(filters):
    conditions = []
    if filters.get("report_type") == "Consol Monthly":
        if filters.get("month"):
            conditions.append("AND t.month = %(month)s")

    # Handle MultiSelect filters - convert list to tuple for IN clause
    primary_group = filters.get("primary_group")
    if primary_group:
        if isinstance(primary_group, list) and len(primary_group) > 0:
            filters["primary_group"] = tuple(primary_group)
            conditions.append("AND gm.primary_group IN %(primary_group)s")
        elif isinstance(primary_group, str):
            filters["primary_group"] = (primary_group,)
            conditions.append("AND gm.primary_group IN %(primary_group)s")

    secondary_group = filters.get("secondary_group")
    if secondary_group:
        if isinstance(secondary_group, list) and len(secondary_group) > 0:
            filters["secondary_group"] = tuple(secondary_group)
            conditions.append("AND gm.secondary_group IN %(secondary_group)s")
        elif isinstance(secondary_group, str):
            filters["secondary_group"] = (secondary_group,)
            conditions.append("AND gm.secondary_group IN %(secondary_group)s")

    higher_secondary_group = filters.get("higher_secondary_group")
    if higher_secondary_group:
        if isinstance(higher_secondary_group, list) and len(higher_secondary_group) > 0:
            filters["higher_secondary_group"] = tuple(higher_secondary_group)
            conditions.append("AND gm.higher_secondary_group IN %(higher_secondary_group)s")
        elif isinstance(higher_secondary_group, str):
            filters["higher_secondary_group"] = (higher_secondary_group,)
            conditions.append("AND gm.higher_secondary_group IN %(higher_secondary_group)s")

    return " ".join(conditions)


@frappe.whitelist()
def download_excel(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    columns, data = execute(filters)

    # Build header row
    header = [col.get("label") for col in columns]

    # Build data rows
    xlsx_data = [header]
    fieldnames = [col.get("fieldname") for col in columns]
    for row in data:
        xlsx_data.append([row.get(f) for f in fieldnames])

    xlsx_file = make_xlsx(xlsx_data, "GL Account Group Report")

    file_name = "Consol_TB_Report.xlsx"
    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": file_name,
        "content": xlsx_file.getvalue(),
        "is_private": 1,
    })
    file_doc.save(ignore_permissions=True)

    return file_doc.file_url
