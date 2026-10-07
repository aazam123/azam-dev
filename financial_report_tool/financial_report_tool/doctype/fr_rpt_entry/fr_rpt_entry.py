# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe.model.document import Document


# Map relation names from Company Hierarchy to RPT Transaction relation types
RELATION_MAP = {
	"Ultimate Holding Company": "Ultimate Holding Company",
	"Holding Company": "Holding Company",
	"Subsidiary Company": "Subsidiary",
	"Fellow Subsidiary": "Fellow Subsidiary",
	"Fellow Subsidiary of Holding Company": "Fellow Subsidiary of Holding Company",
	"Subsidiary of Fellow Subsidiary": "Subsidiary of Fellow Subsidiary",
	"Key Managerial Personnel": "Key Managerial Personnel",
	"Holding Company of Holding Company": "Holding Company of Holding Company",
	"Step-down Subsidiary of Micro Life Sciences Pvt Ltd": "Step-down Subsidiary of Micro Life Sciences Pvt Ltd"
}

RELATION_ORDER = [
	"Ultimate Holding Company",
	"Holding Company",
	"Subsidiary",
	"Fellow Subsidiary of Holding Company",
	"Fellow Subsidiary",
	"Subsidiary of Fellow Subsidiary",
	"Key Managerial Personnel",
	"Holding Company of Holding Company",
	"Step-down Subsidiary of Micro Life Sciences Pvt Ltd"
]

# Default template: Transaction categories
RPT_TRANSACTION_CATEGORIES = [
	"Sale of Goods",
	"Purchase of Goods",
	"Purchase of Assets",
	"Rent Received",
	"Rent Paid",
	"Shared Services Charges",
	"Reimbursement of Expenses",
	"Debit Note towards Expiry of Goods",
	"Guarantees Given",
	"Guarantees Extinguished",
	"Guarantee Expenses",
	"Investment in Subsidiaries",
	"Interest on Preference Shares",
	"License Fees",
	"Gratuity Liabilities Transferred",
	"Remuneration and Perquisites",
	"Receipt of Lease Liability",
	"Payment of Lease Liability",
]

# Default template: Balance Outstanding categories
RPT_BALANCE_CATEGORIES = [
	"Receivable",
	"Payable",
]


class FRRPTEntry(Document):
	pass


@frappe.whitelist()
def fetch_companies_for_table(company, table_type):
	if not company:
		frappe.throw("Please select a Company first.")

	hierarchy_name = frappe.db.exists("FR Company Hierarchy", {"company": company})
	if not hierarchy_name:
		frappe.throw(f"No Company Hierarchy entry found for {company}")

	results = []

	hierarchy_doc = frappe.get_doc("FR Company Hierarchy", hierarchy_name)
	if hierarchy_doc.company_hierarchy_relation:
		for row in hierarchy_doc.company_hierarchy_relation:
			results.append({"company": row.company, "relation": row.relation})
	else:
		frappe.throw("Fill the Company Hierarchy Relation at Company Hierarchy")

	return results


