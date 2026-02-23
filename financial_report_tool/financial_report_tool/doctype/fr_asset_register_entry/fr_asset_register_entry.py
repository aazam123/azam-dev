# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
import calendar

class FRAssetRegisterEntry(Document):
	def before_insert(self):
		if not self.asset:
			asset = frappe.get_doc("FR Assets Master", {"assets_id": self.asset_id, 'company': self.company, 'subnumber': self.subnumber})
			if not asset:
				frappe.throw(f"No Assets Master found for Asset ID {self.asset_id} in Company {self.company} with Subnumber {self.subnumber}")
			else:
				self.asset = asset.name
		self.calculate_days_in_current_year()
		self.set_starting_book_value()
		self.calculation()

	def before_save(self):
		if not (self.asset_value and self.life_days and self.days_in_current_year):
			return

		self.calculate_days_in_current_year()
		self.set_starting_book_value()
		self.calculation()
	
	# 1️⃣ Calculate total days used in current fiscal year
	@frappe.whitelist()
	def calculate_days_in_current_year(self):
		if not self.ordinary_depreciation_start_date or not self.fiscal_year:
			return 0

		fy = frappe.get_doc("Fiscal Year", self.fiscal_year)
		fy_start = getdate(fy.year_start_date)
		fy_end = getdate(fy.year_end_date)
		dep_start = getdate(self.ordinary_depreciation_start_date)

		effective_start = dep_start if dep_start > fy_start else fy_start
		effective_end = getdate(self.sales_date) if self.sales_date else fy_end

		diff_in_days = (effective_end - effective_start).days + 1
		is_leap = calendar.isleap(fy_start.year) or calendar.isleap(fy_end.year)
		max_days = 366 if is_leap else 365
		self.days_in_current_year = min(diff_in_days, max_days)

		return self.days_in_current_year

	# 2️⃣ Set starting book value from last depreciation year
	def set_starting_book_value(self):
		"""
		Pull last year's closing value from the latest FR Asset Register Entry of the same asset_id before this fiscal year.
		"""
		last_entry = frappe.db.get_value(
			"FR Asset Register Entry",{"asset_id": self.asset_id,
				"fiscal_year": ["!=", self.fiscal_year]
			},
			["name", "ending_book_value", "fiscal_year"],
			order_by="creation desc",
			as_dict=True
		)

		if last_entry:
			self.starting_book_value = last_entry.ending_book_value
		else:
			self.starting_book_value = self.asset_value

	# 3️⃣ Main depreciation calculation logic
	def calculation(self):
		if self.life_days == 0:
			frappe.throw("Life Days cannot be zero while calculating depreciation.")

		# Get fiscal year range
		fy = frappe.get_doc("Fiscal Year", self.fiscal_year)
		fy_start = getdate(fy.year_start_date)
		fy_end = getdate(fy.year_end_date)

		# --- Basic Depreciation ---
		self.depreciation = round((self.asset_value * self.days_in_current_year) / self.life_days, 3)

		# --- Shift-based Additional Depreciation ---
		if self.shift == "1":
			self.additional = 0
		elif self.shift == "2":
			self.additional = round(self.depreciation * 0.5, 3)
		elif self.shift == "3":
			self.additional = round(self.depreciation * 1, 3)
		else:
			self.additional = 0

		# --- Total Depreciation ---
		self.total_depreciation = round(self.depreciation + self.additional, 3)

		# --- Accumulated Depreciation ---
		self.open_accumulated_depreciation = self.total_depreciation

		# Planned Depreciation Logic:
		dep_start = getdate(self.ordinary_depreciation_start_date)
		if fy_start <= dep_start <= fy_end:
			self.planned_depreciation = 0
		else:
			self.planned_depreciation = self.total_depreciation

		# --- Gross Block and Book Value Calculations ---
		self.close_gross_block = (self.open_gross_block or 0) + (self.transaction_acquisition_value or 0)
		self.close_accumulated_depreciation = self.open_accumulated_depreciation + self.planned_depreciation
		self.ending_book_value = self.close_gross_block - self.close_accumulated_depreciation


