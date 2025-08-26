# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Nature", "fieldname": "nature", "fieldtype": "Data", "width": 200},
        {"label": "As per TB", "fieldname": "as_per_tb", "fieldtype": "Currency", "width": 180},
        {"label": "As per Working", "fieldname": "as_per_working", "fieldtype": "Currency", "width": 180},
        {"label": "Regrouping", "fieldname": "regrouping", "fieldtype": "Currency", "width": 180},
    ]


def get_data(filters):
    company = filters.get("company")

    # --- Fetch As per TB ---
    tb_data = frappe.db.sql("""
        SELECT nature, SUM(amount_in_lc) as amount
        FROM `tabFR Account Receivable Entry`
        WHERE company = %s
        GROUP BY nature
    """, (company), as_dict=True)

    tb_map = {d.nature: d.amount for d in tb_data}

    # --- Fetch As per Working ---
    working_data = frappe.db.sql("""
        SELECT nature, SUM(amount_in_lc) as amount
        FROM `tabFR Account Receivable Entry`
        WHERE company = %s
        GROUP BY nature
    """, (company), as_dict=True)

    working_map = {d.nature: d.amount for d in working_data}

    # --- Merge both ---
    natures = set(tb_map.keys()) | set(working_map.keys())
    data = []
    for nature in natures:
        tb_amt = tb_map.get(nature, 0)
        working_amt = working_map.get(nature, 0)
        regrouping = tb_amt - working_amt
        data.append({
            "nature": nature,
            "as_per_tb": tb_amt,
            "as_per_working": working_amt,
            "regrouping": regrouping
        })

    # --- Add Totals Row ---
    total_tb = sum(tb_map.values())
    total_working = sum(working_map.values())
    total_regrouping = total_tb - total_working

    data.append({
        "nature": "<b>Total</b>",
        "as_per_tb": total_tb,
        "as_per_working": total_working,
        "regrouping": total_regrouping
    })

    return data