@frappe.whitelist()
def calculate_rpt_transactions(company, fiscal_year, fr_rpt_entry_name=None):
	"""
	Calculate RPT transaction amounts and return default template rows
	with computed amounts from FR Sales Register, FR Purchase Register,
	FR Investment Entry, FR Account Receivable Entry, FR Account Payable Entry.
	"""
	if not company or not fiscal_year:
		frappe.throw("Please select Company and Fiscal Year first.")

	# 1. Get company-relation mapping from names_of_replated in FR RPT Entry
	if not fr_rpt_entry_name:
		fr_rpt_entry_name = frappe.db.exists("FR RPT Entry", {"company": company, "fiscal_year": fiscal_year})
	if not fr_rpt_entry_name:
		frappe.throw(f"No RPT Entry found for {company} / {fiscal_year}")

	fr_rpt_entry_doc = frappe.get_doc("FR RPT Entry", fr_rpt_entry_name)
	if not fr_rpt_entry_doc.get("names_of_replated"):
		frappe.throw("Please fetch related parties in 'Names of Related Parties' table first.")

	company_relation_map = {}
	for row in fr_rpt_entry_doc.get("names_of_replated", []):
		relation = RELATION_MAP.get(row.relation, row.relation)
		company_relation_map[row.company] = relation

	related_companies = list(company_relation_map.keys())
	if not related_companies:
		return []

	# Group companies by relation type
	relation_company_groups = defaultdict(list)
	for comp, rel in company_relation_map.items():
		relation_company_groups[rel].append(comp)

	# 2. Get customer/supplier codes for related companies from FR RPT Master
	rpt_master_name = frappe.db.exists("FR RPT Master", {"company": company})
	customer_to_company = {}
	supplier_to_company = {}

	if rpt_master_name:
		rpt_master = frappe.get_doc("FR RPT Master", rpt_master_name)
		for row in rpt_master.get("internal_customer_list", []):
			if row.customer_code:
				customer_to_company[row.customer_code] = row.customer_name
		for row in rpt_master.get("related_customer_list", []):
			if row.customer_code:
				customer_to_company[row.customer_code] = row.customer_name
		for row in rpt_master.get("internal_supplier", []):
			if row.supplier_code:
				supplier_to_company[row.supplier_code] = row.supplier_name or row.supplier_code
		for row in rpt_master.get("related_party_supplier", []):
			if row.supplier_code:
				supplier_to_company[row.supplier_code] = row.supplier_name or row.supplier_code

	# 3. Determine previous fiscal year
	fy_parts = fiscal_year.split("-")
	if len(fy_parts) == 2:
		previous_fiscal_year = f"{int(fy_parts[0]) - 1}-{int(fy_parts[1]) - 1}"
	else:
		previous_fiscal_year = None

	fiscal_years = [fiscal_year]
	if previous_fiscal_year:
		fiscal_years.append(previous_fiscal_year)

	# 4. Build results dict: relation_type -> category -> company -> {cy, py}
	results_map = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"cy": 0, "py": 0})))

	# Sale of Goods from FR Sales Register
	if customer_to_company:
		customer_codes = list(customer_to_company.keys())
		sales_rows = frappe.db.sql("""
			SELECT bill_to, fiscal_year, SUM(IFNULL(base_amount, 0)) / 100000 as total_amount
			FROM `tabFR Sales Register`
			WHERE company = %s AND fiscal_year IN %s AND bill_to IN %s
			GROUP BY bill_to, fiscal_year
		""", (company, fiscal_years, customer_codes), as_dict=True)
		for row in sales_rows:
			cust_name = customer_to_company.get(row.bill_to, row.bill_to)
			relation = _find_relation_for_party(cust_name, company_relation_map)
			if relation:
				yk = "cy" if row.fiscal_year == fiscal_year else "py"
				results_map[relation]["Sale of Goods"][cust_name][yk] += row.total_amount or 0

	# Purchase of Goods from FR Purchase Register
	if supplier_to_company:
		supplier_codes = list(supplier_to_company.keys())
		purchase_rows = frappe.db.sql("""
			SELECT invoicing_party, fiscal_year, SUM(IFNULL(base_amount, 0)) / 100000 as total_amount
			FROM `tabFR Purchase Register`
			WHERE company = %s AND fiscal_year IN %s AND invoicing_party IN %s
			GROUP BY invoicing_party, fiscal_year
		""", (company, fiscal_years, supplier_codes), as_dict=True)
		for row in purchase_rows:
			sup_name = supplier_to_company.get(row.invoicing_party, row.invoicing_party)
			relation = _find_relation_for_party(sup_name, company_relation_map)
			if relation:
				yk = "cy" if row.fiscal_year == fiscal_year else "py"
				results_map[relation]["Purchase of Goods"][sup_name][yk] += row.total_amount or 0

	# Investment in Subsidiaries from FR Investment Entry
	# CY = cumulative investment up to CY end, PY = cumulative investment up to PY end
	fy_end_dates = {}
	fy_list_for_inv = [fiscal_year]
	if previous_fiscal_year:
		fy_list_for_inv.append(previous_fiscal_year)
	if fy_list_for_inv:
		fy_rows = frappe.db.sql("""
			SELECT name, year_end_date FROM `tabFiscal Year` WHERE name IN %s
		""", (fy_list_for_inv,), as_dict=True)
		for r in fy_rows:
			fy_end_dates[r.name] = r.year_end_date

	for fy_name, end_date in fy_end_dates.items():
		inv_rows = frappe.db.sql("""
			SELECT company as invested_company,
				SUM(IFNULL(investment_value, 0)) / 100000 as total_amount
			FROM `tabFR Investment Entry`
			WHERE holding_company = %s AND company IN %s
			AND posting_date <= %s
			GROUP BY company
		""", (company, related_companies, end_date), as_dict=True)
		for row in inv_rows:
			relation = company_relation_map.get(row.invested_company)
			if relation:
				yk = "cy" if fy_name == fiscal_year else "py"
				results_map[relation]["Investment in Subsidiaries"][row.invested_company][yk] += row.total_amount or 0

	# Receivable from FR Account Receivable Entry (filtered by FR RPT Master customer codes)
	if customer_to_company:
		ar_rows = frappe.db.sql("""
			SELECT customer, fiscal_year,
				SUM(IFNULL(amount_in_lc, 0)) / 100000 as total_amount
			FROM `tabFR Account Receivable Entry`
			WHERE company = %s AND fiscal_year IN %s
			AND report_type = 'Yearly'
			AND customer IN %s
			GROUP BY customer, fiscal_year
		""", (company, fiscal_years, list(customer_to_company.keys())), as_dict=True)
		for row in ar_rows:
			cust_name = customer_to_company.get(row.customer, row.customer)
			relation = _find_relation_for_party(cust_name, company_relation_map)
			if relation:
				yk = "cy" if row.fiscal_year == fiscal_year else "py"
				results_map[relation]["Receivable"][cust_name][yk] += row.total_amount or 0

	# Payable from FR Account Payable Entry (filtered by FR RPT Master supplier codes)
	if supplier_to_company:
		ap_rows = frappe.db.sql("""
			SELECT supplier, fiscal_year,
				SUM(IFNULL(amount_in_lc, 0)) / 100000 as total_amount
			FROM `tabFR Account Payable Entry`
			WHERE company = %s AND fiscal_year IN %s
			AND report_type = 'Yearly'
			AND supplier IN %s
			GROUP BY supplier, fiscal_year
		""", (company, fiscal_years, list(supplier_to_company.keys())), as_dict=True)
		for row in ap_rows:
			sup_name = supplier_to_company.get(row.supplier, row.supplier)
			relation = _find_relation_for_party(sup_name, company_relation_map)
			if relation:
				yk = "cy" if row.fiscal_year == fiscal_year else "py"
				results_map[relation]["Payable"][sup_name][yk] += row.total_amount or 0

	# 5. Build flat rows with default template for ALL categories
	rows = []
	for relation_type in RELATION_ORDER:
		if relation_type not in relation_company_groups:
			continue

		categories = results_map.get(relation_type, {})

		# Transaction categories
		for cat_name in RPT_TRANSACTION_CATEGORIES:
			if cat_name in categories:
				_append_category_rows(rows, relation_type, "Transaction", cat_name, categories[cat_name])
			else:
				# Template row with zero amounts
				rows.append({
					"relation_type": relation_type,
					"entry_type": "Transaction",
					"transaction_category": cat_name,
					"description": cat_name,
					"company_name": "",
					"current_year_amount": 0,
					"previous_year_amount": 0,
				})

		# Balance Outstanding categories
		for cat_name in RPT_BALANCE_CATEGORIES:
			if cat_name in categories:
				_append_category_rows(rows, relation_type, "Balance Outstanding", cat_name, categories[cat_name])
			else:
				rows.append({
					"relation_type": relation_type,
					"entry_type": "Balance Outstanding",
					"transaction_category": cat_name,
					"description": cat_name,
					"company_name": "",
					"current_year_amount": 0,
					"previous_year_amount": 0,
				})

	return rows


