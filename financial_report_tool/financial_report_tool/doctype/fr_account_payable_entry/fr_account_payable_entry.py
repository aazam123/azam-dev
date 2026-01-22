# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FRAccountPayableEntry(Document):
	def set_employee_grouping(self):
		if self.currency != "INR" and self.ap == "Advance":
			self.grouping = "Employee Foreign Advance"
		elif self.currency == "INR" and self.ap == "Advance":
			self.grouping = "Employee Advance"
		elif self.currency == "INR" and self.ap == "Payable":
			self.grouping = "Employee Payable"
		elif self.currency != "INR" and self.ap == "Payable":
			self.grouping = "Employee Foreign Payable"
	
	def before_save(self):
		self.ap = "Payable" if self.amount_in_lc < 0 else "Advance"
		
		if self.document_type in ("AB", "SA"):
			self.nature = "Clearing Document"
		elif self.document_type == "EE":
			self.nature = "Employee"
			self.set_employee_grouping()
		elif self.document_type in ("KR", "RE"):
			self.nature = "Invoicing Document"
		elif self.document_type in ("KZ", "FP", "KG"):
			self.nature = "Payment"
		else:
			self.nature = "Payable" if self.amount_in_lc < 0 else "Advance"

		if self.ap == "Advance":
			if self.special_gl_ind:
				sp_gl_grouping = frappe.get_all("Special GL Indicator Grouping", {"parent": self.company, "special_gl_indicator": self.special_gl_ind}, ["nature", "e_ne", "currency", "grouping"])
				for sp_grouping in sp_gl_grouping:
					if sp_grouping:
						nature, e_ne, currency, grouping = sp_grouping.get("nature"), sp_grouping.get("e_ne"), sp_grouping.get("currency"), sp_grouping.get("grouping")
						if not nature:
							self.grouping = grouping
						else:
							if currency:
								if e_ne == 'Not Equals' and self.currency != currency and self.ap == nature:
									self.grouping = grouping
								elif e_ne == 'Equals' and self.currency == currency and self.ap == nature:
									self.grouping = grouping
							else:
								if self.ap == nature:
									self.grouping = grouping
			else:
				po_series = frappe.get_all("Purchase Order Series For Grouping", filters={"parent": self.company}, fields=["po_series_start_from", "grouping", "ap"])
				for po_s in po_series:
					if str(self.purchase_order).startswith(po_s.po_series_start_from) and self.ap == po_s.ap:
						self.grouping = po_s.grouping
						break
		elif self.ap == "Payable":
			if self.purchase_order:
				po_series = frappe.get_all("Purchase Order Series For Grouping", filters={"parent": self.company}, fields=["po_series_start_from", "grouping", "ap"])
				for po_s in po_series:
					if str(self.purchase_order).startswith(po_s.po_series_start_from) and self.ap == po_s.ap:
						self.grouping = po_s.grouping
						break
			else:
				sp_gl_grouping = frappe.get_all("Special GL Indicator Grouping", {"parent": self.company, "special_gl_indicator": self.special_gl_ind}, ["nature", "e_ne", "currency", "grouping"])
				for sp_grouping in sp_gl_grouping:
					if sp_grouping:
						nature, e_ne, currency, grouping = sp_grouping.get("nature"), sp_grouping.get("e_ne"), sp_grouping.get("currency"), sp_grouping.get("grouping")
						if not nature:
							self.grouping = grouping
						else:
							if currency:
								if e_ne == 'Not Equals' and self.currency != currency and self.ap == nature:
									self.grouping = grouping
								elif e_ne == 'Equals' and self.currency == currency and self.ap == nature:
									self.grouping = grouping
							else:
								if self.ap == nature:
									self.grouping = grouping

		voucher_series = frappe.get_all("Vendor Series For Nature", filters={"parent": self.company}, fields=["series_start_from", "nature"])
		for v_series in voucher_series:
			if str(self.supplier).startswith(v_series.series_start_from):
				self.nature = v_series.nature
				if self.nature == "Employee" and not self.grouping:
					self.set_employee_grouping()
				break

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
		elif self.due_days > 1095:
			self.ageing = "More Than 3 Years"
		else:
			self.ageing = "Not Due"

		if not self.closing_exchange_rate:
			closing_exchange_rate = frappe.get_value("FR Foreign Exchange Rate",{"from_currency": self.currency, "to_currency": "INR", "month": "April", "fiscal_year": self.fiscal_year}, 'closing_rate') or 0
			self.closing_exchange_rate = closing_exchange_rate if closing_exchange_rate else 1
		
		if self.closing_exchange_rate:
			self.restated_value = self.amount_in_dc * self.closing_exchange_rate
			self.gainloss = self.amount_in_lc - self.restated_value

		if not self.nature:
			self.nature == self.ap
		
		gl_account_grouping = frappe.get_value("GL Account For Grouping",{"parent": self.company, "gl_account": self.reconciliation_account},"grouping")	
		if gl_account_grouping and not self.grouping:
			self.grouping = gl_account_grouping

		if self.special_gl_ind == "D":
			self.nature = "Deposit"
			self.grouping = "Deposit"	

		if not self.grouping:
			if self.ap == "Advance":
				self.grouping = "Service Advance"
			elif self.ap == "Payable":
				self.grouping = "Service Payable"
			self.remark = "No Grouping Match"

