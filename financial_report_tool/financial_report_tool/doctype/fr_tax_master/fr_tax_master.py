# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.model.document import Document


class FRTaxMaster(Document):
	pass
	# def before_save(self):
	# 	self.set_currency()
	# 	self.set_profit_before_tax()

	# def set_currency(self):
	# 	# Currency Type na base parthi currency set karo
	# 	if self.currency_type == "Indian":
	# 		self.currency = "INR"
	# 	else:
	# 		# Company ni default currency fetch karo
	# 		self.currency = frappe.db.get_value("Company", self.company, "default_currency")

	# def set_profit_before_tax(self):
	# 	# Company, Fiscal Year ane Currency na base parthi Yearly Financial Report fetch karo
	# 	financial_report = frappe.get_value(
	# 		"FR Financial Report",
	# 		filters={"company": self.company, "report_type": "Yearly", "fiscal_year": self.fiscal_year, "currency": self.currency},
	# 		fieldname="name"
	# 	)

	# 	if not financial_report:
	# 		return

	# 	# Financial Report Details ma thi Profit & Loss section ni table_data fetch karo
	# 	table_data = frappe.get_value(
	# 		"FR Financial Report Details",
	# 		{"parent": financial_report, "parenttype": "FR Financial Report", "section_type": "Profit & Loss"},
	# 		"table_data"
	# 	)

	# 	# table_data JSON ma thi "Profit before tax (I-II)" ni current_month_amount fetch kari ne set karo
	# 	if table_data:
	# 		data = json.loads(table_data)
	# 		for row in data:
	# 			if row.get("account") == "Profit before tax (I-II)":
	# 				self.profit_before_tax = row.get("current_month_amount")
	# 				break
