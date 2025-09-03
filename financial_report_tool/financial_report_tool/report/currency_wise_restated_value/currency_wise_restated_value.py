# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Currency", "fieldname": "currency", "fieldtype": "Data", "width": 120},
		{"label": "Total Amount in LC", "fieldname": "total_amount_in_lc", "fieldtype": "Currency", "width": 150},
		{"label": "Total Amount in DC", "fieldname": "total_amount_in_dc", "fieldtype": "Currency", "width": 150},
		{"label": "Closing Ex. Rate", "fieldname": "avg_closing_ex_rate", "fieldtype": "Float", "width": 130},
		{"label": "Total Restated Value", "fieldname": "restated_value", "fieldtype": "Currency", "width": 160},
		{"label": "Total Gain / Loss", "fieldname": "gainloss", "fieldtype": "Currency", "width": 150},
	]


def get_data(filters):
	company = filters.get("company")
	fiscal_year = filters.get("fiscal_year")
	report_type = filters.get("report_type")

	# fetch all entries
	entries = frappe.db.sql("""
		SELECT 
			customer,
			currency,
			amount_in_lc,
			amount_in_dc,
			closing_ex_rate
		FROM `tabFR Account Receivable Entry`
		WHERE company = %s 
		AND fiscal_year = %s 
		AND report_type = %s
		ORDER BY customer
	""", (company, fiscal_year, report_type), as_dict=True)

	# Step 1: build customer → nature mapping
	customer_running = {}
	customer_nature = {}
	for e in entries:
		customer_running[e.customer] = customer_running.get(e.customer, 0) + (e.amount_in_lc or 0)

	for e in entries:
		customer_nature[e.customer] = "Advance" if customer_running[e.customer] < 0 else "Receivable"

	processed_entries = []
	for e in entries:
		nature = customer_nature[e.customer]
		closing_rate = e.closing_ex_rate or 1
		restated_value = (e.amount_in_dc or 0) * closing_rate

		if nature == "Receivable":
			gainloss = (e.amount_in_lc or 0) - restated_value
			processed_entries.append({
				"currency": e.currency,
				"total_amount_in_lc": e.amount_in_lc or 0,
				"total_amount_in_dc": e.amount_in_dc or 0,
				"avg_closing_ex_rate": closing_rate,
				"restated_value": restated_value,
				"gainloss": gainloss
			})

	# Step 3: aggregate ONLY by currency
	grouped = {}
	for e in processed_entries:
		key = e["currency"]
		if key not in grouped:
			grouped[key] = {
				"currency": e["currency"],
				"total_amount_in_lc": 0,
				"total_amount_in_dc": 0,
				"avg_closing_ex_rate": 0,
				"restated_value": 0,
				"gainloss": 0,
				"count": 0
			}

		g = grouped[key]
		g["total_amount_in_lc"] += e["total_amount_in_lc"]
		g["total_amount_in_dc"] += e["total_amount_in_dc"]
		g["restated_value"] += e["restated_value"]

	
	for g in grouped.values():
		g["gainloss"] = g["restated_value"] - g["total_amount_in_lc"]
		g["avg_closing_ex_rate"] = g["restated_value"] / g["total_amount_in_dc"]

	return list(grouped.values())