# import frappe
# from frappe.model.document import Document


# class FRAccountPayableEntry(Document):
# 	def set_employee_grouping(self):
# 		if self.currency != "INR" and self.ap == "Advance":
# 			self.grouping = "Employee Foreign Advance"
# 		elif self.currency == "INR" and self.ap == "Advance":
# 			self.grouping = "Employee Advance"
# 		elif self.currency == "INR" and self.ap == "Payable":
# 			self.grouping = "Employee Payable"
# 		elif self.currency != "INR" and self.ap == "Payable":
# 			self.grouping = "Employee Foreign Payable"
	
# 	def before_save(self):
# 		self.ap = "Payable" if self.amount_in_lc < 0 else "Advance"
		
# 		if self.document_type in ("AB", "SA"):
# 			self.nature = "Clearing Document"
# 		elif self.document_type == "EE":
# 			self.nature = "Employee"
# 			self.set_employee_grouping()
# 		elif self.document_type in ("KR", "RE"):
# 			self.nature = "Invoicing Document"
# 		elif self.document_type in ("KZ", "FP", "KG"):
# 			self.nature = "Payment"
# 		else:
# 			self.nature = "Payable" if self.amount_in_lc < 0 else "Advance"

# 		if self.special_gl_ind == "D":
# 			self.nature = "Deposit"
# 			self.grouping = "Deposit"

# 		sp_gl_grouping = frappe.get_all("Special GL Indicator Grouping", {"parent": self.company, "special_gl_indicator": self.special_gl_ind}, ["nature", "e_ne", "currency", "grouping"])
# 		for sp_grouping in sp_gl_grouping:
# 			if sp_grouping:
# 				nature, e_ne, currency, grouping = sp_grouping.get("nature"), sp_grouping.get("e_ne"), sp_grouping.get("currency"), sp_grouping.get("grouping")
# 				if not nature:
# 					self.grouping = grouping
# 				else:
# 					if currency:
# 						if e_ne == 'Not Equals' and self.currency != currency and self.ap == nature:
# 							self.grouping = grouping
# 						elif e_ne == 'Equals' and self.currency == currency and self.ap == nature:
# 							self.grouping = grouping
# 					else:
# 						if self.ap == nature:
# 							self.grouping = grouping

# 		voucher_series = frappe.get_all("Vendor Series For Nature", filters={"parent": self.company}, fields=["series_start_from", "nature"])
# 		for v_series in voucher_series:
# 			if str(self.supplier).startswith(v_series.series_start_from):
# 				self.nature = v_series.nature
# 				if self.nature == "Employee":
# 					self.set_employee_grouping()
# 				break

# 		if not self.grouping:
# 			po_series = frappe.get_all("Purchase Order Series For Grouping", filters={"parent": self.company}, fields=["po_series_start_from", "grouping", "ap"])
# 			for po_s in po_series:
# 				if str(self.purchase_order).startswith(po_s.po_series_start_from) and self.ap == po_s.ap:
# 					self.grouping = po_s.grouping
# 					break

# 		if self.due_days == 0:
# 			self.ageing = "Not Due"
# 		elif 0 < self.due_days <= 180:
# 			self.ageing = "0-6 Months"
# 		elif 180 < self.due_days <= 365:
# 			self.ageing = "6-12 Months"
# 		elif 365 < self.due_days <= 730:
# 			self.ageing = "1-2 Years"
# 		elif 730 < self.due_days <= 1095:
# 			self.ageing = "2-3 Years"
# 		elif self.due_days > 1095:
# 			self.ageing = "More Than 3 Years"
# 		else:
# 			self.ageing = "Not Due"

# 		if not self.closing_exchange_rate:
# 			closing_exchange_rate = frappe.get_value("FR Foreign Exchange Rate",{"from_currency": self.currency, "to_currency": "INR", "month": "April", "fiscal_year": self.fiscal_year}, 'closing_rate') or 0
# 			self.closing_exchange_rate = closing_exchange_rate if closing_exchange_rate else 1
		
# 		if self.closing_exchange_rate:
# 			self.restated_value = self.amount_in_dc * self.closing_exchange_rate
# 			self.gainloss = self.amount_in_lc - self.restated_value

# 		if not self.nature:
# 			self.nature == self.ap
		
# 		gl_account_grouping = frappe.get_value("GL Account For Grouping",{"parent": self.company, "gl_account": self.reconciliation_account},"grouping")	
# 		if gl_account_grouping:
# 			self.grouping = gl_account_grouping	

# 		if not self.grouping:
# 			if self.ap == "Advance":
# 				self.grouping = "Service Advance"
# 			elif self.ap == "Payable":
# 				self.grouping = "Service Payable"
# 			self.remark = "No Grouping Match"