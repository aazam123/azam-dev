# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime, date, timedelta



class FRAccountReceivableEntry(Document):
	def before_insert(self):
		if self.report_type == "Yearly":
			customer_sum = frappe.db.sql("""
				SELECT COALESCE(SUM(amount_in_lc), 0) FROM `tabFR Account Receivable Entry` WHERE customer = %s
			""", (self.customer,))[0][0] or 0
			customer_sum += self.amount_in_lc
			self.nature = "Advance" if customer_sum < 0 else "Receivable"

	def before_save(self):
		if self.gl_account:
			if str(self.gl_account).startswith("1"):
				self.tb_nature = "Advance"
			elif str(self.gl_account).startswith("2"):
				self.tb_nature = "Receivable"

		if self.nature == "Receivable":
			# if isinstance(self.posting_date, str):
			# 	date_obj = datetime.strptime(self.posting_date, "%Y-%m-%d")
			# else:
			# 	date_obj = self.posting_date

			# month = date_obj.strftime("%B")
			if not self.closing_ex_rate:
				self.closing_ex_rate = frappe.get_value("FR Foreign Exchange Rate",{"from_currency": self.currency, "to_currency": "INR", "month": "April", "fiscal_year": self.fiscal_year}, 'closing_rate') or 0
			self.restated_value = self.amount_in_dc * self.closing_ex_rate
			self.gainloss = self.amount_in_lc - self.restated_value

		if self.due_days == 0:
			self.ageing = "Not Due"
		elif 0 < self.due_days <= 180:
			self.ageing = "0-6 Months"
		elif 180 < self.due_days <= 365:
			self.ageing = "6-12 Months"
		elif 365 < self.due_days <= 730:
			self.ageing = "1-2 Years"
		elif 730 < self.due_days <= 1095:
			self.ageing = "2-3 Years"
		else:
			self.ageing = "More Than 3 Years"

	def on_update(self):
		if self.report_type == "Yearly":
			customer_sum = frappe.db.sql("""
				SELECT COALESCE(SUM(amount_in_lc), 0) FROM `tabFR Account Receivable Entry` WHERE customer = %s
			""", (self.customer,))[0][0] or 0
			self.nature = "Advance" if customer_sum < 0 else "Receivable"
		elif self.report_type == "Monthly":
			if self.special_gl_ind == "A" or self.special_gl_ind == "B":
				self.nature = "Advance"
			else:
				self.nature = "Receivable"