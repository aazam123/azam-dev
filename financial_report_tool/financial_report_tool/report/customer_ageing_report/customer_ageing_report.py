# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Data", "width": 120},
        {"label": "Customer Name", "fieldname": "customer_name", "fieldtype": "Data", "width": 250},
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

    # Fetch data from custom AR entry table
    invoices = frappe.db.sql("""
        SELECT
            ar.customer, 
            ar.customer_name,
            ar.ageing,
            SUM(ar.amount_in_lc) AS amount
        FROM `tabFR Account Receivable Entry` ar
        WHERE ar.amount_in_lc > 0
        GROUP BY ar.customer, ar.customer_name, ar.ageing
    """, as_dict=True)

    # Group by customer into ageing buckets
    grouped_data = {}

    for inv in invoices:
        cust = inv.customer
        if cust not in grouped_data:
            grouped_data[cust] = {
                "customer": inv.customer,
                "customer_name": inv.customer_name,
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
            grouped_data[cust]["not_due"] += inv.amount
        elif inv.ageing == "0-6 Months":
            grouped_data[cust]["0_6m"] += inv.amount
        elif inv.ageing == "6-12 Months":
            grouped_data[cust]["6_12m"] += inv.amount
        elif inv.ageing == "1-2 Years":
            grouped_data[cust]["1_2yr"] += inv.amount
        elif inv.ageing == "2-3 Years":
            grouped_data[cust]["2_3yr"] += inv.amount
        elif inv.ageing == "More Than 3 Years":
            grouped_data[cust]["more_3yr"] += inv.amount

        # Always update total
        grouped_data[cust]["total_amount"] += inv.amount

    return list(grouped_data.values())