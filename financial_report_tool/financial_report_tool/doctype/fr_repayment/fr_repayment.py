# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
import math
from frappe.model.document import Document
from datetime import datetime
from dateutil.relativedelta import relativedelta

class FRRepayment(Document):
	@frappe.whitelist()
	def apply_adjustment(self, posting_date, amount):
		posting_date = frappe.utils.getdate(posting_date)
		adjustment_amount = float(amount or 0)

		if adjustment_amount <= 0:
			frappe.throw("Adjustment amount must be greater than zero")

		# Find the position to insert adjustment row
		insert_idx = 0
		for idx, row in enumerate(self.repayment_details):
			if frappe.utils.getdate(row.posting_date) > posting_date:
				break
			insert_idx = idx + 1

		fiscal_year = frappe.db.get_value("Fiscal Year", {
			"year_start_date": ["<=", posting_date],
			"year_end_date": [">=", posting_date]
		}, "name")

		balance_before = self.loan_amount
		for i in range(insert_idx):
			balance_before -= self.repayment_details[i].repayment_amount

		if adjustment_amount > balance_before:
			frappe.throw(f"Adjustment amount ({adjustment_amount}) cannot exceed remaining balance ({balance_before})")

		adjustment_row = {
			"posting_date": posting_date,
			"fiscal_year": fiscal_year,
			"month": posting_date.strftime("%B"),
			"repayment_amount": adjustment_amount,
			"balance_amount": max(0, balance_before - adjustment_amount),
			"is_adjustment": 1
		}

		new_details = []
		remaining = self.loan_amount

		for idx, row in enumerate(self.repayment_details):
			if idx == insert_idx:
				new_details.append(adjustment_row)
				remaining -= adjustment_amount

			if remaining <= 0:
				break

			row_amount = min(row.repayment_amount, remaining)
			if row_amount > 0:
				new_details.append({
					"posting_date": row.posting_date,
					"fiscal_year": row.fiscal_year,
					"month": row.month,
					"repayment_amount": row_amount,
					"balance_amount": max(0, remaining - row_amount),
					"is_adjustment": getattr(row, "is_adjustment", 0) or 0
				})
				remaining -= row_amount

		# If adjustment is at the end
		if insert_idx >= len(self.repayment_details) and remaining > 0:
			new_details.append(adjustment_row)

		# Update child table
		self.repayment_details.clear()
		for detail in new_details:
			self.append("repayment_details", detail)

		# Update end date
		if self.repayment_details:
			self.end_date = self.repayment_details[-1].posting_date

		self.flags.skip_regeneration = True
		self.save()
		

	def before_save(self):
		if not self.loan_amount or self.loan_amount <= 0:
			frappe.throw("Loan Amount must be greater than zero")

		if not self.start_date:
			frappe.throw("Start Date is required")

		# Skip regeneration if applying adjustment
		if self.flags.get("skip_regeneration"):
			return

		self.repayment_details.clear()
		start_date = datetime.strptime(str(self.start_date), "%Y-%m-%d")

		if self.type == "Monthly":
			installments = math.ceil(self.loan_amount / self.installment_amount)
			current_date = start_date
			remaining_amount = self.loan_amount

			for i in range(installments):
				fiscal_year = frappe.db.get_value("Fiscal Year",{"year_start_date": ["<=", current_date.date()],"year_end_date": [">=", current_date.date()]}, "name")
				repayment_amount = min(self.installment_amount, remaining_amount)
				self.append("repayment_details", {
					"posting_date": current_date.date(),
					"fiscal_year": fiscal_year,
					"month": current_date.strftime("%B"),
					"repayment_amount": repayment_amount,
					"balance_amount": remaining_amount - repayment_amount
				})
				remaining_amount -= repayment_amount

				# Move to next month
				current_date += relativedelta(months=1)

			# End date is the last installment date
			self.end_date = (current_date - relativedelta(months=1)).date()

		elif self.type == "Quarterly":
			installments = math.ceil(self.loan_amount / self.installment_amount)
			current_date = start_date
			remaining_amount = self.loan_amount

			for i in range(installments):
				fiscal_year = frappe.db.get_value("Fiscal Year",{"year_start_date": ["<=", current_date.date()],"year_end_date": [">=", current_date.date()]}, "name")
				repayment_amount = min(self.installment_amount, remaining_amount)
				self.append("repayment_details", {
					"posting_date": current_date.date(),
					"fiscal_year": fiscal_year,
					"month": current_date.strftime("%B"),
					"repayment_amount": repayment_amount,
					"balance_amount": remaining_amount - repayment_amount
				})
				remaining_amount -= repayment_amount

				# Move to next quarter
				current_date += relativedelta(months=3)

			# End date is the last installment date
			self.end_date = (current_date - relativedelta(months=3)).date()
		else:
			frappe.throw("Repayment Type must be either 'Monthly' or 'Quarterly'")