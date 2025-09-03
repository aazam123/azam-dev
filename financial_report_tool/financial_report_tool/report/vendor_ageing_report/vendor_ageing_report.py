# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Supplier", "fieldname": "supplier", "fieldtype": "Data", "width": 120},
        {"label": "Supplier Name", "fieldname": "supplier_name", "fieldtype": "Data", "width": 250},
        {"label": "Not Due", "fieldname": "not_due", "fieldtype": "Currency", "width": 150},
        {"label": "0-6 Months", "fieldname": "0_6m", "fieldtype": "Currency", "width": 150},
        {"label": "6-12 Months", "fieldname": "6_12m", "fieldtype": "Currency", "width": 150},
        {"label": "1-2 Years", "fieldname": "1_2yr", "fieldtype": "Currency", "width": 150},
        {"label": "2-3 Years", "fieldname": "2_3yr", "fieldtype": "Currency", "width": 150},
        {"label": "More than 3 Years", "fieldname": "more_3yr", "fieldtype": "Currency", "width": 150},
        {"label": "Total Amount", "fieldname": "total_amount", "fieldtype": "Currency", "width": 180},
    ]


def get_data(filters):
    data = []

    conditions = []
    if filters.get("company"):
        conditions.append("ap.company = %(company)s")
    if filters.get("fiscal_year"):
        conditions.append("ap.fiscal_year = %(fiscal_year)s")
    if filters.get("report_type"):
        conditions.append("ap.report_type = %(report_type)s")
    if filters.get("supplier"):
        conditions.append("ap.supplier = %(supplier)s")

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

    # Fetch data from custom AP entry table
    invoices = frappe.db.sql(f"""
        SELECT
            ap.supplier, 
            ap.supplier_name,
            ap.ageing,
            SUM(ap.amount_in_lc) AS amount
        FROM `tabFR Account Payable Entry` ap
        {where_clause}
        GROUP BY ap.supplier, ap.supplier_name, ap.ageing
    """, filters, as_dict=True)

    # Group by supplier into ageing buckets
    grouped_data = {}

    for inv in invoices:
        vend = inv.supplier
        if vend not in grouped_data:
            grouped_data[vend] = {
                "supplier": inv.supplier,
                "supplier_name": inv.supplier_name,
                "not_due": 0,
                "0_6m": 0,
                "6_12m": 0,
                "1_2yr": 0,
                "2_3yr": 0,
                "more_3yr": 0,
                "total_amount": 0,
            }

        # Assign amounts into the correct ageing bucket
        if inv.ageing == "Not Due":
            grouped_data[vend]["not_due"] += inv.amount
        elif inv.ageing == "0-6 Months":
            grouped_data[vend]["0_6m"] += inv.amount
        elif inv.ageing == "6-12 Months":
            grouped_data[vend]["6_12m"] += inv.amount
        elif inv.ageing == "1-2 Years":
            grouped_data[vend]["1_2yr"] += inv.amount
        elif inv.ageing == "2-3 Years":
            grouped_data[vend]["2_3yr"] += inv.amount
        elif inv.ageing == "More Than 3 Years":
            grouped_data[vend]["more_3yr"] += inv.amount

        # Always update total
        grouped_data[vend]["total_amount"] += inv.amount

    return list(grouped_data.values())