def _append_category_rows(rows, relation_type, entry_type, cat_name, companies_data):
	"""Append header + company sub-rows for a category with computed data."""
	company_list = list(companies_data.items())

	if len(company_list) == 1:
		comp_name, amounts = company_list[0]
		rows.append({
			"relation_type": relation_type,
			"entry_type": entry_type,
			"transaction_category": cat_name,
			"description": cat_name,
			"company_name": comp_name,
			"current_year_amount": amounts["cy"],
			"previous_year_amount": amounts["py"],
		})
	else:
		# Header row with totals
		total_cy = sum(a["cy"] for _, a in company_list)
		total_py = sum(a["py"] for _, a in company_list)
		rows.append({
			"relation_type": relation_type,
			"entry_type": entry_type,
			"transaction_category": cat_name,
			"description": cat_name,
			"company_name": "",
			"current_year_amount": total_cy,
			"previous_year_amount": total_py,
		})
		# Company sub-rows
		for comp_name, amounts in company_list:
			rows.append({
				"relation_type": relation_type,
				"entry_type": entry_type,
				"transaction_category": cat_name,
				"description": cat_name,
				"company_name": comp_name,
				"current_year_amount": amounts["cy"],
				"previous_year_amount": amounts["py"],
			})


def _find_relation_for_party(party_name, company_relation_map):
	"""
	Find the relation type for a customer/supplier name by matching
	against the company hierarchy relation map.
	"""
	if party_name in company_relation_map:
		return company_relation_map[party_name]

	party_lower = (party_name or "").lower()
	for comp_name, relation in company_relation_map.items():
		comp_lower = comp_name.lower()
		if comp_lower in party_lower or party_lower in comp_lower:
			return relation

	return None