# import frappe
# from frappe.model.document import Document
# from frappe.utils import getdate
# import calendar

# class FRAssetRegisterEntry(Document):
# 	def before_insert(self):
# 		self.calculate_days_in_current_year()
# 		self.set_starting_book_value()
# 		self.calculation()

# 	def before_save(self):
# 		if not (self.asset_value and self.life_days and self.days_in_current_year):
# 			return

# 		self.calculate_days_in_current_year()
# 		self.set_starting_book_value()
# 		self.calculation()
	
# 	# 1️⃣ Calculate total days used in current fiscal year
# 	@frappe.whitelist()
# 	def calculate_days_in_current_year(self):
# 		if not self.ordinary_depreciation_start_date or not self.fiscal_year:
# 			return 0

# 		fy = frappe.get_doc("Fiscal Year", self.fiscal_year)
# 		fy_start = getdate(fy.year_start_date)
# 		fy_end = getdate(fy.year_end_date)
# 		dep_start = getdate(self.ordinary_depreciation_start_date)

# 		effective_start = dep_start if dep_start > fy_start else fy_start
# 		effective_end = getdate(self.sales_date) if self.sales_date else fy_end

# 		diff_in_days = (effective_end - effective_start).days + 1
# 		is_leap = calendar.isleap(fy_start.year) or calendar.isleap(fy_end.year)
# 		max_days = 366 if is_leap else 365
# 		self.days_in_current_year = min(diff_in_days, max_days)

# 		return self.days_in_current_year

# 	# 2️⃣ Set starting book value from last depreciation year
# 	def set_starting_book_value(self):
# 		"""
# 		Pull last year's closing value from the latest FR Asset Register Entry of the same asset_id before this fiscal year.
# 		"""
# 		last_entry = frappe.db.get_value(
# 			"FR Asset Register Entry",{"asset_id": self.asset_id,
# 				"fiscal_year": ["!=", self.fiscal_year]
# 			},
# 			["name", "ending_book_value", "fiscal_year"],
# 			order_by="creation desc",
# 			as_dict=True
# 		)

# 		if last_entry:
# 			self.starting_book_value = last_entry.ending_book_value
# 		else:
# 			self.starting_book_value = self.asset_value

# 	# 3️⃣ Main depreciation calculation logic
# 	def calculation(self):
# 		if self.life_days == 0:
# 			frappe.throw("Life Days cannot be zero while calculating depreciation.")

# 		# Get fiscal year range
# 		fy = frappe.get_doc("Fiscal Year", self.fiscal_year)
# 		fy_start = getdate(fy.year_start_date)
# 		fy_end = getdate(fy.year_end_date)

# 		# --- Basic Depreciation ---
# 		self.depreciation = round((self.asset_value * self.days_in_current_year) / self.life_days, 3)

# 		# --- Shift-based Additional Depreciation ---
# 		if self.shift == "1":
# 			self.additional = 0
# 		elif self.shift == "2":
# 			self.additional = round(self.depreciation * 0.5, 3)
# 		elif self.shift == "3":
# 			self.additional = round(self.depreciation * 1, 3)
# 		else:
# 			self.additional = 0

# 		# --- Total Depreciation ---
# 		self.total_depreciation = round(self.depreciation + self.additional, 3)

# 		# --- Accumulated Depreciation ---
# 		self.open_accumulated_depreciation = self.total_depreciation

# 		# Planned Depreciation Logic:
# 		dep_start = getdate(self.ordinary_depreciation_start_date)
# 		if fy_start <= dep_start <= fy_end:
# 			self.planned_depreciation = 0
# 		else:
# 			self.planned_depreciation = self.total_depreciation

# 		# --- Gross Block and Book Value Calculations ---
# 		self.close_gross_block = self.open_gross_block + (self.transaction_acquisition_value or 0)
# 		self.close_accumulated_depreciation = self.open_accumulated_depreciation + self.planned_depreciation
# 		self.ending_book_value = self.close_gross_block - self.close_accumulated_depreciation
