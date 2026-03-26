# Copyright (c) 2026, Hybrowlabs Pvt Ltd and Contributors
# See license.txt

# import frappe
from frappe.tests.utils import FrappeTestCase


class TestFRConsoleFinancialReport(FrappeTestCase):
	pass

# # Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# # For license information, please see license.txt

# import re
# import os
# import math
# import json
# import frappe
# import openpyxl
# import calendar
# from frappe.utils import flt
# from bs4 import BeautifulSoup
# from collections import defaultdict
# from frappe.utils import get_site_path, now_datetime
# from datetime import datetime, timedelta, date
# from frappe.model.document import Document
# from openpyxl.utils import get_column_letter
# from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

# def do_generate_report(docname):
# 	doc = frappe.get_doc("Consol Financial Report", docname)
# 	frappe.publish_progress(5, title="Initializing consol report generation...")
# 	doc._generate_report_internal()
# 	frappe.publish_progress(100, title="Report generated successfully!")

# 	frappe.msgprint(f"✅ Consol Financial Report {docname} generated successfully.")
# 	frappe.db.commit()

# class FRConsoleFinancialReport(Document):
# 	def _init_report_caches(self):
# 		"""Initialize instance-level caches for report generation to avoid repeated DB queries."""
# 		if getattr(self, '_caches_initialized', False):
# 			return

# 		# Cache singleton/static values fetched repeatedly
# 		self._erp_type = frappe.get_single_value("FR Financial Settings", "erp_type") or "SAP"
# 		self._closing_month = frappe.get_single_value("FR Financial Settings", "closing_month")

# 		if not hasattr(self, "_report_cache"):
# 			self._report_cache = {}

# 		self._other_equity_total_cache = {}
# 		self._other_equity_full_cache = {}
# 		self._pnl_cache = {}
# 		self._inventory_cache = {}
# 		self._fy_dates_cache = {}
# 		self._month_date_range_cache = {}
# 		self._fx_rate_cache = {}
# 		self._sum_grouping_cache = {}
# 		self._sum_group_amt_cache = {}
# 		self._fr_particular_cache = {}
# 		self._fr_section_cache = {}
# 		self._standalone_group_cache = {}
# 		self._secondary_groups_cache = {}
# 		self._hg_sec_group_cache = {}
# 		self._gl_mapping_cache = {}
# 		self._gl_accounts_for_particular_cache = {}

# 		# Pre-compute note numbers for schedules
# 		self._note_number_map = {}
# 		note_counter = 4
# 		# Bulk-fetch all FR Section is_schedule values needed
# 		section_names = [i.section for i in self.financial_report_details if i.section_type == "Consolidation Note" and i.section]
# 		if section_names:
# 			section_schedule_data = frappe.get_all("FR Section", filters={"name": ["in", section_names]}, fields=["name", "is_schedule"])
# 			section_schedule_map = {s.name: s.is_schedule for s in section_schedule_data}
# 		else:
# 			section_schedule_map = {}

# 		for i in self.financial_report_details:
# 			if i.section_type == "Consolidation Note" and i.section:
# 				if section_schedule_map.get(i.section) == 1:
# 					self._note_number_map[i.section] = str(note_counter)
# 					note_counter += 1

# 		# Pre-fetch FR Section data for _generate_report_internal to avoid per-row queries
# 		if section_names:
# 			section_details = frappe.get_all("FR Section", filters={"name": ["in", section_names]},
# 				fields=["name", "section_type_description", "fetch_data_from_trial_balance", "primary_consolidation_group", "note_type", "is_schedule"])
# 			self._fr_section_detail_cache = {s.name: s for s in section_details}
# 		else:
# 			self._fr_section_detail_cache = {}

# 		# Cache for parsed BS/PL table data JSON
# 		self._bs_table_data_parsed = None
# 		self._pl_table_data_parsed = None

# 		self._caches_initialized = True

# 	def _get_cached_companies(self):
# 		if not hasattr(self, "_companies"):
# 			self._companies = {}
# 		company_names = frappe.get_all("Company", pluck="name")
# 		for name in company_names:
# 			if name not in self._companies:
# 				self._companies[name] = frappe.get_doc("Company", name)

# 		return list(self._companies.values())

# 	def _get_cached_fr_particular(self, name):
# 		"""Instance-level cached FR Particular doc fetch."""
# 		if name not in self._fr_particular_cache:
# 			self._fr_particular_cache[name] = frappe.get_doc("FR Particular", name)
# 		return self._fr_particular_cache[name]

# 	def _get_cached_fr_section(self, name):
# 		"""Instance-level cached FR Section doc fetch."""
# 		if name not in self._fr_section_cache:
# 			self._fr_section_cache[name] = frappe.get_doc("FR Section", name)
# 		return self._fr_section_cache[name]

# 	def _get_cached_standalone_group(self, name):
# 		"""Instance-level cached Standalone Group value fetch."""
# 		if name not in self._standalone_group_cache:
# 			self._standalone_group_cache[name] = frappe.get_value("Standalone Group", name, ["show_reversed_value", "group_type", "report_type"], as_dict=True)
# 		return self._standalone_group_cache[name]

# 	def _get_cached_secondary_groups(self, primary_group):
# 		"""Instance-level cached secondary groups for a primary group."""
# 		if primary_group not in self._secondary_groups_cache:
# 			self._secondary_groups_cache[primary_group] = sorted(set(
# 				g for g in frappe.get_list("GL Group Mapping", {"primary_group": primary_group}, pluck="secondary_group") if g
# 			))
# 		return self._secondary_groups_cache[primary_group]

# 	def _get_cached_hg_sec_groups(self, company, primary_group, secondary_group):
# 		"""Instance-level cached higher secondary group lookup."""
# 		cache_key = (primary_group, secondary_group)
# 		if cache_key not in self._hg_sec_group_cache:
# 			self._hg_sec_group_cache[cache_key] = frappe.get_all(
# 				"GL Group Mapping",
# 				{"company": company, "primary_group": primary_group, "secondary_group": secondary_group, "higher_secondary_group": ["!=", None]},
# 				pluck="higher_secondary_group", distinct=True
# 			)
# 		return self._hg_sec_group_cache[cache_key]

# 	def _get_gl_accounts_for_mappings(self, company, mappings, report_type=None):
# 		"""Cached GL account fetch for primary_and_secondary_group_mapping entries."""
# 		if not mappings:
# 			return []
# 		rt = report_type or self.report_type
# 		gl_accounts = []
# 		for g in mappings:
# 			cache_key = (company, rt, g.primary_group, g.secondary_group)
# 			if cache_key not in self._gl_mapping_cache:
# 				self._gl_mapping_cache[cache_key] = frappe.get_list(
# 					"GL Group Mapping",
# 					{"company": company, "report_type": rt, "primary_group": g.primary_group, "secondary_group": g.secondary_group},
# 					pluck='gl_account'
# 				)
# 			gl_accounts.extend(self._gl_mapping_cache[cache_key])
# 		return gl_accounts

# 	def _get_other_equity_total_only(self, company, field):
# 		cache_key = f"{company}_{field}"

# 		if cache_key in self._other_equity_total_cache:
# 			return self._other_equity_total_cache[cache_key]

# 		# ⚡ MINIMAL CALCULATION (NO recursion)
# 		net_current, net_prev, net_prev_year = self.get_monthly_profit_and_loss_data(
# 			None, fetch_for_other_equity=True
# 		)

# 		# Map fields
# 		field_map = {
# 			"grand_total_current": net_current,
# 			"grand_total_previous": net_prev,
# 			"grand_total_prev_year": net_prev_year,
# 		}

# 		val = field_map.get(field, 0)

# 		self._other_equity_total_cache[cache_key] = val
# 		return val

# 	def before_save(self):
# 		self.update_consolidation_note_numbers()
# 		companies = self._get_cached_companies()
# 		foreign_exchange_rate = ""
# 		for i in self.financial_report_details:
# 			if i.section_type == "Consolidation Note" and i.section:
# 				i.section_name = frappe.get_value("FR Section", i.section, 'section_type_name')
		
# 		for company_doc in companies:
# 			default_currency = company_doc.default_currency
# 			cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 			current_cls_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, 'closing_rate')
# 			previous_cls_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, 'closing_rate')
# 			previous_year_cls_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'closing_rate')
			
# 			current_avg_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, 'average_rate')
# 			previous_avg_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, 'average_rate')
# 			previous_year_avg_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'average_rate')

# 			# Build HTML table
# 			foreign_exchange_rate += f"""
# 				<table style="width:60%; border-collapse: collapse; text-align:center; font-size:13px; margin:-35px 0;">
# 					<thead>
# 						<tr style = "border-bottom:2px solid #222;">
# 							<th style="border:1px solid #ddd; padding:4px;">Month</th>
# 							<th style="border:1px solid #ddd; padding:4px;">Year</th>
# 							<th style="border:1px solid #ddd; padding:4px;">Closing Rate</th>
# 							<th style="border:1px solid #ddd; padding:4px;">Average Rate</th>
# 						</tr>
# 					</thead>
# 					<tbody>
# 						<tr>
# 							<td style="border:1px solid #ddd; padding:4px;"><b>{self.current_month}</b></td>
# 							<td style="border:1px solid #ddd; padding:4px;">{self.fiscal_year}</td>
# 							<td style="border:1px solid #ddd; padding:4px;">{current_cls_fx or "-"}</td>
# 							<td style="border:1px solid #ddd; padding:4px;">{current_avg_fx or "-"}</td>
# 						</tr>
# 						<tr>
# 							<td style="border:1px solid #ddd; padding:4px;"><b>{self.previous_month}</b></td>
# 							<td style="border:1px solid #ddd; padding:4px;">{self.fiscal_year}</td>
# 							<td style="border:1px solid #ddd; padding:4px;">{previous_cls_fx or "-"}</td>
# 							<td style="border:1px solid #ddd; padding:4px;">{previous_avg_fx or "-"}</td>
# 						</tr>
# 						<tr>
# 							<td style="border:1px solid #ddd; padding:4px;"><b>{cls_month}</b></td>
# 							<td style="border:1px solid #ddd; padding:4px;">{self.previous_fiscal_year}</td>
# 							<td style="border:1px solid #ddd; padding:4px;">{previous_year_cls_fx or "-"}</td>
# 							<td style="border:1px solid #ddd; padding:4px;">{previous_year_avg_fx or "-"}</td>
# 						</tr>
# 					</tbody>
# 				</table>
# 			"""
# 		self.foreign_exchange_rate = foreign_exchange_rate

# 	def fetch_equity_data(self, holding_company, company, date_filter):
# 		return frappe.get_all(
# 			"FR Investment Entry",
# 			filters={"company": company,"holding_company": holding_company,"category": "Equity Shares", "capital_type": "Issued Capital", "posting_date": date_filter},
# 			fields=["face_value", "sum(no_of_shares) as no_of_shares", "sum(investment_value) as investment_value", "sum(investment_value_fc) as investment_value_fc"]
# 		)

# 	def generate_note_id(self, note_no, note_title):
# 		"""Generate consistent ID for note anchors"""
# 		if not note_no or not note_title:
# 			return ""
# 		# Clean the title for use as ID (remove special chars, replace spaces with underscores)
# 		clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', note_title).strip()
# 		clean_title = re.sub(r'\s+', '_', clean_title).lower()
# 		return f"note_{note_no}_{clean_title}"

# 	def get_note_number_for_schedule(self, schedule_name):
# 		"""Get the note number for a given schedule"""
# 		if not schedule_name:
# 			return ""
# 		# Use pre-computed map if caches are initialized
# 		if getattr(self, '_caches_initialized', False):
# 			return self._note_number_map.get(schedule_name, "")

# 		note_counter = 4
# 		for i in self.financial_report_details:
# 			if i.section_type == "Consolidation Note" and i.section:
# 				# Check if the FR Section has is_schedule = 1
# 				section_data = frappe.db.get_value("FR Section", i.section, ["is_schedule"], as_dict=True)
# 				if section_data and section_data.is_schedule == 1:
# 					if i.section == schedule_name:
# 						return str(note_counter)
# 					note_counter += 1
# 		return ""

# 	def update_consolidation_note_numbers(self):
# 		"""Update note numbers for consolidation notes starting from 4"""
# 		note_counter = 4
# 		for i in self.financial_report_details:
# 			if i.section_type == "Consolidation Note" and i.section:
# 				# Check if the FR Section has is_schedule = 1
# 				section_data = frappe.db.get_value("FR Section", i.section, ["is_schedule"], as_dict=True)
# 				if section_data and section_data.is_schedule == 1:
# 					i.note_no = str(note_counter)
# 					note_counter += 1
# 				else:
# 					i.note_no = ""
# 			else:
# 				i.note_no = ""

# 	def on_update_after_submit(self):
# 		"""Update note numbers when rows are modified after submit"""
# 		self.update_consolidation_note_numbers()
# 		self.save()

# 	@frappe.whitelist()
# 	def update_note_numbers(self):
# 		"""Update note numbers for consolidation notes"""
# 		self.update_consolidation_note_numbers()
# 		self.save()
# 		frappe.msgprint("Note numbers updated successfully!")

# 	def get_month_start_date(self, month_name):
# 		fiscal_doc = frappe.get_doc("Fiscal Year", self.fiscal_year)
# 		fiscal_start = fiscal_doc.year_start_date
# 		fiscal_end = fiscal_doc.year_end_date

# 		# Handle full and abbreviated month names
# 		month_name = month_name.strip()
# 		if month_name in calendar.month_name:
# 			month_index = list(calendar.month_name).index(month_name)
# 		elif month_name in calendar.month_abbr:
# 			month_index = list(calendar.month_abbr).index(month_name)
# 		else:
# 			frappe.throw(f"Invalid month name: {month_name}")

# 		if month_index == 0:
# 			frappe.throw(f"Invalid month name: {month_name}")

# 		try_date = date(fiscal_start.year, month_index, 1)
# 		if fiscal_start <= try_date <= fiscal_end:
# 			return try_date

# 		try_date = date(fiscal_end.year, month_index, 1)
# 		if fiscal_start <= try_date <= fiscal_end:
# 			return try_date

# 		frappe.throw(f"Month '{month_name}' is not within the fiscal year range {fiscal_start} to {fiscal_end}")

# 	def get_month_end_date(self, month_str):
# 		start = self.get_month_start_date(month_str)
# 		next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
# 		return (next_month - timedelta(days=1))

# 	def get_same_month_last_year_start(self):
# 		start = self.get_month_start_date(self.current_month)
# 		return start.replace(year=start.year - 1)

# 	def get_same_month_last_year_end(self):
# 		end = self.get_month_end_date(self.current_month)
# 		return end.replace(year=end.year - 1)

# 	def get_fiscal_year_by_date(self, date_str):
# 		"""Get fiscal year name by date"""
# 		if isinstance(date_str, str):
# 			date_obj = datetime.strptime(date_str, "%Y-%m-%d")
# 		else:
# 			date_obj = date_str
		
# 		formatted_date = date_obj.strftime("%Y-%m-%d")
# 		fiscal_year = frappe.db.exists("Fiscal Year", {'year_start_date': ["<=", formatted_date], 'year_end_date': [">=", formatted_date]})
# 		return fiscal_year

# 	def get_fiscal_year_before(self, fiscal_year_name):
# 		"""Get the fiscal year that comes before the given fiscal year"""
# 		if not fiscal_year_name:
# 			return None
		
# 		fiscal_year_doc = frappe.get_doc("Fiscal Year", fiscal_year_name)
# 		previous_fiscal_year = frappe.db.exists("Fiscal Year", {'year_end_date': fiscal_year_doc.year_start_date})
# 		return previous_fiscal_year

# 	def get_current_and_prevous_year_date(self):
# 		if isinstance(self.current_year_ending_date, str):
# 			current_year_date_obj = datetime.strptime(self.current_year_ending_date, "%Y-%m-%d")
# 		else:
# 			current_year_date_obj = self.current_year_ending_date

# 		if isinstance(self.previous_year_ending_date, str):
# 			previous_year_date_obj = datetime.strptime(self.previous_year_ending_date, "%Y-%m-%d")
# 		else:
# 			previous_year_date_obj = self.previous_year_ending_date

# 		current_year_date = current_year_date_obj.strftime("%d-%m-%Y")
# 		previous_year_date = previous_year_date_obj.strftime("%d-%m-%Y")
# 		return current_year_date, previous_year_date

# 	def get_previous_year_cls_month(self, year):
# 		month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		previous_year = frappe.get_value("FR Previous Fiscal Year",{"current_fiscal_year": year},"previous_fiscal_year")
# 		return month, previous_year

# 	def get_previous_fiscal_year(self, fiscal_year):
# 		"""Get the previous fiscal year for a given fiscal year."""
# 		return frappe.get_value(
# 			"FR Previous Fiscal Year",
# 			{"current_fiscal_year": fiscal_year},
# 			"previous_fiscal_year"
# 		)

# 	def get_fx_rate(self, default_currency, month, fiscal_year, field_name):
# 		if default_currency == self.currency:
# 			return 1
# 		if not field_name:
# 			return 1
# 		if getattr(self, '_caches_initialized', False):
# 			cache_key = (default_currency, month, fiscal_year, field_name)
# 			if cache_key not in self._fx_rate_cache:
# 				self._fx_rate_cache[cache_key] = frappe.get_value("FR Foreign Exchange Rate",{"from_currency": default_currency, "to_currency": self.currency, "month": month,"fiscal_year": fiscal_year,},field_name) or 0
# 			return self._fx_rate_cache[cache_key]
# 		return frappe.get_value("FR Foreign Exchange Rate",{"from_currency": default_currency, "to_currency": self.currency, "month": month,"fiscal_year": fiscal_year,},field_name) or 0

# 	def get_erp_type(self):
# 		"""Get ERP type from settings - returns 'SAP' or 'ERPNext'"""
# 		if getattr(self, '_caches_initialized', False):
# 			return self._erp_type
# 		return frappe.get_single_value("FR Financial Settings", "erp_type") or "SAP"

# 	def get_fiscal_year_dates(self, fiscal_year):
# 		"""Get start and end dates for a fiscal year"""
# 		if getattr(self, '_caches_initialized', False):
# 			if fiscal_year not in self._fy_dates_cache:
# 				fy = frappe.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"], as_dict=True)
# 				self._fy_dates_cache[fiscal_year] = (fy.year_start_date, fy.year_end_date) if fy else (None, None)
# 			return self._fy_dates_cache[fiscal_year]
# 		fy = frappe.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"], as_dict=True)
# 		if fy:
# 			return fy.year_start_date, fy.year_end_date
# 		return None, None

# 	_MONTH_NUM_MAP = {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
# 					'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12}

# 	def get_month_date_range(self, month, fiscal_year):
# 		"""Get date range for a specific month in a fiscal year"""
# 		if getattr(self, '_caches_initialized', False):
# 			cache_key = (month, fiscal_year)
# 			if cache_key in self._month_date_range_cache:
# 				return self._month_date_range_cache[cache_key]

# 		fy_start, fy_end = self.get_fiscal_year_dates(fiscal_year)
# 		if not fy_start:
# 			result = (None, None)
# 			if getattr(self, '_caches_initialized', False):
# 				self._month_date_range_cache[cache_key] = result
# 			return result

# 		m = self._MONTH_NUM_MAP.get(month, 1)
# 		# Determine year based on fiscal year structure
# 		if m >= fy_start.month:
# 			year = fy_start.year
# 		else:
# 			year = fy_end.year

# 		last_day = calendar.monthrange(year, m)[1]
# 		start_date = date(year, m, 1)
# 		end_date = date(year, m, last_day)
# 		result = (start_date, end_date)
# 		if getattr(self, '_caches_initialized', False):
# 			self._month_date_range_cache[(month, fiscal_year)] = result
# 		return result

# 	def sum_group_amt(self, company, primary_group, group, year, hg_sec_group=""):
# 		if getattr(self, '_caches_initialized', False):
# 			cache_key = ("sum_group_amt", primary_group, group, year, hg_sec_group)
# 			if cache_key in self._sum_group_amt_cache:
# 				return self._sum_group_amt_cache[cache_key]

# 		filters = {"company": company,"report_type": self.report_type,"primary_group": primary_group,"secondary_group": group, "higher_secondary_group": hg_sec_group}
# 		gl_accounts = frappe.get_list("GL Group Mapping", filters, pluck="gl_account")
# 		if not gl_accounts:
# 			result = 0
# 		else:
# 			erp_type = self.get_erp_type()
# 			if erp_type == "ERPNext":
# 				fy_start, fy_end = self.get_fiscal_year_dates(year)
# 				if not fy_start:
# 					result = 0
# 				else:
# 					query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN ({','.join(['%s']*len(gl_accounts))})"
# 					result = (frappe.db.sql(query, [company, fy_start, fy_end]+gl_accounts)[0][0] or 0) / 100000
# 			else:
# 				query = f"SELECT SUM(amount) FROM `tabFR Trial Balance Entry` WHERE company=%s AND fiscal_year=%s AND gl_account IN ({','.join(['%s']*len(gl_accounts))})"
# 				result = (frappe.db.sql(query, [company, year]+gl_accounts)[0][0] or 0) / 100000

# 		if getattr(self, '_caches_initialized', False):
# 			self._sum_group_amt_cache[cache_key] = result
# 		return result

# 	def get_sum_grouping_amount(self, company, primary_group, group, month, year, is_ftm=False, hg_sec_group=""):
# 		if getattr(self, '_caches_initialized', False):
# 			cache_key = ("sum_grouping", primary_group, group, month, year, is_ftm, hg_sec_group)
# 			if cache_key in self._sum_grouping_cache:
# 				return self._sum_grouping_cache[cache_key]

# 		filters = {"company": company, "report_type": self.report_type,"primary_group": primary_group,"secondary_group": group, "higher_secondary_group": hg_sec_group}
# 		gl_accounts = frappe.get_list("GL Group Mapping", filters, pluck="gl_account")
# 		if not gl_accounts:
# 			result = 0
# 		else:
# 			erp_type = self.get_erp_type()
# 			if erp_type == "ERPNext":
# 				start_date, end_date = self.get_month_date_range(month, year)
# 				if not start_date:
# 					result = 0
# 				else:
# 					query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN ({','.join(['%s']*len(gl_accounts))})"
# 					result = round((frappe.db.sql(query, [company, start_date, end_date]+gl_accounts)[0][0] or 0) / 100000, self.show_decimal_value)
# 			else:
# 				field = "amount" if is_ftm else "uploaded_amount"
# 				query = f"SELECT SUM({field}) FROM `tabFR Trial Balance Entry` WHERE company=%s AND fiscal_year=%s AND gl_account IN ({','.join(['%s']*len(gl_accounts))}) AND month=%s"
# 				result = round((frappe.db.sql(query, [company, year]+gl_accounts+[month])[0][0] or 0) / 100000, self.show_decimal_value)

# 		if getattr(self, '_caches_initialized', False):
# 			self._sum_grouping_cache[cache_key] = result
# 		return result

# 	def get_sum_grouping_amount_yearly(company, self, primary_group, group, month, year, is_ftm=False, hg_sec_group=""):
# 		if getattr(self, '_caches_initialized', False):
# 			cache_key = ("sum_grouping_yearly", primary_group, group, month, year, is_ftm, str(hg_sec_group))
# 			if cache_key in self._sum_grouping_cache:
# 				return self._sum_grouping_cache[cache_key]

# 		filters = {"company": company, "report_type": "Yearly","primary_group": primary_group,"secondary_group": group, "higher_secondary_group": ["in", hg_sec_group]}
# 		gl_accounts = frappe.get_list("GL Group Mapping", filters, pluck="gl_account")
# 		if not gl_accounts:
# 			result = 0
# 		else:
# 			erp_type = self.get_erp_type()
# 			if erp_type == "ERPNext":
# 				start_date, end_date = self.get_month_date_range(month, year)
# 				if not start_date:
# 					result = 0
# 				else:
# 					query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN ({','.join(['%s']*len(gl_accounts))})"
# 					result = round((frappe.db.sql(query, [company, start_date, end_date]+gl_accounts)[0][0] or 0) / 100000, self.show_decimal_value)
# 			else:
# 				field = "amount" if is_ftm else "uploaded_amount"
# 				query = f"SELECT SUM({field}) FROM `tabFR Trial Balance Entry` WHERE company=%s AND fiscal_year=%s AND gl_account IN ({','.join(['%s']*len(gl_accounts))}) AND month=%s"
# 				result = round((frappe.db.sql(query, [company, year]+gl_accounts+[month])[0][0] or 0) / 100000, self.show_decimal_value)

# 		if getattr(self, '_caches_initialized', False):
# 			self._sum_grouping_cache[cache_key] = result
# 		return result

# 	def get_yearly_dates(self, only_dates=False):
# 		month_num = {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12}

# 		if isinstance(self.current_year_ending_date, str):
# 			current_year = int(self.current_year_ending_date.split("-")[0]) - 1
# 		elif isinstance(self.current_year_ending_date, datetime):
# 			current_year = self.current_year_ending_date.year - 1
# 		elif hasattr(self.current_year_ending_date, "year"):  # datetime.date
# 			current_year = self.current_year_ending_date.year - 1
# 		else:
# 			current_year = datetime.now().year

# 		month_end_date = datetime(current_year+1, 4, 1) - timedelta(days=1)
# 		if only_dates:
# 			return month_end_date

# 		# Build readable labels
# 		current_month_label = f"Year Ended {month_end_date.strftime('%d/%m/%Y')}"

# 		if self.previous_year_ending_date:
# 			if isinstance(self.previous_year_ending_date, str):
# 				previous_year_date_obj = datetime.strptime(self.previous_year_ending_date, "%Y-%m-%d")
# 			elif hasattr(self.previous_year_ending_date, "year"):
# 				previous_year_date_obj = datetime.combine(self.previous_year_ending_date, datetime.min.time())
# 			else:
# 				previous_year_date_obj = None

# 			previous_year_label = f"Year Ended {previous_year_date_obj.strftime('%d/%m/%Y')}" if previous_year_date_obj else ""
# 		else:
# 			previous_year_label = ""

# 		return current_month_label, previous_year_label

# 	@frappe.whitelist()
# 	def generate_report(doc):
# 		# doc._generate_report_internal()
# 		frappe.enqueue(
# 			"financial_report_tool.financial_report_tool.doctype.fr_console_financial_report.fr_console_financial_report.do_generate_report",
# 			docname=doc.name,
# 			queue='long',                 
# 			job_name=f"Generate Consol Financial Report - {doc.name}",
# 			timeout=600                   
# 		)

# 		return {
# 			"success": True,
# 			"message": f"Report generation started in background for {doc.name}. "
# 					f"You will be notified once it is complete."
# 		}

# 	def _generate_report_internal(self):
# 		self._init_report_caches()
# 		if self.report_type == "Consol Monthly":
# 			for i in self.financial_report_details:
# 				if i.section_type == "Balance Sheet":
# 					i.table_data, i.section_description = self.render_monthly_balance_sheet(i.section)
# 				if i.section_type == "Profit & Loss":
# 					i.table_data, i.section_description = self.render_monthly_profit_and_loss(i.section)
# 				if i.section_type == "Cash Flow":
# 					i.table_data, i.section_description = self.render_monthly_cash_flow(i.section)
# 				if i.section_type == "Equity":
# 					i.section_description = self.render_monthly_equity_share_table()
# 				if i.section_type == "Consolidation Note":
# 					section_data = self._fr_section_detail_cache.get(i.section)
# 					section_description = section_data.section_type_description if section_data else ""
# 					fetch_data_from_trial_balance = section_data.fetch_data_from_trial_balance if section_data else ""
# 					primary_group = section_data.primary_consolidation_group if section_data else ""
# 					note_type = section_data.note_type if section_data else ""
# 					note_table = None
# 					if fetch_data_from_trial_balance == 1:
# 						data = []
# 						if primary_group:
# 							data = self.get_monthly_consolidation_note_data(primary_group)
# 							show_descending_order = frappe.get_value("Standalone Group", primary_group, "show_descending_order")
# 							if show_descending_order:
# 								data = sorted(data, key=lambda x: x["current_month_amount"], reverse=bool(show_descending_order))
# 						i.section_description = self.monthly_table_for_note_template_1(data)

# 					if note_type == "Other Equity":
# 						i.section_description = self.get_console_monthly_other_equity_note_data(section_description)
						
# 		self.save(ignore_permissions=True)
# 		frappe.db.commit()

# 	def get_console_monthly_other_equity_note_data(self, section_description):
# 		all_companies = frappe.get_all("Company", pluck="name")
# 		# Initialize totals
# 		totals = {
# 			"sp": {"current": 0, "previous": 0, "previous_year": 0},
# 			"forex": {
# 				"opening": {"current": 0, "previous": 0, "previous_year": 0},
# 				"addition": {"current": 0, "previous": 0, "previous_year": 0},
# 				"closing": {"current": 0, "previous": 0, "previous_year": 0},
# 			},
# 			"retained": {
# 				"opening": {"current": 0, "previous": 0, "previous_year": 0},
# 				"net": {"current": 0, "previous": 0, "previous_year": 0},
# 				"oci": {"current": 0, "previous": 0, "previous_year": 0},
# 				"closing": {"current": 0, "previous": 0, "previous_year": 0},
# 			},
# 			"cc": {
# 				"opening": {"current": 0, "previous": 0, "previous_year": 0},
# 				"addition": {"current": 0, "previous": 0, "previous_year": 0},
# 				"closing": {"current": 0, "previous": 0, "previous_year": 0},
# 			},
# 			"total": {"current": 0, "previous": 0, "previous_year": 0},
# 		}

# 		# Aggregate
# 		for company in all_companies:
# 			d = self.get_monthly_other_equity_note_data(company, "Other Equity")

# 			for key in totals:
# 				if isinstance(totals[key], dict):
# 					for sub in totals[key]:
# 						if isinstance(totals[key][sub], dict):
# 							for k in totals[key][sub]:
# 								totals[key][sub][k] += d[key][sub][k]
# 						else:
# 							totals[key][sub] += d[key][sub]

# 		# Map into table
# 		data = [
# 			("Securities premium account", "", "", "", True),
# 			("Balance as at the beginning of the year", totals["sp"]["previous_year"], totals["sp"]["previous"], totals["sp"]["previous_year"], False),
# 			("Addition: During the year on issue of equity shares", 0, 0, 0, False),
# 			("Balance as at the end of the year", totals["sp"]["current"], totals["sp"]["previous"], totals["sp"]["previous_year"], True),

# 			("Surplus in Foreign Exchange Reserves", "", "", "", True),
# 			("Balance as at the beginning of the year", totals["forex"]["opening"]["current"], totals["forex"]["opening"]["previous"], totals["forex"]["opening"]["previous_year"], False),
# 			("Addition during the year", totals["forex"]["addition"]["current"], totals["forex"]["addition"]["previous"], totals["forex"]["addition"]["previous_year"], False),
# 			("Balance as at the end of the year", totals["forex"]["closing"]["current"], totals["forex"]["closing"]["previous"], totals["forex"]["closing"]["previous_year"], True),

# 			("Retained earnings", "", "", "", True),
# 			("Balance as at the beginning of the year", totals["retained"]["opening"]["current"], totals["retained"]["opening"]["previous"], totals["retained"]["opening"]["previous_year"], False),
# 			("Net Profit for the year", totals["retained"]["net"]["current"], totals["retained"]["net"]["previous"], totals["retained"]["net"]["previous_year"], False),
# 			("Other comprehensive income", totals["retained"]["oci"]["current"], totals["retained"]["oci"]["previous"], totals["retained"]["oci"]["previous_year"], False),
# 			("Balance as at the end of the year", totals["retained"]["closing"]["current"], totals["retained"]["closing"]["previous"], totals["retained"]["closing"]["previous_year"], True),

# 			("Capital Contribution", "", "", "", True),
# 			("Balance as at the beginning of the year", totals["cc"]["opening"]["current"], totals["cc"]["opening"]["previous"], totals["cc"]["opening"]["previous_year"], False),
# 			("Add: Equity contribution on financial guarantee taken", totals["cc"]["addition"]["current"], totals["cc"]["addition"]["previous"], totals["cc"]["addition"]["previous_year"], False),
# 			("Balance as at the end of the year", totals["cc"]["closing"]["current"], totals["cc"]["closing"]["previous"], totals["cc"]["closing"]["previous_year"], True),

# 			("Total", totals["total"]["current"], totals["total"]["previous"], totals["total"]["previous_year"], True),
# 		]
# 		html = f'''
# 		<table style="width:100%; border-collapse:collapse; border-spacing:0; font-size:13px; margin-top:-25pt; border:1px solid #000; background-color:#fff;">
# 			<thead>
# 				<tr style="border-bottom:2px solid #222; background-color:#fff;">
# 					<th style="border-left:1px solid #222; color: #4472C4; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; width:40%; padding:6px 8px; background-color:#fff; text-align:left;"><b>Particulars</b></th>
# 					<th style="border-left:1px solid #222; color: #4472C4; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:6px 8px; background-color:#fff; text-align:center;"><b>{month_end_label}</b></th>
# 					<th style="border-left:1px solid #222; color: #4472C4; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:6px 8px; background-color:#fff; text-align:center;"><b>{current_fiscal_year_end_label}</b></th>
# 					<th style="border-left:1px solid #222; color: #4472C4; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:6px 8px; background-color:#fff; text-align:center;"><b>{previous_fiscal_year_end_label}</b></th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		'''

# 		for i, (particulars, amt_month, amt_current_fy, amt_previous_fy, is_bold) in enumerate(data):
# 			bold = "font-weight: bold;" if is_bold else ""
# 			# Only vertical borders for regular rows, full borders for bold/total rows
# 			if is_bold:
# 				border = "border-top:1px solid #222; border-bottom:1px solid #222;"
# 			else:
# 				border = "border-top:none; border-bottom:none;"

# 			html += f'''<tr style='background-color:#fff;'>
# 				<td style='{border} border-left:1px solid #222; border-right:1px solid #222; padding:6px 8px; text-align:left; background-color:#fff; {bold}'>{particulars}</td>
# 				<td style='{border} border-left:1px solid #222; border-right:1px solid #222; padding:6px 8px; text-align:right; background-color:#E8F5E8; {bold}'>{amt_month}</td>
# 				<td style='{border} border-left:1px solid #222; border-right:1px solid #222; padding:6px 8px; text-align:right; background-color:#fff; {bold}'>{amt_current_fy}</td>
# 				<td style='{border} border-left:1px solid #222; border-right:1px solid #222; padding:6px 8px; text-align:right; background-color:#fff; {bold}'>{amt_previous_fy}</td>
# 			</tr>'''

# 		html += "</tbody></table>"
# 		return section_description.replace("{{note_table}}", html)


# 	def get_yearly_property_plant_and_equipment_data(self, section_description=""):
# 		# Convert to date objects if they are strings
# 		prev_year_end_date = frappe.utils.getdate(self.previous_year_ending_date)
# 		curr_year_end_date = frappe.utils.getdate(self.current_year_ending_date)

# 		previous_year_ending_date = prev_year_end_date.strftime("%d %B %Y")
# 		previous_year_starting_date = prev_year_end_date.replace(year=prev_year_end_date.year - 1, month=4, day=1).strftime("%d %B %Y")
# 		current_year_ending_date = curr_year_end_date.strftime("%d %B %Y")
# 		current_year_starting_date = curr_year_end_date.replace(year=prev_year_end_date.year - 1, month=4, day=1).strftime("%d %B %Y")

# 		# Asset classes mapping: DB name -> column order in table
# 		asset_classes = [
# 			"Building",
# 			"Plant & Machinery",
# 			"Furniture & Fixtures",
# 			"Vehicle",
# 			"Office Equipment",
# 			"Computer & Hardware",
# 			"Leasehold Improvement"
# 		]

# 		# Define years
# 		previous_year = {
# 			"start": prev_year_end_date.replace(year=prev_year_end_date.year - 1, month=4, day=1).strftime("%Y-%m-%d"),
# 			"end": prev_year_end_date.strftime("%Y-%m-%d")
# 		}
# 		current_year = {
# 			"start": curr_year_end_date.replace(year=curr_year_end_date.year - 1, month=4, day=1).strftime("%Y-%m-%d"),
# 			"end": curr_year_end_date.strftime("%Y-%m-%d")
# 		}

# 		prev_year_start = frappe.utils.getdate(previous_year["start"])
# 		prev_year_end = frappe.utils.getdate(previous_year["end"])
# 		curr_year_start = frappe.utils.getdate(current_year["start"])
# 		curr_year_end = frappe.utils.getdate(current_year["end"])

# 		# Initialize result dictionaries
# 		result = {
# 			"previous_year": {},
# 			"current_year": {},
# 			"previous_year_acc_dep": {},
# 			"current_year_acc_dep": {}
# 		}

# 		for asset in asset_classes:
# 			# Fetch data for previous year
# 			prev_data = frappe.db.get_all(
# 				'FR Asset Register Entry',
# 				fields=['name', 'sap_transaction_acq_value', 'sap_cav', 'sap_tran_accu_dep', 'sap_acc_dep', 'sap_plan_dep', 'ordinary_depreciation_start_date'],
# 				filters={
# 					'company': self.company,
# 					'asset_class': asset,
# 					'ordinary_depreciation_start_date': ['between', [previous_year["start"], previous_year["end"]]]
# 				},
# 				order_by='ordinary_depreciation_start_date asc'
# 			)

# 			# Fetch data for current year
# 			curr_data = frappe.db.get_all(
# 				'FR Asset Register Entry',
# 				fields=['name', 'sap_transaction_acq_value', 'sap_cav', 'sap_tran_accu_dep', 'sap_acc_dep', 'sap_plan_dep', 'ordinary_depreciation_start_date'],
# 				filters={
# 					'company': self.company,
# 					'asset_class': asset,
# 					'ordinary_depreciation_start_date': ['between', [current_year["start"], current_year["end"]]]
# 				},
# 				order_by='ordinary_depreciation_start_date asc'
# 			)

# 			# PREVIOUS YEAR (SAP CAV) - Gross Carrying Amount
# 			prev_opening_value = 0.0
# 			prev_positive = 0.0
# 			prev_negative = 0.0

# 			# Find first entry with sap_cav as opening value
# 			for entry in prev_data:
# 				if entry.sap_cav:
# 					prev_opening_value = float(entry.sap_cav)
# 					break

# 			# Sum all transactions
# 			for entry in prev_data:
# 				value = float(entry.sap_transaction_acq_value) if entry.sap_transaction_acq_value else 0.0
# 				if value > 0:
# 					prev_positive += value
# 				elif value < 0:
# 					prev_negative += value

# 			prev_closing_value = prev_opening_value + prev_positive + prev_negative

# 			result["previous_year"][asset] = {
# 				"opening_value": prev_opening_value,
# 				"positive_transaction": prev_positive,
# 				"negative_transaction": prev_negative,
# 				"closing_value": prev_closing_value
# 			}

# 			# CURRENT YEAR (SAP CAV) - Gross Carrying Amount
# 			curr_opening_value = prev_closing_value
# 			curr_positive = 0.0
# 			curr_negative = 0.0

# 			for entry in curr_data:
# 				value = float(entry.sap_transaction_acq_value) if entry.sap_transaction_acq_value else 0.0
# 				if value > 0:
# 					curr_positive += value
# 				elif value < 0:
# 					curr_negative += value

# 			curr_closing_value = curr_opening_value + curr_positive + curr_negative

# 			result["current_year"][asset] = {
# 				"opening_value": curr_opening_value,
# 				"positive_transaction": curr_positive,
# 				"negative_transaction": curr_negative,
# 				"closing_value": curr_closing_value
# 			}

# 			# PREVIOUS YEAR (SAP Acc Dep) - Accumulated Depreciation
# 			prev_acc_opening_value = 0.0
# 			prev_acc_positive = 0.0
# 			prev_acc_negative = 0.0

# 			# Find first entry with sap_acc_dep as opening value
# 			for entry in prev_data:
# 				if entry.sap_acc_dep:
# 					prev_acc_opening_value = abs(float(entry.sap_acc_dep))
# 					break

# 			for entry in prev_data:
# 				value = float(entry.sap_tran_accu_dep) if entry.sap_tran_accu_dep else 0.0
# 				if value > 0:
# 					prev_acc_negative += value
# 				elif value < 0:
# 					prev_acc_positive += abs(value)

# 				plan_value = float(entry.sap_plan_dep) if entry.sap_plan_dep else 0.0
# 				prev_acc_positive += abs(plan_value)

# 			prev_acc_closing_value = prev_acc_opening_value + prev_acc_positive - prev_acc_negative

# 			result["previous_year_acc_dep"][asset] = {
# 				"opening_value": prev_acc_opening_value,
# 				"positive_transaction": prev_acc_positive,
# 				"negative_transaction": prev_acc_negative,
# 				"closing_value": prev_acc_closing_value
# 			}

# 			# CURRENT YEAR (SAP Acc Dep) - Accumulated Depreciation
# 			curr_acc_opening_value = prev_acc_closing_value
# 			curr_acc_positive = 0.0
# 			curr_acc_negative = 0.0

# 			for entry in curr_data:
# 				value = float(entry.sap_tran_accu_dep) if entry.sap_tran_accu_dep else 0.0
# 				if value > 0:
# 					curr_acc_negative += value
# 				elif value < 0:
# 					curr_acc_positive += abs(value)

# 				plan_value = float(entry.sap_plan_dep) if entry.sap_plan_dep else 0.0
# 				curr_acc_positive += abs(plan_value)

# 			curr_acc_closing_value = curr_acc_opening_value + curr_acc_positive - curr_acc_negative

# 			result["current_year_acc_dep"][asset] = {
# 				"opening_value": curr_acc_opening_value,
# 				"positive_transaction": curr_acc_positive,
# 				"negative_transaction": curr_acc_negative,
# 				"closing_value": curr_acc_closing_value
# 			}

# 		# Helper function to format values in lacs (÷100000)
# 		def fmt(val):
# 			if val is None:
# 				return "0.00"
# 			return f"{val / 100000:,.2f}"

# 		# Get values for each asset class
# 		def get_val(data_dict, asset, key):
# 			if asset in data_dict and data_dict[asset].get(key) is not None:
# 				return data_dict[asset][key]
# 			return 0

# 		# I. Gross carrying amount values
# 		py_opening = {asset: get_val(result["previous_year"], asset, "opening_value") for asset in asset_classes}
# 		py_opening_total = sum(v for v in py_opening.values() if v)

# 		py_additions = {asset: get_val(result["previous_year"], asset, "positive_transaction") for asset in asset_classes}
# 		py_additions_total = sum(v for v in py_additions.values() if v)

# 		py_disposals = {asset: get_val(result["previous_year"], asset, "negative_transaction") for asset in asset_classes}
# 		py_disposals_total = sum(v for v in py_disposals.values() if v)

# 		py_closing = {asset: get_val(result["previous_year"], asset, "closing_value") for asset in asset_classes}
# 		py_closing_total = sum(v for v in py_closing.values() if v)

# 		cy_additions = {asset: get_val(result["current_year"], asset, "positive_transaction") for asset in asset_classes}
# 		cy_additions_total = sum(v for v in cy_additions.values() if v)

# 		cy_disposals = {asset: get_val(result["current_year"], asset, "negative_transaction") for asset in asset_classes}
# 		cy_disposals_total = sum(v for v in cy_disposals.values() if v)

# 		cy_closing = {asset: get_val(result["current_year"], asset, "closing_value") for asset in asset_classes}
# 		cy_closing_total = sum(v for v in cy_closing.values() if v)

# 		# II. Accumulated depreciation values
# 		py_acc_opening = {asset: get_val(result["previous_year_acc_dep"], asset, "opening_value") for asset in asset_classes}
# 		py_acc_opening_total = sum(v for v in py_acc_opening.values() if v)

# 		py_acc_for_year = {asset: get_val(result["previous_year_acc_dep"], asset, "positive_transaction") for asset in asset_classes}
# 		py_acc_for_year_total = sum(v for v in py_acc_for_year.values() if v)

# 		py_acc_disposals = {asset: get_val(result["previous_year_acc_dep"], asset, "negative_transaction") for asset in asset_classes}
# 		py_acc_disposals_total = sum(v for v in py_acc_disposals.values() if v)

# 		py_acc_closing = {asset: get_val(result["previous_year_acc_dep"], asset, "closing_value") for asset in asset_classes}
# 		py_acc_closing_total = sum(v for v in py_acc_closing.values() if v)

# 		cy_acc_for_year = {asset: get_val(result["current_year_acc_dep"], asset, "positive_transaction") for asset in asset_classes}
# 		cy_acc_for_year_total = sum(v for v in cy_acc_for_year.values() if v)

# 		cy_acc_disposals = {asset: get_val(result["current_year_acc_dep"], asset, "negative_transaction") for asset in asset_classes}
# 		cy_acc_disposals_total = sum(v for v in cy_acc_disposals.values() if v)

# 		cy_acc_closing = {asset: get_val(result["current_year_acc_dep"], asset, "closing_value") for asset in asset_classes}
# 		cy_acc_closing_total = sum(v for v in cy_acc_closing.values() if v)

# 		# III. Net carrying amount = Gross Closing - Accumulated Depreciation Closing
# 		py_net = {asset: (py_closing.get(asset, 0) or 0) - (py_acc_closing.get(asset, 0) or 0) for asset in asset_classes}
# 		py_net_total = py_closing_total - py_acc_closing_total

# 		cy_net = {asset: (cy_closing.get(asset, 0) or 0) - (cy_acc_closing.get(asset, 0) or 0) for asset in asset_classes}
# 		cy_net_total = cy_closing_total - cy_acc_closing_total

# 		# <div class="landscape-table-wrapper" style="page-break-before: always; page-break-after: always; transform: rotate(-90deg); transform-origin: top left; position: relative; top: 701px; width: 750px;">
# 		# <div class="landscape-table-wrapper" style="page-break-before: always; page-break-after: always; overflow-x: auto; width: 100%">
# 		html = f'''
# 		<div class="landscape-table-wrapper" style="page-break-before: always; page-break-after: always; transform-origin: top left; position: relative; top: -30px; width: 1200px;">
# 			<table style="margin-bottom: -90px; margin-top: -20px; border-collapse: collapse; border: 1px solid black; width: 100%; table-layout: fixed;">
# 			<thead>
# 				<tr style="color: #4472C4;">
# 					<th style="border: 1px solid black; border-bottom:1px solid black; width: 21%;">Particulars</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black; width: 9%;">Building</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black; width: 10%;">Plant & Machinery</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black; width: 10%;">Furniture and Fitting</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black; width: 8%;">Vehicle</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black; width: 11%;">Office Equipment</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black; width: 10%;">Computer</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black; width: 12%;">Leasehold Improvement</th>
# 					<th style="background-color: #E8F5E8; border: 1px solid black; border-bottom:1px solid black; width: 8%;">Total</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 				<tr>
# 					<td style="border-left: 1px solid black;border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"><b>I. Gross carrying amount<b></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 					<td style="background-color: #E8F5E8; border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 				</tr>
# 				<tr>
# 					<td style="border-top: 1px solid black;border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">As at {previous_year_starting_date}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Building"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Plant & Machinery"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Furniture & Fixtures"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Vehicle"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Office Equipment"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Computer & Hardware"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Leasehold Improvement"))}</td>
# 					<td style="background-color: #E8F5E8; border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening_total)}</td>
# 				</tr>
# 				<tr>
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Additions</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Building"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Plant & Machinery"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Furniture & Fixtures"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Vehicle"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Office Equipment"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Computer & Hardware"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Leasehold Improvement"))}</td>
# 					<td style="background-color: #E8F5E8; border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions_total)}</td>
# 				</tr>
# 				<tr>
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">Disposals</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Building"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Plant & Machinery"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Furniture & Fixtures"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Vehicle"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Office Equipment"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Computer & Hardware"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Leasehold Improvement"))}</td>
# 					<td style="background-color: #E8F5E8; border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals_total)}</td>
# 				</tr>
# 				<tr style="background-color: #E8F5E8">
# 					<td style="border:1px solid black;"><b>As at {previous_year_ending_date}<b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing.get("Building"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing.get("Plant & Machinery"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing.get("Furniture & Fixtures"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing.get("Vehicle"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing.get("Office Equipment"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing.get("Computer & Hardware"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing.get("Leasehold Improvement"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing_total)}</b></td>
# 				</tr>
# 				<tr style="background-color: #E8F5E8">
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-bottom:none;">Additions</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Building"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Plant & Machinery"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Furniture & Fixtures"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Vehicle"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Office Equipment"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Computer & Hardware"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Leasehold Improvement"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions_total)}</td>
# 				</tr>
# 				<tr style="background-color: #E8F5E8">
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:1px solid black;">Disposals</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Building"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Plant & Machinery"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Furniture & Fixtures"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Vehicle"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Office Equipment"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Computer & Hardware"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Leasehold Improvement"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals_total)}</td>
# 				</tr>
# 				<tr style="background-color: #E8F5E8">
# 					<td style="border:1px solid black;"><b>As at {current_year_ending_date}<b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Building"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Plant & Machinery"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Furniture & Fixtures"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Vehicle"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Office Equipment"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Computer & Hardware"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Leasehold Improvement"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing_total)}</b></td>
# 				</tr>
# 				<tr>
# 					<td style="border-left: 1px solid black;border-right: 1px solid black; border-bottom: none;"><b>II.  Accumulated depreciation<b></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>
# 					<td style="background-color: #E8F5E8; border-right: 1px solid black; border-bottom: none;"></td>
# 				</tr>
# 				<tr>
# 					<td style="border-top: 1px solid black;border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">As at {previous_year_starting_date}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Building"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Plant & Machinery"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Furniture & Fixtures"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Vehicle"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Office Equipment"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Computer & Hardware"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Leasehold Improvement"))}</td>
# 					<td style="background-color: #E8F5E8; border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening_total)}</td>
# 				</tr>
# 				<tr>
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Year Ended {previous_year_ending_date}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Building"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Plant & Machinery"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Furniture & Fixtures"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Vehicle"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Office Equipment"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Computer & Hardware"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Leasehold Improvement"))}</td>
# 					<td style="background-color: #E8F5E8; border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year_total)}</td>
# 				</tr>
# 				<tr>
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">Disposals</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Building"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Plant & Machinery"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Furniture & Fixtures"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Vehicle"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Office Equipment"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Computer & Hardware"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Leasehold Improvement"))}</td>
# 					<td style="background-color: #E8F5E8; border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals_total)}</td>
# 				</tr>
# 				<tr style="background-color: #E8F5E8">
# 					<td style="border:1px solid black;"><b>Upto {previous_year_ending_date}<b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Building"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Plant & Machinery"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Furniture & Fixtures"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Vehicle"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Office Equipment"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Computer & Hardware"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Leasehold Improvement"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing_total)}</b></td>
# 				</tr>
# 				<tr style="background-color: #E8F5E8">
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-bottom:none;">Year Ended {current_year_ending_date} </td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Building"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Plant & Machinery"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Furniture & Fixtures"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Vehicle"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Office Equipment"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Computer & Hardware"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Leasehold Improvement"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year_total)}</td>
# 				</tr>
# 				<tr style="background-color: #E8F5E8">
# 					<td style="background-color: #E8F5E8; border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:1px solid black; background-color: #E8F5E8;">Disposals#</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Building"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Plant & Machinery"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Furniture & Fixtures"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Vehicle"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Office Equipment"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Computer & Hardware"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Leasehold Improvement"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals_total)}</td>
# 				</tr>
# 				<tr style="background-color: #E8F5E8">
# 					<td style="border:1px solid black;"><b>Upto {current_year_ending_date}<b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Building"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Plant & Machinery"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Furniture & Fixtures"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Vehicle"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Office Equipment"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Computer & Hardware"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Leasehold Improvement"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing_total)}</b></td>
# 				</tr>
# 				<tr>
# 					<td style="border:1px solid black;"><b>III.  Net carrying amount<b></td>
# 					<td style="border:1px solid black;"><b></b></td>
# 					<td style="border:1px solid black;"><b></b></td>
# 					<td style="border:1px solid black;"><b></b></td>
# 					<td style="border:1px solid black;"><b></b></td>
# 					<td style="border:1px solid black;"><b></b></td>
# 					<td style="border:1px solid black;"><b></b></td>
# 					<td style="border:1px solid black;"><b></b></td>
# 					<td style="background-color: #E8F5E8; border:1px solid black;"><b></b></td>
# 				</tr>
# 				<tr>
# 					<td style="border:1px solid black;"><b>As at {previous_year_ending_date}<b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net.get("Building"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net.get("Plant & Machinery"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net.get("Furniture & Fixtures"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net.get("Vehicle"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net.get("Office Equipment"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net.get("Computer & Hardware"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net.get("Leasehold Improvement"))}</b></td>
# 					<td style="background-color: #E8F5E8; border:1px solid black;"><b>{fmt(py_net_total)}</b></td>
# 				</tr>
# 				<tr style="background-color: #E8F5E8">
# 					<td style="border:1px solid black;"><b>As at {current_year_ending_date}<b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net.get("Building"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net.get("Plant & Machinery"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net.get("Furniture & Fixtures"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net.get("Vehicle"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net.get("Office Equipment"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net.get("Computer & Hardware"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net.get("Leasehold Improvement"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net_total)}</b></td>
# 				</tr>
# 			</tbody>
# 		</table>
# 		</div>
# 		'''
# 		return section_description.replace("{{note_table}}", html)

# 	def get_yearly_other_intangible_assets(self, company, section_description="", field=""):
# 		# Convert to date objects if they are strings
# 		prev_year_end_date = frappe.utils.getdate(self.previous_year_ending_date)
# 		curr_year_end_date = frappe.utils.getdate(self.current_year_ending_date)

# 		previous_year_ending_date = prev_year_end_date.strftime("%d %B %Y")
# 		previous_year_starting_date = prev_year_end_date.replace(year=prev_year_end_date.year - 1, month=4, day=1).strftime("%d %B %Y")
# 		current_year_ending_date = curr_year_end_date.strftime("%d %B %Y")

# 		# Intangible Asset classes
# 		asset_classes = [
# 			"Trademark",
# 			"Software",
# 			"Product Development"
# 		]

# 		# Define years
# 		previous_year = {
# 			"start": prev_year_end_date.replace(year=prev_year_end_date.year - 1, month=4, day=1).strftime("%Y-%m-%d"),
# 			"end": prev_year_end_date.strftime("%Y-%m-%d")
# 		}
# 		current_year = {
# 			"start": curr_year_end_date.replace(year=curr_year_end_date.year - 1, month=4, day=1).strftime("%Y-%m-%d"),
# 			"end": curr_year_end_date.strftime("%Y-%m-%d")
# 		}

# 		prev_year_start = frappe.utils.getdate(previous_year["start"])
# 		prev_year_end = frappe.utils.getdate(previous_year["end"])
# 		curr_year_start = frappe.utils.getdate(current_year["start"])
# 		curr_year_end = frappe.utils.getdate(current_year["end"])

# 		# Initialize result dictionaries
# 		result = {
# 			"previous_year": {},
# 			"current_year": {},
# 			"previous_year_acc_dep": {},
# 			"current_year_acc_dep": {}
# 		}

# 		for asset in asset_classes:
# 			# Fetch data for previous year
# 			prev_data = frappe.db.get_all(
# 				'FR Asset Register Entry',
# 				fields=['name', 'sap_transaction_acq_value', 'sap_cav', 'sap_tran_accu_dep', 'sap_acc_dep', 'sap_plan_dep', 'ordinary_depreciation_start_date'],
# 				filters={
# 					'company': company,
# 					'asset_class': asset,
# 					'ordinary_depreciation_start_date': ['between', [previous_year["start"], previous_year["end"]]]
# 				},
# 				order_by='ordinary_depreciation_start_date asc'
# 			)

# 			# Fetch data for current year
# 			curr_data = frappe.db.get_all(
# 				'FR Asset Register Entry',
# 				fields=['name', 'sap_transaction_acq_value', 'sap_cav', 'sap_tran_accu_dep', 'sap_acc_dep', 'sap_plan_dep', 'ordinary_depreciation_start_date'],
# 				filters={
# 					'company': company,
# 					'asset_class': asset,
# 					'ordinary_depreciation_start_date': ['between', [current_year["start"], current_year["end"]]]
# 				},
# 				order_by='ordinary_depreciation_start_date asc'
# 			)

# 			# PREVIOUS YEAR (SAP CAV) - Gross Carrying Amount
# 			prev_opening_value = 0.0
# 			prev_positive = 0.0
# 			prev_negative = 0.0

# 			for entry in prev_data:
# 				if entry.sap_cav:
# 					prev_opening_value = float(entry.sap_cav)
# 					break

# 			for entry in prev_data:
# 				value = float(entry.sap_transaction_acq_value) if entry.sap_transaction_acq_value else 0.0
# 				if value > 0:
# 					prev_positive += value
# 				elif value < 0:
# 					prev_negative += value

# 			prev_closing_value = prev_opening_value + prev_positive + prev_negative

# 			result["previous_year"][asset] = {
# 				"opening_value": prev_opening_value,
# 				"positive_transaction": prev_positive,
# 				"negative_transaction": prev_negative,
# 				"closing_value": prev_closing_value
# 			}

# 			# CURRENT YEAR (SAP CAV) - Gross Carrying Amount
# 			curr_opening_value = prev_closing_value
# 			curr_positive = 0.0
# 			curr_negative = 0.0

# 			for entry in curr_data:
# 				value = float(entry.sap_transaction_acq_value) if entry.sap_transaction_acq_value else 0.0
# 				if value > 0:
# 					curr_positive += value
# 				elif value < 0:
# 					curr_negative += value

# 			curr_closing_value = curr_opening_value + curr_positive + curr_negative

# 			result["current_year"][asset] = {
# 				"opening_value": curr_opening_value,
# 				"positive_transaction": curr_positive,
# 				"negative_transaction": curr_negative,
# 				"closing_value": curr_closing_value
# 			}

# 			# PREVIOUS YEAR (SAP Acc Dep) - Accumulated Amortisation
# 			prev_acc_opening_value = 0.0
# 			prev_acc_positive = 0.0
# 			prev_acc_negative = 0.0

# 			for entry in prev_data:
# 				if entry.sap_acc_dep:
# 					prev_acc_opening_value = abs(float(entry.sap_acc_dep))
# 					break

# 			for entry in prev_data:
# 				value = float(entry.sap_tran_accu_dep) if entry.sap_tran_accu_dep else 0.0
# 				if value > 0:
# 					prev_acc_negative += value
# 				elif value < 0:
# 					prev_acc_positive += abs(value)

# 				plan_value = float(entry.sap_plan_dep) if entry.sap_plan_dep else 0.0
# 				prev_acc_positive += abs(plan_value)

# 			prev_acc_closing_value = prev_acc_opening_value + prev_acc_positive - prev_acc_negative

# 			result["previous_year_acc_dep"][asset] = {
# 				"opening_value": prev_acc_opening_value,
# 				"positive_transaction": prev_acc_positive,
# 				"negative_transaction": prev_acc_negative,
# 				"closing_value": prev_acc_closing_value
# 			}

# 			# CURRENT YEAR (SAP Acc Dep) - Accumulated Amortisation
# 			curr_acc_opening_value = prev_acc_closing_value
# 			curr_acc_positive = 0.0
# 			curr_acc_negative = 0.0

# 			for entry in curr_data:
# 				value = float(entry.sap_tran_accu_dep) if entry.sap_tran_accu_dep else 0.0
# 				if value > 0:
# 					curr_acc_negative += value
# 				elif value < 0:
# 					curr_acc_positive += abs(value)

# 				plan_value = float(entry.sap_plan_dep) if entry.sap_plan_dep else 0.0
# 				curr_acc_positive += abs(plan_value)

# 			curr_acc_closing_value = curr_acc_opening_value + curr_acc_positive - curr_acc_negative

# 			result["current_year_acc_dep"][asset] = {
# 				"opening_value": curr_acc_opening_value,
# 				"positive_transaction": curr_acc_positive,
# 				"negative_transaction": curr_acc_negative,
# 				"closing_value": curr_acc_closing_value
# 			}

# 		# Helper function to format values in lacs (÷100000)
# 		def fmt(val):
# 			if val is None:
# 				return "0.00"
# 			return f"{val / 100000:,.2f}"

# 		# Get values for each asset class
# 		def get_val(data_dict, asset, key):
# 			if asset in data_dict and data_dict[asset].get(key) is not None:
# 				return data_dict[asset][key]
# 			return 0

# 		# I. Gross carrying amount values
# 		py_opening = {asset: get_val(result["previous_year"], asset, "opening_value") for asset in asset_classes}
# 		py_opening_total = sum(v for v in py_opening.values() if v)

# 		py_additions = {asset: get_val(result["previous_year"], asset, "positive_transaction") for asset in asset_classes}
# 		py_additions_total = sum(v for v in py_additions.values() if v)

# 		py_disposals = {asset: get_val(result["previous_year"], asset, "negative_transaction") for asset in asset_classes}
# 		py_disposals_total = sum(v for v in py_disposals.values() if v)

# 		py_closing = {asset: get_val(result["previous_year"], asset, "closing_value") for asset in asset_classes}
# 		py_closing_total = sum(v for v in py_closing.values() if v)

# 		cy_additions = {asset: get_val(result["current_year"], asset, "positive_transaction") for asset in asset_classes}
# 		cy_additions_total = sum(v for v in cy_additions.values() if v)

# 		cy_disposals = {asset: get_val(result["current_year"], asset, "negative_transaction") for asset in asset_classes}
# 		cy_disposals_total = sum(v for v in cy_disposals.values() if v)

# 		cy_closing = {asset: get_val(result["current_year"], asset, "closing_value") for asset in asset_classes}
# 		cy_closing_total = sum(v for v in cy_closing.values() if v)

# 		# II. Accumulated amortisation values
# 		py_acc_opening = {asset: get_val(result["previous_year_acc_dep"], asset, "opening_value") for asset in asset_classes}
# 		py_acc_opening_total = sum(v for v in py_acc_opening.values() if v)

# 		py_acc_for_year = {asset: get_val(result["previous_year_acc_dep"], asset, "positive_transaction") for asset in asset_classes}
# 		py_acc_for_year_total = sum(v for v in py_acc_for_year.values() if v)

# 		py_acc_disposals = {asset: get_val(result["previous_year_acc_dep"], asset, "negative_transaction") for asset in asset_classes}
# 		py_acc_disposals_total = sum(v for v in py_acc_disposals.values() if v)

# 		py_acc_closing = {asset: get_val(result["previous_year_acc_dep"], asset, "closing_value") for asset in asset_classes}
# 		py_acc_closing_total = sum(v for v in py_acc_closing.values() if v)

# 		cy_acc_for_year = {asset: get_val(result["current_year_acc_dep"], asset, "positive_transaction") for asset in asset_classes}
# 		cy_acc_for_year_total = sum(v for v in cy_acc_for_year.values() if v)

# 		cy_acc_disposals = {asset: get_val(result["current_year_acc_dep"], asset, "negative_transaction") for asset in asset_classes}
# 		cy_acc_disposals_total = sum(v for v in cy_acc_disposals.values() if v)

# 		cy_acc_closing = {asset: get_val(result["current_year_acc_dep"], asset, "closing_value") for asset in asset_classes}
# 		cy_acc_closing_total = sum(v for v in cy_acc_closing.values() if v)

# 		# III. Net carrying amount = Gross Closing - Accumulated Amortisation Closing
# 		py_net = {asset: (py_closing.get(asset, 0) or 0) - (py_acc_closing.get(asset, 0) or 0) for asset in asset_classes}
# 		py_net_total = py_closing_total - py_acc_closing_total

# 		cy_net = {asset: (cy_closing.get(asset, 0) or 0) - (cy_acc_closing.get(asset, 0) or 0) for asset in asset_classes}
# 		cy_net_total = cy_closing_total - cy_acc_closing_total

# 		if field == "curr_intangel_asset":
# 			return fmt(cy_net.get("Trade Mark & Product Registration"))
# 		elif field == "prev_intangel_asset":
# 			return fmt(py_net.get("Trade Mark & Product Registration"))
# 		elif field == "curr_addition":
# 			return fmt(cy_additions_total)
# 		elif field == "prev_addition":
# 			return fmt(py_additions_total)
# 		html = f'''
# 		<table style="margin-top: -10px; margin-bottom: -30px; border-collapse: collapse; border: 1px solid black; width: 100%; table-layout: fixed;">
# 			<thead>
# 				<tr style="color: #4472C4;">
# 					<th style="width: 40%; border: 1px solid black; border-bottom:1px solid black;">Particulars</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black; width: 20%;">Trade Mark & Product Registration (Internally Generated)</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black; width: 20%;">Software (Acquired)</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black; width: 20%;">Designs & Developments (Internally Generated)</th>
# 					<th style="background-color: #E8F5E8; border: 1px solid black; border-bottom:1px solid black; width: 20%;">Total</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 				<tr>
# 					<td style="border-left: 1px solid black;border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"><b>I. Gross carrying amount</b></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 					<td style="background-color: #E8F5E8; border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 				</tr>
# 				<tr>
# 					<td style="border-top: 1px solid black;border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">As at {previous_year_starting_date}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Trade Mark & Product Registration"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Software"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Designs & Developments"))}</td>
# 					<td style="background-color: #E8F5E8; border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening_total)}</td>
					
# 				</tr>
# 				<tr>
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Additions</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Trade Mark & Product Registration"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Software"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Designs & Developments"))}</td>
# 					<td style="background-color: #E8F5E8; border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions_total)}</td>
					
# 				</tr>
# 				<tr>
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">Disposals</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Trade Mark & Product Registration"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Software"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Designs & Developments"))}</td>
# 					<td style="background-color: #E8F5E8; border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals_total)}</td>
					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border:1px solid black;"><b>As at {previous_year_ending_date}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing.get("Trade Mark & Product Registration"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing.get("Software"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing.get("Designs & Developments"))}</b></td>
# 					<td style="background-color: #E8F5E8; border:1px solid black;"><b>{fmt(py_closing_total)}</b></td>
					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-bottom:none;">Additions</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Trade Mark & Product Registration"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Software"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Designs & Developments"))}</td>
# 					<td style="background-color: #E8F5E8; border-right:1px solid black;border-bottom:none;">{fmt(cy_additions_total)}</td>
					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:1px solid black;">Disposals, transfer and adjustments</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Trade Mark & Product Registration"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Software"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Designs & Developments"))}</td>
# 					<td style="background-color: #E8F5E8; border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals_total)}</td>
					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border:1px solid black;"><b>As at {current_year_ending_date}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Trade Mark & Product Registration"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Software"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Designs & Developments"))}</b></td>
# 					<td style="background-color: #E8F5E8; border:1px solid black;"><b>{fmt(cy_closing_total)}</b></td>
					
# 				</tr>
# 				<tr>
# 					<td style="border-left: 1px solid black;border-right: 1px solid black; border-bottom: none;"><b>II.  Accumulated amortisation</b></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>
# 					<td style="background-color: #E8F5E8; border-right: 1px solid black; border-bottom: none;"></td>
					
# 				</tr>
# 				<tr>
# 					<td style="border-top: 1px solid black;border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">As at {previous_year_starting_date}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Trade Mark & Product Registration"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Software"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Designs & Developments"))}</td>
# 					<td style="background-color: #E8F5E8; border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening_total)}</td>
					
# 				</tr>
# 				<tr>
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Year Ended {previous_year_ending_date}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Trade Mark & Product Registration"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Software"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Designs & Developments"))}</td>
# 					<td style="background-color: #E8F5E8; border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year_total)}</td>
					
# 				</tr>
# 				<tr>
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">Disposals</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Trade Mark & Product Registration"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Software"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Designs & Developments"))}</td>
# 					<td style="background-color: #E8F5E8; border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals_total)}</td>
					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border:1px solid black;"><b>Upto {previous_year_ending_date}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Trade Mark & Product Registration"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Software"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Designs & Developments"))}</b></td>
# 					<td style="background-color: #E8F5E8; border:1px solid black;"><b>{fmt(py_acc_closing_total)}</b></td>
					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-bottom:none;">Year Ended {current_year_ending_date}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Trade Mark & Product Registration"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Software"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Designs & Developments"))}</td>
# 					<td style="background-color: #E8F5E8; border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year_total)}</td>
					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:1px solid black;">Disposals and adjustments</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Trade Mark & Product Registration"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Software"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Designs & Developments"))}</td>
# 					<td style="background-color: #E8F5E8; border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals_total)}</td>
					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border:1px solid black;"><b>Upto {current_year_ending_date}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Trade Mark & Product Registration"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Software"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Designs & Developments"))}</b></td>
# 					<td style="background-color: #E8F5E8; border:1px solid black;"><b>{fmt(cy_acc_closing_total)}</b></td>
					
# 				</tr>
# 				<tr>
# 					<td style="border:1px solid black;"><b>III.  Net carrying amount</b></td>
# 					<td style="border:1px solid black;"><b></b></td>
# 					<td style="border:1px solid black;"><b></b></td>
# 					<td style="border:1px solid black;"><b></b></td>
# 					<td style="background-color: #E8F5E8; border:1px solid black;"><b></b></td>
					
# 				</tr>
# 				<tr>
# 					<td style="border:1px solid black;"><b>As at {previous_year_ending_date}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net.get("Trade Mark & Product Registration"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net.get("Software"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net.get("Designs & Developments"))}</b></td>
# 					<td style="background-color: #E8F5E8; border:1px solid black;"><b>{fmt(py_net_total)}</b></td>
					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border:1px solid black;"><b>As at {current_year_ending_date}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net.get("Trade Mark & Product Registration"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net.get("Software"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net.get("Designs & Developments"))}</b></td>
# 					<td style="background-color: #E8F5E8; border:1px solid black;"><b>{fmt(cy_net_total)}</b></td>
					
# 				</tr>
# 			</tbody>
# 		</table>

# 		'''
# 		return section_description.replace("{{note_table}}", html)

# 	def get_yearly_capital_work_in_progress(self, section_description="", field=""):
# 		previous_year_ending_date_display = frappe.utils.getdate(self.previous_year_ending_date).strftime("%d %B %Y")
# 		current_year_ending_date_display = frappe.utils.getdate(self.current_year_ending_date).strftime("%d %B %Y")
# 		cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)

# 		def fmt(val):
# 			return "{:,.2f}".format(val / 100000) if val else "0.00"

# 		def get_cwip_values_for_date(current_fy):
# 			"""Calculate CWIP values for Projects in progress based on ending date"""
# 			if not current_fy:
# 				return 0, 0, 0, 0

# 			# Build list of fiscal years (current, -1, -2, -3 and older)
# 			fy_list = []
# 			fy = current_fy
# 			for i in range(4):  # Get 4 fiscal years
# 				if fy:
# 					fy_list.append(fy)
# 					fy = self.get_fiscal_year_before(fy)
# 				else:
# 					fy_list.append(None)

# 			# Get all older fiscal years for "more than 3 years"
# 			older_fys = []
# 			if fy:  # fy is now the 5th fiscal year (if exists)
# 				older_fys.append(fy)
# 				next_older = self.get_fiscal_year_before(fy)
# 				while next_older:
# 					older_fys.append(next_older)
# 					next_older = self.get_fiscal_year_before(next_older)

# 			def get_cwip_total(fiscal_year):
# 				"""Get CWIP totals for a fiscal year"""
# 				if not fiscal_year:
# 					return 0, 0
# 				result = frappe.db.sql("""
# 					SELECT
# 						SUM(sap_transaction_acq_value) AS total_acq_value,
# 						SUM(sap_ebv) AS total_ebv
# 					FROM `tabFR Asset Register Entry`
# 					WHERE sap_ebv > 0
# 					AND sap_transaction_acq_value >= 0
# 					AND asset_class = 'CWIP'
# 					AND company = %s
# 					AND fiscal_year = %s
# 				""", (self.company, fiscal_year), as_dict=True)
# 				total_acq = result[0].total_acq_value or 0 if result else 0
# 				total_ebv = result[0].total_ebv or 0 if result else 0
# 				return total_acq, total_ebv

# 			# Less than 1 year: total_acq_value (current FY)
# 			acq_0, ebv_0 = get_cwip_total(fy_list[0])
# 			less_1_year = acq_0

# 			# 1-2 years: ebv_0 - acq_0 (current FY)
# 			acq_1, ebv_1 = get_cwip_total(fy_list[1])
# 			one_to_2_years = ebv_0 - acq_0

# 			# 2-3 years: ebv_1 - acq_1 (FY-1)
# 			acq_2, ebv_2 = get_cwip_total(fy_list[2])
# 			two_to_3_years = ebv_1 - acq_1

# 			# More than 3 years: ebv_2 - acq_2 (FY-2)
# 			acq_3, ebv_3 = get_cwip_total(fy_list[3])
# 			more_3_years = ebv_2 - acq_2

# 			return less_1_year, one_to_2_years, two_to_3_years, more_3_years

# 		# Calculate Projects in progress values for current year
# 		cy_pip_less_1, cy_pip_1_to_2, cy_pip_2_to_3, cy_pip_more_3 = get_cwip_values_for_date(self.fiscal_year)

# 		# Calculate Projects in progress values for previous year
# 		py_pip_less_1, py_pip_1_to_2, py_pip_2_to_3, py_pip_more_3 = get_cwip_values_for_date(self.previous_fiscal_year)

# 		# Fetch data from FR CWIP Master for "Projects temporarily suspended"
# 		cwip_data = frappe.db.get_value(
# 			"FR CWIP Master",
# 			{"financial_report": self.name},
# 			[
# 				"less_than_1_year_current", "1_to_2_years_current", "2_to_3_years_current", "more_than_3_years_current",
# 				"less_than_1_year_previous", "1_to_2_years_previous", "2_to_3_years_previous", "more_than_3_years_previous"
# 			],
# 			as_dict=True
# 		) or {}

# 		# Current year - Projects temporarily suspended
# 		cy_pts_less_1 = cwip_data.get("less_than_1_year_current") or 0
# 		cy_pts_1_to_2 = cwip_data.get("1_to_2_years_current") or 0
# 		cy_pts_2_to_3 = cwip_data.get("2_to_3_years_current") or 0
# 		cy_pts_more_3 = cwip_data.get("more_than_3_years_current") or 0

# 		# Previous year - Projects temporarily suspended
# 		py_pts_less_1 = cwip_data.get("less_than_1_year_previous") or 0
# 		py_pts_1_to_2 = cwip_data.get("1_to_2_years_previous") or 0
# 		py_pts_2_to_3 = cwip_data.get("2_to_3_years_previous") or 0
# 		py_pts_more_3 = cwip_data.get("more_than_3_years_previous") or 0

# 		# Calculate totals for Projects in progress
# 		cy_pip_total = cy_pip_less_1 + cy_pip_1_to_2 + cy_pip_2_to_3 + cy_pip_more_3
# 		py_pip_total = py_pip_less_1 + py_pip_1_to_2 + py_pip_2_to_3 + py_pip_more_3

# 		# Calculate totals for Projects temporarily suspended
# 		cy_pts_total = cy_pts_less_1 + cy_pts_1_to_2 + cy_pts_2_to_3 + cy_pts_more_3
# 		py_pts_total = py_pts_less_1 + py_pts_1_to_2 + py_pts_2_to_3 + py_pts_more_3

# 		pre_py_pip_less_1, pre_py_pip_1_to_2, pre_py_pip_2_to_3, pre_py_pip_more_3 = get_cwip_values_for_date(pre_year)
# 		pre_py_pip_total = pre_py_pip_less_1 + pre_py_pip_1_to_2 + pre_py_pip_2_to_3 + pre_py_pip_more_3

# 		if field == "curr_pre_total":
# 			return (cy_pip_total - py_pip_total) / 100000
# 		elif field == "prev_pre_total":
# 			return (py_pip_total - pre_py_pip_total) / 100000

# 		html = f'''
# 			<table style="border-collapse: collapse; border: 1px solid black; width: 100%; table-layout: auto; margin-top: -30px;">
# 				<thead>
# 					<tr>
# 						<th style="border: 1px solid black; border-bottom:1px solid black;">Particulars</th>
# 						<th style="border: 1px solid black; border-bottom:1px solid black;" colspan="2">As at {current_year_ending_date_display}</th>
# 						<th style="border: 1px solid black; border-bottom:1px solid black;" colspan="2">As at {previous_year_ending_date_display}</th>
# 					</tr>
# 				</thead>
# 				<tbody>
# 					<tr>
# 						<td style="border-left: 1px solid black;border-right: 1px solid black;border-top:1px solid black; border-bottom: 1px solid black;"><b>Amount in CWIP for a period of<b></td>
# 						<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: 1px solid black;"><b>Projects in progress</b></td>
# 						<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: 1px solid black;"><b>Projects temporarily suspended</b></td>
# 						<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: 1px solid black;"><b>Projects in progress</b></td>
# 						<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: 1px solid black;"><b>Projects temporarily suspended</b></td>
# 					</tr>
# 					<tr>
# 						<td style="border-top: 1px solid black;border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Less than 1 year</td>
# 						<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(cy_pip_less_1)}</td>
# 						<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(cy_pts_less_1)}</td>
# 						<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_pip_less_1)}</td>
# 						<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_pts_less_1)}</td>
# 					</tr>
# 					<tr>
# 						<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">1-2 years</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(cy_pip_1_to_2)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(cy_pts_1_to_2)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_pip_1_to_2)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_pts_1_to_2)}</td>
# 					</tr>
# 					<tr>
# 						<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:none;">2-3 years</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(cy_pip_2_to_3)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(cy_pts_2_to_3)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_pip_2_to_3)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_pts_2_to_3)}</td>
# 					</tr>
# 					<tr>
# 						<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">More than 3 years</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_pip_more_3)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_pts_more_3)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_pip_more_3)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_pts_more_3)}</td>
# 					</tr>

# 					<tr>
# 						<td style="border:1px solid black;"><b>Total<b></td>
# 						<td style="border:1px solid black;"><b>{fmt(cy_pip_total)}</b></td>
# 						<td style="border:1px solid black;"><b>{fmt(cy_pts_total)}</b></td>
# 						<td style="border:1px solid black;"><b>{fmt(py_pip_total)}</b></td>
# 						<td style="border:1px solid black;"><b>{fmt(py_pts_total)}</b></td>
# 					</tr>
# 				</tbody>
# 			</table>
# 		'''
# 		return section_description.replace("{{note_table}}", html)
		

# 	def get_yearly_right_of_use_assets(self, section_description=""):
# 		# Convert to date objects if they are strings
# 		prev_year_end_date = frappe.utils.getdate(self.previous_year_ending_date)
# 		curr_year_end_date = frappe.utils.getdate(self.current_year_ending_date)

# 		previous_year_ending_date = prev_year_end_date.strftime("%d %B %Y")
# 		previous_year_starting_date = prev_year_end_date.replace(year=prev_year_end_date.year - 1, month=4, day=1).strftime("%d %B %Y")
# 		current_year_ending_date = curr_year_end_date.strftime("%d %B %Y")

# 		# Right of Use Asset classes
# 		asset_classes = [
# 			"Right-of-use assets - Vehicles",
# 			"Right-of-use assets - Immovable property"
# 		]

# 		# Define years
# 		previous_year = {
# 			"start": prev_year_end_date.replace(year=prev_year_end_date.year - 1, month=4, day=1).strftime("%Y-%m-%d"),
# 			"end": prev_year_end_date.strftime("%Y-%m-%d")
# 		}
# 		current_year = {
# 			"start": curr_year_end_date.replace(year=curr_year_end_date.year - 1, month=4, day=1).strftime("%Y-%m-%d"),
# 			"end": curr_year_end_date.strftime("%Y-%m-%d")
# 		}

# 		prev_year_start = frappe.utils.getdate(previous_year["start"])
# 		prev_year_end = frappe.utils.getdate(previous_year["end"])
# 		curr_year_start = frappe.utils.getdate(current_year["start"])
# 		curr_year_end = frappe.utils.getdate(current_year["end"])

# 		# Initialize result dictionaries
# 		result = {
# 			"previous_year": {},
# 			"current_year": {},
# 			"previous_year_acc_dep": {},
# 			"current_year_acc_dep": {}
# 		}

# 		for asset in asset_classes:
# 			# Fetch data for previous year
# 			prev_data = frappe.db.get_all(
# 				'FR Asset Register Entry',
# 				fields=['name', 'sap_transaction_acq_value', 'sap_cav', 'sap_tran_accu_dep', 'sap_acc_dep', 'sap_plan_dep', 'ordinary_depreciation_start_date'],
# 				filters={
# 					'company': self.company,
# 					'asset_class': asset,
# 					'ordinary_depreciation_start_date': ['between', [previous_year["start"], previous_year["end"]]]
# 				},
# 				order_by='ordinary_depreciation_start_date asc'
# 			)

# 			# Fetch data for current year
# 			curr_data = frappe.db.get_all(
# 				'FR Asset Register Entry',
# 				fields=['name', 'sap_transaction_acq_value', 'sap_cav', 'sap_tran_accu_dep', 'sap_acc_dep', 'sap_plan_dep', 'ordinary_depreciation_start_date'],
# 				filters={
# 					'company': self.company,
# 					'asset_class': asset,
# 					'ordinary_depreciation_start_date': ['between', [current_year["start"], current_year["end"]]]
# 				},
# 				order_by='ordinary_depreciation_start_date asc'
# 			)

# 			# PREVIOUS YEAR (SAP CAV) - Gross Carrying Amount
# 			prev_opening_value = 0.0
# 			prev_positive = 0.0
# 			prev_negative = 0.0

# 			for entry in prev_data:
# 				if entry.sap_cav:
# 					prev_opening_value = float(entry.sap_cav)
# 					break

# 			for entry in prev_data:
# 				value = float(entry.sap_transaction_acq_value) if entry.sap_transaction_acq_value else 0.0
# 				if value > 0:
# 					prev_positive += value
# 				elif value < 0:
# 					prev_negative += value

# 			prev_closing_value = prev_opening_value + prev_positive + prev_negative

# 			result["previous_year"][asset] = {
# 				"opening_value": prev_opening_value,
# 				"positive_transaction": prev_positive,
# 				"negative_transaction": prev_negative,
# 				"closing_value": prev_closing_value
# 			}

# 			# CURRENT YEAR (SAP CAV) - Gross Carrying Amount
# 			curr_opening_value = prev_closing_value
# 			curr_positive = 0.0
# 			curr_negative = 0.0

# 			for entry in curr_data:
# 				value = float(entry.sap_transaction_acq_value) if entry.sap_transaction_acq_value else 0.0
# 				if value > 0:
# 					curr_positive += value
# 				elif value < 0:
# 					curr_negative += value

# 			curr_closing_value = curr_opening_value + curr_positive + curr_negative

# 			result["current_year"][asset] = {
# 				"opening_value": curr_opening_value,
# 				"positive_transaction": curr_positive,
# 				"negative_transaction": curr_negative,
# 				"closing_value": curr_closing_value
# 			}

# 			# PREVIOUS YEAR (SAP Acc Dep) - Accumulated Amortisation
# 			prev_acc_opening_value = 0.0
# 			prev_acc_positive = 0.0
# 			prev_acc_negative = 0.0

# 			for entry in prev_data:
# 				if entry.sap_acc_dep:
# 					prev_acc_opening_value = abs(float(entry.sap_acc_dep))
# 					break

# 			for entry in prev_data:
# 				value = float(entry.sap_tran_accu_dep) if entry.sap_tran_accu_dep else 0.0
# 				if value > 0:
# 					prev_acc_negative += value
# 				elif value < 0:
# 					prev_acc_positive += abs(value)

# 				plan_value = float(entry.sap_plan_dep) if entry.sap_plan_dep else 0.0
# 				prev_acc_positive += abs(plan_value)

# 			prev_acc_closing_value = prev_acc_opening_value + prev_acc_positive - prev_acc_negative

# 			result["previous_year_acc_dep"][asset] = {
# 				"opening_value": prev_acc_opening_value,
# 				"positive_transaction": prev_acc_positive,
# 				"negative_transaction": prev_acc_negative,
# 				"closing_value": prev_acc_closing_value
# 			}

# 			# CURRENT YEAR (SAP Acc Dep) - Accumulated Amortisation
# 			curr_acc_opening_value = prev_acc_closing_value
# 			curr_acc_positive = 0.0
# 			curr_acc_negative = 0.0

# 			for entry in curr_data:
# 				value = float(entry.sap_tran_accu_dep) if entry.sap_tran_accu_dep else 0.0
# 				if value > 0:
# 					curr_acc_negative += value
# 				elif value < 0:
# 					curr_acc_positive += abs(value)

# 				plan_value = float(entry.sap_plan_dep) if entry.sap_plan_dep else 0.0
# 				curr_acc_positive += abs(plan_value)

# 			curr_acc_closing_value = curr_acc_opening_value + curr_acc_positive - curr_acc_negative

# 			result["current_year_acc_dep"][asset] = {
# 				"opening_value": curr_acc_opening_value,
# 				"positive_transaction": curr_acc_positive,
# 				"negative_transaction": curr_acc_negative,
# 				"closing_value": curr_acc_closing_value
# 			}

# 		# Helper function to format values in lacs (÷100000)
# 		def fmt(val):
# 			if val is None:
# 				return "0.00"
# 			return f"{val / 100000:,.2f}"

# 		# Get values for each asset class
# 		def get_val(data_dict, asset, key):
# 			if asset in data_dict and data_dict[asset].get(key) is not None:
# 				return data_dict[asset][key]
# 			return 0

# 		# I. Gross carrying amount values
# 		py_opening = {asset: get_val(result["previous_year"], asset, "opening_value") for asset in asset_classes}
# 		py_opening_total = sum(v for v in py_opening.values() if v)

# 		py_additions = {asset: get_val(result["previous_year"], asset, "positive_transaction") for asset in asset_classes}
# 		py_additions_total = sum(v for v in py_additions.values() if v)

# 		py_disposals = {asset: get_val(result["previous_year"], asset, "negative_transaction") for asset in asset_classes}
# 		py_disposals_total = sum(v for v in py_disposals.values() if v)

# 		py_closing = {asset: get_val(result["previous_year"], asset, "closing_value") for asset in asset_classes}
# 		py_closing_total = sum(v for v in py_closing.values() if v)

# 		cy_additions = {asset: get_val(result["current_year"], asset, "positive_transaction") for asset in asset_classes}
# 		cy_additions_total = sum(v for v in cy_additions.values() if v)

# 		cy_disposals = {asset: get_val(result["current_year"], asset, "negative_transaction") for asset in asset_classes}
# 		cy_disposals_total = sum(v for v in cy_disposals.values() if v)

# 		cy_closing = {asset: get_val(result["current_year"], asset, "closing_value") for asset in asset_classes}
# 		cy_closing_total = sum(v for v in cy_closing.values() if v)

# 		# II. Accumulated amortisation values
# 		py_acc_opening = {asset: get_val(result["previous_year_acc_dep"], asset, "opening_value") for asset in asset_classes}
# 		py_acc_opening_total = sum(v for v in py_acc_opening.values() if v)

# 		py_acc_for_year = {asset: get_val(result["previous_year_acc_dep"], asset, "positive_transaction") for asset in asset_classes}
# 		py_acc_for_year_total = sum(v for v in py_acc_for_year.values() if v)

# 		py_acc_disposals = {asset: get_val(result["previous_year_acc_dep"], asset, "negative_transaction") for asset in asset_classes}
# 		py_acc_disposals_total = sum(v for v in py_acc_disposals.values() if v)

# 		py_acc_closing = {asset: get_val(result["previous_year_acc_dep"], asset, "closing_value") for asset in asset_classes}
# 		py_acc_closing_total = sum(v for v in py_acc_closing.values() if v)

# 		cy_acc_for_year = {asset: get_val(result["current_year_acc_dep"], asset, "positive_transaction") for asset in asset_classes}
# 		cy_acc_for_year_total = sum(v for v in cy_acc_for_year.values() if v)

# 		cy_acc_disposals = {asset: get_val(result["current_year_acc_dep"], asset, "negative_transaction") for asset in asset_classes}
# 		cy_acc_disposals_total = sum(v for v in cy_acc_disposals.values() if v)

# 		cy_acc_closing = {asset: get_val(result["current_year_acc_dep"], asset, "closing_value") for asset in asset_classes}
# 		cy_acc_closing_total = sum(v for v in cy_acc_closing.values() if v)

# 		# III. Net carrying amount = Gross Closing - Accumulated Amortisation Closing
# 		py_net = {asset: (py_closing.get(asset, 0) or 0) - (py_acc_closing.get(asset, 0) or 0) for asset in asset_classes}
# 		py_net_total = py_closing_total - py_acc_closing_total

# 		cy_net = {asset: (cy_closing.get(asset, 0) or 0) - (cy_acc_closing.get(asset, 0) or 0) for asset in asset_classes}
# 		cy_net_total = cy_closing_total - cy_acc_closing_total

# 		html = f'''
# 		<table style="margin-top: -20px; margin-bottom: -20px; border-collapse: collapse; border: 1px solid black; width: 100%; table-layout: fixed;">
# 			<thead>
# 				<tr style="color: #4472C4;">
# 					<th style="width: 40%; border: 1px solid black; border-bottom:1px solid black;">Particulars</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black;">Right-of-use assets - Vehicles</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black;">Right-of-use assets - Immovable property</th>
# 					<th style="border: 1px solid black; border-bottom:1px solid black;">Total</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 				<tr>
# 					<td style="border-left: 1px solid black;border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"><b>I. Gross carrying amount</b></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
					
# 				</tr>
# 				<tr>
# 					<td style="border-top: 1px solid black;border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">As at {previous_year_starting_date}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Right-of-use assets - Vehicles"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Right-of-use assets - Immovable property"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening_total)}</td>					
# 				</tr>
# 				<tr>
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Additions</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Right-of-use assets - Vehicles"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Right-of-use assets - Immovable property"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions_total)}</td>
					
# 				</tr>
# 				<tr>
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">Disposals</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Right-of-use assets - Vehicles"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Right-of-use assets - Immovable property"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals_total)}</td>					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border:1px solid black;"><b>As at {previous_year_ending_date}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing.get("Right-of-use assets - Vehicles"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing.get("Right-of-use assets - Immovable property"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_closing_total)}</b></td>					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-bottom:none;">Additions</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Right-of-use assets - Vehicles"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Right-of-use assets - Immovable property"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions_total)}</td>					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:1px solid black;">Disposals, transfer and adjustments</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Right-of-use assets - Vehicles"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Right-of-use assets - Immovable property"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals_total)}</td>					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border:1px solid black;"><b>As at {current_year_ending_date}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Right-of-use assets - Vehicles"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Right-of-use assets - Immovable property"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_closing_total)}</b></td>
# 				</tr>
# 				<tr>
# 					<td style="border-left: 1px solid black;border-right: 1px solid black; border-bottom: none;"><b>II.  Accumulated amortisation<b></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>
# 					<td style="border-right: 1px solid black; border-bottom: none;"></td>					
# 				</tr>
# 				<tr>
# 					<td style="border-top: 1px solid black;border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">As at {previous_year_starting_date}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Right-of-use assets - Vehicles"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Right-of-use assets - Immovable property"))}</td>
# 					<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening_total)}</td>					
# 				</tr>
# 				<tr>
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Year Ended {previous_year_ending_date}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Right-of-use assets - Vehicles"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Right-of-use assets - Immovable property"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year_total)}</td>					
# 				</tr>
# 				<tr>
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">Disposals</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Right-of-use assets - Vehicles"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Right-of-use assets - Immovable property"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals_total)}</td>					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border:1px solid black;"><b>Upto {previous_year_ending_date}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Right-of-use assets - Vehicles"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Right-of-use assets - Immovable property"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_acc_closing_total)}</b></td>					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-bottom:none;">Year Ended {current_year_ending_date}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Right-of-use assets - Vehicles"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Right-of-use assets - Immovable property"))}</td>
# 					<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year_total)}</td>					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:1px solid black;">Disposals and adjustments</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Right-of-use assets - Vehicles"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Right-of-use assets - Immovable property"))}</td>
# 					<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals_total)}</td>					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border:1px solid black;"><b>Upto {current_year_ending_date}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Right-of-use assets - Vehicles"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Right-of-use assets - Immovable property"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_acc_closing_total)}</b></td>					
# 				</tr>
# 				<tr>
# 					<td style="border:1px solid black;"><b>III.  Net carrying amount</b></td>
# 					<td style="border:1px solid black;"><b></b></td>
# 					<td style="border:1px solid black;"><b></b></td>
# 					<td style="border:1px solid black;"><b></b></td>					
# 				</tr>
# 				<tr>
# 					<td style="border:1px solid black;"><b>As at {previous_year_ending_date}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net.get("Right-of-use assets - Vehicles"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net.get("Right-of-use assets - Immovable property"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(py_net_total)}</b></td>					
# 				</tr>
# 				<tr style="background-color: #E8F5E8;">
# 					<td style="border:1px solid black;"><b>As at {current_year_ending_date}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net.get("Right-of-use assets - Vehicles"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net.get("Right-of-use assets - Immovable property"))}</b></td>
# 					<td style="border:1px solid black;"><b>{fmt(cy_net_total)}</b></td>					
# 				</tr>
# 			</tbody>
# 		</table>

# 		'''
# 		return section_description.replace("{{note_table}}", html)

# 	def get_yearly_intangible_assets_under_development(self, company, section_description="", field=""):
# 		curr_year_end_date = frappe.utils.getdate(self.current_year_ending_date)
# 		prev_year_end_date = frappe.utils.getdate(self.previous_year_ending_date)
# 		previous_year_ending_date_display = prev_year_end_date.strftime("%d %B %Y")
# 		current_year_ending_date_display = curr_year_end_date.strftime("%d %B %Y")
# 		cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)

# 		def fmt(val):
# 			return "{:,.2f}".format(val / 100000) if val else "0.00"

# 		def get_iaud_values_for_date(current_fy):
# 			"""Calculate Intangible Assets Under Development values for Projects in progress based on ending date"""
# 			if not current_fy:
# 				return 0, 0, 0, 0

# 			# Build list of fiscal years (current, -1, -2, -3 and older)
# 			fy_list = []
# 			fy = current_fy
# 			for i in range(4):  # Get 4 fiscal years
# 				if fy:
# 					fy_list.append(fy)
# 					fy = self.get_fiscal_year_before(fy)
# 				else:
# 					fy_list.append(None)

# 			def get_iaud_total(company, fiscal_year):
# 				"""Get Intangible Assets Under Development totals for a fiscal year"""
# 				if not fiscal_year:
# 					return 0, 0
# 				result = frappe.db.sql("""
# 					SELECT
# 						SUM(sap_transaction_acq_value) AS total_acq_value,
# 						SUM(sap_ebv) AS total_ebv
# 					FROM `tabFR Asset Register Entry`
# 					WHERE sap_ebv > 0
# 					AND sap_transaction_acq_value >= 0
# 					AND asset_class = 'CWIP Intangible Asse'
# 					AND company = %s
# 					AND fiscal_year = %s
# 				""", (company, fiscal_year), as_dict=True)
# 				total_acq = result[0].total_acq_value or 0 if result else 0
# 				total_ebv = result[0].total_ebv or 0 if result else 0
# 				return total_acq, total_ebv

# 			# Less than 1 year: total_acq_value (current FY)
# 			acq_0, ebv_0 = get_iaud_total(company, fy_list[0])
# 			less_1_year = acq_0

# 			# 1-2 years: ebv_0 - acq_0 (current FY)
# 			acq_1, ebv_1 = get_iaud_total(fy_list[1])
# 			one_to_2_years = ebv_0 - acq_0

# 			# 2-3 years: ebv_1 - acq_1 (FY-1)
# 			acq_2, ebv_2 = get_iaud_total(fy_list[2])
# 			two_to_3_years = ebv_1 - acq_1

# 			# More than 3 years: ebv_2 - acq_2 (FY-2)
# 			acq_3, ebv_3 = get_iaud_total(fy_list[3])
# 			more_3_years = ebv_2 - acq_2

# 			return less_1_year, one_to_2_years, two_to_3_years, more_3_years

# 		# Calculate Projects in progress values for current year
# 		cy_pip_less_1, cy_pip_1_to_2, cy_pip_2_to_3, cy_pip_more_3 = get_iaud_values_for_date(self.fiscal_year)

# 		# Calculate Projects in progress values for previous year
# 		py_pip_less_1, py_pip_1_to_2, py_pip_2_to_3, py_pip_more_3 = get_iaud_values_for_date(self.previous_fiscal_year)

# 		# Fetch data from FR CWIP Master for "Projects temporarily suspended" (change doctype as needed)
# 		iaud_data = frappe.db.get_value(
# 			"FR CWIP Intangible Asse Master",
# 			{"financial_report": self.name},
# 			[
# 				"less_than_1_year_current", "1_to_2_years_current", "2_to_3_years_current", "more_than_3_years_current",
# 				"less_than_1_year_previous", "1_to_2_years_previous", "2_to_3_years_previous", "more_than_3_years_previous"
# 			],
# 			as_dict=True
# 		) or {}

# 		# Current year - Projects temporarily suspended
# 		cy_pts_less_1 = iaud_data.get("less_than_1_year_current") or 0
# 		cy_pts_1_to_2 = iaud_data.get("1_to_2_years_current") or 0
# 		cy_pts_2_to_3 = iaud_data.get("2_to_3_years_current") or 0
# 		cy_pts_more_3 = iaud_data.get("more_than_3_years_current") or 0

# 		# Previous year - Projects temporarily suspended
# 		py_pts_less_1 = iaud_data.get("less_than_1_year_previous") or 0
# 		py_pts_1_to_2 = iaud_data.get("1_to_2_years_previous") or 0
# 		py_pts_2_to_3 = iaud_data.get("2_to_3_years_previous") or 0
# 		py_pts_more_3 = iaud_data.get("more_than_3_years_previous") or 0

# 		# Calculate totals for Projects in progress
# 		cy_pip_total = cy_pip_less_1 + cy_pip_1_to_2 + cy_pip_2_to_3 + cy_pip_more_3
# 		py_pip_total = py_pip_less_1 + py_pip_1_to_2 + py_pip_2_to_3 + py_pip_more_3

# 		# Calculate totals for Projects temporarily suspended
# 		cy_pts_total = cy_pts_less_1 + cy_pts_1_to_2 + cy_pts_2_to_3 + cy_pts_more_3
# 		py_pts_total = py_pts_less_1 + py_pts_1_to_2 + py_pts_2_to_3 + py_pts_more_3

# 		pre_py_pip_less_1, pre_py_pip_1_to_2, pre_py_pip_2_to_3, pre_py_pip_more_3 = get_iaud_values_for_date(pre_year)
# 		pre_py_pip_total = pre_py_pip_less_1 + pre_py_pip_1_to_2 + pre_py_pip_2_to_3 + pre_py_pip_more_3
# 		if field == "curr_total":
# 			return (cy_pip_total - py_pip_total) / 100000
# 		elif field == "prev_total":
# 			return (py_pip_total - pre_py_pip_total) / 100000

# 		html = f'''
# 			<table style="border-collapse: collapse; border: 1px solid black; width: 100%; table-layout: auto; margin-top: 30px;">
# 				<thead>
# 					<tr>
# 						<th style="border: 1px solid black; border-bottom:1px solid black;">Particulars</th>
# 						<th style="border: 1px solid black; border-bottom:1px solid black;" colspan="2">As at {current_year_ending_date_display}</th>
# 						<th style="border: 1px solid black; border-bottom:1px solid black;" colspan="2">As at {previous_year_ending_date_display}</th>
# 					</tr>
# 				</thead>
# 				<tbody>
# 					<tr>
# 						<td style="border-left: 1px solid black;border-right: 1px solid black;border-top:1px solid black; border-bottom: 1px solid black;"><b>Amount in CWIP for a period of<b></td>
# 						<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: 1px solid black;"><b>Projects in progress</b></td>
# 						<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: 1px solid black;"><b>Projects temporarily suspended</b></td>
# 						<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: 1px solid black;"><b>Projects in progress</b></td>
# 						<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: 1px solid black;"><b>Projects temporarily suspended</b></td>
# 					</tr>
# 					<tr>
# 						<td style="border-top: 1px solid black;border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Less than 1 year</td>
# 						<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(cy_pip_less_1)}</td>
# 						<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(cy_pts_less_1)}</td>
# 						<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_pip_less_1)}</td>
# 						<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_pts_less_1)}</td>
# 					</tr>
# 					<tr>
# 						<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">1-2 years</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(cy_pip_1_to_2)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(cy_pts_1_to_2)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_pip_1_to_2)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_pts_1_to_2)}</td>
# 					</tr>
# 					<tr>
# 						<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:none;">2-3 years</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(cy_pip_2_to_3)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(cy_pts_2_to_3)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_pip_2_to_3)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_pts_2_to_3)}</td>
# 					</tr>
# 					<tr>
# 						<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">More than 3 years</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_pip_more_3)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_pts_more_3)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_pip_more_3)}</td>
# 						<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_pts_more_3)}</td>
# 					</tr>

# 					<tr>
# 						<td style="border:1px solid black;"><b>Total<b></td>
# 						<td style="border:1px solid black;"><b>{fmt(cy_pip_total)}</b></td>
# 						<td style="border:1px solid black;"><b>{fmt(cy_pts_total)}</b></td>
# 						<td style="border:1px solid black;"><b>{fmt(py_pip_total)}</b></td>
# 						<td style="border:1px solid black;"><b>{fmt(py_pts_total)}</b></td>
# 					</tr>
# 				</tbody>
# 			</table>
# 		'''
# 		return html

# 	def render_yearly_equity_share_table(self, section_description=""):
# 		def fmt(val):
# 			if val is None:
# 				return ""
# 			if isinstance(val, (int, float)):
# 				return f"({abs(val):,})" if val < 0 else f"{val:,}"
# 			return val

# 		data = [
# 			("As at 1st April, 2023", 59360000, 5936, True),
# 			("Changes in equity share capital during the year", None, None, False),
# 			("Balance as at 31st March, 2024", 59360000, 5936, True),
# 			("Changes in equity share capital during the year", None, None, False),
# 			("Balance as at 31st March, 2025", 59360000, 5936, True),
# 		]

# 		html = """
# 		<p><strong style="color:#4472C4; font-size:13px;">A. Equity Share Capital</strong></p>
# 		<table style="width:100%; border-collapse:collapse; border-spacing:0; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr style="color:#4472C4; background-color:#E8F5E8;">
# 					<th style="background-color:#E8F5E8; border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:left; padding:2px 5px; width:60%;">Particulars</th>
# 					<th style="background-color:#E8F5E8; border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:right; padding:2px 5px; width:20%;">Number of Shares</th>
# 					<th style="background-color:#E8F5E8; border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #4473C4;">Equity share capital</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		for row in data:
# 			particulars, shares, capital, is_balance = row
# 			if is_balance:
# 				border = "border:1px solid #222;"
# 			else:
# 				border = "border-left:1px solid #222; border-right:1px solid #222; border-top:none; border-bottom:none;"
# 			bold = "font-weight:bold;" if is_balance else ""

# 			html += f"""
# 			<tr style="line-height:1; border:none;">
# 				<td style="padding:2px 5px; {border} {bold}">{particulars}</td>
# 				<td style="padding:2px 5px; text-align:right; {border} {bold}">{fmt(shares)}</td>
# 				<td style="padding:2px 5px; text-align:right; {border} {bold}">{fmt(capital)}</td>
# 			</tr>
# 			"""

# 		html += "</tbody></table>"

# 		data = [
# 			("Balance as at 31st March, 2023", 41144, 4459, 45603, True),
# 			("Profit for the year", 18111, None, 18111, False),
# 			("Other comprehensive income", -72, None, -72, False),
# 			("Balance as at 31st March, 2024", 59183, 4459, 63642, True),
# 			("Profit for the year", 42545, None, 42545, False),
# 			("Other comprehensive income", -142, None, -142, False),
# 			("Add: Equity contribution on financial guarantee taken", None, 3, 3, False),
# 			("Balance as at 31st March, 2025", 101586, 4462, 106048, True),
# 		]

# 		html += """
# 		<br>
# 		<p><strong style="color:#4472C4; font-size:13px;">B. Other Equity</strong></p>
# 		<table style="width:100%; border-collapse:collapse; border-spacing:0; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr style="color:#4472C4; background-color:#E8F5E8;">
# 					<th style="background-color:#E8F5E8; border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:left; padding:2px 5px; width:40%;">Particulars</th>
# 					<th style="background-color:#E8F5E8; border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:right; padding:2px 5px; width:20%;">Retained Earnings</th>
# 					<th style="background-color:#E8F5E8; border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:right; padding:2px 5px; width:20%;">Capital Contribution</th>
# 					<th style="background-color:#E8F5E8; border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:right; padding:2px 5px; width:20%;">Total Other Equity</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		for row in data:
# 			particulars, re, cc, total, is_balance = row
# 			# Only vertical borders for regular rows, full borders for balance rows
# 			if is_balance:
# 				border = "border:1px solid #222;"
# 			else:
# 				border = "border-left:1px solid #222; border-right:1px solid #222; border-top:none; border-bottom:none;"
# 			bold = "font-weight:bold;" if is_balance else ""

# 			html += f"""
# 			<tr style="line-height:1; border:none;">
# 				<td style="padding:2px 5px; {border} {bold}">{particulars}</td>
# 				<td style="padding:2px 5px; text-align:right; {border} {bold}">{fmt(re)}</td>
# 				<td style="padding:2px 5px; text-align:right; {border} {bold}">{fmt(cc)}</td>
# 				<td style="padding:2px 5px; text-align:right; {border} {bold}">{fmt(total)}</td>
# 			</tr>
# 			"""

# 		html += "</tbody></table>"
# 		return html


# 	def get_yearly_current_tax_note_data(self, section_description=""):
# 		# Get dynamic date labels
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_year_label.replace("Year Ended ", "").replace("/", "-")
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")

# 		def fmt(val):
# 			if val < 0:
# 				return f"({abs(val):,})"
# 			return f"{val:,}"

# 		html = ""
# 		cur_current_tax = self.get_sum_grouping_amount(company, "P&L", "Current Tax", cls_month, self.fiscal_year)
# 		pre_current_tax = self.get_sum_grouping_amount(company, "P&L", "Current Tax", cls_month, self.previous_fiscal_year)
# 		cur_prior_year_adj = self.get_sum_grouping_amount(company, "P&L", "Prior Year Adjustment", cls_month, self.fiscal_year)
# 		pre_prior_year_adj = self.get_sum_grouping_amount(company, "P&L", "Prior Year Adjustment", cls_month, self.previous_fiscal_year)
# 		a_data = {
# 			"current": {"current_tax": cur_current_tax, "prior_year_adj": cur_prior_year_adj, "deferred_tax": -38},
# 			"previous": {"current_tax": pre_current_tax, "prior_year_adj": -43, "deferred_tax": -220},
# 		}

# 		for y in a_data:
# 			a_data[y]["total_current"] = (a_data[y]["current_tax"] + a_data[y]["prior_year_adj"])
# 			a_data[y]["total_tax"] = (a_data[y]["total_current"] + a_data[y]["deferred_tax"])

# 		html += f"""
# 		<p><strong style="color:#4472C4; font-size:13px;">(a) Income Tax Expenses</strong></p>
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000; background-color:#fff; margin-top:10px;">
# 			<thead>
# 				<tr style="background-color:#fff;">
# 					<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#fff;">Particulars</th>
# 					<th style="border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4; background-color:#fff;">As at {current_date}</th>
# 					<th style="border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4; background-color:#fff;">As at {previous_date}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px;">i) Current Tax</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;"></td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right;"></td>
# 				</tr>

# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">  Current tax</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(a_data["current"]["current_tax"])}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(a_data["previous"]["current_tax"])}</td>
# 				</tr>

# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">  Adjustment for prior years</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(a_data["current"]["prior_year_adj"])}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(a_data["previous"]["prior_year_adj"])}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; padding:6px;"><strong>Total current tax</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(a_data["current"]["total_current"])}</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(a_data["previous"]["total_current"])}</strong></td>
# 				</tr>

# 				<tr>
# 					<td style="border:border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px;">ii) Deferred Tax</td>
# 					<td style="border:border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;"></td>
# 					<td style="border:border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right;"></td>
# 				</tr>

# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">  Increase in deferred tax assets</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(a_data["current"]["deferred_tax"])}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(a_data["previous"]["deferred_tax"])}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; padding:6px;"><strong>Total Income tax expense</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(a_data["current"]["total_tax"])}</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(a_data["previous"]["total_tax"])}</strong></td>
# 				</tr>
# 			</tbody>
# 		</table>
# 		<br>
# 		"""

# 		# Fetch PBT from P&L Particular
# 		pbt_particular = frappe.get_value("FR Particular", {'type': "Profit Before Tax"}, 'name')
# 		cur_pbt = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Profit Before Tax"}, 'name'),'current_month_amount') or 0
# 		pre_pbt = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Profit Before Tax"}, 'name'),'previous_year') or 0

# 		# Fetch tax rate from FR Tax Master
# 		cur_tax_master = frappe.db.exists("FR Tax Master", {"company": self.company, "fiscal_year": self.fiscal_year})
# 		pre_tax_master = frappe.db.exists("FR Tax Master", {"company": self.company, "fiscal_year": self.previous_fiscal_year})
# 		if cur_tax_master:
# 			cur_tax_master_doc = frappe.get_doc("FR Tax Master", cur_tax_master)
# 			cur_rate = cur_tax_master_doc.profit_before_tax
# 			cur_diff_items = cur_tax_master_doc.difference_due_to
# 		else:
# 			cur_rate = 0
# 			cur_diff_items = []

# 		if pre_tax_master:
# 			pre_tax_master_doc = frappe.get_doc("FR Tax Master", pre_tax_master)
# 			pre_rate = pre_tax_master_doc.profit_before_tax
# 			pre_diff_items = pre_tax_master_doc.difference_due_to
# 		else:
# 			pre_rate = 0
# 			pre_diff_items = []

# 		# Build lookup for previous items by particulars
# 		pre_diff_map = {d.particulars: d for d in pre_diff_items}

# 		cur_tax_at_rate = round(cur_pbt * cur_rate / 100)
# 		pre_tax_at_rate = round(pre_pbt * pre_rate / 100)

# 		# Calculate total tax (tax_at_rate + sum of all difference values)
# 		cur_diff_total = sum(flt(d.value) for d in cur_diff_items)
# 		pre_diff_total = sum(flt(d.value) for d in pre_diff_items)
# 		cur_tax = cur_tax_at_rate + cur_diff_total
# 		pre_tax = pre_tax_at_rate + pre_diff_total
# 		cur_tax_pct = round(cur_tax / cur_pbt * 100, 2) if cur_pbt else 0
# 		pre_tax_pct = round(pre_tax / pre_pbt * 100, 2) if pre_pbt else 0

# 		html += f"""
# 		<p><strong style="color:#4472C4; font-size:13px;">b) Reconciliation between the average effective tax rate and applicable tax rate:</strong></p>
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000; background-color:#fff;">
# 			<thead>
# 				<tr style="background-color:#fff;">
# 					<th rowspan="2" style="width: 45%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#fff;">Particulars</th>
# 					<th colspan="2" style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#fff;">As at {current_date}</th>
# 					<th colspan="2" style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#fff;">As at {previous_date}</th>
# 				</tr>
# 				<tr style="background-color:#fff;">
# 					<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#fff;">Percentage</th>
# 					<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#fff;">(₹ in lacs)</th>
# 					<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#fff;">Percentage</th>
# 					<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#fff;">(₹ in lacs)</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px;font-weight: bold;">Profit before tax</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; background-color:#E8F5E8;">{cur_rate}%</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_pbt)}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px;">{pre_rate}%</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right;">{fmt(pre_pbt)}</td>
# 				</tr>

# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;font-weight: bold;">Tax at domestic rate</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; background-color:#E8F5E8;"></td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_tax_at_rate)}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;"></td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(pre_tax_at_rate)}</td>
# 				</tr>
# 		"""
# 		# Dynamic difference_due_to rows from FR Tax Master child table
# 		all_particulars = list(dict.fromkeys([d.particulars for d in cur_diff_items] + [d.particulars for d in pre_diff_items]))
# 		html += f"""
# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; font-weight: bold;">Difference due to :</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; background-color:#E8F5E8;"></td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;"></td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;"></td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;"></td>
# 				</tr>
# 				"""
# 		for particular in all_particulars:
# 			cur_d = next((d for d in cur_diff_items if d.particulars == particular), None)
# 			pre_d = pre_diff_map.get(particular)

# 			cur_pct = f'{flt(cur_d.percentage):.2f}%' if cur_d else ""
# 			pre_pct = f'{flt(pre_d.percentage):.2f}%' if pre_d else ""

# 			cur_val = flt(cur_d.value) if cur_d else 0
# 			pre_val = flt(pre_d.value) if pre_d else 0
# 			html += f"""
# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">{particular}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; background-color:#E8F5E8;">{cur_pct}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_val)}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">{pre_pct}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(pre_val)}</td>
# 				</tr>
# 			"""

# 		html += f"""
# 				<tr>
# 					<td style="border:1px solid #000; padding:6px;"><strong>Income tax expense</strong></td>
# 					<td style="border:1px solid #000; padding:6px; background-color:#E8F5E8;"><strong>{cur_tax_pct}%</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(cur_tax)}</strong></td>
# 					<td style="border:1px solid #000; padding:6px;"><strong>{pre_tax_pct}%</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(pre_tax)}</strong></td>
# 				</tr>
# 			</tbody>
# 		</table>
# 		<br>
# 		<p><strong style="color:#4472C4; font-size:13px;">c) Deferred Tax Assets (Net) </strong></p>
# 		<p><strong style="font-size:13px;">The balance comprises temporary differences attributable to the below items and corresponding movement in deferred tax assets:</strong></p>
# 		"""

# 		# (c) Deferred Tax Assets (Net)
# 		def render_dta_table(rows):
# 			if not rows:
# 				return ""
# 			total = [sum(col) for col in zip(*[r[1:] for r in rows])]
# 			table = f"""
# 			<table style="width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000; background-color:#fff;">
# 				<tr style="background-color:#fff;">
# 					<th style="width: 45%; border-top:1px solid #000; border-right:1px solid #000; border-left:1px solid #000; border-bottom:1px solid #000 !important; padding:6px; font-weight:bold; color:#4472C4; background-color:#fff;">Particulars</th>
# 					<th style="border-top:1px solid #000; border-right:1px solid #000; border-left:1px solid #000; border-bottom:1px solid #000 !important; padding:6px; font-weight:bold; text-align: center; color:#4472C4; background-color:#fff;">As at <br> {current_date}</th>
# 					<th style="border-top:1px solid #000; border-right:1px solid #000; border-left:1px solid #000; border-bottom:1px solid #000 !important; padding:6px; font-weight:bold; text-align: center; color:#4472C4; background-color:#fff;">(Charged)/Credited to <br> profit or loss</th>
# 					<th style="border-top:1px solid #000; border-right:1px solid #000; border-left:1px solid #000; border-bottom:1px solid #000 !important; padding:6px; font-weight:bold; text-align: center; color:#4472C4; background-color:#fff;">As at <br> {previous_date}</th>
# 				</tr>
# 			"""
# 			for r in rows:
# 				table += f"""
# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">{r[0]}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(r[1])}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(r[2])}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(r[3])}</td>
# 				</tr>
# 				"""
# 			table += f"""
# 				<tr>
# 					<td style="border:1px solid #000; padding:6px;"><strong>Total</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(total[0])}</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(total[1])}</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total[2])}</strong></td>
# 				</tr>
# 			</table>
# 			<br>
# 			"""
# 			return table
			
# 		# Dynamically fetch DTA rows from GL Group Mapping + FR Trial Balance Entry
# 		dta_primary_group = "Deferred tax assets (net)"
# 		dta_secondary_groups = sorted(set(
# 			g for g in frappe.get_list("GL Group Mapping", {"primary_group": dta_primary_group, "company": self.company}, pluck="secondary_group") if g
# 		))

# 		dta_rows = []
# 		for sec_group in dta_secondary_groups:
# 			gl_accounts = frappe.get_list("GL Group Mapping",
# 				{"company": self.company, "primary_group": dta_primary_group, "secondary_group": sec_group}, pluck="gl_account"
# 			)
# 			cur_amt = 0
# 			pre_amt = 0
# 			if gl_accounts:
# 				placeholders = ','.join(['%s'] * len(gl_accounts))
# 				query = f"SELECT SUM(uploaded_amount) FROM `tabFR Trial Balance Entry` WHERE company=%s AND fiscal_year=%s AND gl_account IN ({placeholders}) AND month=%s"
# 				cur_amt = round((frappe.db.sql(query, [self.company, self.fiscal_year] + gl_accounts + [cls_month])[0][0] or 0) / 100000, self.show_decimal_value)
# 				pre_amt = round((frappe.db.sql(query, [self.company, self.previous_fiscal_year] + gl_accounts + [cls_month])[0][0] or 0) / 100000, self.show_decimal_value)
# 			charged_credited = round(cur_amt - pre_amt, self.show_decimal_value)
# 			dta_rows.append((sec_group, cur_amt, charged_credited, pre_amt))

# 		html += render_dta_table(dta_rows)
# 		return section_description.replace("{{note_table}}", html)

# 	def get_yearly_capital_management_note_data(self, section_description=""):
# 		# Get dynamic date labels
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_year_label.replace("Year Ended ", "").replace("/", "-")

# 		def fmt(val):
# 			return f"{val:,.0f}" if isinstance(val, (int, float)) else val

# 		borrowings_non_current = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Borrowing"}, 'name'), 'current_month_amount') or 0
# 		borrowings_current = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Current Borrowing"}, 'name'), 'current_month_amount') or 0)
# 		lease_liabilities_current = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Current Lease Liability"}, 'name'), 'current_month_amount') or 0)
# 		lease_liabilities_non_current = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Lease Liability"}, 'name'), 'current_month_amount') or 0)
# 		cur_borrowings = borrowings_non_current + borrowings_current + lease_liabilities_current + lease_liabilities_non_current

# 		cur_cash = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Cash and Cash Equivalents"}, 'name'), 'current_month_amount') or 0
# 		cur_bank_balances = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Other Bank Balances"}, 'name'), 'current_month_amount') or 0
# 		cur_tot_equity = self.get_pl_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Equity"}, 'name'), 'current_month_amount') or 0

# 		pre_borrowings_non_current = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Borrowing"}, 'name'), 'current_month_amount') or 0
# 		pre_borrowings_current = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Current Borrowing"}, 'name'), 'current_month_amount') or 0)
# 		pre_lease_liabilities_current = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Current Lease Liability"}, 'name'), 'current_month_amount') or 0)
# 		pre_lease_liabilities_non_current = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Lease Liability"}, 'name'), 'current_month_amount') or 0)
# 		pre_borrowings = pre_borrowings_non_current + pre_borrowings_current + pre_lease_liabilities_current + pre_lease_liabilities_non_current

# 		pre_cash = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Cash and Cash Equivalents"}, 'name'), 'current_month_amount') or 0
# 		pre_bank_balances = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Other Bank Balances"}, 'name'), 'current_month_amount') or 0
# 		pre_tot_equity = self.get_pl_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Equity"}, 'name'), 'current_month_amount') or 0

# 		data = {
# 			"current": {"borrowings": cur_borrowings,"cash": cur_cash,"bank_balances": cur_bank_balances,"equity": cur_tot_equity},
# 			"previous": {"borrowings": pre_borrowings,"cash": pre_cash,"bank_balances": pre_bank_balances,"equity": pre_tot_equity}
# 		}

# 		for y in data:
# 			data[y]["adjusted_net_debt"] = (data[y]["borrowings"] - data[y]["cash"] - data[y]["bank_balances"])
# 			data[y]["de_ratio"] = (round(data[y]["adjusted_net_debt"] / data[y]["equity"], 1)) if data[y]["equity"] != 0 else 0

# 		html = f"""
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000; background-color:#fff;">
# 			<thead>
# 				<tr style="background-color:#fff;">
# 					<th style="width: 60%; border:1px solid #000; border-bottom:2px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#fff;">Particulars</th>
# 					<th style="border:1px solid #000; border-bottom:2px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4; background-color:#fff;">As at {current_date}</th>
# 					<th style="border:1px solid #000; border-bottom:2px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4; background-color:#fff;">As at {previous_date}</th>
# 				</tr>
# 			</thead>
# 			<tbody>

# 				<tr>
# 					<td style="border:1px solid #000; padding:6px;">Borrowings (Non-current and current borrowings incl. current maturities) and lease liabilities</td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(data["current"]["borrowings"])}</td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#fff;">{fmt(data["previous"]["borrowings"])}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; padding:6px;">Gross debt</td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(data["current"]["borrowings"])}</td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(data["previous"]["borrowings"])}</td>
# 				</tr>

# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Less – Cash and cash equivalents</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(data["current"]["cash"])}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(data["previous"]["cash"])}</td>
# 				</tr>

# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Less – Bank balances other than Cash and Cash Equivalents</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(data["current"]["bank_balances"])}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(data["previous"]["bank_balances"])}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; padding:6px;"><strong>Adjusted net debt</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(data["current"]["adjusted_net_debt"])}</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(data["previous"]["adjusted_net_debt"])}</strong></td>
# 				</tr>

# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Total equity</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(data["current"]["equity"])}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(data["previous"]["equity"])}</td>
# 				</tr>

# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;"><strong>Adjusted net debt to equity ratio</strong></td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{data["current"]["de_ratio"]}</strong></td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;"><strong>{data["previous"]["de_ratio"]}</strong></td>
# 				</tr>

# 			</tbody>
# 		</table>
# 		"""

# 		return section_description.replace("{{note_table}}", html)

# 	def get_yearly_fair_value_measurements_note_data(self, section_description=""):
# 		# Get dynamic date labels
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_year_label.replace("Year Ended ", "").replace("/", "-")
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")

# 		def fmt(val):
# 			if val in (None, "-", 0):
# 				return "-"
# 			return f"{val:,.0f}"

# 		html = ""
# 		cur_fair_value = frappe.db.exists("FR Fair Value Measurements", {"company": self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month})
# 		if cur_fair_value:
# 			fv_doc = frappe.get_doc("FR Fair Value Measurements", cur_fair_value)
# 			cur_tpl_investment = fv_doc.tpl_investment or 0
# 			cur_oci_investment = fv_doc.oci_investment or 0
# 			cur_tpl_trade_receivable = fv_doc.tpl_trade_receivable or 0
# 			cur_oci_trade_receivable = fv_doc.oci_trade_receivable or 0
# 			cur_tpl_loan = fv_doc.tpl_loan or 0
# 			cur_oci_loan = fv_doc.oci_loan or 0
# 			cur_tpl_fini_assets = fv_doc.tpl_fini_assets or 0
# 			cur_oci_fini_assets = fv_doc.oci_fini_assets or 0
# 			cur_tpl_cach = fv_doc.tpl_cach or 0
# 			cur_oci_cach = fv_doc.oci_cach or 0
# 			cur_tpl_bank_cash = fv_doc.tpl_bank_cash or 0
# 			cur_oci_bank_cash = fv_doc.oci_bank_cash or 0
# 			cur_tpl_borrowing = fv_doc.tpl_borrowing or 0
# 			cur_oci_borrowing = fv_doc.oci_borrowing or 0
# 			cur_tpl_lease_lib = fv_doc.tpl_lease_lib or 0
# 			cur_oci_lease_lib = fv_doc.oci_lease_lib or 0
# 			cur_tpl_trade_pay = fv_doc.tpl_trade_pay or 0
# 			cur_oci_trade_pay = fv_doc.oci_trade_pay or 0
# 			cur_tpl_financial_lib_curr = fv_doc.tpl_financial_lib_curr or 0
# 			cur_oci_financial_lib_curr = fv_doc.oci_financial_lib_curr or 0
# 			cur_tpl_financial_lib_non_curr = fv_doc.tpl_financial_lib_non_curr or 0
# 			cur_oci_financial_lib_non_curr = fv_doc.oci_financial_lib_non_curr or 0
# 			#table2
# 			cur_forward_contract = fv_doc.forward_contract or 0
# 			cur_fair_value_hierarchy = fv_doc.fair_value_hierarchy or '-'
# 			cur_valuation_technique = fv_doc.valuation_technique or '-'
# 			cur_significant_observable = fv_doc.significant_observable or '-'
# 			cur_relationship_observable = fv_doc.relationship_observable or '-'
# 		else:
# 			cur_tpl_investment, cur_oci_investment, cur_tpl_trade_receivable, cur_oci_trade_receivable, cur_tpl_loan, cur_oci_loan, cur_tpl_fini_assets, cur_oci_fini_assets, cur_tpl_cach, cur_oci_cach, cur_tpl_bank_cash, cur_oci_bank_cash = 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
# 			cur_tpl_borrowing, cur_oci_borrowing, cur_tpl_lease_lib, cur_oci_lease_lib, cur_tpl_trade_pay, cur_oci_trade_pay, cur_tpl_financial_lib_curr, cur_oci_financial_lib_curr, cur_tpl_financial_lib_non_curr, cur_oci_financial_lib_non_curr = 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
# 			cur_forward_contract = 0
# 			cur_fair_value_hierarchy = '-'
# 			cur_valuation_technique = '-'
# 			cur_significant_observable = '-'
# 			cur_relationship_observable = '-'

# 		pre_fair_value = frappe.db.exists("FR Fair Value Measurements", {"company": self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month})
# 		if pre_fair_value:
# 			prev_fv_doc = frappe.get_doc("FR Fair Value Measurements", pre_fair_value)
# 			pre_tpl_investment = prev_fv_doc.tpl_investment or 0
# 			pre_oci_investment = prev_fv_doc.oci_investment or 0
# 			pre_tpl_trade_receivable = prev_fv_doc.tpl_trade_receivable or 0
# 			pre_oci_trade_receivable = prev_fv_doc.oci_trade_receivable or 0
# 			pre_tpl_loan = prev_fv_doc.tpl_loan or 0
# 			pre_oci_loan = prev_fv_doc.oci_loan or 0
# 			pre_tpl_fini_assets = prev_fv_doc.tpl_fini_assets or 0
# 			pre_oci_fini_assets = prev_fv_doc.oci_fini_assets or 0
# 			pre_tpl_cach = prev_fv_doc.tpl_cach or 0
# 			pre_oci_cach = prev_fv_doc.oci_cach or 0
# 			pre_tpl_bank_cash = prev_fv_doc.tpl_bank_cash or 0
# 			pre_oci_bank_cash = prev_fv_doc.oci_bank_cash or 0
# 			pre_tpl_borrowing = prev_fv_doc.tpl_borrowing or 0
# 			pre_oci_borrowing = prev_fv_doc.oci_borrowing or 0
# 			pre_tpl_lease_lib = prev_fv_doc.tpl_lease_lib or 0
# 			pre_oci_lease_lib = prev_fv_doc.oci_lease_lib or 0
# 			pre_tpl_trade_pay = prev_fv_doc.tpl_trade_pay or 0
# 			pre_oci_trade_pay = prev_fv_doc.oci_trade_pay or 0
# 			pre_tpl_financial_lib_curr = prev_fv_doc.tpl_financial_lib_curr or 0
# 			pre_oci_financial_lib_curr = prev_fv_doc.oci_financial_lib_curr or 0
# 			pre_tpl_financial_lib_non_curr = prev_fv_doc.tpl_financial_lib_non_curr or 0
# 			pre_oci_financial_lib_non_curr = prev_fv_doc.oci_financial_lib_non_curr or 0

# 			pre_forward_contract = fv_doc.forward_contract or 0
# 		else:
# 			pre_tpl_investment, pre_oci_investment, pre_tpl_trade_receivable, pre_oci_trade_receivable, pre_tpl_loan, pre_oci_loan, pre_tpl_fini_assets, pre_oci_fini_assets, pre_tpl_cach, pre_oci_cach, pre_tpl_bank_cash, pre_oci_bank_cash = 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
# 			pre_tpl_borrowing, pre_oci_borrowing, pre_tpl_lease_lib, pre_oci_lease_lib, pre_tpl_trade_pay, pre_oci_trade_pay, pre_tpl_financial_lib_curr, pre_oci_financial_lib_curr, pre_tpl_financial_lib_non_curr, pre_oci_financial_lib_non_curr = 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
# 			pre_forward_contract = 0

# 		bs_cur_investment = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Investment"}, 'name'), 'current_month_amount') or 0
# 		bs_pre_investment = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Investment"}, 'name'), 'previous_year') or 0
# 		bs_cur_trade_receivable = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Trade & Other Receivables"}, 'name'), 'current_month_amount') or 0
# 		bs_pre_trade_receivable = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Trade & Other Receivables"}, 'name'), 'previous_year') or 0		
# 		bs_cur_loan = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Current Loan"}, 'name'), 'current_month_amount') or 0) + (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Loan"}, 'name'), 'current_month_amount') or 0)
# 		bs_pre_loan = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Current Loan"}, 'name'), 'previous_year') or 0) + (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Loan"}, 'name'), 'previous_year') or 0)
# 		bs_cur_fin_assets = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Current Financial Assets"}, 'name'), 'current_month_amount') or 0) + (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Financial Assets"}, 'name'), 'current_month_amount') or 0)
# 		bs_pre_fin_assets = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Current Financial Assets"}, 'name'), 'previous_year') or 0) + (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Financial Assets"}, 'name'), 'previous_year') or 0)
# 		bs_cur_cash = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Cash & Cash Equivalents"}, 'name'), 'current_month_amount') or 0
# 		bs_pre_cash = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Cash & Cash Equivalents"}, 'name'), 'previous_year') or 0
# 		bs_cur_bank = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Other Bank Balances"}, 'name'), 'current_month_amount') or 0
# 		bs_pre_bank = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Other Bank Balances"}, 'name'), 'previous_year') or 0
		
# 		financial_assets = [
# 			("Investments in subsidiary companies", cur_tpl_investment, cur_oci_investment, ((cur_tpl_investment + cur_oci_investment) - bs_cur_investment), pre_tpl_investment, pre_oci_investment, ((pre_tpl_investment + pre_oci_investment) - bs_pre_investment)),
# 			("Trade receivables", cur_tpl_trade_receivable, cur_oci_trade_receivable, ((cur_tpl_trade_receivable + cur_oci_trade_receivable) - bs_cur_trade_receivable), pre_tpl_trade_receivable, pre_oci_trade_receivable, ((pre_tpl_trade_receivable + pre_oci_trade_receivable) - bs_pre_trade_receivable)),
# 			("Loans", cur_tpl_loan, cur_oci_loan, ((cur_tpl_loan + cur_oci_loan) - bs_cur_loan), pre_tpl_loan, pre_oci_loan, ((pre_tpl_loan + pre_oci_loan) - bs_pre_loan)),
# 			("Other financial assets", cur_tpl_fini_assets, cur_oci_fini_assets, ((cur_tpl_fini_assets + cur_oci_fini_assets) - bs_cur_fin_assets), pre_tpl_financial_lib_curr + pre_tpl_financial_lib_non_curr, pre_oci_fini_assets + pre_oci_financial_lib_curr + pre_oci_financial_lib_non_curr, ((pre_tpl_financial_lib_curr + pre_tpl_financial_lib_non_curr) - bs_pre_fin_assets)),
# 			("Cash and cash equivalents", cur_tpl_cach, cur_oci_cach, ((cur_tpl_cach + cur_oci_cach) - bs_cur_cash), pre_tpl_cach, pre_oci_cach, ((pre_tpl_cach + pre_oci_cach) - bs_pre_cash)),
# 			("Bank balances other than cash and cash equivalents", cur_tpl_bank_cash, cur_oci_bank_cash, ((cur_tpl_bank_cash + cur_oci_bank_cash) - bs_cur_bank), pre_tpl_bank_cash, pre_oci_bank_cash, ((pre_tpl_bank_cash + pre_oci_bank_cash) - bs_pre_bank)),
# 		]

# 		pl_cur_borrowing = (self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Current Borrowing"}, 'name'), 'current_month_amount') or 0) + (self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Borrowing"}, 'name'), 'current_month_amount') or 0)
# 		pl_pre_borrowing = (self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Current Borrowing"}, 'name'), 'previous_year') or 0) + (self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Borrowing"}, 'name'), 'previous_year') or 0)
# 		pl_cur_lease_lib = (self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Current Lease"}, 'name'), 'current_month_amount') or 0) + (self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Lease"}, 'name'), 'current_month_amount') or 0)
# 		pl_pre_lease_lib = (self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Current Lease"}, 'name'), 'previous_year') or 0) + (self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Lease"}, 'name'), 'previous_year') or 0)
# 		pl_cur_trade_payable = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Trade & Other Payables"}, 'name'), 'current_month_amount') or 0
# 		pl_pre_trade_payable = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Trade & Other Payables"}, 'name'), 'previous_year') or 0
# 		pl_cur_financial_lib_curr = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Current Financial Liabilities"}, 'name'), 'current_month_amount') or 0
# 		pl_pre_financial_lib_curr = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Current Financial Liabilities"}, 'name'), 'previous_year') or 0
# 		pl_cur_financial_lib_non_curr = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Financial Liabilities"}, 'name'), 'current_month_amount') or 0
# 		pl_pre_financial_lib_non_curr = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Financial Liabilities"}, 'name'), 'previous_year') or 0
		
# 		financial_liabilities = [
# 			("Borrowings", cur_tpl_borrowing, cur_oci_borrowing, ((cur_tpl_borrowing + cur_oci_borrowing) - pl_cur_borrowing), pre_tpl_borrowing, pre_oci_borrowing, ((pre_tpl_borrowing + pre_oci_borrowing) - pl_pre_borrowing)),
# 			("Lease liabilities", cur_tpl_lease_lib, cur_oci_lease_lib, ((cur_tpl_lease_lib + cur_oci_lease_lib) - pl_cur_lease_lib), pre_tpl_lease_lib, pre_oci_lease_lib, ((pre_tpl_lease_lib + pre_oci_lease_lib) - pl_pre_lease_lib)),
# 			("Trade payables", cur_tpl_trade_pay, cur_oci_trade_pay, ((cur_tpl_trade_pay + cur_oci_trade_pay) - pl_cur_trade_payable), pre_tpl_trade_pay, pre_oci_trade_pay, ((pre_tpl_trade_pay + pre_oci_trade_pay) - pl_pre_trade_payable)),
# 			("Other financial liabilities - Current", cur_tpl_financial_lib_curr, cur_oci_financial_lib_curr, ((cur_tpl_financial_lib_curr + cur_oci_financial_lib_curr) - pl_cur_financial_lib_curr), pre_tpl_financial_lib_curr, pre_oci_financial_lib_curr, ((pre_tpl_financial_lib_curr + pre_oci_financial_lib_curr) - pl_pre_financial_lib_curr)),
# 			("Other financial liabilities - Non-current", cur_tpl_financial_lib_non_curr, cur_oci_financial_lib_non_curr, ((cur_tpl_financial_lib_non_curr + cur_oci_financial_lib_non_curr) - pl_cur_financial_lib_non_curr), pre_tpl_financial_lib_non_curr, pre_oci_financial_lib_non_curr, ((pre_tpl_financial_lib_non_curr + pre_oci_financial_lib_non_curr) - pl_pre_financial_lib_non_curr)),
# 		]

# 		def build_category_rows(rows):
# 			out = ""
# 			for r in rows:
# 				name, fvtpl_25, fvoci_25, amort_25, fvtpl_24, fvoci_24, amort_24 = r
# 				out += f"""
# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">{name}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(fvtpl_25)}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(fvoci_25)}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(amort_25)}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(fvtpl_24)}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(fvoci_24)}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(amort_24)}</td>
# 				</tr>
# 				"""
# 			return out

# 		# Financial Assets totals
# 		total_fa_fvtpl_25 = sum(r[1] for r in financial_assets)
# 		total_fa_fvoci_25 = sum(r[2] for r in financial_assets)
# 		total_fa_amort_25 = sum(r[3] for r in financial_assets)
# 		total_fa_fvtpl_24 = sum(r[4] for r in financial_assets)
# 		total_fa_fvoci_24 = sum(r[5] for r in financial_assets)
# 		total_fa_amort_24 = sum(r[6] for r in financial_assets)

# 		# Financial Liabilities totals
# 		total_fl_fvtpl_25 = sum(r[1] for r in financial_liabilities)
# 		total_fl_fvoci_25 = sum(r[2] for r in financial_liabilities)
# 		total_fl_amort_25 = sum(r[3] for r in financial_liabilities)
# 		total_fl_fvtpl_24 = sum(r[4] for r in financial_liabilities)
# 		total_fl_fvoci_24 = sum(r[5] for r in financial_liabilities)
# 		total_fl_amort_24 = sum(r[6] for r in financial_liabilities)

# 		note_table_a = f"""
# 		<p style="margin-bottom:-20px; margin-top:-20px;"><strong style="color:#4472C4;">(a) Financial instruments by category</strong></p>
# 		<table style="margin-bottom: -20px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 		<tr>
# 			<th rowspan="2" style="width: 40%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Particulars</th>
# 			<th colspan="3" style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 			<th colspan="3" style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 		</tr>
# 		<tr>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">FVTPL</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">FVOCI</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">Amortised Cost</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">FVTPL</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">FVOCI</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Amortised Cost</th>
# 		</tr>

# 		<tr>
# 			<td style="border:1px solid #000; padding:6px;">Financial Assets</td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"></td>
# 		</tr>

# 		{build_category_rows(financial_assets)}

# 		<tr>
# 			<td style="border:1px solid #000; padding:6px;"><strong>Total Financial Assets</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(total_fa_fvtpl_25)}</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(total_fa_fvoci_25)}</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(total_fa_amort_25)}</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total_fa_fvtpl_24)}</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total_fa_fvoci_24)}</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total_fa_amort_24)}</strong></td>
# 		</tr>

# 		<tr>
# 			<td style="border:1px solid #000; padding:6px;">Financial Liabilities</td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"></td>
# 		</tr>

# 		{build_category_rows(financial_liabilities)}

# 		<tr>
# 			<td style="border:1px solid #000; padding:6px;"><strong>Total Financial Liabilities</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(total_fl_fvtpl_25)}</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(total_fl_fvoci_25)}</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(total_fl_amort_25)}</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total_fl_fvtpl_24)}</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total_fl_fvoci_24)}</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total_fl_amort_24)}</strong></td>
# 		</tr>
# 		</table>
# 		"""
		
# 		note_table_b = f"""
# 		<table style="margin-top: -20px; margin-bottom: -20px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 		<tr>
# 			<th rowspan="2" style="width: 20%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Particulars</th>
# 			<th colspan="2" style="width: 20%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Fair Value</th>
# 			<th rowspan="2" style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Fair Value Hierarchy</th>
# 			<th rowspan="2" style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Valuation technique(s) and key input(s)</th>
# 			<th rowspan="2" style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Significant unobservable input(s)</th>
# 			<th rowspan="2" style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Relationship of unobservable inputs to fair value</th>
# 		</tr>
# 		<tr>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 		</tr>

# 		<tr>
# 			<td style="border:1px solid #000; padding:6px; font-weight:bold">Financial Assets / (Liabilities)</td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"></td>
# 			<td rowspan="3" style="border:1px solid #000; padding:6px; vertical-align:middle;">{cur_fair_value_hierarchy}</td>
# 			<td rowspan="3" style="border:1px solid #000; padding:6px; vertical-align:middle;">{cur_valuation_technique}</td>
# 			<td rowspan="3" style="border:1px solid #000; padding:6px; vertical-align:middle;">{cur_significant_observable}</td>
# 			<td rowspan="3" style="border:1px solid #000; padding:6px; vertical-align:middle;">{cur_relationship_observable}</td>
# 		</tr>

# 		<tr>
# 			<td style="border:1px solid #000; border-bottom: none; border-top: none; padding:6px;">Derivatives designated as hedges</td>
# 			<td style="border:1px solid #000; border-bottom: none; border-top: none; padding:6px; text-align:right; background-color:#E8F5E8;"></td>
# 			<td style="border:1px solid #000; border-bottom: none; border-top: none; padding:6px; text-align:right;"></td>
# 		</tr>

# 		<tr>
# 			<td style="border:1px solid #000; border-top: none; padding:6px;">Foreign exchange forward contracts</td>
# 			<td style="border:1px solid #000; border-top: none; padding:6px; text-align:right; background-color:#E8F5E8;">{cur_forward_contract or 0}</td>
# 			<td style="border:1px solid #000; border-top: none; padding:6px; text-align:right;">{pre_forward_contract or 0}</td>
# 		</tr>

# 		<tr>
# 			<td style="border:1px solid #000; padding:6px;"><strong>Total</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(cur_forward_contract) or 0}</strong></td>
# 			<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(pre_forward_contract) or 0}</strong></td>
# 			<td colspan="4" style="border:1px solid #000; padding:6px;"></td>
# 		</tr>
# 		</table>
# 		"""
# 		section_description = section_description.replace("{{note_table_a}}", note_table_a)
# 		section_description = section_description.replace("{{note_table_b}}", note_table_b)

# 		return section_description


# 	def get_yearly_financial_risk_management_note_data(self, section_description=""):
# 		# Get dynamic date labels
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_year_label.replace("Year Ended ", "").replace("/", "-")
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		def fmt(val):
# 			if val in (None, "-", ""):
# 				return "-"
# 			return f"{val:,.0f}"

# 		html = ""
# 		cur_credit_impaired = -round((self.get_sum_grouping_amount(company, "Trade Receivables - credit Impaired", "Trade Receivables - credit Impaired", cls_month, self.fiscal_year) or 0), self.show_decimal_value)
# 		cur_provision_deb = round((self.get_sum_grouping_amount(company, "Other expenses", "Provision for Doubtful Debts/Bad Debts", cls_month, self.fiscal_year) or 0), self.show_decimal_value)
# 		pre_credit_impaired = -round((self.get_sum_grouping_amount(company, "Trade Receivables - credit Impaired", "Trade Receivables - credit Impaired", cls_month, self.previous_fiscal_year) or 0), self.show_decimal_value)
# 		pre_provision_deb = round((self.get_sum_grouping_amount(company, "Other expenses", "Provision for Doubtful Debts/Bad Debts", cls_month, self.previous_fiscal_year) or 0), self.show_decimal_value)
		
# 		loss_allowance = {
# 			"current_year": {"opening": cur_credit_impaired,"reversed": 0,"provision": cur_provision_deb,"closing": cur_credit_impaired - cur_provision_deb},
# 			"previous_year": {"opening": pre_credit_impaired,"reversed": 0,"provision": pre_provision_deb,"closing": pre_credit_impaired - pre_provision_deb}
# 		}

# 		note_table_b = f"""
# 		<p><strong style="margin-top: -20px; margin-bottom: -20px;">Reconciliation of loss allowance provision for Trade Receivables</strong></p>
# 		<table style="margin-top: -20px; margin-bottom: -20px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<tr>
# 				<th style="width: 60%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Particulars</th>
# 				<th style="width: 20%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">FY 24-25</th>
# 				<th style="width: 20%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">FY 23-24</th>
# 			</tr>
# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px;">As at beginning of the year</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(loss_allowance["current_year"]["opening"])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right;">{fmt(loss_allowance["previous_year"]["opening"])}</td>
# 			</tr>
# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Less: Loss recognised / (reversed) during the year</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">-</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(loss_allowance["previous_year"]["reversed"])}</td>
# 			</tr>
# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Add: Loss allowance provision for the year</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">-</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(loss_allowance["previous_year"]["provision"])}</td>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;"><strong>As at end of the year</strong></td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(loss_allowance["current_year"]["closing"])}</strong></td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(loss_allowance["previous_year"]["closing"])}</strong></td>
# 			</tr>
# 		</table>
# 		"""
# 		hg_sec_groups = frappe.get_all("GL Group Mapping", filters={"company": company, "report_type": "Yearly", "primary_group": "Borrowings (Current)", "secondary_group": "Borrowings (Current) - Current Maturities of non-current Borrowings"}, pluck="higher_secondary_group") 
# 		non_current_borrowing = round((self.get_sum_grouping_amount_yearly(company, "Borrowings (Current)", "Borrowings (Current) - Current Maturities of non-current Borrowings", cls_month, self.fiscal_year, hg_sec_group=hg_sec_groups) or 0), self.show_decimal_value)
# 		curr_borrowing = (self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Current Borrowing"}, 'name'), 'current_month_amount') or 0) - non_current_borrowing
# 		current_year_end = frappe.utils.getdate(self.current_year_ending_date)
# 		one_year_from_end = current_year_end + timedelta(days=365)
# 		three_years_from_end = current_year_end + timedelta(days=1095)
# 		repayment = frappe.get_all("FR Repayment", {'company': company}, pluck='name') or []
# 		repaymnet_less_than_one = (frappe.get_value("FR Repayment Details", {'parent': ['in', repayment], 'posting_date': ['between', [current_year_end, one_year_from_end]]}, 'SUM(repayment_amount)') or 0) / 100000
# 		repayment_one_three = (frappe.get_value("FR Repayment Details", {'parent': ['in', repayment], 'posting_date': ['between', [one_year_from_end + timedelta(days=1), three_years_from_end]]}, 'SUM(repayment_amount)') or 0) / 100000
# 		repayment_more_than_three = (frappe.get_value("FR Repayment Details", {'parent': ['in', repayment], 'posting_date': ['>', three_years_from_end]}, 'SUM(repayment_amount)') or 0)/ 100000
# 		lease = frappe.get_value("FR Lease", {'company': company, 'fiscal_year': self.fiscal_year}, 'less_than_one_year') or 0
# 		lease_one_to_three = frappe.get_value("FR Lease", {'company': company, 'fiscal_year': self.fiscal_year}, 'one_to_three_years') or 0
# 		lease_more_than_three = frappe.get_value("FR Lease", {'company': company, 'fiscal_year': self.fiscal_year}, 'more_than_three_years') or 0
# 		cur_trade_pay = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Trade & Other Payables"}, 'name'), 'current_month_amount') or 0
# 		cur_financial_lib_curr = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Current Financial Liabilities"}, 'name'), 'current_month_amount') or 0
# 		cur_financial_lib_non_curr = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Financial Liabilities"}, 'name'), 'current_month_amount') or 0

# 		c1_curr = [
# 			("Non current borrowings (including current maturities)", repaymnet_less_than_one, repayment_one_three, repayment_more_than_three),
# 			("Lease liabilities (Refer Note No. 37)", lease, lease_one_to_three, lease_more_than_three),
# 			("Current borrowings", curr_borrowing, 0, 0),
# 			("Trade payables", cur_trade_pay, 0, 0),
# 			("Other financial liabilities - Current", cur_financial_lib_curr, 0, 0),
# 			("Other financial liabilities - Non-current", 0, cur_financial_lib_non_curr, 0),
# 		]

# 		pre_non_current_borrowing = round((self.get_sum_grouping_amount_yearly(company, "Borrowings (Current)", "Borrowings (Current) - Current Maturities of non-current Borrowings", cls_month, self.previous_fiscal_year, hg_sec_group=hg_sec_groups) or 0), self.show_decimal_value)
# 		prev_year_end = frappe.utils.getdate(self.previous_year_ending_date)
# 		pre_one_year_from_end = prev_year_end + timedelta(days=365)
# 		pre_three_years_from_end = prev_year_end + timedelta(days=1095)
# 		pre_repaymnet_less_than_one = (frappe.get_value("FR Repayment Details", {'parent': ['in', repayment], 'posting_date': ['between', [prev_year_end, pre_one_year_from_end]]}, 'SUM(repayment_amount)') or 0) / 100000
# 		pre_repayment_one_three = (frappe.get_value("FR Repayment Details", {'parent': ['in', repayment], 'posting_date': ['between', [pre_one_year_from_end + timedelta(days=1), pre_three_years_from_end]]}, 'SUM(repayment_amount)') or 0) / 100000
# 		pre_repayment_more_than_three = (frappe.get_value("FR Repayment Details", {'parent': ['in', repayment], 'posting_date': ['>', pre_three_years_from_end]}, 'SUM(repayment_amount)') or 0)/ 100000
# 		pre_lease = frappe.get_value("FR Lease", {'company': company, 'fiscal_year': self.previous_fiscal_year}, 'less_than_one_year') or 0
# 		pre_lease_one_to_three = frappe.get_value("FR Lease", {'company': company, 'fiscal_year': self.previous_fiscal_year}, 'one_to_three_years') or 0
# 		pre_lease_more_than_three = frappe.get_value("FR Lease", {'company': company, 'fiscal_year': self.previous_fiscal_year}, 'more_than_three_years') or 0
# 		pre_borrowing = (self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Current Borrowing"}, 'name'), 'previous_year') or 0) - pre_non_current_borrowing
# 		pre_trade_pay = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Trade & Other Payables"}, 'name'), 'previous_year') or 0
# 		pre_financial_lib_curr = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Current Financial Liabilities"}, 'name'), 'previous_year') or 0
# 		pre_financial_lib_non_curr = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Financial Liabilities"}, 'name'), 'previous_year') or 0
		
# 		c1_prev = [
# 			("Non current borrowings (including current maturities)", pre_repaymnet_less_than_one, pre_repayment_one_three, pre_repayment_more_than_three),
# 			("Lease liabilities (Refer Note No. 37)", pre_lease, pre_lease_one_to_three, pre_lease_more_than_three),
# 			("Current borrowings", pre_borrowing, 0, 0),
# 			("Trade payables", pre_trade_pay, 0, 0),
# 			("Other financial liabilities - Current", pre_financial_lib_curr, 0, 0),
# 			("Other financial liabilities - Non-current", 0, pre_financial_lib_non_curr, 0),
# 		]

# 		def build_maturity_table(title, rows, color=""):
# 			total_1y = sum(r[1] for r in rows)
# 			total_3y = sum(r[2] for r in rows)
# 			total_3y_plus = sum(r[3] for r in rows)
# 			total_all = total_1y + total_3y + total_3y_plus

# 			table = f"""
# 			<p><strong>{title}</strong></p>
# 			<table style="margin-top: -20px; margin-bottom: -20px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 				<tr>
# 					<th style="width: 50%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Particulars</th>
# 					<th style="border:1px solid #000; padding:6px; font-weight:bold; color: #4472C4; background-color:{color};">Less than 1 Year</th>
# 					<th style="border:1px solid #000; padding:6px; font-weight:bold; color: #4472C4; background-color:{color};">1–3 Years</th>
# 					<th style="border:1px solid #000; padding:6px; font-weight:bold; color: #4472C4; background-color:{color};">3 years and above</th>
# 					<th style="border:1px solid #000; padding:6px; font-weight:bold; color: #4472C4; background-color:{color};">Total</th>
# 				</tr>
# 			"""
# 			for i, r in enumerate(rows):
# 				row_total = r[1] + r[2] + r[3]
# 				border_top = "border-top:1px solid #000;" if i == 0 else "border-top:none;"

# 				table += f"""
# 				<tr>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; {border_top} border-bottom:none; padding:6px;">{r[0]}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; {border_top} border-bottom:none; padding:6px; text-align:right; background-color:{color};">{fmt(r[1])}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; {border_top} border-bottom:none; padding:6px; text-align:right; background-color:{color};">{fmt(r[2])}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; {border_top} border-bottom:none; padding:6px; text-align:right; background-color:{color};">{fmt(r[3])}</td>
# 					<td style="border-right:1px solid #000; border-left:1px solid #000; {border_top} border-bottom:none; padding:6px; text-align:right; background-color:{color};">{fmt(row_total)}</td>
# 				</tr>
# 				"""
# 			table += f"""
# 				<tr>
# 					<td style="border:1px solid #000; padding:6px;"><strong>Total Financial Liabilities</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total_1y)}</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total_3y)}</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total_3y_plus)}</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total_all)}</strong></td>
# 				</tr>
# 			</table>
# 			"""
# 			return table

# 		note_table_c1 = (
# 			build_maturity_table(f"Contractual maturities of financial liabilities - {current_date}", c1_curr, "#E8F5E8") + build_maturity_table(f"Contractual maturities of financial liabilities - {previous_date}", c1_prev)
# 		)

# 		financing = {
# 			"current": frappe.get_value("FR Undrawn Facilities",{"company": self.company,"fiscal_year": self.fiscal_year,"month": cls_month},"total") or 0,
# 			"previous": frappe.get_value("FR Undrawn Facilities",{"company": self.company,"fiscal_year": self.previous_fiscal_year,"month": cls_month},"total") or 0,
# 		}


# 		note_table_c2 = f"""
# 		<table style="margin-top: -20px; margin-bottom: -20px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<tr>
# 				<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Particulars</th>
# 				<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 				<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;">Expiring within one year</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(financing["current"])}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(financing["previous"])}</td>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;"><strong>Total</strong></td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(financing["current"])}</strong></td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(financing["previous"])}</strong></td>
# 			</tr>
# 		</table>
# 		"""
# 		note_data_d = [
# 			{"is_section": True, "label": "Financial Assets"},
# 		]
# 		currency_trade_rec = set(frappe.get_all("FR Account Receivable Entry", {'company': self.company, 'fiscal_year': ["in", self.fiscal_year, self.previous_fiscal_year], 'special_gl_ind': ["!=", "D"]}, pluck='currency')) or []
# 		for c in currency_trade_rec:
# 			result_current = frappe.get_value("FR Account Receivable Entry",{'company': self.company, 'type': 'Account Receivable', 'currency': c, 'month': cls_month, 'fiscal_year': self.fiscal_year, 'special_gl_ind': ["!=", "D"]},['SUM(amount_in_lc)', 'SUM(amount_in_dc)']) or (0, 0)
# 			fc_current = (result_current[0] if isinstance(result_current, tuple) else result_current) or 0
# 			inr_current = (result_current[1] if isinstance(result_current, tuple) else 0) or 0
# 			result_previous = frappe.get_value("FR Account Receivable Entry",{'company': self.company, 'type': 'Account Receivable', 'currency': c, 'month': cls_month, 'fiscal_year': self.previous_fiscal_year, 'special_gl_ind': ["!=", "D"]},['SUM(amount_in_lc)', 'SUM(amount_in_dc)']) or (0, 0)
# 			fc_previous = (result_previous[0] if isinstance(result_previous, tuple) else result_previous) or 0
# 			inr_previous = (result_previous[1] if isinstance(result_previous, tuple) else 0) or 0
# 			pbt_current = -round((inr_current / fc_current) * 1.05 * fc_current - inr_current, 2) / 100000 if fc_current else 0
# 			pbt_previous = -round((inr_previous / fc_previous) * 1.05 * fc_previous - inr_previous, 2) / 100000 if fc_previous else 0
# 			note_data_d.append({
# 				"particular": "Trade Receivables",
# 				"currency": c,
# 				"fc_current": fmt(round(fc_current / 100000, self.show_decimal_value)),
# 				"inr_current": fmt(round(inr_current / 100000, self.show_decimal_value)),
# 				"fc_previous": fmt(round(fc_previous / 100000, self.show_decimal_value)),
# 				"inr_previous": fmt(round(inr_previous / 100000, self.show_decimal_value)),
# 				"pbt_current": fmt(round(pbt_current, self.show_decimal_value)),
# 				"pbt_previous": fmt(round(pbt_previous, self.show_decimal_value)),
# 			})

# 		deposit_currency_trade_rec = set(frappe.get_all("FR Account Receivable Entry", {'company': self.company, 'fiscal_year': ["in", [self.fiscal_year, self.previous_fiscal_year]], 'special_gl_ind': "D"}, pluck='currency')) or []
# 		for c in deposit_currency_trade_rec:
# 			result_current = frappe.get_value("FR Account Receivable Entry",{'company': self.company, 'type': 'Account Receivable', 'currency': c, 'month': cls_month, 'fiscal_year': self.fiscal_year, 'special_gl_ind': "D"},['SUM(amount_in_lc)', 'SUM(amount_in_dc)']) or (0, 0)
# 			fc_current = (result_current[0] if isinstance(result_current, tuple) else result_current) or 0
# 			inr_current = (result_current[1] if isinstance(result_current, tuple) else 0) or 0
# 			result_previous = frappe.get_value("FR Account Receivable Entry",{'company': self.company, 'type': 'Account Receivable', 'currency': c, 'month': cls_month, 'fiscal_year': self.previous_fiscal_year, 'special_gl_ind': "D"},['SUM(amount_in_lc)', 'SUM(amount_in_dc)']) or (0, 0)
# 			fc_previous = (result_previous[0] if isinstance(result_previous, tuple) else result_previous) or 0
# 			inr_previous = (result_previous[1] if isinstance(result_previous, tuple) else 0) or 0
# 			pbt_current = -round((inr_current / fc_current) * 1.05 * fc_current - inr_current, 2) / 100000 if fc_current else 0
# 			pbt_previous = -round((inr_previous / fc_previous) * 1.05 * fc_previous - inr_previous, 2) / 100000 if fc_previous else 0
# 			note_data_d.append({
# 				"particular": "Other Deposits",
# 				"currency": c,
# 				"fc_current": fmt(round(fc_current / 100000, self.show_decimal_value)),
# 				"inr_current": fmt(round(inr_current / 100000, self.show_decimal_value)),
# 				"fc_previous": fmt(round(fc_previous / 100000, self.show_decimal_value)),
# 				"inr_previous": fmt(round(inr_previous / 100000, self.show_decimal_value)),
# 				"pbt_current": fmt(round(pbt_current, self.show_decimal_value)),
# 				"pbt_previous": fmt(round(pbt_previous, self.show_decimal_value)),
# 			})

# 		note_data_d.append({"is_section": True, "label": "Financial Liabilities"})
# 		currency_trade_pay = set(frappe.get_all("FR Account Payable Entry", {'company': self.company, 'fiscal_year': ["in", [self.fiscal_year, self.previous_fiscal_year]]}, pluck='currency')) or []
# 		for c in currency_trade_pay:
# 			result_current = frappe.get_value("FR Account Payable Entry",{'company': self.company, 'currency': c, 'fiscal_year': self.fiscal_year},['SUM(amount_in_lc)', 'SUM(amount_in_dc)']) or (0, 0)
# 			fc_current = (result_current[0] if isinstance(result_current, tuple) else result_current) or 0
# 			inr_current = (result_current[1] if isinstance(result_current, tuple) else 0) or 0
# 			result_previous = frappe.get_value("FR Account Payable Entry",{'company': self.company, 'currency': c, 'fiscal_year': self.previous_fiscal_year},['SUM(amount_in_lc)', 'SUM(amount_in_dc)']) or (0, 0)
# 			fc_previous = (result_previous[0] if isinstance(result_previous, tuple) else result_previous) or 0
# 			inr_previous = (result_previous[1] if isinstance(result_previous, tuple) else 0) or 0
# 			pbt_current = round((inr_current / fc_current) * 1.05 * fc_current - inr_current, 2) / 100000 if fc_current else 0
# 			pbt_previous = round((inr_previous / fc_previous) * 1.05 * fc_previous - inr_previous, 2) / 100000 if fc_previous else 0
# 			note_data_d.append({
# 				"particular": "Trade & Other Payables",
# 				"currency": c,
# 				"fc_current": fmt(round(fc_current / 100000, self.show_decimal_value)),
# 				"inr_current": fmt(round(inr_current / 100000, self.show_decimal_value)),
# 				"fc_previous": fmt(round(fc_previous / 100000, self.show_decimal_value)),
# 				"inr_previous": fmt(round(inr_previous / 100000, self.show_decimal_value)),
# 				"pbt_current": fmt(round(pbt_current, self.show_decimal_value)),
# 				"pbt_previous": fmt(round(pbt_previous, self.show_decimal_value)),
# 			})

# 		note_table_d = """
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr>
# 					<th rowspan="3" style="width: 11%; border:1px solid #000; padding:6px; color: #4472C4">Particulars</th>
# 					<th rowspan="3" style="width: 8%; border:1px solid #000; padding:6px; color: #4472C4">Foreign<br>Currency</th>
# 					<th colspan="4" style="border:1px solid #000; padding:6px; color: #4472C4">Exposure</th>
# 					<th colspan="2" style="border:1px solid #000; padding:6px; color: #4472C4">Effect on Profit<br>Before Tax</th>
# 				</tr>
# 				<tr>
# 					<th colspan="2" style="border:1px solid #000; padding:6px; color: #4472C4;">As at 31-03-2025</th>
# 					<th colspan="2" style="border:1px solid #000; padding:6px; color: #4472C4;">As at 31-03-2024</th>
# 					<th rowspan="2" style="border:1px solid #000; padding:6px; color: #4472C4;">31-03-2025<br>(₹ in lacs)</th>
# 					<th rowspan="2" style="border:1px solid #000; padding:6px; color: #4472C4;">31-03-2024<br>(₹ in lacs)</th>
# 				</tr>
# 				<tr>
# 					<th style="border:1px solid #000; padding:6px; color: #4472C4">FC in Lacs</th>
# 					<th style="border:1px solid #000; padding:6px; color: #4472C4">₹ in Lacs</th>
# 					<th style="border:1px solid #000; padding:6px; color: #4472C4">FC in Lacs</th>
# 					<th style="border:1px solid #000; padding:6px; color: #4472C4">₹ in Lacs</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		# Group rows by particular to calculate rowspan
# 		i = 0
# 		while i < len(note_data_d):
# 			r = note_data_d[i]
# 			if r.get("is_section"):
# 				note_table_d += f"""
# 				<tr>
# 					<td colspan="8" style="border:1px solid #000; padding:6px; font-weight:bold;">{r["label"]}</td>
# 				</tr>
# 				"""
# 				i += 1
# 				continue

# 			# Count how many rows have the same particular
# 			particular = r["particular"]
# 			rowspan = 1
# 			for j in range(i + 1, len(note_data_d)):
# 				if note_data_d[j].get("is_section") or note_data_d[j].get("particular") != particular:
# 					break
# 				rowspan += 1

# 			# First row with rowspan for particular
# 			note_table_d += f"""
# 			<tr>
# 				<td rowspan="{rowspan}" style="border:1px solid #000; padding:6px; vertical-align:middle;">{r["particular"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:center;">{r["currency"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{r["fc_current"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{r["inr_current"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{r["fc_previous"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{r["inr_previous"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{r["pbt_current"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{r["pbt_previous"]}</td>
# 			</tr>
# 			"""
# 			i += 1

# 			# Subsequent rows without particular cell
# 			for _ in range(rowspan - 1):
# 				r = note_data_d[i]
# 				note_table_d += f"""
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px; text-align:center;">{r["currency"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{r["fc_current"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{r["inr_current"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{r["fc_previous"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{r["inr_previous"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{r["pbt_current"]}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{r["pbt_previous"]}</td>
# 			</tr>
# 			"""
# 				i += 1

# 		note_table_d += "</tbody></table>"


# 		section_description = section_description.replace("{{note_table_b}}", note_table_b)
# 		section_description = section_description.replace("{{note_table_c1}}", note_table_c1)
# 		section_description = section_description.replace("{{note_table_c2}}", note_table_c2)
# 		section_description = section_description.replace("{{note_table_d}}", note_table_d)

# 		return section_description

# 	def get_yearly_leases_note_data(self, section_description=""):
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_year_label.replace("Year Ended ", "").replace("/", "-")
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		pre_prev_year = self.get_previous_fiscal_year(self.previous_fiscal_year)

# 		def fmt(val):
# 			if val in (None, "-", ""):
# 				return "-"
# 			if val < 0:
# 				return f"({abs(val):,})"
# 			return f"{val:,}"

# 		# First, get pre_opening from pre_prev_year (needed to calculate pre_closing)
# 		pre_prev_lease = frappe.db.exists("FR Lease", {'company': self.company, 'fiscal_year': pre_prev_year, 'month': cls_month})
# 		if pre_prev_lease:
# 			pre_prev_lease_doc = frappe.get_doc("FR Lease", pre_prev_lease)
# 			pre_opening = pre_prev_lease_doc.additions_modifications + pre_prev_lease_doc.finance_cost_accrued + pre_prev_lease_doc.derecognition + pre_prev_lease_doc.payment_of_lease_liabilities
# 		else:
# 			pre_opening = 0

# 		# Get previous year lease data and calculate pre_closing (needed for current year opening)
# 		pre_lease = frappe.db.exists("FR Lease", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month})
# 		if pre_lease:
# 			pre_lease_doc = frappe.get_doc("FR Lease", pre_lease)
# 			pre_additions_modifications_py = pre_lease_doc.additions_modifications
# 			pre_finance_cost_accrued_py = pre_lease_doc.finance_cost_accrued
# 			pre_derecognition_py = pre_lease_doc.derecognition
# 			pre_payment_of_lease_liabilities_py = pre_lease_doc.payment_of_lease_liabilities
# 			pre_closing = pre_opening + pre_additions_modifications_py + pre_finance_cost_accrued_py + pre_derecognition_py + pre_payment_of_lease_liabilities_py

# 			pre_less_than_one_year = pre_lease_doc.less_than_one_year
# 			pre_one_to_five_years = pre_lease_doc.one_to_five_years
# 			pre_more_than_five_years = pre_lease_doc.more_than_five_years
# 		else:
# 			pre_additions_modifications_py, pre_finance_cost_accrued_py, pre_derecognition_py, pre_payment_of_lease_liabilities_py, pre_closing = 0, 0, 0, 0, 0
# 			pre_less_than_one_year, pre_one_to_five_years, pre_more_than_five_years = 0, 0, 0

# 		# Get current year lease data (opening = pre_closing)
# 		cur_lease = frappe.db.exists("FR Lease", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month})
# 		if cur_lease:
# 			cur_lease_doc = frappe.get_doc("FR Lease", cur_lease)
# 			cur_additions_modifications = cur_lease_doc.additions_modifications
# 			cur_finance_cost_accrued = cur_lease_doc.finance_cost_accrued
# 			cur_derecognition = cur_lease_doc.derecognition
# 			cur_payment_of_lease_liabilities = cur_lease_doc.payment_of_lease_liabilities
# 			cur_closing = pre_closing + cur_additions_modifications + cur_finance_cost_accrued + cur_derecognition + cur_payment_of_lease_liabilities

# 			cur_less_than_one_year = cur_lease_doc.less_than_one_year
# 			cur_one_to_five_years = cur_lease_doc.one_to_five_years
# 			cur_more_than_five_years = cur_lease_doc.more_than_five_years
# 		else:
# 			cur_additions_modifications, cur_finance_cost_accrued, cur_derecognition, cur_payment_of_lease_liabilities, cur_closing = 0, 0, 0, 0, 0
# 			cur_less_than_one_year, cur_one_to_five_years, cur_more_than_five_years = 0, 0, 0

# 		a_data = {
# 			"current": {
# 				"opening": pre_closing,
# 				"additions": cur_additions_modifications,
# 				"finance_cost": cur_finance_cost_accrued,
# 				"derecognition": cur_derecognition,
# 				"payment": cur_payment_of_lease_liabilities,
# 				"closing": cur_closing
# 			},
# 			"previous": {
# 				"opening": pre_opening,
# 				"additions": pre_additions_modifications_py,
# 				"finance_cost": pre_finance_cost_accrued_py,
# 				"derecognition": pre_derecognition_py,
# 				"payment": pre_payment_of_lease_liabilities_py,
# 				"closing": pre_closing
# 			}
# 		}

# 		note_table_a = f"""
# 		<table style="margin-top:-30px; margin-bottom: -30px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<tr>
# 				<th style="border:1px solid #000; padding:6px; width:50%; font-weight:bold; color:#4472C4;">Particulars</th>
# 				<th style="border:1px solid #000; padding:6px; width:25%; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">{self.fiscal_year}<br>(₹ in Lacs)</th>
# 				<th style="border:1px solid #000; padding:6px; width:25%; font-weight:bold; color:#4472C4;">{self.previous_fiscal_year}<br>(₹ in Lacs)</th>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px;">Balance at the beginning of the year</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(a_data["current"]["opening"])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right;">{fmt(a_data["previous"]["opening"])}</td>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Additions / Modifications during the year</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(a_data["current"]["additions"])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(a_data["previous"]["additions"])}</td>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Finance cost accrued</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(a_data["current"]["finance_cost"])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(a_data["previous"]["finance_cost"])}</td>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Derecognition during the year</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(a_data["current"]["derecognition"])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(a_data["previous"]["derecognition"])}</td>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Payment of lease liabilities</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(a_data["current"]["payment"])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(a_data["previous"]["payment"])}</td>
# 			</tr>

# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;"><strong>Balance at the end of the year</strong></td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(a_data["current"]["closing"])}</strong></td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(a_data["previous"]["closing"])}</strong></td>
# 			</tr>
# 		</table>
# 		"""


# 		b_data = {
# 			"current": {
# 				"lt_1": cur_less_than_one_year,
# 				"one_to_five": cur_one_to_five_years,
# 				"gt_5": cur_more_than_five_years,
# 				"total": cur_less_than_one_year + cur_one_to_five_years + cur_more_than_five_years
# 			},
# 			"previous": {
# 				"lt_1": pre_less_than_one_year,
# 				"one_to_five": pre_one_to_five_years,
# 				"gt_5": pre_more_than_five_years,
# 				"total": pre_less_than_one_year + pre_one_to_five_years + pre_more_than_five_years
# 			}
# 		}

# 		note_table_b = f"""
# 		<table style="margin-top: -20px; margin-bottom: -20px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<tr>
# 				<th style="border:1px solid #000; padding:6px; width:50%; font-weight:bold; color:#4472C4;">Particulars</th>
# 				<th style="border:1px solid #000; padding:6px; width:25%; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}<br>(₹ in Lacs)</th>
# 				<th style="border:1px solid #000; padding:6px; width:25%; font-weight:bold; color:#4472C4;">As at {previous_date}<br>(₹ in Lacs)</th>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px;">Less than one year</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(b_data["current"]["lt_1"])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right;">{fmt(b_data["previous"]["lt_1"])}</td>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">One to five years</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(b_data["current"]["one_to_five"])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(b_data["previous"]["one_to_five"])}</td>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">More than five years</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(b_data["current"]["gt_5"])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(b_data["previous"]["gt_5"])}</td>
# 			</tr>

# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;"><strong>Total</strong></td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(b_data["current"]["total"])}</strong></td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(b_data["previous"]["total"])}</strong></td>
# 			</tr>
# 		</table>
# 		"""

# 		section_description = section_description.replace("{{note_table_a}}", note_table_a)
# 		section_description = section_description.replace("{{note_table_b}}", note_table_b)
# 		return section_description
	

# 	def get_yearly_related_party_disclosure_note_data(self, section_description=""):
# 		fr_rpt_entry = frappe.db.exists("FR RPT Entry", {'company': self.company, 'fiscal_year': self.fiscal_year})
# 		if not fr_rpt_entry:
# 			return section_description.replace("{{note_table}}", "")

# 		fr_rpt_entry_doc = frappe.get_doc("FR RPT Entry", fr_rpt_entry)
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		cy_label = current_year_label.replace("Year Ended ", "") if current_year_label else ""
# 		py_label = previous_year_label.replace("Year Ended ", "") if previous_year_label else ""

# 		def fmt(val):
# 			if val in (None, 0, 0.0):
# 				return "-"
# 			return f"{val:,.0f}"

# 		def build_table(rows, header):
# 			if not rows:
# 				return ""
# 			row_html = ""
# 			for idx, row in enumerate(rows, 1):
# 				row_html += f"""<tr>
# 					<td style="border:1px solid black; text-align:center;">{idx}</td>
# 					<td style="border:1px solid black;">{row.company or ""}</td>
# 					<td style="border:1px solid black;">{row.relation or ""}</td>
# 				</tr>"""

# 			return f'''
# 			<div>
# 			<p style="margin-top: -70px; color: #4472C4;"><b>{header}</b></p>
# 			<table style="width:100%; border-collapse:collapse; margin-top: -25px">
# 				<thead>
# 					<tr style="background-color:#E8F5E8;">
# 						<th style="border:1px solid black; width:8%; text-align:center;">Sr. No.</th>
# 						<th style="border:1px solid black; width:46%;">Company</th>
# 						<th style="border:1px solid black; width:46%;">Relation</th>
# 					</tr>
# 				</thead>
# 				<tbody>{row_html}</tbody>
# 			</table>
# 			</div>'''

# 		table_a = build_table(fr_rpt_entry_doc.where_control_exists, "i. Where Control Exists")
# 		table_b = build_table(fr_rpt_entry_doc.names_of_replated, "ii. Names of related parties and description of relationship, where transactions have taken place")

# 		# ---- Table iii: Transactions and Balances Outstanding ----
# 		table_c = ""
# 		transactions = fr_rpt_entry_doc.get("rpt_transactions", [])
# 		if transactions:
# 			relation_order = [
# 				"Ultimate Holding Company",
# 				"Holding Company",
# 				"Subsidiary",
# 				"Fellow Subsidiary of Holding Company",
# 				"Fellow Subsidiary",
# 				"Key Managerial Personnel",
# 			]

# 			# Group rows by relation_type, preserving input order within each group
# 			from collections import OrderedDict
# 			grouped = OrderedDict()
# 			for rel in relation_order:
# 				grouped[rel] = []
# 			for row in transactions:
# 				rt = row.relation_type
# 				if rt not in grouped:
# 					grouped[rt] = []
# 				grouped[rt].append(row)

# 			# Build one sub-table per relation type
# 			all_relation_tables = ""
# 			for relation_type, rows in grouped.items():
# 				if not rows:
# 					continue

# 				# Separate transactions and balances
# 				txn_rows = [r for r in rows if r.entry_type == "Transaction"]
# 				bal_rows = [r for r in rows if r.entry_type == "Balance Outstanding"]

# 				# Build rows HTML
# 				body_html = ""

# 				# Transaction rows
# 				current_sno = 0
# 				current_desc = None
# 				for row in txn_rows:
# 					if row.description != current_desc:
# 						current_sno += 1
# 						current_desc = row.description

# 					if row.company_name:
# 						# Sub-row (company-level detail) — indented, no S.No.
# 						body_html += f"""<tr>
# 							<td style="border:1px solid black;"></td>
# 							<td style="border:1px solid black; padding-left:30px;">{row.company_name}</td>
# 							<td style="border:1px solid black; text-align:right; background-color:#E8F5E8;">{fmt(row.current_year_amount)}</td>
# 							<td style="border:1px solid black; text-align:right;">{fmt(row.previous_year_amount)}</td>
# 						</tr>"""
# 					else:
# 						# Main transaction row
# 						body_html += f"""<tr>
# 							<td style="border:1px solid black; text-align:center;">{current_sno}</td>
# 							<td style="border:1px solid black;">{row.description}</td>
# 							<td style="border:1px solid black; text-align:right; background-color:#E8F5E8;">{fmt(row.current_year_amount)}</td>
# 							<td style="border:1px solid black; text-align:right;">{fmt(row.previous_year_amount)}</td>
# 						</tr>"""

# 				# Balances Outstanding header
# 				if bal_rows:
# 					body_html += f"""<tr style="background-color:#E8F5E8;">
# 						<td style="border:1px solid black;"></td>
# 						<td style="border:1px solid black;" colspan="3"><b>Balances Outstanding</b></td>
# 					</tr>"""

# 					bal_sno = 0
# 					bal_desc = None
# 					for row in bal_rows:
# 						if row.description != bal_desc:
# 							bal_sno += 1
# 							bal_desc = row.description

# 						if row.company_name:
# 							body_html += f"""<tr>
# 								<td style="border:1px solid black;"></td>
# 								<td style="border:1px solid black; padding-left:30px;">{row.company_name}</td>
# 								<td style="border:1px solid black; text-align:right; background-color:#E8F5E8;">{fmt(row.current_year_amount)}</td>
# 								<td style="border:1px solid black; text-align:right;">{fmt(row.previous_year_amount)}</td>
# 							</tr>"""
# 						else:
# 							body_html += f"""<tr>
# 								<td style="border:1px solid black; text-align:center;">{bal_sno}</td>
# 								<td style="border:1px solid black;">{row.description}</td>
# 								<td style="border:1px solid black; text-align:right; background-color:#E8F5E8;">{fmt(row.current_year_amount)}</td>
# 								<td style="border:1px solid black; text-align:right;">{fmt(row.previous_year_amount)}</td>
# 							</tr>"""

# 				relation_label = f"Transactions with {relation_type}"
# 				all_relation_tables += f'''
# 				<table style="width:100%; border-collapse:collapse; margin-bottom:15px;">
# 					<thead>
# 						<tr style="background-color:#E8F5E8;">
# 							<th style="border:1px solid black; width:8%; text-align:center;">S.No.</th>
# 							<th style="border:1px solid black; width:52%;">{relation_label}</th>
# 							<th style="border:1px solid black; width:20%; text-align:center; background-color:#E8F5E8;">{cy_label}<br>(\u20b9 in lacs)</th>
# 							<th style="border:1px solid black; width:20%; text-align:center;">{py_label}<br>(\u20b9 in lacs)</th>
# 						</tr>
# 					</thead>
# 					<tbody>{body_html}</tbody>
# 				</table>'''

# 			if all_relation_tables:
# 				table_c = f'''
# 				<div>
# 				<p style="color: #4472C4;"><b>iii. Transactions and balances outstanding with Related Parties</b></p>
# 				{all_relation_tables}
# 				</div>'''

# 		note_table = table_a + table_b + table_c
# 		return section_description.replace("{{note_table}}", note_table)

# 	def get_yearly_contingent_liabilities_note_data(self, section_description=""):
# 		# Get dynamic date labels
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_year_label.replace("Year Ended ", "").replace("/", "-")
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		def fmt(val):
# 			if val in (None, "-", ""):
# 				return "-"
# 			if isinstance(val, str):
# 				return val
# 			return f"{val:,.0f}"

# 		# Fetch contingent liabilities data using get_value for efficiency
# 		cur_contingent = frappe.db.exists("FR Contingent Liabilities", {"company": self.company, "fiscal_year": self.fiscal_year, "month": cls_month})
# 		if cur_contingent:
# 			cur_contingent_doc = frappe.get_doc("FR Contingent Liabilities", cur_contingent)
# 			cur_bank_guarantees = cur_contingent_doc.bank_guarantees
# 			cur_company_imported = cur_contingent_doc.company_imported
# 			cur_claim_against = cur_contingent_doc.claim_against
# 		else:
# 			cur_bank_guarantees = 0
# 			cur_company_imported = 0
# 			cur_claim_against = "-"

# 		prev_contingent = frappe.db.exists("FR Contingent Liabilities", {"company": self.company, "fiscal_year": self.previous_fiscal_year, "month": cls_month})
# 		if prev_contingent:
# 			prev_contingent_doc = frappe.get_doc("FR Contingent Liabilities", prev_contingent)
# 			pre_bank_guarantees = prev_contingent_doc.bank_guarantees
# 			pre_company_imported = prev_contingent_doc.company_imported
# 			pre_claim_against = prev_contingent_doc.claim_against
# 		else:
# 			pre_bank_guarantees = 0
# 			pre_company_imported = 0
# 			pre_claim_against = "-"

# 		data = [
# 			("a) Bank guarantees given to excise authorities and other institutions", cur_bank_guarantees, pre_bank_guarantees),
# 			("b) The Company has imported Capital Goods under the Export Promotion Capital Goods Scheme, of the Government of India, against which the company is committed to make exports of ₹ 397 Lacs (P.Y. ₹ 3,061 Lacs) within prescribed time period. In case the company does not export it would be liable to pay customs duty.", cur_company_imported, pre_company_imported),
# 			("c) Claims against the company not acknowledged as debt, Amount indeterminate (Refer Note (ii) below), Amount indeterminate (Refer Note (ii) below)", cur_claim_against, pre_claim_against),
# 		]

# 		total_curr = cur_bank_guarantees + cur_company_imported
# 		total_prev = pre_bank_guarantees + pre_company_imported

# 		rows_html = ""
# 		for row in data:
# 			rows_html += f"""
# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; vertical-align:top;">{row[0]}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; vertical-align:top; background-color:#E8F5E8;">{fmt(row[1])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; vertical-align:top;">{fmt(row[2])}</td>
# 			</tr>
# 			"""

# 		note_table = f"""
# 		<table style="margin-top: -30px; margin-bottom: -30px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<tr>
# 				<th style="border:1px solid #000; padding:6px; width:65%; font-weight:bold; color:#4472C4;">Particulars</th>
# 				<th style="border:1px solid #000; padding:6px; width:17.5%; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 				<th style="border:1px solid #000; padding:6px; width:17.5%; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 			</tr>

# 			{rows_html}

# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;"><strong>TOTAL</strong></td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(total_curr)}</strong></td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total_prev)}</strong></td>
# 			</tr>
# 		</table>
# 		"""

# 		return section_description.replace("{{note_table}}", note_table)

# 	def get_yearly_capital_and_other_commitments_note_data(self, section_description=""):
# 		# Get dynamic date labels
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "")
# 		previous_date = previous_year_label.replace("Year Ended ", "")
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		curr_date = datetime.strptime(current_date, "%d/%m/%Y").strftime("%Y-%m-%d")
# 		prev_date = datetime.strptime(previous_date, "%d/%m/%Y").strftime("%Y-%m-%d")

# 		# Fetch capital and other commitments data using get_value for efficiency
# 		cur_cap_data = frappe.db.get_value(
# 			"FR Capital and Other Commitments",
# 			{"company": self.company, "fiscal_year": self.fiscal_year, "month": cls_month},
# 			["estimated_capital_contracts_unexecuted", "other_commitments"],
# 			as_dict=True
# 		)
# 		pre_cap_data = frappe.db.get_value(
# 			"FR Capital and Other Commitments",
# 			{"company": self.company, "fiscal_year": self.previous_fiscal_year, "month": cls_month},
# 			["estimated_capital_contracts_unexecuted", "other_commitments"],
# 			as_dict=True
# 		)

# 		cur_estimated_capital = cur_cap_data.estimated_capital_contracts_unexecuted if cur_cap_data else "-"
# 		cur_other_commitments = cur_cap_data.other_commitments if cur_cap_data else "-"
# 		pre_estimated_capital = pre_cap_data.estimated_capital_contracts_unexecuted if pre_cap_data else "-"
# 		pre_other_commitments = pre_cap_data.other_commitments if pre_cap_data else "-"

# 		def fmt(val):
# 			if val in (None, "-", ""):
# 				return "-"
# 			return f"{val:,.0f}"

# 		def safe_val(val):
# 			"""Return numeric value or 0 for summing"""
# 			return val if isinstance(val, (int, float)) else 0

# 		rows = []
# 		total_current = safe_val(cur_estimated_capital)
# 		total_previous = safe_val(pre_estimated_capital)

# 		rows.append((
# 			"Estimated value of contracts remaining to be executed on capital account and not provided for "
# 			"(Net of advances ₹ 1,477 Lacs (P.Y. ₹ 2,727 Lacs))",
# 			cur_estimated_capital, pre_estimated_capital
# 		))

# 		# Fetch all equity entries in bulk for efficiency
# 		companies = frappe.get_all("FR Investment Entry", filters={"holding_company": self.company}, pluck="company")

# 		if companies:
# 			# Batch fetch all required data
# 			equity_data = frappe.db.sql("""
# 				SELECT
# 					name,
# 					company,
# 					capital_type,
# 					face_value,
# 					SUM(CASE WHEN posting_date <= %s THEN investment_value ELSE 0 END) AS cur_investment,
# 					SUM(CASE WHEN posting_date <= %s THEN investment_value ELSE 0 END) AS pre_investment
# 				FROM `tabFR Investment Entry`
# 				WHERE company IN %s
# 				AND holding_company = %s
# 				AND category = 'Equity Shares'
# 				AND capital_type IN ('Authorised Capital', 'Issued Capital')
# 				GROUP BY company, capital_type, face_value;
# 			""", (curr_date, prev_date, tuple(companies), self.company), as_dict=True)
			
# 			# Organize data by company
# 			company_data = {}
# 			for entry in equity_data:
# 				if entry.company not in company_data:
# 					company_data[entry.company] = {}
# 				company_data[entry.company][entry.capital_type] = entry

# 			for company in companies:
# 				data = company_data.get(company, {})
# 				auth_data = data.get("Authorised Capital", {})
# 				issued_data = data.get("Issued Capital", {})

# 				cur_auth_invest = auth_data.get("cur_investment") or 0
# 				pre_auth_invest = auth_data.get("pre_investment") or 0
# 				face_value = auth_data.get("face_value") or issued_data.get("face_value") or "-"

# 				cur_commit = issued_data.get("cur_investment") or "-"
# 				pre_commit = issued_data.get("pre_investment") or "-"

# 				# Get company details for display
# 				company_name = frappe.db.get_value("Company", company, "company_name") or company

# 				rows.append((
# 					f"Commitment to invest in {fmt(cur_auth_invest)} (P.Y. {fmt(pre_auth_invest)}) Equity Shares of {face_value} TRY each in {company_name}.",
# 					cur_commit, pre_commit
# 				))

# 				total_current += safe_val(cur_commit)
# 				total_previous += safe_val(pre_commit)

# 		# Add other commitments
# 		rows.append((
# 			"<strong>ii) Other Commitments</strong><br>"
# 			"Contractual arrangement for payment on corporate credit card facility availed by the company from the bank.",
# 			cur_other_commitments, pre_other_commitments
# 		))
# 		total_current += safe_val(cur_other_commitments)
# 		total_previous += safe_val(pre_other_commitments)

# 		# Build HTML using list join for efficiency
# 		rows_html_parts = []
# 		for r in rows:
# 			rows_html_parts.append(f"""
# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; vertical-align:top;">{r[0]}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; vertical-align:top; background-color:#E8F5E8;">{fmt(r[1])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; vertical-align:top;">{fmt(r[2])}</td>
# 			</tr>
# 			""")
# 		rows_html = "".join(rows_html_parts)

# 		note_table = f"""
# 		<table style="margin-top: -30px; margin-bottom: -30px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<tr>
# 				<th style="border:1px solid #000; padding:6px; width:65%; font-weight:bold; color:#4472C4;">Particulars</th>
# 				<th style="border:1px solid #000; padding:6px; width:17.5%; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 				<th style="border:1px solid #000; padding:6px; width:17.5%; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px;"><strong>i) Capital Commitments</strong></td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; background-color:#E8F5E8;"></td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px;"></td>
# 			</tr>

# 			{rows_html}

# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;"><strong>TOTAL</strong></td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{fmt(total_current)}</strong></td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{fmt(total_previous)}</strong></td>
# 			</tr>
# 		</table>
# 		"""

# 		return section_description.replace("{{note_table}}", note_table)

# 	def get_yearly_interest_in_subsidiaries_and_nci_note_data(self, section_description=""):
# 		# Get dynamic date labels
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_year_label.replace("Year Ended ", "").replace("/", "-")
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")

# 		curr_msme = frappe.db.exists("FR MSMSE Disclosure", {"company": self.company, "fiscal_year": self.fiscal_year, "month": cls_month})
# 		prev_msme = frappe.db.exists("FR MSMSE Disclosure", {"company": self.company, "fiscal_year": self.previous_fiscal_year, "month": cls_month})

# 		if curr_msme:
# 			curr_msme_doc = frappe.get_doc("FR MSMSE Disclosure", curr_msme)
# 			cur_principal_amount_outstanding = curr_msme_doc.principal_amount_outstanding
# 			cur_interest_amount_outstanding = curr_msme_doc.interest_amount_outstanding
# 			cur_interest_paid_on_delayed_payment = curr_msme_doc.interest_paid_on_delayed_payment
# 			cur_interest_due_for_the_year = curr_msme_doc.interest_due_for_the_year
# 			cur_interest_accrued_unpaid = curr_msme_doc.interest_accrued_unpaid
# 			cur_future_interest_payable = curr_msme_doc.future_interest_payable
# 		else:
# 			cur_principal_amount_outstanding = "-"
# 			cur_interest_amount_outstanding = "-"
# 			cur_interest_paid_on_delayed_payment = "-"
# 			cur_interest_due_for_the_year = "-"
# 			cur_interest_accrued_unpaid = "-"
# 			cur_future_interest_payable = "-"
		
# 		if prev_msme:
# 			prev_msme_doc = frappe.get_doc("FR MSMSE Disclosure", prev_msme)
# 			pre_principal_amount_outstanding = prev_msme_doc.principal_amount_outstanding
# 			pre_interest_amount_outstanding = prev_msme_doc.interest_amount_outstanding
# 			pre_interest_paid_on_delayed_payment = prev_msme_doc.interest_paid_on_delayed_payment
# 			pre_interest_due_for_the_year = prev_msme_doc.interest_due_for_the_year
# 			pre_interest_accrued_unpaid = prev_msme_doc.interest_accrued_unpaid
# 			pre_future_interest_payable = prev_msme_doc.future_interest_payable
# 		else:
# 			pre_principal_amount_outstanding = "-"
# 			pre_interest_amount_outstanding = "-"
# 			pre_interest_paid_on_delayed_payment = "-"
# 			pre_interest_due_for_the_year = "-"
# 			pre_interest_accrued_unpaid = "-"
# 			pre_future_interest_payable = "-"


# 		def fmt(val):
# 			if val in (None, "-", ""):
# 				return "-"
# 			if isinstance(val, (int, float)):
# 				if val < 0:
# 					return f"({abs(val):,})"
# 				return f"{val:,}"
# 			return val

# 		note_table = f"""
# 		<table style="marign-top: -20px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr>
# 					<th style="width: 60%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Particulars</th>
# 					<th style="border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">Year Ended<br>{current_date}<br>(₹ in lacs)</th>
# 					<th style="border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4;">Year Ended<br>{previous_date}<br>(₹ in lacs)</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 				<tr>
# 					<td style="border:1px solid #000; border-bottom:none; padding:6px;">(i) Principal amount remaining unpaid to any supplier as at the end of the accounting year</td>
# 					<td style="border:1px solid #000; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_principal_amount_outstanding)}</td>
# 					<td style="border:1px solid #000; border-bottom:none; padding:6px; text-align:right;">{fmt(pre_principal_amount_outstanding)}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px;">(ii) Interest due thereon remaining unpaid to any supplier as at the end of the accounting year</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_interest_amount_outstanding or "-")}</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(pre_interest_amount_outstanding or "-")}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px;">(iii) Interest paid on delayed payments beyond the appointed day</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_interest_paid_on_delayed_payment or "-")}</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(pre_interest_paid_on_delayed_payment or "-")}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px;">(iv) Interest due and payable for the year (CY ₹ 8,284)</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_interest_due_for_the_year or "-")}</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(pre_interest_due_for_the_year or "-")}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px;">(v) Interest accrued and remaining unpaid at the end of the accounting year (CY ₹ 8,284)</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_interest_accrued_unpaid or "-")}</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(pre_interest_accrued_unpaid or "-")}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px;">(vi) Further interest due and payable even in the succeeding year until payment</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_future_interest_payable or "-")}</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(pre_future_interest_payable or "-")}</td>
# 				</tr>
# 			</tbody>
# 		</table>
# 		"""

# 		return section_description.replace("{{note_table}}", note_table)
	
# 	def get_yearly_earning_per_equity_share_note_data(self, section_description=""):
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_year_label.replace("Year Ended ", "").replace("/", "-")
# 		face_value = frappe.get_value("Company", self.company, 'share_capital_amount')
# 		def fmt(val, decimals=0):
# 			if val in (None, "-", ""):
# 				return "-"
# 			if isinstance(val, float):
# 				return f"{val:,.{decimals}f}"
# 			return f"{val:,}"

# 		curr_profit = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Profit for the year from continuing operations"}, 'name'), 'current_month_amount')
# 		curr_share = -round((self.get_sum_grouping_amount(company, "Equity Share Capital - Paid up Capital", "Equity Share Capital - Paid up Capital", cls_month, self.fiscal_year) or 0), self.show_decimal_value) * 10000
		
# 		prev_profit = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Profit for the year from continuing operations"}, 'name'), 'previous_year')
# 		prev_shares = -round((self.get_sum_grouping_amount(company, "Equity Share Capital - Paid up Capital", "Equity Share Capital - Paid up Capital", cls_month, self.previous_fiscal_year) or 0), self.show_decimal_value) * 10000
# 		data = {
# 			"current": {
# 				"profit": curr_profit,
# 				"shares": curr_share,
# 				"eps": 0 if curr_share == 0 else (curr_profit/curr_share) * 100000,
# 				"face_value": face_value
# 			},
# 			"previous": {
# 				"profit": prev_profit,
# 				"shares": prev_shares,
# 				"eps": 0 if prev_shares == 0 else (prev_profit/prev_shares) * 100000,
# 				"face_value": face_value
# 			}
# 		}

# 		note_table = f"""
# 		<table style="margin-top: -20px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<tr>
# 				<th style="width:50%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Particulars</th>
# 				<th style="border:1px solid #000; padding:6px; width:25%; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">Year Ended<br>{current_date}<br>(₹ in Lacs)</th>
# 				<th style="border:1px solid #000; padding:6px; width:25%; font-weight:bold; color:#4472C4;">Year Ended<br>{previous_date}<br>(₹ in Lacs)</th>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; font-weight:bold;">Basic & Diluted</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;"></td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:1px solid #000; border-bottom:none; padding:6px; text-align:right;"></td>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Profit for the year as per Statement of Profit &amp; Loss</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(data["current"]["profit"])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(data["previous"]["profit"])}</td>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Weighted Average Number of Equity Shares (in Nos)</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(data["current"]["shares"])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(data["previous"]["shares"])}</td>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; font-weight:bold;">Basic and Diluted Earnings per Share (in ₹)</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(data["current"]["eps"], 2)}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(data["previous"]["eps"], 2)}</td>
# 			</tr>

# 			<tr>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Face value per share (in ₹)</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(data["current"]["face_value"])}</td>
# 				<td style="border-right:1px solid #000; border-left:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{fmt(data["previous"]["face_value"])}</td>
# 			</tr>
# 		</table>
# 		"""

# 		return section_description.replace("{{note_table}}", note_table)


# 	def get_yearly_employee_benefit_obligation_note_data(self, section_description=""):
# 		# Get dynamic date labels
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_year_label.replace("Year Ended ", "").replace("/", "-")
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")

# 		def fmt_amt(val):
# 			if val in (None, "-", ""):
# 				return "-"
# 			if isinstance(val, (int, float)):
# 				if val < 0:
# 					return f"({abs(val):,})"
# 				return f"{val:,}"
# 			return val

# 		def fmt_pct(val):
# 			return val if isinstance(val, str) else f"{val:.2f}%"
# 		curr_ebo = prev_ebo = None
# 		curr_name = frappe.db.exists("FR Employee Benefit Obligation",{"company": self.company,"fiscal_year": self.fiscal_year,"month": cls_month})
# 		if curr_name:
# 			curr_ebo = frappe.get_doc("FR Employee Benefit Obligation", curr_name)

# 		prev_name = frappe.db.exists("FR Employee Benefit Obligation",{"company": self.company,"fiscal_year": self.previous_fiscal_year,"month": cls_month})
# 		if prev_name:
# 			prev_ebo = frappe.get_doc("FR Employee Benefit Obligation", prev_name)
		
# 		note_table_1_map = {}
# 		if curr_ebo:
# 			for i in curr_ebo.amount_recognised_in_the_balance_sheet:
# 				note_table_1_map[i.label] = {
# 					"label": i.label,
# 					"curr_amt": i.value,
# 					"prev_amt": "-",
# 					"is_bold": i.is_bold
# 				}
# 		if prev_ebo:
# 			for i in prev_ebo.amount_recognised_in_the_balance_sheet:
# 				if i.label in note_table_1_map:
# 					note_table_1_map[i.label]["prev_amt"] = i.value
# 				else:
# 					note_table_1_map[i.label] = {
# 						"label": i.label,
# 						"curr_amt": "-",
# 						"prev_amt": i.value,
# 						"is_bold": i.is_bold
# 					}

# 		rows_html = ""
# 		for row in note_table_1_map.values():
# 			style = "font-weight:bold;" if row["is_bold"] else ""
# 			rows_html += f"""
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px; {style}">{row['label']}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8; {style}">{fmt_amt(row['curr_amt']) if row['curr_amt'] != '-' else '-'}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; {style}">{fmt_amt(row['prev_amt']) if row['prev_amt'] != '-' else '-'}</td>
# 			</tr>
# 			"""


# 		note_table_1 = f"""
# 		<table style="margin-top: -30px; margin-bottom: -30px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 		<tr>
# 			<th style="width:60%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">(I) Amount recognised in the Balance Sheet</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 		</tr>
# 		{rows_html}
# 		</table>
# 		"""

# 		note_table_2_map = {}
# 		if curr_ebo:
# 			for i in curr_ebo.amount_recognised_in_statement_of_profit:
# 				note_table_2_map[i.label] = {
# 					"label": i.label,
# 					"curr_amt": i.value,
# 					"prev_amt": "-",
# 					"is_bold": i.is_bold
# 				}
# 		if prev_ebo:
# 			for i in prev_ebo.amount_recognised_in_statement_of_profit:
# 				if i.label in note_table_2_map:
# 					note_table_2_map[i.label]["prev_amt"] = i.value
# 				else:
# 					note_table_2_map[i.label] = {
# 						"label": i.label,
# 						"curr_amt": "-",
# 						"prev_amt": i.value,
# 						"is_bold": i.is_bold
# 					}

# 		rows_2_html = ""
# 		for row in note_table_2_map.values():
# 			style = "font-weight:bold;" if row["is_bold"] else "border-top:none; border-bottom:none;"
# 			rows_2_html += f"""
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px; {style}">{row['label']}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8; {style}">{fmt_amt(row['curr_amt']) if row['curr_amt'] != '-' else '-'}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; {style}">{fmt_amt(row['prev_amt']) if row['prev_amt'] != '-' else '-'}</td>
# 			</tr>
# 			"""
			
# 		note_table_2 = f"""
# 		<table style="margin-top: -30px; margin-bottom: -30px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 		<tr>
# 			<th style="width:60%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">(II) Amount recognised in Statement of Profit & Loss</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 		</tr>
# 		{rows_2_html}
# 		</table>
# 		"""

# 		note_table_3_map = {}
# 		if curr_ebo:
# 			for i in curr_ebo.reconciliation_of_defined_benefit_obligation:
# 				note_table_3_map[i.label] = {
# 					"label": i.label,
# 					"curr_amt": i.value,
# 					"prev_amt": "-",
# 					"is_bold": i.is_bold
# 				}
# 		if prev_ebo:
# 			for i in prev_ebo.reconciliation_of_defined_benefit_obligation:
# 				if i.label in note_table_3_map:
# 					note_table_3_map[i.label]["prev_amt"] = i.value
# 				else:
# 					note_table_3_map[i.label] = {
# 						"label": i.label,
# 						"curr_amt": "-",
# 						"prev_amt": i.value,
# 						"is_bold": i.is_bold
# 					}

# 		rows_3_html = ""
# 		for row in note_table_3_map.values():
# 			style = "font-weight:bold;" if row["is_bold"] else "border-top:none; border-bottom:none;"
# 			rows_3_html += f"""
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px; {style}">{row['label']}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8; {style}">{fmt_amt(row['curr_amt']) if row['curr_amt'] != '-' else '-'}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; {style}">{fmt_amt(row['prev_amt']) if row['prev_amt'] != '-' else '-'}</td>
# 			</tr>
# 			"""

# 		note_table_3 = f"""
# 		<table style="margin-top: -30px; margin-bottom: -30px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 		<tr>
# 			<th style="width: 60%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">(III) Reconciliation of Defined Benefit Obligation</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 		</tr>
# 		{rows_3_html}
# 		</table>
# 		"""

# 		note_table_4_map = {}
# 		if curr_ebo:
# 			for i in curr_ebo.actuarial_assumptions:
# 				note_table_4_map[i.label] = {
# 					"label": i.label,
# 					"curr_amt": i.value,
# 					"prev_amt": "-",
# 					"is_bold": i.is_bold
# 				}
# 		if prev_ebo:
# 			for i in prev_ebo.actuarial_assumptions:
# 				if i.label in note_table_4_map:
# 					note_table_4_map[i.label]["prev_amt"] = i.value
# 				else:
# 					note_table_4_map[i.label] = {
# 						"label": i.label,
# 						"curr_amt": "-",
# 						"prev_amt": i.value,
# 						"is_bold": i.is_bold
# 					}

# 		rows_4_html = ""
# 		for row in note_table_4_map.values():
# 			style = "font-weight:bold;" if row["is_bold"] else "border-top:none; border-bottom:none;"
# 			rows_4_html += f"""
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px; {style}">{row['label']}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8; {style}">{fmt_amt(row['curr_amt']) if row['curr_amt'] != '-' else '-'}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; {style}">{fmt_amt(row['prev_amt']) if row['prev_amt'] != '-' else '-'}</td>
# 			</tr>
# 			"""

# 		note_table_4 = f"""
# 		<table style="margin-top: -30px; margin-bottom: -30px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 		<tr>
# 			<th style="width: 60%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">(IV) Actuarial Assumptions</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 		</tr>
# 		{rows_4_html}
# 		</table>
# 		"""

# 		note_table_8_map = {}
# 		if curr_ebo:
# 			for i in curr_ebo.experience_adjustments:
# 				note_table_8_map[i.label] = {
# 					"label": i.label,
# 					"curr_amt": i.value,
# 					"prev_amt": "-",
# 					"is_bold": i.is_bold
# 				}
# 		if prev_ebo:
# 			for i in prev_ebo.experience_adjustments:
# 				if i.label in note_table_8_map:
# 					note_table_8_map[i.label]["prev_amt"] = i.value
# 				else:
# 					note_table_8_map[i.label] = {
# 						"label": i.label,
# 						"curr_amt": "-",
# 						"prev_amt": i.value,
# 						"is_bold": i.is_bold
# 					}

# 		rows_8_html = ""
# 		for row in note_table_8_map.values():
# 			style = "font-weight:bold;" if row["is_bold"] else "border-top:none; border-bottom:none;"
# 			rows_8_html += f"""
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px; {style}">{row['label']}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8; {style}">{fmt_amt(row['curr_amt']) if row['curr_amt'] != '-' else '-'}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; {style}">{fmt_amt(row['prev_amt']) if row['prev_amt'] != '-' else '-'}</td>
# 			</tr>
# 			"""

# 		note_table_8 = f"""
# 		<table style="margin-top: -30px; margin-bottom: -30px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 		<tr>	
# 			<th style="width: 60%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">(viii) Experience Adjustments</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 		</tr>
# 		{rows_8_html}
# 		</table>
# 		"""

# 		note_table_9_map = {}
# 		if curr_ebo:
# 			for i in curr_ebo.sensitivity_analysis:
# 				note_table_9_map[i.label] = {
# 					"label": i.label,
# 					"curr_amt": i.value,
# 					"prev_amt": "-",
# 					"is_bold": i.is_bold
# 				}
# 		if prev_ebo:
# 			for i in prev_ebo.sensitivity_analysis:
# 				if i.label in note_table_9_map:
# 					note_table_9_map[i.label]["prev_amt"] = i.value
# 				else:
# 					note_table_9_map[i.label] = {
# 						"label": i.label,
# 						"curr_amt": "-",
# 						"prev_amt": i.value,
# 						"is_bold": i.is_bold
# 					}

# 		rows_9_html = ""
# 		for row in note_table_9_map.values():
# 			style = "font-weight:bold;" if row["is_bold"] else "border-top:none; border-bottom:none;"
# 			rows_9_html += f"""
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px; {style}">{row['label']}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8; {style}">{fmt_amt(row['curr_amt']) if row['curr_amt'] != '-' else '-'}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; {style}">{fmt_amt(row['prev_amt']) if row['prev_amt'] != '-' else '-'}</td>
# 			</tr>
# 			"""

# 		note_table_9 = f"""
# 		<table style="margin-top: -30px; margin-bottom: -30px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 		<tr>	
# 			<th style="width: 60%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">(IX) Sensitivity Analysis</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 		</tr>
# 		{rows_9_html}
# 		</table>
# 		"""

# 		note_table_11_map = {}
# 		if curr_ebo:
# 			for i in curr_ebo.maturity_analysis:
# 				note_table_11_map[i.label] = {
# 					"label": i.label,
# 					"curr_amt": i.value,
# 					"prev_amt": "-",
# 					"is_bold": i.is_bold
# 				}
# 		if prev_ebo:
# 			for i in prev_ebo.maturity_analysis:
# 				if i.label in note_table_11_map:
# 					note_table_11_map[i.label]["prev_amt"] = i.value
# 				else:
# 					note_table_11_map[i.label] = {
# 						"label": i.label,
# 						"curr_amt": "-",
# 						"prev_amt": i.value,
# 						"is_bold": i.is_bold
# 					}

# 		rows_11_html = ""
# 		for row in note_table_11_map.values():
# 			style = "font-weight:bold;" if row["is_bold"] else "border-top:none; border-bottom:none;"
# 			rows_11_html += f"""
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px; {style}">{row['label']}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8; {style}">{fmt_amt(row['curr_amt']) if row['curr_amt'] != '-' else '-'}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; {style}">{fmt_amt(row['prev_amt']) if row['prev_amt'] != '-' else '-'}</td>
# 			</tr>
# 			"""

# 		note_table_11 = f"""
# 		<table style="margin-top: -30px; margin-bottom: -30px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 		<tr>
# 			<th style="width: 60%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">(XI) Maturity Analysis</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 		</tr>
# 		{rows_11_html}
# 		</table>
# 		"""

# 		note_table_12_map = {}
# 		if curr_ebo:
# 			for i in curr_ebo.actuarial_assumption_for_compensated_absences:
# 				note_table_12_map[i.label] = {
# 					"label": i.label,
# 					"curr_amt": i.value,
# 					"prev_amt": "-",
# 					"is_bold": i.is_bold
# 				}
# 		if prev_ebo:
# 			for i in prev_ebo.actuarial_assumption_for_compensated_absences:
# 				if i.label in note_table_12_map:
# 					note_table_12_map[i.label]["prev_amt"] = i.value
# 				else:
# 					note_table_12_map[i.label] = {
# 						"label": i.label,
# 						"curr_amt": "-",
# 						"prev_amt": i.value,
# 						"is_bold": i.is_bold
# 					}

# 		rows_12_html = ""
# 		for row in note_table_12_map.values():
# 			style = "font-weight:bold;" if row["is_bold"] else "border-top:none; border-bottom:none;"
# 			rows_12_html += f"""
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px; {style}">{row['label']}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8; {style}">{fmt_amt(row['curr_amt']) if row['curr_amt'] != '-' else '-'}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; {style}">{fmt_amt(row['prev_amt']) if row['prev_amt'] != '-' else '-'}</td>
# 			</tr>
# 			"""

# 		note_table_12 = f"""
# 		<table style="margin-top: -30px; margin-bottom: -30px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 		<tr>
# 			<th style="width: 60%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Actuarial assumption for compensated absences</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 		</tr>
# 		{rows_12_html}
# 		</table>
# 		"""

# 		note_table_12_2_map = {}
# 		if curr_ebo:
# 			for i in curr_ebo.actuarial_assumption_for_compensated_absences:
# 				note_table_12_2_map[i.label] = {
# 					"label": i.label,
# 					"curr_amt": i.value,
# 					"prev_amt": "-",
# 					"is_bold": i.is_bold
# 				}
# 		if prev_ebo:
# 			for i in prev_ebo.actuarial_assumption_for_compensated_absences:
# 				if i.label in note_table_12_2_map:
# 					note_table_12_2_map[i.label]["prev_amt"] = i.value
# 				else:
# 					note_table_12_2_map[i.label] = {
# 						"label": i.label,
# 						"curr_amt": "-",
# 						"prev_amt": i.value,
# 						"is_bold": i.is_bold
# 					}

# 		rows_12_2_html = ""
# 		for row in note_table_12_2_map.values():
# 			style = "font-weight:bold;" if row["is_bold"] else "border-top:none; border-bottom:none;"
# 			rows_12_2_html += f"""
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px; {style}">{row['label']}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8; {style}">{fmt_amt(row['curr_amt']) if row['curr_amt'] != '-' else '-'}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; {style}">{fmt_amt(row['prev_amt']) if row['prev_amt'] != '-' else '-'}</td>
# 			</tr>
# 			"""

# 		note_table_12 += f"""
# 		<p><strong>Defined Contribution Plans:</strong></p>
# 		<table style="margin-top: -30px; margin-bottom: -30px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 		<tr>
# 			<th style="width: 60%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">AMOUNT RECOGNISED IN THE STATEMENT OF PROFIT AND LOSS</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 			<th style="border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 		</tr>
# 		{rows_12_2_html}
# 		</table>
# 		"""

# 		section_description = (
# 			section_description
# 			.replace("{{note_table_1}}", note_table_1)
# 			.replace("{{note_table_2}}", note_table_2)
# 			.replace("{{note_table_3}}", note_table_3)
# 			.replace("{{note_table_4}}", note_table_4)
# 			.replace("{{note_table_8}}", note_table_8)
# 			.replace("{{note_table_9}}", note_table_9)
# 			.replace("{{note_table_11}}", note_table_11)
# 			.replace("{{note_table_12}}", note_table_12)
# 		)

# 		return section_description

# 	def get_yearly_ratio_note_data(self, section_description=""):
# 		cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 		bs_template = next(d.section for d in self.get("financial_report_details", []) if d.section_type == "Balance Sheet")	
# 		def fmt(val, is_ratio=False, is_pct=False):
# 			if val in (None, "", "-"):
# 				return "-"
# 			val = flt(val)
# 			if is_pct:
# 				return f"{val:.2f}%"
# 			if is_ratio:
# 				return f"{val:.2f}"
# 			return f"{int(val):,}"

# 		cur_current_asset = self.get_bs_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Current Assets"}, 'name'), 'current_month_amount')
# 		cur_current_liab = self.get_bs_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Current Liabilities"}, 'name'), 'current_month_amount')
# 		curr_ratio = 0 if cur_current_liab == 0 else round(cur_current_asset/cur_current_liab, 2)

# 		pre_current_asset = self.get_bs_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Current Assets"}, 'name'), 'previous_year')
# 		pre_current_liab = self.get_bs_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Current Liabilities"}, 'name'), 'previous_year')
# 		pre_ratio = 0 if pre_current_liab == 0 else round(pre_current_asset/pre_current_liab, 2)

# 		cur_tot_ded = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Borrowing"}, 'name'), 'current_month_amount') + self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Lease"}, 'name'), 'current_month_amount') + self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Current Borrowing"}, 'name'), 'current_month_amount') + self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Current Lease"}, 'name'), 'current_month_amount')
# 		cur_tot_equ = self.get_bs_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Equity"}, 'name'), 'current_month_amount')
# 		cur_ded_ratio = 0 if cur_tot_equ == 0 else (cur_tot_ded/cur_tot_equ)

# 		pre_tot_ded = self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Borrowing"}, 'name'), 'previous_year') + self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Lease"}, 'name'), 'previous_year') + self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Current Borrowing"}, 'name'), 'previous_year') + self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Current Lease"}, 'name'), 'previous_year')
# 		pre_tot_equ = self.get_bs_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Equity"}, 'name'), 'previous_year')
# 		pre_ded_ratio = 0 if pre_tot_equ == 0 else (pre_tot_ded/pre_tot_equ)

# 		curr_net_op = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Profit for the year from continuing operations"}, 'name'), 'current_month_amount') + self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Depreciation & Amortisation Expenses"}, 'name'), 'current_month_amount') + self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Finance Cost"}, 'name'), 'current_month_amount')
# 		curr_deb_ser = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Finance Cost"}, 'name'), 'current_month_amount')
# 		curr_deb_ser_ratio = 0 if curr_deb_ser == 0 else curr_net_op/curr_deb_ser

# 		pre_net_op = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Profit for the year from continuing operations"}, 'name'), 'previous_year') + self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Depreciation & Amortisation Expenses"}, 'name'), 'previous_year') + self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Finance Cost"}, 'name'), 'previous_year')
# 		pre_deb_ser = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Finance Cost"}, 'name'), 'previous_year')
# 		pre_deb_ser_ratio = 0 if pre_deb_ser == 0 else pre_net_op/pre_deb_ser

# 		curr_pro_af_tax = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Profit for the year from continuing operations"}, 'name'), 'current_month_amount')
# 		curr_avg_share_equ = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Equity"}, 'name'), 'current_month_amount') + self.get_bs_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Equity"}, 'name'), 'previous_year'))/2
# 		curr_equ_ratio = 0 if curr_avg_share_equ == 0 else curr_pro_af_tax/curr_avg_share_equ

# 		pre_total_equity = flt(self.get_sum_grouping_amount(company, "Equity Share Capital - Paid up Capital", "Equity Share Capital - Paid up Capital", cls_month, pre_year)) + flt(self.get_yearly_other_equity_note_data(self.previous_fiscal_year, pre_year, total=True, field='grand_total_prev_year')) or 0
# 		pre_pro_af_tax = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Profit for the year from continuing operations"}, 'name'), 'previous_year')
# 		pre_avg_share_equ = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Equity"}, 'name'), 'previous_year') + pre_total_equity)/2
# 		pre_equ_ratio = 0 if pre_avg_share_equ == 0 else pre_pro_af_tax/pre_avg_share_equ

# 		curr_cogs = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Cost of Goods Sold"}, 'name'), 'current_month_amount') + self.get_pl_particular_data(frappe.get_value("FR Particular", {'is_purchase_of_stock_in_trade': 1}, 'name'), 'current_month_amount') + self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Change In Inventory"}, 'name'), 'current_month_amount')
# 		curr_avg_inv = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Inventory"}, 'name'), 'current_month_amount') + self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Inventory"}, 'name'), 'previous_year')) / 2
# 		curr_inv_ratio = 0 if curr_avg_inv == 0 else curr_cogs/curr_avg_inv

# 		secondary_groups = sorted(set(g for g in frappe.get_list("GL Group Mapping", {"primary_group": "Inventories", "company": self.company}, pluck="secondary_group") if g))
# 		pre_cogs = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Cost of Goods Sold"}, 'name'), 'previous_year') + self.get_pl_particular_data(frappe.get_value("FR Particular", {'is_purchase_of_stock_in_trade': 1}, 'name'), 'previous_year') + self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Change In Inventory"}, 'name'), 'previous_year')
# 		pre_avg_inv = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Inventory"}, 'name'), 'previous_year') + sum(flt(self.get_sum_grouping_amount(company, "Inventories", sec, cls_month, pre_year)) for sec in secondary_groups)) / 2
# 		pre_inv_ratio = 0 if pre_avg_inv == 0 else pre_cogs/pre_avg_inv

# 		curr_rev = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Revenue from Operations"}, 'name'), 'current_month_amount') 
# 		curr_avg_trade = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Trade & Other Receivables"}, 'name'), 'current_month_amount') + self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Trade & Other Receivables"}, 'name'), 'previous_year'))/2
# 		curr_trade_ratio = 0 if curr_avg_trade == 0 else curr_rev/curr_avg_trade

# 		credit_impaired_prev = round((self.get_sum_grouping_amount(company, "Trade Receivables - credit Impaired", "Trade Receivables - credit Impaired", cls_month, pre_year) or 0), self.show_decimal_value)
# 		trade_recv_prev = round((self.get_sum_grouping_amount(company, "Trade Receivables", "Trade Receivables", cls_month, pre_year) or 0), self.show_decimal_value)
# 		other_recv_prev = round((self.get_sum_grouping_amount(company, "Trade Receivables", "Other Trade receivables", cls_month, pre_year) or 0), self.show_decimal_value)

# 		pre_rev = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Revenue from Operations"}, 'name'), 'current_month_amount') 
# 		pre_avg_trade = (self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Trade & Other Receivables"}, 'name'), 'previous_year') + (credit_impaired_prev + trade_recv_prev + other_recv_prev))/2
# 		pre_trade_ratio = 0 if pre_avg_trade == 0 else pre_rev/pre_avg_trade

# 		trade_payables_turnover_ratio_grouping = frappe.get_doc("FR Financial Settings").trade_payables_turnover_ratio_grouping or []
# 		curr_pur = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Other Expense"}, 'name'), 'current_month_amount') + sum(self.get_sum_grouping_amount(company, i.primary_group, i.secoundary_group, cls_month, self.fiscal_year) for i in trade_payables_turnover_ratio_grouping)
# 		curr_avg_trade_pay = self.get_sum_grouping_amount(company, "Trade payables", "Trade payables", cls_month, self.fiscal_year) + self.get_sum_grouping_amount(company, "Trade payables", "Trade payables", cls_month, self.previous_fiscal_year)
# 		curr_trade_payable = 0 if curr_avg_trade_pay == 0 else curr_pur/curr_avg_trade_pay

# 		pre_pur = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Other Expense"}, 'name'), 'current_month_amount') + sum(self.get_sum_grouping_amount(company, i.primary_group, i.secoundary_group, cls_month, self.previous_fiscal_year) for i in trade_payables_turnover_ratio_grouping)
# 		pre_avg_trade_pay = self.get_sum_grouping_amount(company, "Trade payables", "Trade payables", cls_month, self.previous_fiscal_year) + self.get_sum_grouping_amount(company, "Trade payables", "Trade payables", cls_month, pre_year)
# 		pre_trade_payable = 0 if pre_avg_trade_pay == 0 else pre_pur/pre_avg_trade_pay

# 		curr_work_cap = cur_current_asset - cur_current_liab
# 		curr_net_rev_rat = 0 if curr_work_cap == 0 else curr_rev/curr_work_cap

# 		pre_work_cap = pre_current_asset - pre_current_liab
# 		pre_net_rev_rat = 0 if pre_work_cap == 0 else pre_rev/ pre_work_cap

# 		curr_net_pro_ratio = 0 if curr_rev == 0 else curr_pro_af_tax/curr_rev
# 		pre_net_pro_ratio = 0 if pre_rev == 0 else pre_pro_af_tax/pre_rev

# 		curr_ear_be_tax = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Profit Before Tax"}, 'name'), 'current_month_amount') + self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Finance Cost"}, 'name'), 'current_month_amount')
# 		curr_cap_emp_equity = self.get_bs_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Equity"}, 'name'), 'current_month_amount') + self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Borrowing"}, 'name'), 'current_month_amount') + self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Lease"}, 'name'), 'current_month_amount')
# 		curr_ret_cap_emp = 0 if curr_cap_emp_equity == 0 else curr_ear_be_tax/curr_cap_emp_equity 

# 		pre_ear_be_tax = self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Profit Before Tax"}, 'name'), 'previous_year') + self.get_pl_particular_data(frappe.get_value("FR Particular", {'type': "Finance Cost"}, 'name'), 'previous_year')
# 		pre_cap_emp_equity = pre_total_equity + self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Borrowing"}, 'name'), 'previous_year') + self.get_bs_particular_data(frappe.get_value("FR Particular", {'type': "Non Current Lease"}, 'name'), 'previous_year')
# 		pre_ret_cap_emp = 0 if pre_cap_emp_equity == 0 else pre_ear_be_tax/pre_cap_emp_equity 

# 		note_table_1 = f"""
# 		<table style="margin-top: -20px; margin-bottom: -20px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr>
# 					<th style="width:19%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Particulars</th>
# 					<th style="width:24%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4; font-size:8px;">Formula</th>
# 					<th style="width:17%; border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">Current Year<br></th>
# 					<th style="width:7%; border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">Ratio</th>
# 					<th style="width:17%; border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4;">Previous Year<br></th>
# 					<th style="width:7%; border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4;">Ratio</th>
# 					<th style="width:9%; border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4;">Change in %</th>
# 				</tr>
# 			</thead>
# 			<tbody>

# 			<tr>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; vertical-align:middle;">Current Ratio</td>
# 				<td style="border:1px solid #000; padding:6px;">Current Assets</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_current_asset)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle; background-color:#E8F5E8;">{fmt(curr_ratio, is_ratio=True)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_current_asset)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(pre_ratio, is_ratio=True)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(0 if pre_ratio == 0 else (curr_ratio/pre_ratio), is_pct=True)}</td>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;">Current Liabilities</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_current_liab)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_current_liab)}</td>
# 			</tr>

# 			<tr>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; vertical-align:middle;">Debt-Equity Ratio</td>
# 				<td style="border:1px solid #000; padding:6px;">Total Debt</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_tot_ded)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle; background-color:#E8F5E8;">{fmt(cur_ded_ratio, is_ratio=True)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_tot_ded)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(pre_ded_ratio, is_ratio=True)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(0 if pre_ded_ratio == 0 else (cur_ded_ratio/pre_ded_ratio), is_pct=True)}</td>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;">Total Equity</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(cur_tot_equ)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_tot_equ)}</td>
# 			</tr>

# 			<tr>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; vertical-align:middle;">Debt Service Coverage Ratio</td>
# 				<td style="border:1px solid #000; padding:6px;">Net Operating Income</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_net_op)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle; background-color:#E8F5E8;">{fmt(curr_deb_ser_ratio, is_ratio=True)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_net_op)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(pre_deb_ser_ratio, is_ratio=True)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(0 if pre_deb_ser_ratio == 0 else fmt(curr_deb_ser_ratio/pre_deb_ser_ratio), is_pct=True)}</td>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;">Total Debt Service</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_deb_ser)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_deb_ser)}</td>
# 			</tr>

# 			<tr>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; vertical-align:middle;">Return on Equity Ratio</td>
# 				<td style="border:1px solid #000; padding:6px;">PAT</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_pro_af_tax)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle; background-color:#E8F5E8;">{fmt(curr_equ_ratio, is_ratio=True)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_pro_af_tax)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(pre_equ_ratio, is_ratio=True)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(0 if pre_equ_ratio == 0 else fmt(curr_equ_ratio/pre_equ_ratio), is_pct=True)}</td>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;">Average Shareholder's Equity</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_avg_share_equ)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_avg_share_equ)}</td>
# 			</tr>

# 			<tr>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; vertical-align:middle;">Inventory Turnover Ratio</td>
# 				<td style="border:1px solid #000; padding:6px;">COGS</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_cogs)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle; background-color:#E8F5E8;">{fmt(curr_inv_ratio, is_ratio=True)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_cogs)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(pre_inv_ratio, is_ratio=True)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(0 if pre_inv_ratio == 0 else fmt(curr_inv_ratio/pre_inv_ratio), is_pct=True)}</td>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;">Average Inventory</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_avg_inv)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_avg_inv)}</td>
# 			</tr>

# 			<tr>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; vertical-align:middle;">Trade Receivables Turnover Ratio</td>
# 				<td style="border:1px solid #000; padding:6px;">Revenue from operations</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_rev)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle; background-color:#E8F5E8;">{fmt(curr_trade_ratio, is_ratio=True)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_rev)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(pre_trade_ratio, is_ratio=True)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(0 if pre_trade_ratio == 0 else curr_trade_ratio/pre_trade_ratio, is_pct=True)}</td>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;">Avg Trade Receivable</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_avg_trade)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_avg_trade)}</td>
# 			</tr>

# 			<tr>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; vertical-align:middle;">Trade Payables Turnover Ratio</td>
# 				<td style="border:1px solid #000; padding:6px;">Purchases</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_pur)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle; background-color:#E8F5E8;">{fmt(curr_trade_payable, is_ratio=True)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_pur)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(pre_trade_payable, is_ratio=True)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(0 if pre_trade_payable == 0 else (curr_trade_payable/pre_trade_payable) , is_pct=True)}</td>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;">Avg Trade Payable</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_avg_trade_pay)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_avg_trade_pay)}</td>
# 			</tr>

# 			<tr>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; vertical-align:middle;">Net Capital Turnover Ratio</td>
# 				<td style="border:1px solid #000; padding:6px;">Revenue from operations</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_rev)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle; background-color:#E8F5E8;">{fmt(curr_net_rev_rat, is_ratio=True)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_rev)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(pre_net_rev_rat, is_ratio=True)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(0 if pre_net_rev_rat == 0 else curr_net_rev_rat/pre_net_rev_rat, is_pct=True)}</td>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;">Working Capital</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_work_cap)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_work_cap)}</td>
# 			</tr>

# 			<tr>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; vertical-align:middle;">Net Profit Ratio</td>
# 				<td style="border:1px solid #000; padding:6px;">PAT</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_pro_af_tax)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle; background-color:#E8F5E8;">{fmt(curr_net_pro_ratio, is_ratio=True)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_pro_af_tax)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(pre_net_pro_ratio, is_ratio=True)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(0 if pre_net_pro_ratio == 0 else curr_net_pro_ratio/pre_net_pro_ratio, is_pct=True)}</td>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;">Revenue</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_rev)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_rev)}</td>
# 			</tr>

# 			<tr>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; vertical-align:middle;">Return on Capital Employed</td>
# 				<td style="border:1px solid #000; padding:6px;">Earning Before Interest & Tax</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_ear_be_tax)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle; background-color:#E8F5E8;">{fmt(curr_ret_cap_emp, is_ratio=True)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_ear_be_tax)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(pre_ret_cap_emp, is_ratio=True)}</td>
# 				<td rowspan="2" style="border:1px solid #000; padding:6px; text-align:right; vertical-align:middle;">{fmt(0 if pre_ret_cap_emp == 0 else curr_ret_cap_emp/pre_ret_cap_emp, is_pct=True)}</td>
# 			</tr>
# 			<tr>
# 				<td style="border:1px solid #000; padding:6px;">Capital Employed</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;">{fmt(curr_cap_emp_equity)}</td>
# 				<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(pre_cap_emp_equity)}</td>
# 			</tr>

# 			</tbody>
# 		</table>
# 		"""

# 		fr_ratio = frappe.db.exists("FR Ratio Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month})
# 		curr_ratio_rem, debt_equ_rem, debt_serv_rem, ret_equ_rat, inv_turn_ratio, trade_rec_turn_ratio, trade_pay_turn_ratio, net_cap_turn_ration, net_pro_ration, ret_on_cap_emp = "-", "-", "-","-", "-", "-","-", "-", "-","-"
# 		if fr_ratio:
# 			fr_ratio_mast = frappe.get_doc("FR Ratio Master", fr_ratio)
# 			curr_ratio_rem = fr_ratio_mast.current_ratio
# 			debt_equ_rem = fr_ratio_mast.debt_equity_ratio
# 			debt_serv_rem = fr_ratio_mast.debt_service_coverage_ratio
# 			ret_equ_rat = fr_ratio_mast.return_on_equity_ratio
# 			inv_turn_ratio = fr_ratio_mast.inventory_turnover_ratio
# 			trade_rec_turn_ratio = fr_ratio_mast.trade_receivables_turnover_ratio
# 			trade_pay_turn_ratio = fr_ratio_mast.trade_payables_turnover_ratio
# 			net_cap_turn_ration = fr_ratio_mast.net_capital_turnover_ratio
# 			net_pro_ration = fr_ratio_mast.net_profit_ratio
# 			ret_on_cap_emp = fr_ratio_mast.return_on_capital_employed
# 		ratio_data = [
# 			("Current Ratio", 0 if pre_ratio == 0 else (curr_ratio - pre_ratio) / pre_ratio * 100, curr_ratio_rem),
# 			("Debt-Equity Ratio", 0 if pre_ded_ratio == 0 else (cur_ded_ratio - pre_ded_ratio) / pre_ded_ratio * 100, debt_equ_rem),
# 			("Debt Service Coverage Ratio", 0 if pre_deb_ser_ratio == 0 else (curr_deb_ser_ratio - pre_deb_ser_ratio) / pre_deb_ser_ratio * 100, debt_serv_rem),
# 			("Return on Equity Ratio", 0 if pre_equ_ratio == 0 else (curr_equ_ratio - pre_equ_ratio) / pre_equ_ratio * 100, ret_equ_rat),
# 			("Inventory Turnover Ratio", 0 if pre_inv_ratio == 0 else (curr_inv_ratio - pre_inv_ratio) / pre_inv_ratio * 100, inv_turn_ratio),
# 			("Trade Receivables Turnover Ratio", 0 if pre_trade_ratio == 0 else (curr_trade_ratio - pre_trade_ratio) / pre_trade_ratio * 100, trade_rec_turn_ratio),
# 			("Trade Payables Turnover Ratio", 0 if pre_trade_payable == 0 else (curr_trade_payable - pre_trade_payable) / pre_trade_payable * 100, trade_pay_turn_ratio),
# 			("Net Capital Turnover Ratio", 0 if pre_net_rev_rat == 0 else (curr_net_rev_rat - pre_net_rev_rat) / pre_net_rev_rat * 100, net_cap_turn_ration),
# 			("Net Profit Ratio", 0 if pre_net_pro_ratio == 0 else (curr_net_pro_ratio - pre_net_pro_ratio) / pre_net_pro_ratio * 100, net_pro_ration),
# 			("Return on Capital Employed", 0 if pre_ret_cap_emp == 0 else (curr_ret_cap_emp - pre_ret_cap_emp) / pre_ret_cap_emp * 100, ret_on_cap_emp),
# 		]

# 		rows_html = ""
# 		for idx, (name, change_pct, remark) in enumerate(ratio_data, 1):
# 			rows_html += f"""
# 				<tr>
# 					<td style="border:1px solid #000; padding:6px; text-align:center;">{idx}</td>
# 					<td style="border:1px solid #000; padding:6px;">{name}</td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right;">{fmt(change_pct, is_pct=True)}</td>
# 					<td style="border:1px solid #000; padding:6px;">{remark or "-"}</td>
# 				</tr>"""

# 		note_table_2 = f"""
# 		<table style="margin-top: -20px; margin-bottom: -20px; width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr>
# 					<th style="width: 10%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Sr No.</th>
# 					<th style="width: 30%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Particulars</th>
# 					<th style="width: 15%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Change in %</th>
# 					<th style="width: 45%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Remarks</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 				{rows_html}
# 			</tbody>
# 		</table>
# 		"""
# 		section_description = section_description.replace("{{note_table_1}}", note_table_1)
# 		section_description = section_description.replace("{{note_table_2}}", note_table_2)
# 		return section_description
	
# 	def get_yearly_research_and_development_expenditure_note_data(self, section_description=""):
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_year_label.replace("Year Ended ", "").replace("/", "-")

# 		curr_ebe = frappe.get_value("FR Research and Development Expenditure Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, 'employee_benefits_expense') or 0
# 		curr_oe = frappe.get_value("FR Research and Development Expenditure Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, 'other_expenses') or 0
# 		curr_ppe = frappe.get_value("FR Research and Development Expenditure Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, 'property_plant_and_equipment') or 0
# 		curr_intangible = frappe.get_value("FR Research and Development Expenditure Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, 'intangible_assets') or 0

# 		prev_ebe = frappe.get_value("FR Research and Development Expenditure Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, 'employee_benefits_expense') or 0
# 		prev_oe = frappe.get_value("FR Research and Development Expenditure Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, 'other_expenses') or 0
# 		prev_ppe = frappe.get_value("FR Research and Development Expenditure Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, 'property_plant_and_equipment') or 0
# 		prev_intangible = frappe.get_value("FR Research and Development Expenditure Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, 'intangible_assets') or 0

# 		data = {
# 			"current": {
# 				"employee_benefits": curr_ebe,
# 				"other_expenses": curr_oe,
# 				"ppe": curr_ppe,
# 				"intangible": curr_intangible
# 			},
# 			"previous": {
# 				"employee_benefits": prev_ebe,
# 				"other_expenses": prev_oe,
# 				"ppe": prev_ppe,
# 				"intangible": prev_intangible
# 			}
# 		}

# 		total_current = sum(data["current"].values())
# 		total_previous = sum(data["previous"].values())

# 		html = f"""
# 		<table style="width:100%; margin-top: -30px; margin-bottom: -30px; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr>
# 					<th style="width: 60%; border:1px solid #000; padding:6px; text-align:left; font-weight:bold; color:#4472C4;">Particulars</th>
# 					<th style="border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">Year Ended<br>{current_date}</th>
# 					<th style="border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4;">Year Ended<br>{previous_date}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 				<tr>
# 					<td style="border:1px solid #000; border-bottom:none; padding:6px;"><strong>A. Revenue Expenditure</strong></td>
# 					<td style="border:1px solid #000; border-bottom:none; background-color:#E8F5E8;"></td>
# 					<td style="border:1px solid #000; border-bottom:none;"></td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-bottom:none; border-top:none; padding:6px;">Employee benefits expense</td>
# 					<td style="border:1px solid #000; border-bottom:none; border-top:none; padding:6px; text-align:right; background-color:#E8F5E8;">{data["current"]["employee_benefits"]:,}</td>
# 					<td style="border:1px solid #000; border-bottom:none; border-top:none; padding:6px; text-align:right;">{data["previous"]["employee_benefits"]:,}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-bottom:none; border-top:none; padding:6px;">Other Expenses (Includes Testing, Depreciation, Clinical Trial Expense,Consumables Stores, Insurance, Travel & Conveyance)</td>
# 					<td style="border:1px solid #000; border-bottom:none; border-top:none; padding:6px; text-align:right; background-color:#E8F5E8;">{data["current"]["other_expenses"]:,}</td>
# 					<td style="border:1px solid #000; border-bottom:none; border-top:none; padding:6px; text-align:right;">{data["previous"]["other_expenses"]:,}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-bottom:none; border-top:none; padding:6px;"><strong>B. Capital Expenditure</strong></td>
# 					<td style="border:1px solid #000; border-bottom:none; border-top:none; background-color:#E8F5E8;"></td>
# 					<td style="border:1px solid #000; border-bottom:none; border-top:none;"></td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-bottom:none; border-top:none; padding:6px;">Property, Plant and Equipment</td>
# 					<td style="border:1px solid #000; border-bottom:none; border-top:none; padding:6px; text-align:right; background-color:#E8F5E8;">{data["current"]["ppe"]:,}</td>
# 					<td style="border:1px solid #000; border-bottom:none; border-top:none; padding:6px; text-align:right;">{data["previous"]["ppe"]:,}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; padding:6px;">Intangible Assets (Including Intangible Assets under Development)</td>
# 					<td style="border:1px solid #000; border-top:none; padding:6px; text-align:right; background-color:#E8F5E8;">{data["current"]["intangible"]:,}</td>
# 					<td style="border:1px solid #000; border-top:none; padding:6px; text-align:right;">{data["previous"]["intangible"]:,}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; padding:6px;"><strong>Total</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right; background-color:#E8F5E8;"><strong>{total_current:,}</strong></td>
# 					<td style="border:1px solid #000; padding:6px; text-align:right;"><strong>{total_previous:,}</strong></td>
# 				</tr>
# 			</tbody>
# 		</table>
# 		"""

# 		return section_description.replace("{{note_table}}", html)

# 	def get_yearly_corporate_social_responsibility_note_data(self, section_description=""):
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_year_label.replace("Year Ended ", "").replace("/", "-")

# 		curr_open_short = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, 'shortfall_at_the_beginning_of_the_year') or 0
# 		curr_rts = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, 'amount_required_to_be_spent_by_the_company_during_the_year') or 0
# 		curr_spent = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, 'amount_of_expenditure_incurred') or 0
# 		curr_closing_short = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, 'shortfall_at_the_end_of_the_year') or 0
# 		curr_nature = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, 'nature_of_csr_activities') or ""
# 		curr_related_party = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, 'details_of_related_party_transactions') or ""
# 		curr_provision_movement = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, 'small_text_vucn') or ""

# 		prev_open_short = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, 'shortfall_at_the_beginning_of_the_year') or 0
# 		prev_rts = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, 'amount_required_to_be_spent_by_the_company_during_the_year') or 0
# 		prev_spent = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, 'amount_of_expenditure_incurred') or 0
# 		prev_closing_short = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, 'shortfall_at_the_end_of_the_year') or 0
# 		prev_nature = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, 'nature_of_csr_activities') or ""
# 		prev_related_party = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, 'details_of_related_party_transactions') or ""
# 		prev_provision_movement = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, 'small_text_vucn') or ""
		
# 		data = {
# 			"current": {
# 				"opening_shortfall": curr_open_short,
# 				"required_to_spend": curr_rts,
# 				"spent": curr_spent,
# 				"closing_shortfall": curr_closing_short,
# 				"nature": curr_nature,
# 				"related_party": curr_related_party,
# 				"provision_movement": curr_provision_movement
# 			},
# 			"previous": {
# 				"opening_shortfall": prev_open_short,
# 				"required_to_spend": prev_rts,
# 				"spent": prev_spent,
# 				"closing_shortfall": prev_closing_short,
# 				"nature": prev_nature,
# 				"related_party": prev_related_party,
# 				"provision_movement": prev_provision_movement
# 			}
# 		}

# 		html = f"""
# 		<table style="width:100%; margin-top: -30px; margin-bottom: -30px; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr>
# 					<th style="width: 60%; border:1px solid #000; padding:6px; text-align:left; font-weight:bold; color:#4472C4;">Particulars</th>
# 					<th style="border:1px solid #000; padding:6px; text-align:center; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">Year Ended<br>{current_date}</th>
# 					<th style="border:1px solid #000; padding:6px; text-align:center; font-weight:bold; color:#4472C4;">Year Ended<br>{previous_date}</th>
# 				</tr>
# 			</thead>
# 			<tbody>

# 				<tr>
# 					<td style="border:1px solid #000; border-bottom:none; padding:6px;">Shortfall at the beginning of the year</td>
# 					<td style="border:1px solid #000; border-bottom:none; padding:6px; text-align:center; background-color:#E8F5E8;">{data["current"]["opening_shortfall"]}</td>
# 					<td style="border:1px solid #000; border-bottom:none; padding:6px; text-align:center;">{data["previous"]["opening_shortfall"]}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Amount required to be spent by the company during the year</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{data["current"]["required_to_spend"]:,}</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{data["previous"]["required_to_spend"]:,}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Amount of expenditure incurred (including shortfall at the beginning of the year)</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right; background-color:#E8F5E8;">{data["current"]["spent"]:,}</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:right;">{data["previous"]["spent"]:,}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Shortfall at the end of the year</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:center; background-color:#E8F5E8;">{data["current"]["closing_shortfall"]}</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:center;">{data["previous"]["closing_shortfall"]}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Nature of CSR activities</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:center; background-color:#E8F5E8;">{data["current"]["nature"]}</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:center;">{data["previous"]["nature"]}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px;">Details of related party transactions, e.g., contribution to a trust controlled by the company in relation to CSR expenditure as per relevant Accounting Standard</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:center; background-color:#E8F5E8;">{data["current"]["related_party"]}</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; padding:6px; text-align:center;">{data["previous"]["related_party"]}</td>
# 				</tr>

# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; padding:6px;">Where a provision is made with respect to a liability incurred by entering into a contractual obligation, the movements in the provision during the year shall be shown separately</td>
# 					<td style="border:1px solid #000; border-top:none; padding:6px; text-align:center; background-color:#E8F5E8;">{data["current"]["provision_movement"]}</td>
# 					<td style="border:1px solid #000; border-top:none; padding:6px; text-align:center;">{data["previous"]["provision_movement"]}</td>
# 				</tr>

# 			</tbody>
# 		</table>
# 		"""

# 		return section_description.replace("{{note_table}}", html)

# 	def get_yearly_segmental_information_note_data(self, section_description=""):
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		current_year_label, previous_year_label = self.get_yearly_dates()
# 		current_date = current_year_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_year_label.replace("Year Ended ", "").replace("/", "-")

# 		def fmt(val):
# 			if val in (None, "-", 0):
# 				return "-"
# 			return f"{val:,.0f}"

# 		# current_sr_ind = frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, "sr_ind") or 0
# 		# previous_sr_ind = frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, "sr_ind") or 0
# 		# current_sr_row = frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, "sr_row") or 0
# 		# previous_sr_row = frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, "sr_row") or 0

# 		# current_ccsa_ind = frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, "ccsa_ind") or 0
# 		# previous_ccsa_ind = frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, "ccsa_ind") or 0
# 		# current_ccsa_row = frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, "ccsa_row") or 0
# 		# previous_ccsa_row = frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, "ccsa_row") or 0

# 		# current_ce_ind = frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, "ce_ind") or 0
# 		# previous_ce_ind = frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, "ce_ind") or 0
# 		# current_ce_row = frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, "ce_row") or 0
# 		# previous_ce_row = frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, "ce_row") or 0
# 		bs_template = next(
# 			d.section for d in self.get("financial_report_details", [])
# 			if d.section_type == "Balance Sheet"
# 		)	
# 		current_sr_ind = -self.get_sum_grouping_amount_yearly(company, "Revenue from Operations", "Domestic Sales", cls_month, self.fiscal_year) or 0
# 		previous_sr_ind = -self.get_sum_grouping_amount_yearly(company, "Revenue from Operations", "Domestic Sales", cls_month, self.previous_fiscal_year) or 0
# 		current_sr_row = -self.get_sum_grouping_amount_yearly(company, "Revenue from Operations", "Export Sales", cls_month, self.fiscal_year) or 0
# 		previous_sr_row = -self.get_sum_grouping_amount_yearly(company, "Revenue from Operations", "Export Sales", cls_month, self.previous_fiscal_year) or 0

# 		current_ccsa_row = flt(frappe.get_value("FR Account Receivable Entry", {'company': self.company, 'fiscal_year': self.fiscal_year, 'currency': ["!=", "INR"]}, "amount_in_lc")) + \
# 			flt(self.get_yearly_other_intangible_assets(field="curr_intangel_asset")) + flt(frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.fiscal_year, 'month': cls_month}, "ccsa_row"))
# 		curr_total = flt(self.get_bs_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Assets"}, 'name'), 'current_month_amount'))
# 		current_ccsa_ind = curr_total - current_ccsa_row

# 		previous_ccsa_row = flt(frappe.get_value("FR Account Receivable Entry", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'currency': ["!=", "INR"]}, "amount_in_lc")) + \
# 			flt(self.get_yearly_other_intangible_assets(field="intangel_asset")) + flt(frappe.get_value("FR Segmental Information Master", {'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'month': cls_month}, "ccsa_row"))
# 		prev_total = flt(self.get_bs_particular_data(frappe.get_value("FR Particular", {'particular_type': "Total Assets"}, 'name'), 'previous_year'))
# 		previous_ccsa_ind = prev_total - previous_ccsa_row

# 		current_ce_ind = flt(self.get_yearly_other_intangible_assets(field="curr_addition")) + flt(self.get_yearly_intangible_assets_under_development(field="curr_total")) + flt(self.get_yearly_capital_work_in_progress(field="curr_pre_total"))
# 		previous_ce_ind = flt(self.get_yearly_other_intangible_assets(field="prev_addition")) + flt(self.get_yearly_intangible_assets_under_development(field="prev_total")) + flt(self.get_yearly_capital_work_in_progress(field="prev_pre_total"))
# 		current_ce_row = previous_ce_row = 0
# 		data = {
# 			"Segment Revenue (Net)": {
# 				"India": (current_sr_ind, previous_sr_ind),
# 				"Rest of the world": (current_sr_row, previous_sr_row),
# 			},
# 			"Carrying Cost of Segment Asset": {
# 				"India": (current_ccsa_ind, previous_ccsa_ind),
# 				"Rest of the world": (current_ccsa_row, previous_ccsa_row),
# 			},
# 			"Capital Expenditure": {
# 				"India": (current_ce_ind, previous_ce_ind),
# 				"Rest of the world": (current_ce_row, previous_ce_row),
# 			},
# 		}

# 		html = f"""
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr>
# 					<th style="width: 60%; border:1px solid #000; padding:6px; font-weight:bold; color:#4472C4;">Particulars</th>
# 					<th style="border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4; background-color:#E8F5E8;">As at {current_date}</th>
# 					<th style="border:1px solid #000; padding:6px; text-align:right; font-weight:bold; color:#4472C4;">As at {previous_date}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		for section, rows in data.items():
# 			html += f"""
# 			<tr>
# 				<td style="border:1px solid #000; border-bottom:none;"><strong>{section}</strong></td>
# 				<td style="border:1px solid #000; border-bottom:none; background-color:#E8F5E8;"><strong></strong></td>
# 				<td style="border:1px solid #000; border-bottom:none;"><strong></strong></td>
# 			</tr>
# 			"""

# 			total_25 = 0
# 			total_24 = 0

# 			for name, (val_25, val_24) in rows.items():
# 				if isinstance(val_25, (int, float)):
# 					total_25 += val_25
# 				if isinstance(val_24, (int, float)):
# 					total_24 += val_24

# 				html += f"""
# 				<tr>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none;">{name}</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; text-align:right; background-color:#E8F5E8;">{fmt(val_25)}</td>
# 					<td style="border:1px solid #000; border-top:none; border-bottom:none; text-align:right;">{fmt(val_24)}</td>
# 				</tr>
# 				"""

# 			html += f"""
# 			<tr>
# 				<td style="border:1px solid #000;"><strong>Total</strong></td>
# 				<td style="border:1px solid #000; text-align:right; background-color:#E8F5E8;"><strong>{fmt(total_25)}</strong></td>
# 				<td style="border:1px solid #000; text-align:right;"><strong>{fmt(total_24)}</strong></td>
# 			</tr>
# 			"""

# 		html += """
# 			</tbody>
# 		</table>
# 		"""

# 		return section_description.replace("{{note_table}}", html)


# 	def get_yearly_finished_goods_and_wip(self, section_description="", total=False, field=None):
# 		rows = []
# 		add = lambda p, cy=0, py=0, st=False: rows.append({"p": p, "cy": cy, "py": py, "st": st})

# 		cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 		month_lbl, prev_year_lbl = self.get_yearly_dates()

# 		cur_total = prev_total = prev_prev_total = 0
# 		add("Inventories at the end of the year", st=True)

# 		def add_group(sec, label):
# 			nonlocal cur_total, prev_total
# 			cy = self.get_sum_grouping_amount(company, "Inventories", sec, cls_month, self.fiscal_year) or 0
# 			py = self.get_sum_grouping_amount(company, "Inventories", sec, cls_month, self.previous_fiscal_year) or 0
# 			add(label, cy, py)
# 			cur_total += cy; prev_total += py

# 			hgs = frappe.get_all(
# 				"GL Group Mapping",
# 				{"company": self.company, "primary_group": "Inventories", "secondary_group": sec, "higher_secondary_group": ["!=", None]},
# 				pluck="higher_secondary_group", distinct=True
# 			)

# 			for hg in hgs:
# 				cy_hg = self.get_sum_grouping_amount(company, "Inventories", sec, cls_month, self.fiscal_year, hg_sec_group=hg) or 0
# 				py_hg = self.get_sum_grouping_amount(company, "Inventories", sec, cls_month, self.previous_fiscal_year, hg_sec_group=hg) or 0
# 				add(f"  {hg}", cy_hg, py_hg)
# 			return cy, py

# 		cur_fg, py_fg = add_group("Finished Goods", "Finished goods")
# 		cur_wip, py_wip = add_group("Work in Progress", "Work-in-progress")
# 		cur_sit, py_sit = add_group("Stock In Trade", "Stock-in-trade")

# 		add("", cur_total, prev_total)

# 		add("Inventories at the beginning of the year", st=True)

# 		def add_prev_group(sec, label):
# 			nonlocal prev_prev_total
# 			py = self.get_sum_grouping_amount(company, "Inventories", sec, cls_month, self.previous_fiscal_year) or 0
# 			pp = self.sum_group_amt(company, "Inventories", sec, pre_year) or 0
# 			add(label, py, pp)
# 			prev_prev_total += pp
# 			return py, pp

# 		p_fg, pp_fg = add_prev_group("Finished Goods", "Finished goods")
# 		p_wip, pp_wip = add_prev_group("Work in Progress", "Work-in-progress")
# 		p_sit, pp_sit = add_prev_group("Stock In Trade", "Stock-in-trade")

# 		prev_year_opening = p_fg + p_wip + p_sit
# 		prev_prev_total = pp_fg + pp_wip + pp_sit

# 		net_increase = cur_total - prev_year_opening
# 		prev_year_net = prev_total - prev_prev_total

# 		add("", prev_year_opening, prev_prev_total)
# 		add("Net increase", net_increase, prev_year_net, st=True)

# 		if total:
# 			if field == "net_increase_total": return net_increase
# 			if field == "prev_year_amt": return prev_year_net
# 			return 0

# 		html = f'''
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr style="border-bottom:2px solid #222;">
# 					<th style="border:1px solid #222; color: #4472C4; text-align:left; width:40%; padding:6px 8px;"><b>Particulars</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>{month_lbl}</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>{prev_year_lbl}</b></th>
# 				</tr>
# 			</thead><tbody>
# 		'''

# 		for r in rows:
# 			b = "font-weight:bold;" if r["st"] else ""
# 			br = "border:1px solid #222; border-top:none; border-bottom:none;" if not r["st"] else "border:1px solid #222;"
# 			cy = round(r["cy"], self.show_decimal_value) if r["cy"] else ""
# 			py = round(r["py"], self.show_decimal_value) if r["py"] else ""
# 			html += f'''
# 			<tr>
# 				<td style="{br} text-align:left; padding:6px 8px; {b}">{r["p"]}</td>
# 				<td style="{br} text-align:right; padding:6px 8px; {b} background:#e8f5e8;">{cy}</td>
# 				<td style="{br} text-align:right; padding:6px 8px; {b}">{py}</td>
# 			</tr>
# 			'''
# 		html += '</tbody></table>'
# 		return section_description.replace("{{note_table}}", html)

# 	@frappe.whitelist()
# 	def get_yearly_purchases_of_stock_in_trade(self, section_description, total, field=None):
# 		cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 		default_currency = frappe.get_value("Company", self.company, 'default_currency')
# 		opening_stock = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", cls_month, self.previous_fiscal_year)
# 		closing_stock_current = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", cls_month, self.fiscal_year)

# 		purchases_current = (
# 			self.get_sum_grouping_amount(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", cls_month, self.fiscal_year)
# 			- self.get_yearly_finished_goods_and_wip("Cost of Materials Consumed", total=True, field='net_increase_total')
# 			+ (closing_stock_current - opening_stock)
# 		)

# 		closing_stock_pre_previous = self.sum_group_amt(company, "Inventories", "Raw Materials and Packing Material", pre_year)
# 		prev_year_closing_stock = self.sum_group_amt(company, "Inventories", "Raw Materials and Packing Material", self.previous_fiscal_year)

# 		closing_wip_pre_previous = (
# 			self.sum_group_amt(company, "Inventories", "Work in Progress", pre_year) + self.sum_group_amt(company, "Inventories", "Finished Goods", pre_year)
# 			+ self.sum_group_amt(company, "Inventories", "Stock In Trade", pre_year)
# 		)
# 		prev_year_closing_wip = (
# 			self.sum_group_amt(company, "Inventories", "Work in Progress", self.previous_fiscal_year) + self.sum_group_amt(company, "Inventories", "Finished Goods", self.previous_fiscal_year)
# 			+ self.sum_group_amt(company, "Inventories", "Stock In Trade", self.previous_fiscal_year)
# 		)

# 		prev_year_purchases = (
# 			self.sum_group_amt(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.previous_fiscal_year)
# 			+ (prev_year_closing_wip - closing_wip_pre_previous) + (prev_year_closing_stock - closing_stock_pre_previous)
# 		)

# 		if default_currency != self.currency:
# 			current_fx = self.get_fx_rate(default_currency, cls_month, self.fiscal_year, 'average_rate')
# 			prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'average_rate')
# 			purchases_current = round(purchases_current * current_fx, self.show_decimal_value) or 1
# 			prev_year_purchases = round(prev_year_purchases * prev_year_fx, self.show_decimal_value) or 1

# 		if total:
# 			if field == "purchases_current": return purchases_current
# 			if field == "prev_year_purchases": return prev_year_purchases

# 		data.append({"account": account, "current_month_amount": purchases_current, "previous_year": prev_year_purchases, "indent": indent, "is_bold": 0})
# 		table_data = self.monthly_table_for_note_template_1(data)
# 		return section_description.replace("{{note_table}}", table_data)


# 	def get_yearly_cost_of_material_consumed(self, section_description, total, field=None):
# 		rows = []
# 		cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 		default_currency = frappe.get_value("Company", self.company, 'default_currency')
# 		month_end_label, previous_fiscal_year_end_label = self.get_yearly_dates()

# 		# --- Current & Previous Month Stocks ---
# 		opening_stock = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", cls_month, self.previous_fiscal_year)
# 		closing_stock_current = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", cls_month, self.fiscal_year)

# 		# --- Purchases & SIT ---
# 		curr_month_purchase_sit = 0 if default_currency != "INR" else self.get_sum_grouping_amount(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.current_month, self.fiscal_year)
# 		prev_month_purchase_sit = 0 if default_currency != "INR" else self.get_sum_grouping_amount(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.previous_month, self.fiscal_year)

# 		purchases_current = (
# 			self.get_sum_grouping_amount(company, "Material consumed", "Cost of Goods Sold", cls_month, self.fiscal_year)
# 			- (0 if default_currency != "INR" else self.get_yearly_finished_goods_and_wip(total=True, field='net_increase_total'))
# 			+ (closing_stock_current - opening_stock)
# 			- curr_month_purchase_sit
# 		)

# 		# --- Cost of Materials Consumed ---
# 		cost_consumed_current = opening_stock + purchases_current - closing_stock_current
# 		closing_stock_pre_previous = self.sum_group_amt(company, "Inventories", "Raw Materials and Packing Material", pre_year)
# 		prev_year_closing_stock = self.sum_group_amt(company, "Inventories", "Raw Materials and Packing Material", self.previous_fiscal_year)

# 		closing_wip_pre_previous = (
# 			self.sum_group_amt(company, "Inventories", "Work in Progress", pre_year)
# 			+ self.sum_group_amt(company, "Inventories", "Finished Goods", pre_year)
# 			+ self.sum_group_amt(company, "Inventories", "Stock In Trade", pre_year)
# 		)
# 		prev_year_closing_wip = (
# 			self.sum_group_amt(company, "Inventories", "Work in Progress", self.previous_fiscal_year)
# 			+ self.sum_group_amt(company, "Inventories", "Finished Goods", self.previous_fiscal_year)
# 			+ self.sum_group_amt(company, "Inventories", "Stock In Trade", self.previous_fiscal_year)
# 		)

# 		pre_purchase_sit = 0 if default_currency != "INR" else self.sum_group_amt(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.previous_fiscal_year)
# 		prev_year_purchases = (
# 			self.sum_group_amt(company, "Material consumed", "Cost of Goods Sold", self.previous_fiscal_year)
# 			+ (0 if default_currency != "INR" else (prev_year_closing_wip - closing_wip_pre_previous))
# 			+ (prev_year_closing_stock - closing_stock_pre_previous)
# 			- pre_purchase_sit
# 		)

# 		prev_year_cost_consumed = closing_stock_pre_previous + prev_year_purchases - prev_year_closing_stock

# 		# --- Currency Conversion ---
# 		if default_currency != self.currency:
# 			current_fx = self.get_fx_rate(default_currency, cls_month, self.fiscal_year, 'average_rate')
# 			prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'average_rate')
# 			pre_prev_year_fx = self.get_fx_rate(default_currency, cls_month, pre_year, 'average_rate')

# 			# Apply conversion
# 			cost_consumed_current *= current_fx
# 			ftm_cost_consumed *= current_fx
# 			prev_year_cost_consumed *= prev_year_fx

# 			purchases_current *= current_fx
# 			closing_stock_current *= current_fx
# 			prev_year_purchases *= prev_year_fx
# 			closing_stock_pre_previous *= pre_prev_year_fx

# 		# --- If only returning totals ---
# 		if total:
# 			if field == 'cost_consumed_current':
# 				return cost_consumed_current
# 			elif field == 'ftm_cost_consumed':
# 				return ftm_cost_consumed
# 			elif field == 'prev_year_cost_consumed':
# 				return prev_year_cost_consumed
# 			else:
# 				return 0

# 		# --- Final Rows ---
# 		rows.extend([
# 			{"particulars": "Opening Stock","current_month_amt": opening_stock,"previous_year_amt": closing_stock_pre_previous,"is_subtotal": False},
# 			{"particulars": "Add: purchases & other related costs","current_month_amt": purchases_current,"previous_year_amt": prev_year_purchases,"is_subtotal": False},
# 			{"particulars": "Less: closing stock","current_month_amt": closing_stock_current,"previous_year_amt": opening_stock,"is_subtotal": False},
# 			{"particulars": "Cost of Materials Consumed","current_month_amt": cost_consumed_current,"previous_year_amt": prev_year_cost_consumed,"is_subtotal": True}
# 		])


# 		# Generate HTML table
# 		html = f'''
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr style = "border-bottom:2px solid #222;">
# 					<th style="border:1px solid #222; color: #4472C4; text-align:left; width:40%; padding:6px 8px;"><b>Particulars</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>{month_end_label}</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>{previous_fiscal_year_end_label}</b></th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		'''

# 		for row in rows:
# 			# Format amounts
# 			current_month_amt_str = round(row['current_month_amt'], self.show_decimal_value) if row['current_month_amt'] else "-"
# 			previous_year_amt = round(row['previous_year_amt'], self.show_decimal_value) if row['previous_year_amt'] else "-"
			
# 			# Style for totals
# 			bold_style = "border:1px solid #222; font-weight: bold;" if row["is_subtotal"] else ""
# 			border_style = "border:1px solid #222; border-top:none; border-bottom:none;"
			
# 			html += f'''
# 				<tr>
# 					<td style="{border_style} text-align:left; padding:6px 8px; {bold_style}">{row['particulars']}</td>
# 					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style} background-color:#e8f5e8;">{current_month_amt_str}</td>
# 					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{previous_year_amt}</td>
# 				</tr>
# 			'''
		
# 		html += "</tbody></table>"
# 		return section_description.replace("{{note_table}}", html)


# 	def get_yearly_borrowing_non_current_note_data(self, primary_group, total=False, field=None, section_description=""):
# 		"""Get yearly borrowing non-current note data with optimized structure"""
# 		rows = []
# 		total_current_month_amt = 0
# 		total_previous_year = 0
# 		month_end_label, previous_fiscal_year_end_label = self.get_yearly_dates()
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		secondary_groups = sorted(set(g for g in frappe.get_list("GL Group Mapping", {"primary_group": primary_group, "company": self.company}, pluck="secondary_group") if g))

# 		for secondary_group in secondary_groups:
# 			ind_as_description = frappe.get_value("Standalone Group", secondary_group, 'ind_as_description')
# 			html_particulars = f"<b>{secondary_group}</b><br>{ind_as_description or ''}"
			
# 			current_month_amt = self.get_sum_grouping_amount(company, primary_group, secondary_group, self.current_month, self.fiscal_year)
# 			previous_year = self.get_sum_grouping_amount(company, primary_group, secondary_group, cls_month, self.previous_fiscal_year)

# 			if current_month_amt < 0:
# 				current_month_amt = -current_month_amt
# 			if previous_year < 0:
# 				previous_year = -previous_year

# 			rows.append({
# 				"particulars": html_particulars,
# 				"current_month_amt": f"{current_month_amt:,.0f}" if current_month_amt else "-",
# 				"previous_year": f"{previous_year:,.0f}" if previous_year else "-",
# 				"group": False
# 			})

# 			total_current_month_amt += current_month_amt or 0
# 			total_previous_year += previous_year or 0

# 		if total:
# 			if field == "total_current_month_amt":
# 				return total_current_month_amt
# 			elif field == "total_previous_year":
# 				return total_previous_year
# 			else:
# 				return 0

# 		# HTML rendering with optimized structure
# 		html = f'''
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; margin-top: -25pt; border:1px solid #000;">
# 			<thead>
# 				<tr style = "border-bottom:2px solid #222;">
# 					<th style="border:1px solid #222; color: #4472C4; text-align:left; width:50%; padding:6px 8px;"><b>Particulars</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>{month_end_label}</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>{previous_fiscal_year_end_label}</b></th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		'''

# 		for row in rows:
# 			bold = "font-weight: bold;" if row.get("group") else ""
# 			html += f'''
# 				<tr>
# 					<td style="border:1px solid #222; border-top:none; border-bottom:none; text-align:left; padding:6px 8px; {bold}">{row['particulars']}</td>
# 					<td style="border:1px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; background-color:#e8f5e8;">{row['current_month_amt']}</td>
# 					<td style="border:1px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row['previous_year']}</td>
# 				</tr>
# 			'''

# 		# Append total row
# 		html += f'''
# 			<tr>
# 				<td style="border:1px solid #222; text-align:left; font-weight:bold; padding:6px 8px;">Total</td>
# 				<td style="border:1px solid #222; text-align:right; font-weight:bold; padding:6px 8px; background-color:#e8f5e8;">{total_current_month_amt:,.0f}</td>
# 				<td style="border:1px solid #222; text-align:right; font-weight:bold; padding:6px 8px;">{total_previous_year:,.0f}</td>
# 			</tr>
# 		'''
# 		html += "</tbody></table>"
# 		return section_description.replace("{{note_table}}", html)

# 	def update_yearly_foreign_exchange_in_profit_loss(self, for_exc_add_cur, for_exc_add_prev):
# 		data = self.get('financial_report_details', {'section_type': "Profit & Loss"})
# 		found_account = False

# 		if not data:
# 			return
# 		account = frappe.get_value("FR Particular", {'template_type': "Profit & Loss", 'type': "Foreign Exchange Difference"}, 'name')
# 		if not account:
# 			return

# 		table_data_str = data[0].table_data or "[]"
# 		try:
# 			table_data = json.loads(table_data_str)
# 		except (json.JSONDecodeError, TypeError):
# 			table_data = []
	
# 		for row in table_data:
# 			if row.get("id") == account:
# 				row["current_month_amount"] = round(for_exc_add_cur, self.show_decimal_value)
# 				row["previous_year"] = round(for_exc_add_prev, self.show_decimal_value)
# 				found_account = True
# 			elif found_account:
# 				is_total, is_sub = frappe.db.get_value("FR Particular",row.get("id"), ["is_total", "to_subtract"])
# 				if is_total:
# 					if not is_sub:
# 						row["current_month_amount"] = round((row.get("current_month_amount") or 0) + for_exc_add_cur,self.show_decimal_value)
# 						row["previous_year"] = round((row.get("previous_year") or 0) + for_exc_add_prev,self.show_decimal_value)
# 					else:
# 						row["current_month_amount"] = round((row.get("current_month_amount") or 0) - for_exc_add_cur,self.show_decimal_value)
# 						row["previous_year"] = round((row.get("previous_year") or 0) - for_exc_add_prev,self.show_decimal_value)

# 		data[0].table_data = json.dumps(table_data)
# 		_, data[0].section_description = self.render_yearly_profit_and_loss(data[0].section, table_data)

# 	def get_yearly_other_equity_note_data(self, current_year, previous_year, section_description="", total=False, field=None):
# 		"""Generate yearly Other Equity note table"""
# 		cls_month, pre_year = self.get_previous_year_cls_month(previous_year)
# 		month_end_label, prev_fy_label = self.get_yearly_dates()
# 		pnl_template = self.get("financial_report_details", {"section_type": "Profit & Loss"})[0].section
# 		bs_template = self.get("financial_report_details", {"section_type": "Balance Sheet"})[0].section
# 		net_cur, net_prev, net_prev_year = self.get_monthly_profit_and_loss_data(pnl_template, fetch_for_other_equity=True)
# 		default_currency = frappe.get_value("Company", self.company, "default_currency")
# 		cur_tot_asset = prev_tot_asset = cur_cur_liab = prev_cur_liab = cur_ncur_liab = prev_ncur_liab = cur_eq_share = prev_eq_share = 0

# 		if default_currency != self.currency:
# 			sp_prev_year = round(frappe.get_value("Other Equity Opening Entry", {"company": self.company, "fiscal_year": pre_year}, "share_premium_inr") or 0, self.show_decimal_value)
# 			bal_prev_year = round(frappe.get_value("Other Equity Opening Entry", {"company": self.company, "fiscal_year": pre_year}, "pl_inr") or 0, self.show_decimal_value)

# 			tot_asset = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account=frappe.get_value("FR Particular", {"particular_type": "Total Assets"}, "name"))
# 			tot_cur_liab = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account=frappe.get_value("FR Particular", {"particular_type": "Total Current Liabilities"}, "name"))
# 			tot_ncur_liab = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account=frappe.get_value("FR Particular", {"particular_type": "Total Non Current Liabilities"}, "name"))
# 			equity_share = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account=frappe.get_value("FR Particular", {"particular_type": "Equity Share Capital"}, "name"))

# 			cur_tot_asset, prev_tot_asset = tot_asset["current_month_amount"], tot_asset["previous_year"]
# 			cur_cur_liab, prev_cur_liab = tot_cur_liab["current_month_amount"], tot_cur_liab["previous_year"]
# 			cur_ncur_liab, prev_ncur_liab = tot_ncur_liab["current_month_amount"], tot_ncur_liab["previous_year"]
# 			cur_eq_share, prev_eq_share = equity_share["current_month_amount"], equity_share["previous_year"]
# 		else:
# 			sp_prev_year = abs(round(self.get_sum_grouping_amount(company, "Other Equity", "Other equity - Share Premium", cls_month, previous_year), self.show_decimal_value))
# 			bal_prev_year = -round(self.get_sum_grouping_amount(company, "Other Equity", "Other equity - Retained earnings", cls_month, previous_year), self.show_decimal_value)
# 			add_sp_prev_year = add_sp_cur = add_sp_prev = 0

# 		oci_prev_year = round(self.get_sum_grouping_amount(company, "OCI", "OCI", cls_month, previous_year), self.show_decimal_value)
# 		retained_prev_year = round(bal_prev_year + net_prev_year + oci_prev_year, self.show_decimal_value)

# 		oci_cur = round(self.get_sum_grouping_amount(company, "OCI", "OCI", cls_month, current_year), self.show_decimal_value)
# 		retained_cur = round(retained_prev_year + net_cur + oci_cur, self.show_decimal_value)
# 		retained_prev = round(retained_prev_year + net_prev, self.show_decimal_value)

# 		cc_open_prev = round(self.get_sum_grouping_amount(company, "Other Equity", "Other equity - Capital Contribution", cls_month, previous_year), self.show_decimal_value)
# 		cc_add_prev = round(self.get_sum_grouping_amount(company, "Other Equity", "Other equity - Capital Contribution", cls_month, previous_year), self.show_decimal_value) - cc_open_prev
# 		cc_close_prev = round(cc_open_prev + cc_add_prev, self.show_decimal_value)

# 		cc_add_cur = round(self.get_sum_grouping_amount(company, "Other Equity", "Other equity - Capital Contribution", cls_month, current_year), self.show_decimal_value) - cc_close_prev
# 		cc_close_cur = round(cc_close_prev + cc_add_cur, self.show_decimal_value)
# 		add_sp_prev_year = round(prev_tot_asset - (prev_cur_liab + prev_ncur_liab + prev_eq_share) - retained_prev_year - sp_prev_year, self.show_decimal_value)
# 		add_sp_cur = round(cur_tot_asset - (cur_cur_liab + cur_ncur_liab + cur_eq_share) - retained_cur - (sp_prev_year + add_sp_prev_year), self.show_decimal_value)
# 		add_sp_prev = round(prev_tot_asset - (prev_cur_liab + prev_ncur_liab + prev_eq_share) - retained_prev - (sp_prev_year + add_sp_prev_year), self.show_decimal_value)
		
# 		for_exc_open = for_exc_add_prev = for_exc_add_cur = 0
# 		if default_currency != self.currency:
# 			for_exc_open = round(prev_tot_asset - (prev_cur_liab + prev_ncur_liab + prev_eq_share) - retained_prev_year - sp_prev_year, self.show_decimal_value)
# 			for_exc_add_cur = round(cur_tot_asset - (cur_cur_liab + cur_ncur_liab + cur_eq_share) - retained_cur - (sp_prev_year), self.show_decimal_value)
# 			for_exc_add_prev = round(prev_tot_asset - (prev_cur_liab + prev_ncur_liab + prev_eq_share) - retained_prev - (sp_prev_year), self.show_decimal_value)
# 		else:
# 			for_exc_open = -round(self.get_sum_grouping_amount(company, "Other Equity", "Opening - Currency Fluctuation", cls_month, previous_year), self.show_decimal_value) 
# 			for_exc_add_prev = -round(self.get_sum_grouping_amount(company, "Other Equity", "Currency Fluctuation", cls_month, previous_year), self.show_decimal_value) 
# 			for_exc_add_cur = -round(self.get_sum_grouping_amount(company, "Other Equity", "Currency Fluctuation", cls_month, current_year), self.show_decimal_value)

		
# 		sp_open = round(sp_prev_year + add_sp_prev_year, self.show_decimal_value)
# 		sp_cur = round(sp_open + add_sp_cur, self.show_decimal_value)
# 		for_exc_prev_year = round(for_exc_open + for_exc_add_prev, self.show_decimal_value)
# 		for_exc_cur = round(for_exc_prev_year + for_exc_add_cur, self.show_decimal_value)

# 		grand_cur = round(retained_cur + cc_close_cur + sp_cur + for_exc_cur, self.show_decimal_value)
# 		grand_prev_year = round(retained_prev_year + cc_close_prev + sp_open + for_exc_prev_year, self.show_decimal_value)

# 		if total and field:
# 			if field == "grand_total_current":
# 				return grand_cur
# 			elif field == "grand_total_prev_year":
# 				return grand_prev_year
			
# 		rows = [
# 			("Securities premium account", "", "", True),
# 			("Balance as at the beginning of the year", sp_open, sp_prev_year, False),
# 			("Addition during the year", add_sp_cur, add_sp_prev_year, False),
# 			("Balance as at the end of the year", sp_cur, sp_open, True),

# 			("Surplus in Foreign Exchange Reserves", "", "", True),
# 			("Balance as at the beginning of the year", for_exc_prev_year, for_exc_open, False),
# 			("Addition during the year", for_exc_add_cur, for_exc_add_prev, False),
# 			("Balance as at the end of the year", for_exc_cur, for_exc_prev_year, True),

# 			("Retained earnings", "", "", True),
# 			("Balance as at the beginning of the year", retained_prev_year, bal_prev_year, False),
# 			("Net Profit for the year", net_cur, net_prev_year, False),
# 			("Other comprehensive income", oci_cur, oci_prev_year, False),
# 			("Balance as at the end of the year", retained_cur, retained_prev_year, True),

# 			("Capital Contribution", "", "", True),
# 			("Balance as at the beginning of the year", cc_close_prev, cc_open_prev, False),
# 			("Add: Equity contribution on financial guarantee taken", cc_add_cur, cc_add_prev, False),
# 			("Balance as at the end of the year", cc_close_cur, cc_close_prev, True),

# 			("Total", grand_cur, grand_prev_year, True),
# 		]
# 		if for_exc_add_cur or for_exc_add_prev:
# 			self.update_yearly_foreign_exchange_in_profit_loss(for_exc_add_cur, for_exc_add_prev)

# 		html = f"""
# 		<table style="width:100%; border-collapse:collapse; border-spacing:0; font-size:13px; border:1px solid #000; background-color:#fff;">
# 		<thead>
# 		<tr style="border-bottom:2px solid #222; background-color:#fff;">
# 			<th style="border-left:1px solid #222; color: #4472C4; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; width:60%; padding:6px 8px; background-color:#fff; text-align:left;"><b>Particulars</b></th>
# 			<th style="border-left:1px solid #222; color: #4472C4; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:6px 8px; background-color:#fff; text-align:center;"><b>{month_end_label}</b></th>
# 			<th style="border-left:1px solid #222; color: #4472C4; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:6px 8px; background-color:#fff; text-align:center;"><b>{prev_fy_label}</b></th>
# 		</tr>
# 		</thead><tbody>
# 		"""

# 		for i, (p, c, py, b) in enumerate(rows):
# 			style = "font-weight:bold;" if b else ""
# 			# Only vertical borders for regular rows, full borders for bold/total rows
# 			if b:
# 				border = "border-top:1px solid #222; border-bottom:1px solid #222;"
# 			else:
# 				border = "border-top:none; border-bottom:none;"
# 			html += f"""<tr style='background-color:#fff;'>
# 				<td style='{border} border-left:1px solid #222; border-right:1px solid #222; padding:6px 8px; text-align:left; background-color:#fff; {style}'>{p}</td>
# 				<td style='{border} border-left:1px solid #222; border-right:1px solid #222; padding:6px 8px; text-align:right; background-color:#E8F5E8; {style}'>{c}</td>
# 				<td style='{border} border-left:1px solid #222; border-right:1px solid #222; padding:6px 8px; text-align:right; background-color:#fff; {style}'>{py}</td></tr>"""

# 		html += "</tbody></table>"
# 		return section_description.replace("{{note_table}}", html)

# 	def get_yearly_investment_non_current_note_data(self, total=False, field=None, section_description=""):
# 		_, current_month_date = self.get_month_date_range(self.current_month, self.fiscal_year)
# 		total_current = total_previous_year = 0
# 		month_end_label, prev_fy_label = self.get_yearly_dates()
# 		prev_fs_year_start_date, prev_fs_year_end_date = self.previous_year_start_date, self.previous_year_ending_date
# 		curr_fs_year_start_date, curr_fs_year_end_date = self.current_year_start_date, self.current_year_ending_date

# 		data = [{
# 			"particulars": "Investment in equity Instruments of subsidiaries measured at Cost (Unquoted, Fully paid Up)",
# 			"face_value": "", "shares_current": "", "amount_current": "","shares_previous": "", "amount_previous": "","shares_previous_year": "", "amount_previous_year": "","bold": 1
# 		}]

# 		all_companies = set(frappe.get_list("FR Investment Entry",filters={"holding_company": self.company},pluck="company"))
# 		for company in all_companies:
# 			e_previous_year = self.fetch_equity_data(company, ["<=", prev_fs_year_end_date])
# 			e_current_month = self.fetch_equity_data(company, ["<=", current_month_date])

# 			e_previous_year = e_previous_year[0] if e_previous_year else {}
# 			e_current_month = e_current_month[0] if e_current_month else {}

# 			default_currency = frappe.get_value("Company", company, "default_currency")

# 			face_value = f"{e_current_month.get('face_value', 0)} {default_currency}"
# 			shares_current = e_current_month.get("no_of_shares", 0) or 0
# 			shares_previous_year = e_previous_year.get("no_of_shares", 0) or 0

# 			if self.currency != "INR":
# 				amount_current = e_current_month.get("investment_value_fc", 0) or 0
# 				amount_previous_year = e_previous_year.get("investment_value_fc", 0) or 0
# 			else:
# 				amount_current = e_current_month.get("investment_value", 0) or 0
# 				amount_previous_year = e_previous_year.get("investment_value", 0) or 0

# 			total_current += amount_current
# 			total_previous_year += amount_previous_year

# 			data.append({
# 				"particulars": company,
# 				"face_value": face_value,
# 				"shares_current": shares_current,
# 				"amount_current": amount_current,
# 				"shares_previous_year": shares_previous_year,
# 				"amount_previous_year": amount_previous_year,
# 				"bold": 0
# 			})

# 		if total:
# 			if field == "total_current":
# 				return total_current
# 			if field == "total_previous_year":
# 				return total_previous_year

# 		data.append({
# 			"particulars": "Total of Equity Instruments Measured at cost",
# 			"face_value": "",
# 			"shares_current": "",
# 			"amount_current": f"{total_current:,.0f}",
# 			"shares_previous_year": "",
# 			"amount_previous_year": f"{total_previous_year:,.0f}",
# 			"bold": 1
# 		})
		
# 		# HTML table
# 		table = f"""
# 		<table style="width:100%; border-collapse:collapse; font-size:12px; margin-top: 20px; border:1px solid #222;">
# 			<thead>
# 				<tr style="border-bottom:2px solid #222;">
# 					<th rowspan="2"style="border:1px solid #222; color:#4472C4; width:25%; text-align:left; padding:6px 8px;"><b>Particulars</b></th>
# 					<th rowspan="2"style="border:1px solid #222; color:#4472C4; width:10%; text-align:center;"><b>Face Value</b></th>
# 					<th colspan="2"style="border:1px solid #222; color:#4472C4; text-align:center;"><b>{month_end_label}</b></th>
# 					<th colspan="2"style="border:1px solid #222; color:#4472C4; text-align:center;"><b>{prev_fy_label}</b></th>
# 				</tr>
# 				<tr>
# 					<th style="border:1px solid #222; color:#4472C4; text-align:center;">No. of Shares</th>
# 					<th style="border:1px solid #222; color:#4472C4; text-align:center;">(₹ in lacs)</th>
# 					<th style="border:1px solid #222; color:#4472C4; text-align:center;">No. of Shares</th>
# 					<th style="border:1px solid #222; color:#4472C4; text-align:center;">(₹ in lacs)</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""


# 		for row in data:
# 			bold = "font-weight: bold;" if row["bold"] else ""

# 			table += f'''
# 			<tr style="background-color:#fff;">
# 				<td style="border:1px solid #222; padding:6px 8px; text-align:left; background-color:#fff; {bold}">{row["particulars"]}</td>
# 				<td style="border:1px solid #222; text-align:center; background-color:#fff;">{row["face_value"]}</td>
# 				<td style="border:1px solid #222; text-align:right; background-color:#fff;">{row["shares_current"]}</td>
# 				<td style="border:1px solid #222; text-align:right; background-color:#fff;">{row["amount_current"]}</td>
# 				<td style="border:1px solid #222; text-align:right; background-color:#fff;">{row["shares_previous_year"]}</td>
# 				<td style="border:1px solid #222; text-align:right; background-color:#fff;">{row["amount_previous_year"]}</td>
# 			</tr>
# 			'''

# 		table += "</tbody></table>"
# 		return table

# 	def get_yearly_trade_and_other_receivables_note_data(self, section_description=""):
# 		"""Get yearly trade and other receivables note data"""
# 		month_end_label, prev_fy_label = self.get_yearly_dates()
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		current_year_end_date = frappe.utils.formatdate(self.current_year_ending_date, "dd-MM-yyyy")
# 		previous_year_end_date = frappe.utils.formatdate(self.previous_year_ending_date, "dd-MM-yyyy")
# 		default_currency = frappe.get_value("Company", self.company, "default_currency")
# 		current_fx = self.get_fx_rate(default_currency, cls_month, self.fiscal_year, "closing_rate") if self.currency != default_currency else 1
# 		prev_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, "closing_rate") if self.currency != default_currency else 1

# 		# One-line calculations
# 		credit_impaired_cur = round((self.get_sum_grouping_amount(company, "Trade Receivables - credit Impaired", "Trade Receivables - credit Impaired", cls_month, self.fiscal_year) or 0) * current_fx, self.show_decimal_value)
# 		trade_recv_cur = round((self.get_sum_grouping_amount(company, "Trade Receivables", "Trade Receivables", cls_month, self.fiscal_year) or 0) * current_fx, self.show_decimal_value)
# 		other_recv_cur = round((self.get_sum_grouping_amount(company, "Trade Receivables", "Other Trade receivables", cls_month, self.fiscal_year) or 0) * current_fx, self.show_decimal_value)
# 		credit_impaired_prev = round((self.get_sum_grouping_amount(company, "Trade Receivables - credit Impaired", "Trade Receivables - credit Impaired", cls_month, self.previous_fiscal_year) or 0) * prev_fx, self.show_decimal_value)
# 		trade_recv_prev = round((self.get_sum_grouping_amount(company, "Trade Receivables", "Trade Receivables", cls_month, self.previous_fiscal_year) or 0) * prev_fx, self.show_decimal_value)
# 		other_recv_prev = round((self.get_sum_grouping_amount(company, "Trade Receivables", "Other Trade receivables", cls_month, self.previous_fiscal_year) or 0) * prev_fx, self.show_decimal_value)
# 		unsecured_good_cur = trade_recv_cur + credit_impaired_cur
# 		unsecured_good_prev = trade_recv_prev + credit_impaired_prev

# 		total_cur = unsecured_good_cur + other_recv_cur
# 		total_prev = unsecured_good_prev + other_recv_prev

# 		# (label, current, previous, bold)
# 		rows = [
# 			("Unsecured, considered good", unsecured_good_cur, unsecured_good_prev, False, 0),
# 			("Credit impaired", -credit_impaired_cur, credit_impaired_prev, False, 0),
# 			("", trade_recv_cur, trade_recv_prev, False, 1),
# 			("Less: Provision for credit impaired trade receivables", -credit_impaired_cur, credit_impaired_prev, False, 2),
# 			("Other receivables", "", "", True, 0),
# 			("Unsecured, considered good", other_recv_cur, other_recv_prev, False, 0),
# 			("Total", total_cur, total_prev, True, 0),
# 		]

# 		html = f"""
# 		<table style="width:100%; border-collapse:collapse; border-spacing:0; font-size:13px; margin-top:-25pt; border:1px solid #000;">
# 			<thead>
# 				<tr style="color: #4472C4; background-color: #E8F5E8;">
# 					<th style="border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; width:60%; padding:2px 5px; text-align:left;">Particulars</th>
# 					<th style="border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:2px 5px; text-align:center; background-color: #E8F5E8;">{month_end_label}</th>
# 					<th style="border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:2px 5px; text-align:center;">{prev_fy_label}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		for i, (label, cur, prev, bold, border_type) in enumerate(rows):
# 			style = "font-weight:bold;" if bold else ""
# 			last = i == len(rows) - 1
# 			# Only vertical borders for regular rows, full borders for last (Total) row
# 			if last:
# 				border = "border:1px solid #222;"
# 			elif border_type == 2:
# 				border = "border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:none;"
# 			else:
# 				border = "border-left:1px solid #222; border-right:1px solid #222; border-top:none; border-bottom:none;"

# 			if border_type == 1:
# 				short_border = "border-left: none; border-right: 1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222;"
# 			else:
# 				short_border = border

# 			html += f"""
# 			<tr style="line-height: 1; border:none;">
# 				<td style="{border} padding:2px 5px; text-align:left; {style}">{label}</td>
# 				<td style="{border} {short_border} padding:2px 5px; text-align:right; {style} background-color: #E8F5E8;">{cur}</td>
# 				<td style="{border} {short_border} padding:2px 5px; text-align:right; {style}">{prev}</td>
# 			</tr>
# 			"""

# 		html += "</tbody></table>"

# 		ageing_keys = ["Not Due", "0-6 Months", "6-12 Months", "1-2 Years", "2-3 Years", "More Than 3 Years"]
# 		def process_ageing(entries):
# 			undisputed_good = {k: 0 for k in ageing_keys}
# 			undisputed_doubtful = {k: 0 for k in ageing_keys}
# 			disputed_good = {k: 0 for k in ageing_keys}
# 			disputed_doubtful = {k: 0 for k in ageing_keys}

# 			for entry in entries:
# 				if not entry.ageing or entry.ageing not in ageing_keys:
# 					continue

# 				amount = flt(entry.amount_in_lc)
# 				provision_pct = flt(entry.provision_percentage)
# 				provision_amt = flt(entry.provision_amount)

# 				if entry.legal == "Yes":
# 					if provision_pct:
# 						disputed_good[entry.ageing] += amount - provision_amt
# 						disputed_doubtful[entry.ageing] += provision_amt
# 					else:
# 						disputed_good[entry.ageing] += amount
# 				else:
# 					if provision_pct:
# 						undisputed_good[entry.ageing] += amount - provision_amt
# 						undisputed_doubtful[entry.ageing] += provision_amt
# 					else:
# 						undisputed_good[entry.ageing] += amount

# 			return [
# 				{"label": "Undisputed Trade Receivables", "is_header": 1},
# 				{"label": "Considered Good", "data": undisputed_good},
# 				{"label": "Considered Doubtful", "data": undisputed_doubtful},

# 				{"label": "Disputed Trade Receivables", "is_header": 1},
# 				{"label": "Considered Good", "data": disputed_good},
# 				{"label": "Considered Doubtful", "data": disputed_doubtful},
# 			]

# 		def fmt_ageing_val(val):
# 			val = round(val / 100000, self.show_decimal_value)
# 			return frappe.utils.fmt_money(val, self.show_decimal_value) if val else "-"

# 		def render_table(rows):
# 			html = ""
# 			for row in rows:
# 				if row.get("is_header"):
# 					html += f"""
# 					<tr><td colspan="8" style="border:1px solid #222; padding:6px; font-weight:bold; background:#f2f2f2;">{row['label']}</td></tr>
# 					"""
# 					continue

# 				data = row.get("data", {})
# 				vals = [data.get(k, 0) for k in ageing_keys]
# 				total = sum(vals)

# 				formatted_vals = [fmt_ageing_val(v) for v in vals]
# 				total_fmt = fmt_ageing_val(total)
# 				html += f"""
# 				<tr>
# 					<td style="border:1px solid #222; padding:4px 5px; padding-left:15px;">{row['label']}</td>
# 					<td style="border:1px solid #222; text-align:right;">{formatted_vals[0]}</td>
# 					<td style="border:1px solid #222; text-align:right;">{formatted_vals[1]}</td>
# 					<td style="border:1px solid #222; text-align:right;">{formatted_vals[2]}</td>
# 					<td style="border:1px solid #222; text-align:right;">{formatted_vals[3]}</td>
# 					<td style="border:1px solid #222; text-align:right;">{formatted_vals[4]}</td>
# 					<td style="border:1px solid #222; text-align:right;">{formatted_vals[5]}</td>
# 					<td style="border:1px solid #222; text-align:right; font-weight:bold;">{total_fmt}</td>
# 				</tr>
# 				"""
# 			return html

# 		cur_entries = frappe.get_all(
# 			"FR Account Receivable Entry",
# 			filters={
# 				'company': self.company,'fiscal_year': self.fiscal_year,'report_type': 'Yearly'
# 			},
# 			fields=['ageing', 'legal', 'provision_percentage', 'provision_amount', 'amount_in_lc'],
# 			limit_page_length=0
# 		)

# 		cur_data = process_ageing(cur_entries)

# 		html += f"""
# 		<p style="margin-top: -15px"><b>Ageing for trade & other receivables outstanding as at {current_year_end_date}</b></p>
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000; margin-top: -30px">
# 		<thead>
# 		<tr>
# 		<th rowspan="2" style="border:1px solid #222;">Particulars</th>
# 		<th rowspan="2" style="border:1px solid #222;">Not Due</th>
# 		<th colspan="5" style="border:1px solid #222;">Outstanding as on {current_year_end_date}</th>
# 		<th rowspan="2" style="border:1px solid #222;">Total</th>
# 		</tr>
# 		<tr>
# 		<th style="border:1px solid #222;">0-6M</th>
# 		<th style="border:1px solid #222;">6M-1Y</th>
# 		<th style="border:1px solid #222;">1Y-2Y</th>
# 		<th style="border:1px solid #222;">2Y-3Y</th>
# 		<th style="border:1px solid #222;">&gt; 3Y</th>
# 		</tr>
# 		</thead>
# 		<tbody>
# 		{render_table(cur_data)}
# 		</tbody>
# 		</table>
# 		"""

# 		# ================= PREVIOUS YEAR =================
# 		prev_entries = frappe.get_all(
# 			"FR Account Receivable Entry",
# 			filters={
# 				'company': self.company,
# 				'fiscal_year': self.previous_fiscal_year,
# 				'report_type': 'Yearly'
# 			},
# 			fields=['ageing', 'legal', 'provision_percentage', 'provision_amount', 'amount_in_lc'],
# 			limit_page_length=0
# 		)

# 		prev_data = process_ageing(prev_entries)

# 		html += f"""
# 		<p style="margin-top: -15px"><b>Ageing for trade & other receivables outstanding as at {previous_year_end_date}</b></p>
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000; margin-top: -30px">
# 		<thead>
# 		<tr>
# 		<th rowspan="2" style="border:1px solid #222;">Particulars</th>
# 		<th rowspan="2" style="border:1px solid #222;">Not Due</th>
# 		<th colspan="5" style="border:1px solid #222;">Outstanding as on {previous_year_end_date}</th>
# 		<th rowspan="2" style="border:1px solid #222;">Total</th>
# 		</tr>
# 		<tr>
# 		<th style="border:1px solid #222;">&lt; 6M</th>
# 		<th style="border:1px solid #222;">6M-1Y</th>
# 		<th style="border:1px solid #222;">1Y-2Y</th>
# 		<th style="border:1px solid #222;">2Y-3Y</th>
# 		<th style="border:1px solid #222;">&gt; 3Y</th>
# 		</tr>
# 		</thead>
# 		<tbody>
# 		{render_table(prev_data)}
# 		</tbody>
# 		</table>
# 		"""

# 		return section_description.replace("{{note_table}}", html)
# 	def get_yearly_trade_payable_note_data(self, section_description=""):
# 		"""Get yearly trade and other receivables note data"""
# 		month_end_label, prev_fy_label = self.get_yearly_dates()
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")

# 		default_currency = frappe.get_value("Company", self.company, "default_currency")
# 		current_fx = self.get_fx_rate(default_currency, cls_month, self.fiscal_year, "closing_rate") if self.currency != default_currency else 1
# 		prev_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, "closing_rate") if self.currency != default_currency else 1

# 		msme_current = round(self.get_sum_grouping_amount(company, "Trade payables", "Dues of MSME", cls_month, self.fiscal_year) or 0,self.show_decimal_value)
# 		msme_previous = round(self.get_sum_grouping_amount(company, "Trade payables", "Dues of MSME", cls_month, self.previous_fiscal_year) or 0,self.show_decimal_value)

# 		creditor_current = round((self.get_sum_grouping_amount(company, "Trade payables", "Trade payables", cls_month, self.fiscal_year) or 0) +(self.get_sum_grouping_amount(company, "Trade payables", "Dues of Creditors Other Than MSME", cls_month, self.fiscal_year) or 0),self.show_decimal_value)
# 		creditor_previous = round((self.get_sum_grouping_amount(company, "Trade payables", "Dues of Creditors Other Than MSME", cls_month, self.previous_fiscal_year) or 0) +(self.get_sum_grouping_amount(company, "Trade payables", "Trade payables", cls_month, self.previous_fiscal_year) or 0),self.show_decimal_value)

# 		# (label, current, previous)
# 		rows = [
# 			("Total outstanding dues of micro enterprises and small enterprises", msme_current, msme_previous),
# 			("Total outstanding dues of creditors other than micro enterprises and small enterprises", creditor_current, creditor_previous),
# 			("Total", (msme_current + creditor_current), (msme_previous + creditor_previous))
# 		]


# 		html = f"""
# 		<table style="width:100%; border-collapse:collapse; border-spacing:0; font-size:13px; margin-top:-25pt; border:1px solid #000;">
# 			<thead>
# 				<tr style="color: #4472C4; background-color: #E8F5E8;">
# 					<th style="border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; width:60%; padding:2px 5px; text-align:left;">Particulars</th>
# 					<th style="border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:2px 5px; text-align:center; background-color: #E8F5E8;">{month_end_label}</th>
# 					<th style="border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:2px 5px; text-align:center;">{prev_fy_label}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		for i, (label, cur, prev) in enumerate(rows):
# 			last = i == len(rows) - 1
# 			style = "font-weight:bold;" if last else ""
# 			# Only vertical borders for regular rows, full borders for last (Total) row
# 			if last:
# 				border = "border:1px solid #222;"
# 			else:
# 				border = "border-left:1px solid #222; border-right:1px solid #222; border-top:none; border-bottom:none;"

# 			html += f"""
# 			<tr style="line-height: 1; border:none;">
# 				<td style="{border} padding:2px 5px; text-align:left; {style}">{label}</td>
# 				<td style="{border} padding:2px 5px; text-align:right; {style} background-color: #E8F5E8;">{cur}</td>
# 				<td style="{border} padding:2px 5px; text-align:right; {style}">{prev}</td>
# 			</tr>
# 			"""

# 		html += "</tbody></table>"

# 		html += f"""
# 		<p style="margin-top: -20px">Ageing for trade payables outstanding as at {month_end_label}</b></p>
# 		<table style="width:100%; border-collapse:collapse; border-spacing:0; font-size:13px; border:1px solid #000; margin-top: -20px">
# 			<thead>
# 				<tr style="color: #00008B;">
# 					<th rowspan="2" style="border:1px solid #222; width:15%; padding:4px 5px; text-align:center;">Particulars</th>
# 					<th rowspan="2" style="border:1px solid #222; width:12%; padding:4px 5px; text-align:center; background-color:#D5F5D5 !important;">Not Due</th>
# 					<th colspan="4" style="border:1px solid #222; padding:4px 5px; text-align:center; background-color:#D5F5D5 !important;">Outstanding for following periods from due date of payment</th>
# 					<th rowspan="2" style="border:1px solid #222; width:15%; padding:4px 5px; text-align:center; background-color:#D5F5D5 !important;">Total</th>
# 				</tr>
# 				<tr>
# 					<th style="border:1px solid #222; padding:4px 5px; text-align:center;background-color: #D5F5D5 !important;">Less than 1 Year</th>
# 					<th style="border:1px solid #222; padding:4px 5px; text-align:center;background-color: #D5F5D5 !important;">1-2 Year</th>
# 					<th style="border:1px solid #222; padding:4px 5px; text-align:center;background-color: #D5F5D5 !important;">2-3 Year</th>
# 					<th style="border:1px solid #222; padding:4px 5px; text-align:center;background-color: #D5F5D5 !important;">More than 3 Year</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		pay_ageing_keys = ["Not Due", "0-6 Months", "6-12 Months", "1-2 Years", "2-3 Years", "More Than 3 Years"]
# 		pay_display_keys = ["Not Due", "Less than 1 Year", "1-2 Year", "2-3 Year", "More than 3 Year"]
# 		msme_undisputed = {k: 0 for k in pay_display_keys}
# 		others_undisputed = {k: 0 for k in pay_display_keys}
# 		msme_disputed = {k: 0 for k in pay_display_keys}
# 		others_disputed = {k: 0 for k in pay_display_keys}

# 		pay_ageing_map = {
# 			"Not Due": "Not Due",
# 			"0-6 Months": "Less than 1 Year",
# 			"6-12 Months": "Less than 1 Year",
# 			"1-2 Years": "1-2 Year",
# 			"2-3 Years": "2-3 Year",
# 			"More Than 3 Years": "More than 3 Year",
# 		}

# 		cur_pay_entries = frappe.get_all("FR Account Payable Entry",
# 			filters={'company': self.company, 'fiscal_year': self.fiscal_year, 'report_type': 'Yearly'},
# 			fields=['ageing', 'msme_vendor', 'legal', 'amount_in_lc'],
# 			limit_page_length=0
# 		)

# 		for entry in cur_pay_entries:
# 			if not entry.ageing or entry.ageing not in pay_ageing_keys:
# 				continue
# 			amount = flt(entry.amount_in_lc)
# 			display_key = pay_ageing_map[entry.ageing]

# 			if entry.legal == "Yes":
# 				if entry.msme_vendor == "Yes":
# 					msme_disputed[display_key] += amount
# 				else:
# 					others_disputed[display_key] += amount
# 			else:
# 				if entry.msme_vendor == "Yes":
# 					msme_undisputed[display_key] += amount
# 				else:
# 					others_undisputed[display_key] += amount

# 		def fmt_pay_ageing_val(val):
# 			val = round(val / 100000, self.show_decimal_value)
# 			return frappe.utils.fmt_money(val, self.show_decimal_value) if val else "-"

# 		pay_ageing_rows = []
# 		for label, data in [
# 			("MSME", msme_undisputed),
# 			("Others", others_undisputed),
# 			("Disputed dues-MSME", msme_disputed),
# 			("Disputed dues-Others", others_disputed),
# 		]:
# 			vals = [data[k] for k in pay_display_keys]
# 			row_total = sum(vals)
# 			pay_ageing_rows.append((label,) + tuple(fmt_pay_ageing_val(v) for v in vals) + (fmt_pay_ageing_val(row_total),))

# 		for label, not_due, lt1y, y1_2, y2_3, mt3, total in pay_ageing_rows:
# 			html += f"""
# 			<tr style="line-height:1.4;">
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:left;">{label}</td>
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:right;background-color: #D5F5D5 !important;">{not_due}</td>
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:right;background-color: #D5F5D5 !important;">{lt1y}</td>
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:right;background-color: #D5F5D5 !important;">{y1_2}</td>
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:right;background-color: #D5F5D5 !important;">{y2_3}</td>
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:right;background-color: #D5F5D5 !important;">{mt3}</td>
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:right;background-color: #D5F5D5 !important;">{total}</td>
# 			</tr>
# 			"""

# 		html += "</tbody></table>"

# 		#previous year
# 		html += f"""
# 		<p style="margin-top: -20px">Ageing for trade payables outstanding as at {prev_fy_label}</b></p>
# 		<table style="width:100%; border-collapse:collapse; border-spacing:0; font-size:13px; border:1px solid #000; margin-top: -20px">
# 			<thead>
# 				<tr style="color: #00008B;">
# 					<th rowspan="2" style="border:1px solid #222; width:15%; padding:4px 5px; text-align:center;">Particulars</th>
# 					<th rowspan="2" style="border:1px solid #222; width:12%; padding:4px 5px; text-align:center;">Not Due</th>
# 					<th colspan="4" style="border:1px solid #222; padding:4px 5px; text-align:center; ">Outstanding for following periods from due date of payment</th>
# 					<th rowspan="2" style="border:1px solid #222; width:15%; padding:4px 5px; text-align:center;">Total</th>
# 				</tr>
# 				<tr>
# 					<th style="border:1px solid #222; padding:4px 5px; text-align:center;">Less than 1 Year</th>
# 					<th style="border:1px solid #222; padding:4px 5px; text-align:center;">1-2 Year</th>
# 					<th style="border:1px solid #222; padding:4px 5px; text-align:center;">2-3 Year</th>
# 					<th style="border:1px solid #222; padding:4px 5px; text-align:center;">More than 3 Year</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		prev_msme_undisputed = {k: 0 for k in pay_display_keys}
# 		prev_others_undisputed = {k: 0 for k in pay_display_keys}
# 		prev_msme_disputed = {k: 0 for k in pay_display_keys}
# 		prev_others_disputed = {k: 0 for k in pay_display_keys}

# 		prev_pay_entries = frappe.get_all("FR Account Payable Entry",
# 			filters={'company': self.company, 'fiscal_year': self.previous_fiscal_year, 'report_type': 'Yearly'},
# 			fields=['ageing', 'msme_vendor', 'legal', 'amount_in_lc'],
# 			limit_page_length=0
# 		)

# 		for entry in prev_pay_entries:
# 			if not entry.ageing or entry.ageing not in pay_ageing_keys:
# 				continue
# 			amount = flt(entry.amount_in_lc)
# 			display_key = pay_ageing_map[entry.ageing]

# 			if entry.legal == "Yes":
# 				if entry.msme_vendor == "Yes":
# 					prev_msme_disputed[display_key] += amount
# 				else:
# 					prev_others_disputed[display_key] += amount
# 			else:
# 				if entry.msme_vendor == "Yes":
# 					prev_msme_undisputed[display_key] += amount
# 				else:
# 					prev_others_undisputed[display_key] += amount

# 		prev_pay_ageing_rows = []
# 		for label, data in [
# 			("MSME", prev_msme_undisputed),
# 			("Others", prev_others_undisputed),
# 			("Disputed dues-MSME", prev_msme_disputed),
# 			("Disputed dues-Others", prev_others_disputed),
# 		]:
# 			vals = [data[k] for k in pay_display_keys]
# 			row_total = sum(vals)
# 			prev_pay_ageing_rows.append((label,) + tuple(fmt_pay_ageing_val(v) for v in vals) + (fmt_pay_ageing_val(row_total),))

# 		for label, not_due, lt1y, y1_2, y2_3, mt3, total in prev_pay_ageing_rows:
# 			html += f"""
# 			<tr style="line-height:1.4;">
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:left;">{label}</td>
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:right;">{not_due}</td>
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:right;">{lt1y}</td>
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:right;">{y1_2}</td>
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:right;">{y2_3}</td>
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:right;">{mt3}</td>
# 				<td style="border:1px solid #222; padding:2px 5px; text-align:right;">{total}</td>
# 			</tr>
# 			"""

# 		html += "</tbody></table>"
# 		return section_description.replace("{{note_table}}", html)

# 	@frappe.whitelist()
# 	def get_yearly_consolidation_note_data(self, primary_group):
# 		self._init_report_caches()
# 		data = []
# 		group_info = self._get_cached_standalone_group(primary_group)
# 		show_reversed_value = group_info.show_reversed_value
# 		group_type = group_info.group_type
# 		def format_amount(val):
# 			return flt(-val if show_reversed_value and val < 0 else val or 0)

# 		def append_data(account, cm, py, indent=0, is_bold=0):
# 			data.append({"account": account, "current_year": format_amount(cm), "previous_year": format_amount(py), "indent": indent, "is_bold": is_bold})

# 		cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 		default_currency = self._default_currency

# 		if primary_group == "Purchases of Stock in Trade" and default_currency != "INR":
# 			cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 			opening_stock = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", cls_month, self.previous_fiscal_year)
# 			closing_stock_current = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", cls_month, self.fiscal_year)
# 			closing_stock_pre_previous = self.sum_group_amt(company, "Inventories", "Raw Materials and Packing Material", pre_year)
# 			prev_year_closing_stock = self.sum_group_amt(company, "Inventories", "Raw Materials and Packing Material", self.previous_fiscal_year)

# 			purchases_current = (
# 				self.get_sum_grouping_amount(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", cls_month, self.fiscal_year)
# 				- self.get_yearly_finished_goods_and_wip(total=True, field='net_increase_total') + (closing_stock_current - opening_stock)
# 			)
# 			closing_wip_pre_previous = (
# 				self.sum_group_amt(company, "Inventories", "Work in Progress", pre_year) + self.sum_group_amt(company, "Inventories", "Finished Goods", pre_year) + self.sum_group_amt(company, "Inventories", "Stock In Trade", pre_year)
# 			)
# 			prev_year_closing_wip = (
# 				self.sum_group_amt(company, "Inventories", "Work in Progress", self.previous_fiscal_year) + self.sum_group_amt(company, "Inventories", "Finished Goods", self.previous_fiscal_year) + self.sum_group_amt(company, "Inventories", "Stock In Trade", self.previous_fiscal_year)
# 			)
# 			prev_year_purchases = (
# 				self.sum_group_amt(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.previous_fiscal_year)
# 				+ (prev_year_closing_wip - closing_wip_pre_previous) + (prev_year_closing_stock - closing_stock_pre_previous)
# 			)

# 			# --- Currency Conversion for Purchases of Stock in Trade ---
# 			if default_currency != self.currency:
# 				current_fx = self.get_fx_rate(default_currency, cls_month, self.fiscal_year, 'average_rate')
# 				prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'average_rate')
# 				purchases_current = round(purchases_current * current_fx, self.show_decimal_value)
# 				prev_year_purchases = round(prev_year_purchases * prev_year_fx, self.show_decimal_value)

# 			append_data(primary_group, purchases_current, round(prev_year_purchases, self.show_decimal_value))
# 		else:
# 			if group_type in ("Other Income", "Other Expense"):
# 				primary_groups = frappe.get_list("Standalone Group",filters={"is_primary_group": 1, "group_type": ["in", ["Other Income", "Other Expense"]]},pluck="name")
# 			else:
# 				primary_groups = [primary_group]
			
# 			for primary_group in primary_groups:
# 				secondary_groups = frappe.db.get_list("GL Group Mapping", {"primary_group": ["in", primary_group], "company": self.company, "report_type": self.report_type}, pluck="secondary_group")
# 				secondary_groups = sorted(set(filter(None, secondary_groups)))
# 				custom_order = frappe.db.get_value("Schedule Reorder",{"primary_group": primary_group},"name")
# 				if custom_order:
# 					ordered_rows = frappe.get_all("Schedule Reorder Details",filters={"parent": custom_order},fields=["standalone_group"],order_by="idx asc")
# 					ordered_groups = [r.standalone_group for r in ordered_rows if r.standalone_group]
# 					secondary_consolidation_groups = [g for g in ordered_groups if g in secondary_groups]
# 					missing_groups = [g for g in secondary_groups if g not in ordered_groups]
# 					secondary_consolidation_groups.extend(sorted(missing_groups))
# 				else:
# 					secondary_consolidation_groups = secondary_groups

# 				sg_info = self._get_cached_standalone_group(primary_group)
# 				report_type = sg_info.report_type if sg_info else None
# 				default_currency = self._default_currency
# 				cls_month = self._closing_month
# 				if default_currency != self.currency:
# 					if report_type == "Balance Sheet":
# 						field_name = 'closing_rate'
# 					elif report_type == "Profit & Loss":
# 						field_name = 'average_rate'
# 					else:
# 						field_name = None
# 				else:
# 					field_name = None

# 				current_fx = self.get_fx_rate(default_currency, cls_month, self.fiscal_year, field_name) if field_name else 1
# 				prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, field_name) if field_name else 1

# 				for sec in secondary_consolidation_groups:
# 					cm = self.get_sum_grouping_amount(company, primary_group, sec, cls_month, self.fiscal_year) * current_fx
# 					py = self.get_sum_grouping_amount(company, primary_group, sec, cls_month, self.previous_fiscal_year) * prev_year_fx
# 					has_hg_sec_group = self._get_cached_hg_sec_groups(company, primary_group, sec)

# 					if group_type in ("Other Income", "Other Expense"):
# 						if group_type == "Other Income":
# 							cm = cm if cm < 0 else 0
# 							py = py if py < 0 else 0
# 						elif group_type == "Other Expense":
# 							cm = cm if cm > 0 else 0
# 							py = py if py > 0 else 0

# 						if any(val != 0 for val in (cm, py)):
# 							append_data(sec, cm, py)
# 					else:
# 						if any(val != 0 for val in (cm, py)) or has_hg_sec_group:
# 							append_data(sec, cm, py, is_bold=1 if has_hg_sec_group else 0)

# 					for hg_sec in has_hg_sec_group:
# 						cm = self.get_sum_grouping_amount(company, primary_group, sec, cls_month, self.fiscal_year, hg_sec_group=hg_sec) * current_fx
# 						py = self.get_sum_grouping_amount(company, primary_group, sec, cls_month, self.previous_fiscal_year, hg_sec_group=hg_sec) * prev_year_fx

# 						if any(val != 0 for val in (cm, py)):
# 							append_data(hg_sec, cm, py, indent = 1)

# 		return data
	
# 	def yearly_table_for_note_template(self, data, section_description=""):
# 		current_year_date, previous_year_date = self.get_current_and_prevous_year_date()

# 		note_table = f'''
# 		<table style="width:100%; border-collapse:collapse; border-spacing:0; font-size:13px; margin-top: -25pt; border:1px solid #000; background-color:#fff;">
# 			<thead>
# 				<tr style="color: #4472C4; background-color:#fff;">
# 					<th style='border:1px solid #222; text-align:left; padding: 2px 5px; width: 60%; background-color:#fff;'>Particulars</th>
# 					<th style='border:1px solid #222; text-align:center; padding: 2px 5px; width: 20%; background-color:#fff;'>{current_year_date}</th>
# 					<th style='border:1px solid #222; text-align:center; padding: 2px 5px; width: 20%; background-color:#fff;'>{previous_year_date}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		'''

# 		total_current_month = 0
# 		total_previous_year = 0
# 		for i, row in enumerate(data):
# 			indent = "&nbsp;" * (int(row.get("indent", 0)) * 4)
# 			bold = "font-weight: bold;" if row.get("is_bold") else ""
# 			current_month_amount = row.get('current_year') or 0
# 			previous_year = row.get('previous_year') or 0
# 			total_current_month += current_month_amount
# 			total_previous_year += previous_year
# 			top_border = "border-top:1px solid #222;" if i==0 else "border-top: none;"

# 			note_table += f'''
# 			<tr style="line-height: 1; border:none;">
# 				<td style='text-align:left; padding: 2px 5px; border-left:1px solid #222; border-right:1px solid #222; border-bottom:none; {top_border} {bold}'>{indent}{row.get("account") or ""}</td>
# 				<td style='text-align:right; padding: 2px 5px; border-left:1px solid #222; border-right:1px solid #222; border-bottom:none; background-color: #e8f5e8; {top_border} {bold}'>{current_month_amount if current_month_amount else 0}</td>
# 				<td style='text-align:right; padding: 2px 5px; border-left:1px solid #222; border-right:1px solid #222; border-bottom:none; {top_border} {bold}'>{previous_year if previous_year else 0}</td>
# 			</tr>
# 			'''
# 		# Add total row as footer
# 		note_table += f'''
# 			<tr style="line-height: 1;">
# 				<td style='text-align:left; padding: 2px 5px; border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:1px solid #222; font-weight: bold;'>Total</td>
# 				<td style='text-align:right; padding: 2px 5px; border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:1px solid #222; font-weight: bold; background-color: #e8f5e8;'>{round(total_current_month, self.show_decimal_value)}</td>
# 				<td style='text-align:right; padding: 2px 5px; border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:1px solid #222; font-weight: bold;'>{round(total_previous_year, self.show_decimal_value)}</td>
# 			</tr>
# 		'''
# 		note_table += "</tbody></table>"
# 		return section_description.replace("{{note_table}}", note_table)
	
# 	def render_yearly_balance_sheet(self, template_name):
# 		"""Render yearly balance sheet with note-style UI"""
# 		data = self.get_yearly_balance_sheet_data(template_name)
# 		month_end_label, previous_fiscal_year_end_label = self.get_yearly_dates()

# 		html = f"""
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; margin-top: -25pt; border:1px solid #000; background-color:#fff;">
# 			<thead>
# 				<tr style="color: #4472C4; border-bottom:2px solid #222; background-color:#fff;">
# 					<th colspan="2" style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:left; padding: 5px; width: 45%; background-color:#fff;'>Particulars</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; width: 10%; background-color:#fff;'>Note No.</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; width: 15%; background-color:#fff;'>{month_end_label}</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; width: 10%; background-color:#fff;'>{previous_fiscal_year_end_label}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		# Counters for structured index generation
# 		header_counter = 0
# 		group_counter = 0
# 		group_stack = [{'alpha_counter': 0, 'roman_counter': 0, 'indent': 0, 'last_indent_1': None}]

# 		# Helpers for indices
# 		def to_alpha(idx): return f"({chr(65+idx)})"
# 		def to_roman(idx): return f"({['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX'][idx]})"
# 		def to_lower_alpha(idx): return f"({chr(97+idx)})"
# 		def to_lower_roman(idx): return f"({['i','ii','iii','iv','v','vi','vii','viii','ix','x','xi','xii','xiii','xiv','xv','xvi','xvii','xviii','xix','xx'][idx]})"

# 		for row in data:
# 			indent_val = int(row.get("indent", 0))
# 			indent = "&nbsp;" * (indent_val * 4)
# 			bold = "font-weight: bold;" if row.get("is_bold") else ""
# 			account_label = row.get("account") or ""
# 			note_no = row.get("note_no")
# 			schedule = row.get("schedule")
# 			index = ""
			
# 			# Section Headers
# 			if row.get("header"):
# 				index = to_alpha(header_counter)
# 				header_counter += 1
# 				group_stack = [{'alpha_counter': 0, 'roman_counter': 0, 'indent': 0, 'last_indent_1': None}]
# 			elif row.get("group"):
# 				index = to_roman(group_counter)
# 				group_counter += 1
# 				group_stack.append({'alpha_counter': 0, 'roman_counter': 0, 'indent': indent_val, 'last_indent_1': None})
# 			elif not row.get("is_bold"):
# 				if indent_val == 0:
# 					alpha_idx = group_stack[-1]['alpha_counter']
# 					account_label = f"{to_lower_alpha(alpha_idx)} {account_label}"
# 					group_stack[-1]['alpha_counter'] += 1
# 				elif indent_val == 1:
# 					if group_stack[-1]['last_indent_1'] != 1:
# 						group_stack[-1]['roman_counter'] = 0
# 					roman_idx = group_stack[-1]['roman_counter']
# 					account_label = f"{to_lower_roman(roman_idx)} {account_label}"
# 					group_stack[-1]['roman_counter'] += 1
# 					group_stack[-1]['last_indent_1'] = 1
# 				else:
# 					group_stack[-1]['last_indent_1'] = indent_val

# 			# Add data-schedule attribute and clickable styling for account rows
# 			schedule_attr = f' data-schedule="{note_no}"' if note_no else ""
# 			clickable_style = "cursor: pointer;" if note_no else ""
			
# 			# Add anchor link if schedule exists
# 			account_text = account_label
# 			if schedule and note_no:
# 				note_id = self.generate_note_id(note_no, account_label)
# 				account_text = f'<a href="#{note_id}" style="color: #000000;">{account_label}</a>'

# 			# Final row - only vertical borders for regular rows, add horizontal border for sub-total (bold) rows
# 			horizontal_border = "border-top:1px solid #222; border-bottom:1px solid #222;" if row.get("is_bold") and not row.get("header") and not row.get("group") else ""
# 			html += f"""
# 			<tr{schedule_attr} class="clickable-row" style="{clickable_style} line-height: 1;">
# 				<td style='text-align:center; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {bold}'>{index}</td>
# 				<td style='text-align:left; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {bold}'>{indent}{account_text}</td>
# 				<td style='text-align:center; padding: 2px; border-left:1px solid #222; border-right:1px solid #222 '>{note_no or ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} background-color: #e8f5e8; {bold}'>{row.get("current_month_amount", 0) if row.get("current_month_amount") else ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} {bold}'>{row.get("previous_year", 0) if row.get("previous_year") else ""}</td>
# 			</tr>
# 			"""

# 		html += "</tbody></table>"
# 		return json.dumps(data), html

# 	def get_yearly_balance_sheet_data(self, template_name, for_other_equity=False, account=None, field=""):
# 		"""Get yearly balance sheet data with current year, previous year, and FTY amounts"""
# 		self._init_report_caches()
# 		balance_sheet_doc = frappe.get_doc("Balance Sheet Template", template_name)
# 		amount_cache = {}
# 		default_currency = self._default_currency

# 		get_fr_particular = self._get_cached_fr_particular
# 		get_fr_section = self._get_cached_fr_section
# 		get_standalone_group = self._get_cached_standalone_group
# 		get_secondary_groups = self._get_cached_secondary_groups

# 		def get_grouped_gl_amount(gl_accounts, year, month=None):
# 			if not gl_accounts:
# 				return 0
# 			placeholders = ','.join(['%s'] * len(gl_accounts))
# 			erp_type = self.get_erp_type()

# 			if erp_type == "ERPNext":
# 				if month:
# 					start_date, end_date = self.get_month_date_range(month, year)
# 					if not start_date: return 0
# 					query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN ({placeholders})"
# 					params = [self.company, start_date, end_date] + gl_accounts
# 				else:
# 					fy_start, fy_end = self.get_fiscal_year_dates(year)
# 					if not fy_start: return 0
# 					query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN ({placeholders})"
# 					params = [self.company, fy_start, fy_end] + gl_accounts
# 			else:
# 				query = f"""
# 					SELECT SUM(uploaded_amount) FROM `tabFR Trial Balance Entry`
# 					WHERE company=%s AND fiscal_year=%s AND gl_account IN ({placeholders})
# 				"""
# 				params = [self.company, year] + gl_accounts
# 				if month:
# 					query += " AND month=%s"
# 					params.append(month)
# 			return (frappe.db.sql(query, params)[0][0] or 0) / 100000

# 		def calc_amount_for_particular_monthly(particular_name, month, year, is_current=False, is_yearly=False, fx_rate=1, convert=True):
# 			cache_key = (particular_name, month, year, fx_rate)
# 			if cache_key in amount_cache:
# 				return amount_cache[cache_key]

# 			fr_particular = get_fr_particular(particular_name)
# 			amount = 0

# 			if fr_particular.is_total:
# 				for p in fr_particular.get("particulars", []):
# 					amount += calc_amount_for_particular_monthly(p.particular, month, year, is_current, is_yearly, fx_rate, convert)

# 			elif fr_particular.particular_type == "Equity Share Capital" and default_currency != self.currency:
# 				amount = frappe.get_value("FR Investment Entry",{'company': self.company, 'category': "Equity Shares", 'default_currency': default_currency},'investment_value')

# 			elif fr_particular.fetch_from_schedule:
# 				note_type = get_fr_section(fr_particular.schedule).note_type if fr_particular.schedule else None
# 				if note_type == "Other Equity":
# 					field = 'grand_total_current' if is_current else 'grand_total_prev_year'
# 					amount = self._get_other_equity_total_only(company, field)
# 				else:
# 					amount = 0
# 				# if note_type == "Changes in inventories of Finished Goods and Work-In-Progress":
# 				# 	field = 'ftm_total' if is_current else 'net_increase_total'
# 				# 	amount = self.get_yearly_finished_goods_and_wip(total=True, field=field)
# 				# elif note_type == "Cost of Materials Consumed":
# 				# 	field = 'cost_consumed_previous' if is_current else 'cost_consumed_current'
# 				# 	amount = self.get_yearly_cost_of_material_consumed(note_type, total=True, field=field)
# 				# elif note_type == "Other Equity" and not for_other_equity and not account:
# 				# 	field = 'grand_total_current' if is_current else 'grand_total_prev_year'
# 				# 	amount = self.get_yearly_other_equity_note_data(self.fiscal_year, self.previous_fiscal_year, total=True, field=field)
# 				# elif note_type == "Borrowings (Non-current)":
# 				# 	field = 'total_current_month_amt' if is_current else 'total_previous_year'
# 				# 	amount = self.get_yearly_borrowing_non_current_note_data(note_type, total=True, field=field)
# 				# elif note_type == "Investments (Non-current)":
# 				# 	field = 'total_current' if is_current else 'total_previous_year'
# 				# 	amount = self.get_yearly_investment_non_current_note_data(total=True, field=field)

# 			elif fr_particular.schedule:
# 				fr_section = get_fr_section(fr_particular.schedule)
# 				if fr_section.fetch_data_from_trial_balance:
# 					group_info = get_standalone_group(fr_section.primary_consolidation_group)
# 					group_type = group_info.group_type
# 					primary_groups = (set(frappe.get_list("Standalone Group", filters={"is_primary_group": 1,"group_type": ["in", ["Current Tax Liabilities", "Income Tax Assets"]]}, pluck="name"))if group_type in ("Current Tax Liabilities", "Income Tax Assets") else {fr_section.primary_consolidation_group})
# 					for pg in primary_groups:
# 						for sec in get_secondary_groups(pg):
# 							face_amount = self.get_sum_grouping_amount(company, pg, sec, month, year)
# 							has_hg_sec_group = self._get_cached_hg_sec_groups(company, pg, sec)
# 							for hg_sec in has_hg_sec_group:
# 								face_amount += self.get_sum_grouping_amount(company, pg, sec, month, year, hg_sec_group=hg_sec)

# 							if ((group_type == "Current Tax Liabilities" and face_amount < 0) or(group_type == "Income Tax Assets" and face_amount > 0) or
# 								(group_type not in ("Current Tax Liabilities", "Income Tax Assets") and face_amount != 0)):
# 								amount += face_amount
# 				else:
# 					gl_accounts = self._get_gl_accounts_for_mappings(company, fr_particular.get('primary_and_secondary_group_mapping'))
# 					amount = get_grouped_gl_amount(gl_accounts, year, month)

# 			else:
# 				gl_accounts = self._get_gl_accounts_for_mappings(company, fr_particular.get('primary_and_secondary_group_mapping'))
# 				amount = get_grouped_gl_amount(gl_accounts, year, month)

# 			# Reverse if required
# 			if fr_particular.show_reversed_value and not (fr_particular.particular_type == "Equity Share Capital" and default_currency != self.currency):
# 				amount = -amount

# 			if convert and not fr_particular.is_total and not fr_particular.fetch_from_schedule and not (fr_particular.particular_type == "Equity Share Capital" and default_currency != self.currency):
# 				amount *= fx_rate

# 			amount_cache[cache_key] = flt(round(amount if amount else 0, self.show_decimal_value))
# 			return amount_cache[cache_key]

# 		# --- Main loop ---
# 		data = []
# 		cls_month = self._closing_month

# 		current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, "closing_rate") if self.currency != default_currency else 1
# 		previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, "closing_rate") if self.currency != default_currency else 1
# 		prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, "closing_rate") if self.currency != default_currency else 1

# 		for row in balance_sheet_doc.balance_sheet_template_details:
# 			if not row.account:
# 				continue

# 			fr_particular = get_fr_particular(row.account)
# 			particular_type = getattr(fr_particular, "particular_type", "")

# 			# Special case: Equity Share Capital → fixed INR investment value
# 			if default_currency != self.currency and particular_type == "Equity Share Capital":
# 				investment_value = frappe.get_value("FR Investment Entry",{'company': self.company, 'category': "Equity Shares", 'default_currency': default_currency},'investment_value') or 0
# 				current_month_amount = previous_year_amount = investment_value
# 			else:
# 				current_month_amount = calc_amount_for_particular_monthly(row.account, self.current_month, self.fiscal_year, is_current=True, fx_rate=current_fx) or 0
# 				previous_year_amount = calc_amount_for_particular_monthly(row.account, cls_month, self.previous_fiscal_year, is_yearly=True, fx_rate=prev_year_fx) or 0

# 			schedule = getattr(fr_particular, "schedule", "")
# 			note_no = self.get_note_number_for_schedule(schedule) if schedule else ""

# 			data.append({
# 				"id": row.account,
# 				"account": row.particular_name,
# 				"note_no": note_no,
# 				"current_month_amount": current_month_amount,
# 				"previous_year": previous_year_amount,
# 				"indent": int(row.indent_level or 0),
# 				"is_bold": row.is_bold,
# 				"header": row.header,
# 				"group": row.group,
# 				"schedule": schedule,
# 			})

# 		if for_other_equity and account:
# 			return next((row for row in data if row["id"] == account), None)

# 		return data

# 	def get_yearly_profit_and_loss_data(self, template_name, fetch_for_other_equity=False):
# 		"""Optimized: Get monthly P&L data with current month, previous month, FTM, and previous year amounts"""
# 		self._init_report_caches()
# 		profit_and_loss_doc = frappe.get_doc("Profit And Loss Template", template_name)
# 		cls_month = self._closing_month

# 		amount_cache = {}

# 		get_fr_section = self._get_cached_fr_section
# 		get_fr_particular = self._get_cached_fr_particular
# 		get_standalone_group = self._get_cached_standalone_group
# 		get_secondary_groups = self._get_cached_secondary_groups

# 		def calc_amount_for_particular_monthly(particular_name, month, year, is_current=False, is_yearly=False, fx_rate=1, convert=True):
# 			"""
# 			Calculate amount for a particular in base currency, then apply FX conversion only for non-total nodes.
# 			"""
# 			cache_key = (particular_name, month, year, is_current, is_yearly, fx_rate)
# 			if cache_key in amount_cache:
# 				return amount_cache[cache_key]

# 			fr_particular = get_fr_particular(particular_name)
# 			amount = 0

# 			if fr_particular.is_total:
# 				for idx, p in enumerate(fr_particular.particulars or []):
# 					child_key = (p.particular, month, year, is_current, is_yearly, fx_rate)
# 					child_amount = amount_cache.get(child_key, 0)
# 					if fr_particular.to_subtract:
# 						amount = (child_amount if idx == 0 and amount == 0 else amount - child_amount)
# 					else:
# 						amount += child_amount

# 			elif fr_particular.fetch_from_schedule and not fr_particular.is_purchase_of_stock_in_trade:
# 				note_type = get_fr_section(fr_particular.schedule).note_type
# 				if note_type == "Changes in inventories of Finished Goods and Work-In-Progress":
# 					field = 'net_increase_total' if is_current else ('prev_year_amt' if is_yearly else 'previous_month_amt')
# 					amount = self.get_yearly_finished_goods_and_wip(total=True, field=field)
# 				elif note_type == "Cost of Materials Consumed":
# 					field = 'cost_consumed_current' if is_current else ('prev_year_cost_consumed' if is_yearly else 'cost_consumed_previous')
# 					amount = self.get_yearly_cost_of_material_consumed(note_type, total=True, field=field)

# 			elif fr_particular.schedule and fr_particular.is_purchase_of_stock_in_trade:
# 				if default_currency != "INR":
# 					cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 					opening_stock = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", cls_month, self.previous_fiscal_year)
# 					closing_stock_current = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", cls_month, self.fiscal_year)

# 					if is_current:
# 						amount = (
# 							self.get_sum_grouping_amount(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", cls_month, year)
# 							- self.get_yearly_finished_goods_and_wip(total=True, field='net_increase_total')
# 							+ (closing_stock_current - opening_stock)
# 						)

# 					elif is_yearly:
# 						closing_stock_pre_previous = self.sum_group_amt(company, "Inventories", "Raw Materials and Packing Material", pre_year)
# 						prev_year_closing_stock = self.sum_group_amt(company, "Inventories", "Raw Materials and Packing Material", self.previous_fiscal_year)

# 						closing_wip_pre_previous = (
# 							self.sum_group_amt(company, "Inventories", "Work in Progress", pre_year)
# 							+ self.sum_group_amt(company, "Inventories", "Finished Goods", pre_year)
# 							+ self.sum_group_amt(company, "Inventories", "Stock In Trade", pre_year)
# 						)

# 						prev_year_closing_wip = (
# 							self.sum_group_amt(company, "Inventories", "Work in Progress", self.previous_fiscal_year)
# 							+ self.sum_group_amt(company, "Inventories", "Finished Goods", self.previous_fiscal_year)
# 							+ self.sum_group_amt(company, "Inventories", "Stock In Trade", self.previous_fiscal_year)
# 						)

# 						amount = (
# 							self.sum_group_amt(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.previous_fiscal_year)
# 							+ (prev_year_closing_wip - closing_wip_pre_previous)
# 							+ (prev_year_closing_stock - closing_stock_pre_previous)
# 						)
# 					else:
# 						amount = (
# 							self.sum_group_amt(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.previous_fiscal_year)
# 							+ (prev_year_closing_wip - closing_wip_pre_previous)
# 							+ (prev_year_closing_stock - closing_stock_pre_previous)
# 						)
# 				else:
# 					amount = self.sum_group_amt(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", year)

# 			elif fr_particular.schedule:
# 				fr_section = get_fr_section(fr_particular.schedule)
# 				if fr_section.fetch_data_from_trial_balance:
# 					group_info = get_standalone_group(fr_section.primary_consolidation_group)
# 					group_type = group_info.group_type
# 					primary_groups = (
# 						set(frappe.get_list("Standalone Group", filters={"is_primary_group": 1, "group_type": ["in", ["Other Income", "Other Expense"]]}, pluck="name"))
# 						if group_type in ("Other Income", "Other Expense") else {fr_section.primary_consolidation_group}
# 					)

# 					for pg in primary_groups:
# 						for sec in get_secondary_groups(pg):
# 							face_amount = self.get_sum_grouping_amount(company, pg, sec, month, year)
# 							has_hg_sec_group = self._get_cached_hg_sec_groups(company, pg, sec)
# 							for hg_sec in has_hg_sec_group:
# 								face_amount += self.get_sum_grouping_amount(company, pg, sec, month, year, hg_sec_group=hg_sec)
# 							if group_type == "Other Income":
# 								face_amount = face_amount if face_amount < 0 else 0
# 							if group_type == "Other Expense":
# 								face_amount = face_amount if face_amount > 0 else 0
# 							if (group_type == "Other Income" and face_amount < 0) or (group_type == "Other Expense" and face_amount > 0) or (group_type not in ("Other Income", "Other Expense") and face_amount != 0):
# 								amount += face_amount
# 				else:
# 					gl_accounts = self._get_gl_accounts_for_mappings(company, fr_particular.get('primary_and_secondary_group_mapping'))
# 					if gl_accounts:
# 						placeholders = ','.join(['%s'] * len(gl_accounts))
# 						erp_type = self.get_erp_type()
# 						if erp_type == "ERPNext":
# 							start_date, end_date = self.get_month_date_range(month, year)
# 							if start_date:
# 								query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company = %s AND posting_date BETWEEN %s AND %s AND account IN ({placeholders})"
# 								params = [self.company, start_date, end_date] + gl_accounts
# 								amount = (frappe.db.sql(query, params)[0][0] or 0) / 100000
# 						else:
# 							query = f"""
# 								SELECT SUM(uploaded_amount) FROM `tabFR Trial Balance Entry`
# 								WHERE company = %s AND fiscal_year = %s AND month = %s AND gl_account IN ({placeholders})
# 							"""
# 							params = [self.company, year, month] + gl_accounts
# 							amount = (frappe.db.sql(query, params)[0][0] or 0) / 100000
# 			else:
# 				gl_accounts = self._get_gl_accounts_for_mappings(company, fr_particular.get('primary_and_secondary_group_mapping'))
# 				if gl_accounts:
# 					placeholders = ','.join(['%s'] * len(gl_accounts))
# 					erp_type = self.get_erp_type()
# 					if erp_type == "ERPNext":
# 						start_date, end_date = self.get_month_date_range(month, year)
# 						if start_date:
# 							query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company = %s AND posting_date BETWEEN %s AND %s AND account IN ({placeholders})"
# 							params = [self.company, start_date, end_date] + gl_accounts
# 							amount = (frappe.db.sql(query, params)[0][0] or 0) / 100000
# 					else:
# 						query = f"""
# 							SELECT SUM(uploaded_amount) FROM `tabFR Trial Balance Entry`
# 							WHERE company = %s AND fiscal_year = %s AND month = %s AND gl_account IN ({placeholders})
# 						"""
# 						params = [self.company, year, month] + gl_accounts
# 						amount = (frappe.db.sql(query, params)[0][0] or 0) / 100000

# 			if fr_particular.show_reversed_value:
# 				amount = -amount

# 			if convert and not fr_particular.is_total and (not fr_particular.fetch_from_schedule or fr_particular.is_purchase_of_stock_in_trade):
# 				amount *= fx_rate

# 			amount_cache[cache_key] = flt(round(amount, self.show_decimal_value))
# 			return amount_cache[cache_key]

# 		default_currency = self._default_currency
# 		current_fx = self.get_fx_rate(default_currency, cls_month, self.fiscal_year, 'average_rate') if self.currency != default_currency else 1
# 		prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'average_rate') if self.currency != default_currency else 1

# 		grouped_data = []
# 		for row in profit_and_loss_doc.profit_and_loss_template_details:
# 			if not row.account:
# 				continue

# 			current_month_amount = calc_amount_for_particular_monthly(row.account, cls_month, self.fiscal_year, is_current=True, fx_rate=current_fx)
# 			previous_year_amount = calc_amount_for_particular_monthly(row.account, cls_month, self.previous_fiscal_year, is_yearly=True, fx_rate=prev_year_fx)

# 			fr_particular = get_fr_particular(row.account)
# 			schedule = getattr(fr_particular, "schedule", "")
# 			note_no = self.get_note_number_for_schedule(schedule) if schedule else ""

# 			grouped_data.append({
# 				"id": row.account,
# 				"account": row.particular_name,
# 				"note_no": note_no or "",
# 				"current_month_amount": current_month_amount,
# 				"previous_year": previous_year_amount,
# 				"indent": int(row.indent_level or 0),
# 				"is_bold": row.is_bold,
# 				"group": row.group,
# 				"schedule": schedule,
# 			})
	
# 		if fetch_for_other_equity:
# 			account = profit_and_loss_doc.profit_and_loss_template_details[-1].account
# 			return (
# 				calc_amount_for_particular_monthly(account, self.current_month, self.fiscal_year, is_current=True, fx_rate=current_fx),
# 				calc_amount_for_particular_monthly(account, self.previous_month, self.fiscal_year, fx_rate=previous_fx),
# 				calc_amount_for_particular_monthly(account, cls_month, self.previous_fiscal_year, is_yearly=True, fx_rate=prev_year_fx)
# 			)

# 		return grouped_data

# 	def render_yearly_profit_and_loss(self, template_name, data=[]):
# 		"""Render yearly profit and loss with note-style UI"""
# 		current_month_end, previous_fiscal_year_end_label = self.get_yearly_dates()
# 		if not data:
# 			data = self.get_yearly_profit_and_loss_data(template_name)

# 		html = f"""
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; margin-top: -25pt; border:1px solid #000; background-color:#fff;">
# 			<thead>
# 				<tr style="color: #4472C4; border-bottom:2px solid #222; background-color:#fff;">
# 					<th colspan="2" style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:left; padding: 5px; font-size: 12px; width: 45%; background-color:#fff;'>Particulars</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; font-size: 12px; width: 10%; background-color:#fff;'>Note No.</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; font-size: 12px; width: 15%; background-color:#fff;'>{current_month_end}</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; font-size: 12px; width: 10%; background-color:#fff;'>{previous_fiscal_year_end_label}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		def to_roman(idx):
# 			romans = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX']
# 			return f"({romans[idx]})" if idx < len(romans) else f"({idx+1})"

# 		group_counter = 0
# 		for row in data:
# 			note_no = row.get("note_no")
# 			indent_val = int(row.get("indent", 0))
# 			indent = "&nbsp;" * (indent_val * 4)
# 			bold = "font-weight: bold;" if row.get("is_bold") else ""
# 			index = to_roman(group_counter) if row.get("group") else ""
# 			if row.get("group"): group_counter += 1

# 			# Add data-schedule attribute and clickable styling for account rows
# 			schedule_attr = f' data-schedule="{note_no}"' if note_no else ""
# 			clickable_style = "cursor: pointer;" if note_no else ""

# 			# Handle anchor link for schedule
# 			account_text = row.get("account") or ""
# 			schedule = row.get("schedule")
# 			if schedule and note_no:
# 				note_id = self.generate_note_id(note_no, account_text)
# 				if note_id:
# 					account_text = f'<a href="#' + note_id + '" style="color: #000000;">' + account_text + '</a>'

# 			# Only vertical borders for regular rows, add horizontal border for total (bold) rows
# 			horizontal_border = "border-top:1px solid #222; border-bottom:1px solid #222;" if row.get("is_bold") and not row.get("group") else ""
# 			html += f"""
# 			<tr{schedule_attr} class="clickable-row" style="{clickable_style}">
# 				<td style='text-align:center; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {bold}'>{index}</td>
# 				<td style='text-align:left; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {bold}'>{indent}{account_text}</td>
# 				<td style='text-align:center; padding: 2px; border-left:1px solid #222; border-right:1px solid #222;'>{note_no or ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} background-color: #e8f5e8; {bold}'>{row.get("current_month_amount", 0) if row.get("current_month_amount") else ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} {bold}'>{row.get("previous_year", 0) if row.get("previous_year") else ""}</td>
# 			</tr>
# 			"""

# 		html += "</tbody></table>"
# 		return json.dumps(data), html
	
# 	def get_yearly_cash_flow_data(self, template_name):
# 		"""Get monthly cash flow data with current month, previous month, and FTM amounts"""
# 		self._init_report_caches()
# 		cash_flow_doc = frappe.get_doc("Cash Flow Template", template_name)
# 		amount_cache = {}

# 		def calc_amount_for_particular_monthly(particular_name, month, year):
# 			cache_key = (particular_name, month, year)
# 			if cache_key in amount_cache:
# 				return amount_cache[cache_key]

# 			fr_particular = self._get_cached_fr_particular(particular_name)
# 			if getattr(fr_particular, "is_total", 1):
# 				amount = 0
# 				for p in getattr(fr_particular, "particulars", []):
# 					child_name = p.particular
# 					amount += calc_amount_for_particular_monthly(child_name, month, year)
# 				amount = amount * 100000
# 			else:
# 				gl_accounts = self._get_gl_accounts_for_mappings(company, fr_particular.get('primary_and_secondary_group_mapping'))

# 				if len(gl_accounts) == 0:
# 					amount = 0
# 				else:
# 					placeholders = ','.join(['%s'] * len(gl_accounts))
# 					erp_type = self.get_erp_type()
# 					if erp_type == "ERPNext":
# 						start_date, _ = self.get_month_date_range(month, year)
# 						fy_start, fy_end = self.get_fiscal_year_dates(year)
# 						if start_date and fy_end:
# 							query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN ({placeholders})"
# 							params = [self.company, start_date, fy_end] + gl_accounts
# 							amount = (frappe.db.sql(query, params)[0][0] or 0)
# 						else:
# 							amount = 0
# 					else:
# 						query = f"""
# 							SELECT SUM(amount) FROM `tabFR Trial Balance Entry`
# 							WHERE company=%s AND fiscal_year=%s AND account IN ({placeholders})
# 							AND month >= %s
# 						"""
# 						params = [self.company, year] + gl_accounts + [month]
# 						amount = (frappe.db.sql(query, params)[0][0] or 0)

# 			# Apply value reversal if show_reversed_value is checked
# 			if getattr(fr_particular, "show_reversed_value", 0):
# 				amount = -amount

# 			amount_cache[cache_key] = flt(round((amount / 100000), self.show_decimal_value))
# 			return amount_cache[cache_key]

# 		data = []
# 		for row in cash_flow_doc.cash_flow_template_details:
# 			if not row.account:
# 				continue
# 			current_month_amount = calc_amount_for_particular_monthly(row.account, self.current_month, self.fiscal_year)
# 			data.append({
# 				"account": row.particular_name,
# 				"note_no": getattr(row, "note", None),
# 				"current_month_amount": current_month_amount,
# 				"previous_year": 0,
# 				"indent": int(row.indent_level or 0),
# 				"is_bold": row.is_bold,
# 				"group": row.group,
# 			})
# 		return data


# 	def render_yearly_cash_flow(self, template_name):
# 		"""Render yearly cash flow with note-style UI"""
# 		data = self.get_yearly_cash_flow_data(template_name)
# 		month_end_label, previous_fiscal_year_end_label = self.get_yearly_dates()

# 		html = f"""
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; margin-top: -25pt; border:1px solid #000; background-color:#fff;">
# 			<thead>
# 				<tr style="color: #4472C4; border-bottom:2px solid #222; background-color:#fff;">
# 					<th colspan="2" style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:left; padding: 5px; width: 45%; background-color:#fff;'>Particulars</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; width: 15%; background-color:#fff;'>{month_end_label}</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; width: 10%; background-color:#fff;'>{previous_fiscal_year_end_label}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		def to_roman(idx):
# 			romans = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX']
# 			return f"({romans[idx]})" if idx < len(romans) else f"({idx+1})"

# 		group_counter = 0
# 		for row in data:
# 			indent = "&nbsp;" * (int(row.get("indent", 0)) * 4)
# 			bold = "font-weight: bold;" if row.get("is_bold") else ""
# 			index = to_roman(group_counter) if row.get("group") else ""
# 			if row.get("group"): group_counter += 1

# 			account_text = row.get("account") or ""

# 			# Only vertical borders for regular rows, add horizontal border for total (bold) rows
# 			horizontal_border = "border-top:1px solid #222; border-bottom:1px solid #222;" if row.get("is_bold") and not row.get("group") else ""
# 			html += f"""
# 			<tr>
# 				<td style='text-align:center; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {bold}'>{index}</td>
# 				<td style='text-align:left; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {bold}'>{indent}{account_text}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} background-color: #e8f5e8; {bold}'>{'{:,.2f}'.format(row.get("current_month_amount", 0)) if row.get("current_month_amount") else ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} {bold}'>{'{:,.2f}'.format(row.get("previous_year", 0)) if row.get("previous_year") else ""}</td>
# 			</tr>
# 			"""

# 		html += "</tbody></table>"
# 		return html

# 	def get_yearly_equity_share_capital_note_data(self, section_description=""):
# 		month_end_label, previous_fiscal_year_end_label = self.get_yearly_dates()

# 		# Get dynamic dates for current, previous, and pre-previous fiscal years
# 		current_date = month_end_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_fiscal_year_end_label.replace("Year Ended ", "").replace("/", "-")

# 		# Get pre-previous fiscal year date
# 		cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 		if pre_year:
# 			pre_year_doc = frappe.get_doc("Fiscal Year", pre_year)
# 			pre_previous_date = pre_year_doc.year_end_date.strftime("%d-%m-%Y") if pre_year_doc.year_end_date else ""
# 		else:
# 			pre_previous_date = ""

# 		def render_note_table(headers, sub_headers, rows):
# 			html = """
# 			<table style="width:100%; border-collapse:collapse; font-size:13px;">
# 				<thead>
# 			"""

# 			# Main header
# 			html += "<tr>"
# 			for idx, h in enumerate(headers):
# 				width_style = "width:30%;" if idx == 0 else ""
# 				html += f"<th style='border:1px solid #000; padding:4px; text-align:center; {width_style}'>{h}</th>"
# 			html += "</tr>"

# 			# Sub header
# 			if sub_headers:
# 				html += "<tr>"
# 				for idx, sh in enumerate(sub_headers):
# 					width_style = "width:30%;" if idx == 0 else ""
# 					html += f"<th style='border:1px solid #000; padding:4px; text-align:center; {width_style}'>{sh}</th>"
# 				html += "</tr>"

# 			html += "</thead><tbody>"

# 			for row in rows:
# 				html += "<tr>"
# 				for idx, col in enumerate(row):
# 					width_style = "width:30%;" if idx == 0 else ""
# 					html += f"<td style='border:1px solid #000; padding:4px; {width_style}'>{col or ''}</td>"
# 				html += "</tr>"

# 			html += "</tbody></table>"
# 			return html

# 		headers = [
# 			"Particulars",
# 			f"As at {current_date}", f"As at {current_date}",
# 			f"As at {previous_date}", f"As at {previous_date}",
# 			f"As at {pre_previous_date}", f"As at {pre_previous_date}",
# 		]

# 		sub_headers = [
# 			"", "No. of shares", "(₹ in lacs)",
# 			"No. of shares", "(₹ in lacs)",
# 			"No. of shares", "(₹ in lacs)"
# 		]

# 		rows = [
# 			["Authorised", "", "", "", "", "", ""],
# 			["Equity Shares of ₹10/- each", "6,00,00,000", "6,000", "6,00,00,000", "6,000", "6,00,00,000", "6,000"],
# 			["Redeemable Preference Shares of ₹10/- each", "4,00,00,000", "4,000", "4,00,00,000", "4,000", "4,00,00,000", "4,000"],
# 			["Total", "10,00,00,000", "10,000", "10,00,00,000", "10,000", "10,00,00,000", "10,000"],
# 			["Issued, Subscribed and Fully Paid", "", "", "", "", "", ""],
# 			["Equity Shares of ₹10/- each", "5,93,60,000", "5,936", "5,93,60,000", "5,936", "5,93,60,000", "5,936"],
# 			["Total", "5,93,60,000", "5,936", "5,93,60,000", "5,936", "5,93,60,000", "5,936"],
# 		]

# 		section_description = section_description.replace("{{note_table}}", render_note_table(headers, sub_headers, rows))

# 		headers_1 = [
# 			"Particulars",
# 			f"As at {current_date}", f"As at {current_date}",
# 			f"As at {previous_date}", f"As at {previous_date}",
# 			f"As at {pre_previous_date}", f"As at {pre_previous_date}",
# 		]

# 		sub_headers_1 = [
# 			"", "No. of shares", "(₹ in lacs)",
# 			"No. of shares", "(₹ in lacs)",
# 			"No. of shares", "(₹ in lacs)"
# 		]

# 		rows_1 = [
# 			["Equity Shares", "", "", "", "", "", ""],
# 			["Outstanding at the beginning of the year", "5,93,60,000", "5,936", "5,93,60,000", "5,936", "5,93,60,000", "5,936"],
# 			["Outstanding at the end of the year", "5,93,60,000", "5,936", "5,93,60,000", "5,936", "5,93,60,000", "5,936"],
# 		]
# 		section_description = section_description.replace("{{note_table_1}}", render_note_table(headers_1, sub_headers_1, rows_1))

# 		headers_3 = [
# 			"Particulars",
# 			f"As at {current_date}", f"As at {current_date}",
# 			f"As at {previous_date}", f"As at {previous_date}",
# 			f"As at {pre_previous_date}", f"As at {pre_previous_date}",
# 		]

# 		sub_headers_3 = [
# 			"", "No. of shares", "(₹ in lacs)",
# 			"No. of shares", "(₹ in lacs)",
# 			"No. of shares", "(₹ in lacs)"
# 		]

# 		rows_3 = [
# 			["Equity Shares", "", "", "", "", "", ""],
# 			[
# 				"Micro Life Sciences Private Limited, the Holding company together with its nominee",
# 				"5,93,60,000", "5,936",
# 				"5,93,60,000", "5,936",
# 				"5,93,60,000", "5,936"
# 			]
# 		]
# 		section_description = section_description.replace("{{note_table_3}}", render_note_table(headers_3, sub_headers_3, rows_3))

# 		headers_4 = [
# 			"Name of Shareholder",
# 			f"As at {current_date}", f"As at {current_date}",
# 			f"As at {previous_date}", f"As at {previous_date}",
# 			f"As at {pre_previous_date}", f"As at {pre_previous_date}",
# 		]

# 		sub_headers_4 = [
# 			"", "No. of Shares held", "% of Holding",
# 			"No. of Shares held", "% of Holding",
# 			"No. of Shares held", "% of Holding"
# 		]

# 		rows_4 = [
# 			["Equity Shares", "", "", "", "", "", ""],
# 			[
# 				"Micro Life Sciences Private Limited, the Holding company together with its nominee",
# 				"5,93,60,000", "100%",
# 				"5,93,60,000", "100%",
# 				"5,93,60,000", "100%",
# 			]
# 		]
# 		section_description = section_description.replace("{{note_table_4}}", render_note_table(headers_4, sub_headers_4, rows_4))

# 		headers_5 = [
# 			"Name of Promoter",
# 			f"As at {current_date}", f"As at {current_date}", f"As at {current_date}"
# 		]

# 		sub_headers_5 = [
# 			"", "No. of Shares", "% of total shares", "% Change during the year"
# 		]

# 		rows_5 = [
# 			["Equity Shares", "", "", ""],
# 			[
# 				"Micro Life Sciences Private Limited, the Holding company together with its nominee",
# 				"5,93,60,000", "100%", "-"
# 			],
# 			["Total", "5,93,60,000", "100%", ""]
# 		]
# 		section_description = section_description.replace("{{note_table_5}}", render_note_table(headers_5, sub_headers_5, rows_5))

# 		headers_6 = [
# 			"Name of Promoter",
# 			f"As at {previous_date}", f"As at {previous_date}", f"As at {previous_date}"
# 		]

# 		sub_headers_6 = [
# 			"", "No. of Shares", "% of total shares", "% Change during the year"
# 		]

# 		rows_6 = [
# 			["Equity Shares", "", "", ""],
# 			[
# 				"Micro Life Sciences Private Limited, the Holding company together with its nominee",
# 				"5,93,60,000", "100%", "-"
# 			],
# 			["Total", "5,93,60,000", "100%", ""]
# 		]
# 		section_description = section_description.replace("{{note_table_6}}", render_note_table(headers_6, sub_headers_6, rows_6))
# 		return section_description

# 	def get_yearly_render_equity_share_table(self, section_description=""):
# 		rows = [
# 			{"particular": "As at 1st April, 2023", "shares": "5,93,60,000", "amount": "5,936", "bold": 1},
# 			{"particular": "Changes in equity share capital during the year", "shares": "-", "amount": "-", "bold": 0},
# 			{"particular": "Balance as at 31st March, 2024", "shares": "5,93,60,000", "amount": "5,936", "bold": 1},
# 			{"particular": "Changes in equity share capital during the year", "shares": "-", "amount": "-", "bold": 0},
# 			{"particular": "Balance as at 31st March, 2025", "shares": "5,93,60,000", "amount": "5,936", "bold": 1},
# 		]

# 		html = '''
# 		<h5 style="text-align: left; font-weight: bold; padding: 8px;">A. Equity share capital (Amount in ₹ Lacs)</h5>
# 		<table style="width: 60%; border-collapse: collapse; border: 1px solid #000; font-family: Arial, sans-serif; font-size: 13px;">
# 		<thead>
# 			<tr style = "border-bottom:2px solid #222;">
# 				<th style="padding: 8px; border: 1px solid black; width: 50%;">Particulars</th>
# 				<th style="padding: 8px; text-align: right; border: 1px solid black; width: 25%;">Number of Shares</th>
# 				<th style="padding: 8px; text-align: right; border: 1px solid black; width: 25%; background-color: #e8f5e8;">Equity share capital</th>
# 			</tr>
# 		</thead>
# 		<tbody>
# 		'''

# 		for idx, row in enumerate(rows):
# 			bold_class = 'font-weight: bold;' if row["bold"] == 1 else ''
# 			# For the last row, treat as footer with full border
# 			if idx == len(rows) - 1:
# 				html += f'''
# 				<tr>
# 					<td style="padding: 8px; border: 1px solid black; {bold_class} width: 50%;">{row['particular']}</td>
# 					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 25%;">{row['shares']}</td>
# 					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 25%; background-color: #e8f5e8;">{row['amount']}</td>
# 				</tr>
# 			'''
# 			else:
# 				html += f'''
# 				<tr>
# 					<td style="padding: 8px; border: 1px solid black; {bold_class} width: 50%;">{row['particular']}</td>
# 					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 25%;">{row['shares']}</td>
# 					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 25%; background-color: #e8f5e8;">{row['amount']}</td>
# 				</tr>
# 			'''

# 		html += "</tbody>\n</table>"
# 		return section_description.replace("{{note_table}}", html)

# 	def get_bs_particular_data(self, id, field):
# 		# Use cached parsed data if available
# 		if getattr(self, '_caches_initialized', False):
# 			if self._bs_table_data_parsed is None:
# 				data = self.get('financial_report_details', {'section_type': "Balance Sheet"})
# 				if not data:
# 					self._bs_table_data_parsed = {}
# 				else:
# 					table_data_str = data[0].table_data or "[]"
# 					try:
# 						table_data = json.loads(table_data_str)
# 					except (json.JSONDecodeError, TypeError):
# 						table_data = []
# 					self._bs_table_data_parsed = {row.get("id"): row for row in table_data if row.get("id")}
# 			row = self._bs_table_data_parsed.get(id)
# 			return row.get(field) if row else 0

# 		data = self.get('financial_report_details', {'section_type': "Balance Sheet"})
# 		if not data:
# 			return 0
# 		table_data_str = data[0].table_data or "[]"
# 		try:
# 			table_data = json.loads(table_data_str)
# 		except (json.JSONDecodeError, TypeError):
# 			table_data = []
# 		for row in table_data:
# 			if row.get("id") == id:
# 				return row.get(field)
# 		return 0

# 	def get_pl_particular_data(self, id, field):
# 		# Use cached parsed data if available
# 		if getattr(self, '_caches_initialized', False):
# 			if self._pl_table_data_parsed is None:
# 				data = self.get('financial_report_details', {'section_type': "Profit & Loss"})
# 				if not data:
# 					self._pl_table_data_parsed = {}
# 				else:
# 					table_data_str = data[0].table_data or "[]"
# 					try:
# 						table_data = json.loads(table_data_str)
# 					except (json.JSONDecodeError, TypeError):
# 						table_data = []
# 					self._pl_table_data_parsed = {row.get("id"): row for row in table_data if row.get("id")}
# 			row = self._pl_table_data_parsed.get(id)
# 			return row.get(field) if row else 0

# 		data = self.get('financial_report_details', {'section_type': "Profit & Loss"})
# 		if not data:
# 			return 0
# 		table_data_str = data[0].table_data or "[]"
# 		try:
# 			table_data = json.loads(table_data_str)
# 		except (json.JSONDecodeError, TypeError):
# 			table_data = []
# 		for row in table_data:
# 			if row.get("id") == id:
# 				return row.get(field)
# 		return 0

# 	@frappe.whitelist()
# 	def get_financial_report_template(self):
# 		self.financial_report_details.clear()

# 		if not self.financial_report_template:
# 			frappe.throw("Please select a Financial Report Template before fetching.")

# 		template = frappe.get_doc("Financial Report Template", self.financial_report_template)

# 		for d in template.financial_report_template_details:
# 			context = {
# 				"company": "Bilakhia Group"
# 			}
# 			section_desc = frappe.render_template(d.section_description or "", context)
# 			section_desc = f'<div style="text-align: justify;">{section_desc}</div>'
# 			subsection_desc = frappe.render_template(d.subsection_description or "", context)
# 			subsection_desc = f'<div style="text-align: justify;">{subsection_desc}</div>'
			
# 			self.append('financial_report_details', {
# 				'section_type': d.section_type,
# 				'doctype_name': d.doctype_name,
# 				'section': d.section,
# 				'subsection': d.subsection,
# 				'section_description': section_desc,
# 				'subsection_description': subsection_desc,
# 			})

# 	"""	    ################################################################################################
# 			################################################################################################
# 		#######################                                                              #####################
# 		#######################                                                              #####################
# 		#######################                Monthly Financial Report Logic                #####################
# 		#######################                                                              #####################
# 		#######################                                                              #####################
# 			################################################################################################
# 			################################################################################################        """

# 	def get_monthly_dates(self, only_dates=False):
# 		if not self.current_month or not self.previous_month:
# 			return ("", "", "") if not only_dates else (None, None)

# 		month_num = {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12}

# 		if isinstance(self.current_year_ending_date, str):
# 			current_year = int(self.current_year_ending_date.split("-")[0]) - 1
# 		elif isinstance(self.current_year_ending_date, datetime):
# 			current_year = self.current_year_ending_date.year - 1
# 		elif hasattr(self.current_year_ending_date, "year"):  # datetime.date
# 			current_year = self.current_year_ending_date.year - 1
# 		else:
# 			current_year = datetime.now().year

# 		current_month_num = month_num.get(self.current_month, 1)
# 		previous_month_num = month_num.get(self.previous_month, 1)

# 		# Compute month-end dates
# 		if current_month_num == 12:
# 			month_end_date = datetime(current_year, 12, 31)
# 		elif current_month_num <= 3:
# 			month_end_date = datetime(current_year+1, current_month_num + 1, 1) - timedelta(days=1)
# 		else:
# 			month_end_date = datetime(current_year, current_month_num + 1, 1) - timedelta(days=1)

# 		if previous_month_num == 12:
# 			previous_month_end_date = datetime(current_year, 12, 31)
# 		elif previous_month_num < 3:
# 			previous_month_end_date = datetime(current_year+1, previous_month_num + 1, 1) - timedelta(days=1)
# 		else:
# 			previous_month_end_date = datetime(current_year, previous_month_num + 1, 1) - timedelta(days=1)

# 		if only_dates:
# 			return month_end_date, previous_month_end_date

# 		# Build readable labels
# 		current_month_label = f"Month Ended {month_end_date.strftime('%d/%m/%Y')}"
# 		previous_month_label = f"Month Ended {previous_month_end_date.strftime('%d/%m/%Y')}"

# 		if self.previous_year_ending_date:
# 			if isinstance(self.previous_year_ending_date, str):
# 				previous_year_date_obj = datetime.strptime(self.previous_year_ending_date, "%Y-%m-%d")
# 			elif hasattr(self.previous_year_ending_date, "year"):
# 				previous_year_date_obj = datetime.combine(self.previous_year_ending_date, datetime.min.time())
# 			else:
# 				previous_year_date_obj = None

# 			previous_year_label = (
# 				f"Year Ended {previous_year_date_obj.strftime('%d/%m/%Y')}" if previous_year_date_obj else ""
# 			)
# 		else:
# 			previous_year_label = ""

# 		return current_month_label, previous_month_label, previous_year_label

# 	def get_monthly_finished_goods_and_wip(self, company, section_description, total, get_face=None, field=None):
# 		rows = []
# 		add_row = lambda p, cm=0, pm=0, ftm=0, py=0, st=False: rows.append({
# 			"particulars": p, "current_month_amt": cm, "previous_month_amt": pm, "ftm_amt": ftm, "previous_year_amt": py, "is_subtotal": st
# 		})
# 		add_row("Inventories at the end of the month", st=True)

# 		cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 		default_currency = frappe.get_value("Company", company, "default_currency")
# 		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
# 		current_month_total = cls_previous_month_total = f_previous_year_amt = ftm_total = previous_month_total = 0

# 		if default_currency != self.currency:
# 			if not total:
# 				current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, 'closing_rate') or 1
# 				previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, 'closing_rate') or 1
# 				prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'closing_rate') or 1
# 				pre_prev_year_fx = self.get_fx_rate(default_currency, cls_month, pre_year, 'closing_rate') or 1
# 			else:
# 				if get_face:
# 					current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, 'closing_rate') or 1
# 					previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, 'closing_rate') or 1
# 					prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'closing_rate') or 1
# 					pre_prev_year_fx = self.get_fx_rate(default_currency, cls_month, pre_year, 'closing_rate') or 1
# 				else:
# 					current_fx = previous_fx = prev_year_fx = pre_prev_year_fx = 1
# 		else:
# 			current_fx = previous_fx = prev_year_fx = pre_prev_year_fx = 1


# 		def add_inventory_group(secondary_group, label):
# 			nonlocal current_month_total, cls_previous_month_total, f_previous_year_amt, ftm_total
# 			cur = self.get_sum_grouping_amount(company, "Inventories", secondary_group, self.current_month, self.fiscal_year) * current_fx
# 			prev = self.get_sum_grouping_amount(company, "Inventories", secondary_group, self.previous_month, self.fiscal_year) * previous_fx
# 			prev_year_closing = self.sum_group_amt(company, "Inventories", secondary_group, self.previous_fiscal_year) * prev_year_fx
# 			ftm_val = cur - prev

# 			add_row(label, cur, prev, ftm_val, prev_year_closing)

# 			# higher secondary group breakdown
# 			hg_list = frappe.get_all(
# 				"GL Group Mapping",
# 				{"company": company, "primary_group": "Inventories", "secondary_group": secondary_group, "higher_secondary_group": ["!=", None]},
# 				pluck="higher_secondary_group", distinct=True
# 			)

# 			for hg in hg_list:
# 				cur_hg = self.get_sum_grouping_amount(company, "Inventories", secondary_group, self.current_month, self.fiscal_year, hg_sec_group=hg) * current_fx
# 				prev_hg = self.get_sum_grouping_amount(company, "Inventories", secondary_group, self.previous_month, self.fiscal_year, hg_sec_group=hg) * previous_fx
# 				prev_year_hg = self.get_sum_grouping_amount(company, "Inventories", secondary_group, cls_month, self.previous_fiscal_year, hg_sec_group=hg) * prev_year_fx
# 				add_row(f"  {hg}", cur_hg, prev_hg, cur_hg - prev_hg, prev_year_hg)
# 				current_month_total += cur_hg; cls_previous_month_total += prev_hg
# 				f_previous_year_amt += prev_year_hg; ftm_total += (cur_hg - prev_hg)

# 			return cur, prev, prev_year_closing, ftm_val

# 		# Finished Goods, WIP, SIT
# 		cur_fg, prev_fg, prev_year_fg, ftm_fg = add_inventory_group("Finished Goods", "Finished goods")
# 		cur_wip, prev_wip, prev_year_wip, ftm_wip = add_inventory_group("Work in Progress", "Work-in-progress")
# 		cur_sit, prev_sit, prev_year_sit, ftm_sit = add_inventory_group("Stock In Trade", "Stock-in-trade")

# 		# totals
# 		current_month_total += cur_fg + cur_wip + cur_sit
# 		cls_previous_month_total += prev_fg + prev_wip + prev_sit
# 		f_previous_year_amt += prev_year_fg + prev_year_wip + prev_year_sit
# 		ftm_total += ftm_fg + ftm_wip + ftm_sit
# 		add_row("", current_month_total, cls_previous_month_total, ftm_total, f_previous_year_amt)

# 		add_row("Inventories at the beginning of the month", st=True)

# 		# ---------- Previous year section (optimized same way) ----------
# 		def add_prev_year_group(secondary_group, label):
# 			nonlocal previous_month_total
# 			prev_month_val = self.get_sum_grouping_amount(company, "Inventories", secondary_group, cls_month, self.previous_fiscal_year) * prev_year_fx
# 			pre_prev_closing = self.sum_group_amt(company, "Inventories", secondary_group, pre_year) * pre_prev_year_fx
# 			add_row(label, prev_month_val, prev_month_val, 0, pre_prev_closing)

# 			hg_list = frappe.get_all(
# 				"GL Group Mapping",
# 				{"company": company, "primary_group": "Inventories", "secondary_group": secondary_group, "higher_secondary_group": ["!=", None]},
# 				pluck="higher_secondary_group", distinct=True
# 			)
# 			for hg in hg_list:
# 				hg_val = self.get_sum_grouping_amount(company, "Inventories", secondary_group, cls_month, self.previous_fiscal_year, hg_sec_group=hg) * prev_year_fx
# 				prev_year_hg = self.get_sum_grouping_amount(company, "Inventories", secondary_group, cls_month, pre_year, hg_sec_group=hg) * pre_prev_year_fx
# 				add_row(f"  {hg}", hg_val, hg_val, 0, prev_year_hg)
# 				previous_month_total += hg_val; pre_prev_closing += prev_year_hg
# 			return prev_month_val, pre_prev_closing

# 		previous_month_fg, closing_fg_pre_prev = add_prev_year_group("Finished Goods", "Finished goods")
# 		previous_month_wip, closing_wip_pre_prev = add_prev_year_group("Work in Progress", "Work-in-progress")
# 		previous_month_sit, closing_sit_pre_prev = add_prev_year_group("Stock In Trade", "Stock-in-trade")

# 		previous_month_total += previous_month_fg + previous_month_wip + previous_month_sit

# 		# ---------- Net increases ----------
# 		net_increase_fg = cur_fg - previous_month_fg
# 		net_increase_wip = cur_wip - previous_month_wip
# 		net_increase_total = previous_month_total - current_month_total
# 		prev_net_total = previous_month_total - cls_previous_month_total
# 		prev_year_amt = (closing_wip_pre_prev + closing_fg_pre_prev + closing_sit_pre_prev) - f_previous_year_amt

# 		if total:
# 			if field == "net_increase_total": return net_increase_total
# 			if field == "ftm_total": return ftm_total 
# 			if field == "previous_month_amt": return prev_net_total
# 			if field == "prev_year_amt": return prev_year_amt
# 			return 0

# 		# face-only fetch
# 		if get_face and total:
# 			if field == "net_increase_total": return net_increase_total
# 			if field == "ftm_total": return ftm_total
# 			if field == "previous_month_amt": return prev_net_total
# 			if field == "prev_year_amt": return prev_year_amts
# 			return 0

# 		# final subtotal rows
# 		add_row("", previous_month_total, previous_month_total, 0, closing_wip_pre_prev + closing_fg_pre_prev + closing_sit_pre_prev)
# 		add_row("Net increase", net_increase_total, prev_net_total, prev_net_total - net_increase_total, prev_year_amt, st=True)

# 		# HTML rendering
# 		html = f'''
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr style="border-bottom:2px solid #222;">
# 					<th style="border:1px solid #222; color: #4472C4; text-align:left; width:40%; padding:6px 8px;"><b>Particulars</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>{month_end_label}</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>FTM</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>{current_fiscal_year_end_label}</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>{previous_fiscal_year_end_label}</b></th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		'''

# 		for r in rows:
# 			cm, pm, ftm, py = [round(r[v], self.show_decimal_value) if r[v] else "" for v in ["current_month_amt", "previous_month_amt", "ftm_amt", "previous_year_amt"]]
# 			bold = "font-weight:bold;" if r["is_subtotal"] else ""
# 			br = "border:1px solid #222; border-top:none; border-bottom:none;" if not r["is_subtotal"] else "border:1px solid #222;"
# 			html += f'''
# 			<tr>
# 				<td style="{br} text-align:left; padding:6px 8px; {bold}">{r["particulars"]}</td>
# 				<td style="{br} text-align:right; padding:6px 8px; {bold} background:#e8f5e8;">{cm}</td>
# 				<td style="{br} text-align:right; padding:6px 8px; {bold}">{ftm}</td>
# 				<td style="{br} text-align:right; padding:6px 8px; {bold}">{pm}</td>
# 				<td style="{br} text-align:right; padding:6px 8px; {bold}">{py}</td>
# 			</tr>
# 			'''

# 		html += "</tbody></table>"
# 		return section_description.replace("{{note_table}}", html)

# 	def get_monthly_cost_of_material_consumed(self, company, section_description, total, field=None):
# 		rows = []
# 		cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 		default_currency = frappe.get_value("Company", company, 'default_currency')

# 		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()

# 		# --- Current & Previous Month Stocks ---
# 		opening_stock = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", cls_month, self.previous_fiscal_year)
# 		closing_stock_current = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", self.current_month, self.fiscal_year)
# 		closing_stock_previous = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", self.previous_month, self.fiscal_year)

# 		# --- Purchases & SIT ---
# 		curr_month_purchase_sit = 0 if default_currency != "INR" else self.get_sum_grouping_amount(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.current_month, self.fiscal_year)
# 		prev_month_purchase_sit = 0 if default_currency != "INR" else self.get_sum_grouping_amount(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.previous_month, self.fiscal_year)

# 		purchases_current = (
# 			self.get_sum_grouping_amount(company, "Material consumed", "Cost of Goods Sold", self.current_month, self.fiscal_year)
# 			- (0 if default_currency != "INR" else self.get_monthly_finished_goods_and_wip(company, "Changes in inventories of Finished Goods and Work-In-Progress", total=True, field='net_increase_total'))
# 			+ (closing_stock_current - opening_stock)
# 			- curr_month_purchase_sit
# 		)

# 		purchases_previous = (
# 			self.get_sum_grouping_amount(company, "Material consumed", "Cost of Goods Sold", self.previous_month, self.fiscal_year)
# 			- (0 if default_currency != "INR" else self.get_monthly_finished_goods_and_wip(company, "Changes in inventories of Finished Goods and Work-In-Progress", total=True, field='previous_month_amt'))
# 			+ (closing_stock_previous - opening_stock)
# 			- prev_month_purchase_sit
# 		)

# 		# --- Cost of Materials Consumed ---
# 		cost_consumed_current = opening_stock + purchases_current - closing_stock_current
# 		cost_consumed_previous = opening_stock + purchases_previous - closing_stock_previous

# 		# --- FTM ---
# 		ftm_purchases = purchases_current - purchases_previous
# 		ftm_closing_stock = closing_stock_current - closing_stock_previous
# 		ftm_cost_consumed = cost_consumed_current - cost_consumed_previous

# 		# --- Previous Year (same month) ---
# 		closing_stock_pre_previous = self.sum_group_amt(company, "Inventories", "Raw Materials and Packing Material", pre_year)
# 		prev_year_closing_stock = self.sum_group_amt(company, "Inventories", "Raw Materials and Packing Material", self.previous_fiscal_year)

# 		closing_wip_pre_previous = (
# 			self.sum_group_amt(company, "Inventories", "Work in Progress", pre_year)
# 			+ self.sum_group_amt(company, "Inventories", "Finished Goods", pre_year)
# 			+ self.sum_group_amt(company, "Inventories", "Stock In Trade", pre_year)
# 		)
# 		prev_year_closing_wip = (
# 			self.sum_group_amt(company, "Inventories", "Work in Progress", self.previous_fiscal_year)
# 			+ self.sum_group_amt(company, "Inventories", "Finished Goods", self.previous_fiscal_year)
# 			+ self.sum_group_amt(company, "Inventories", "Stock In Trade", self.previous_fiscal_year)
# 		)

# 		pre_purchase_sit = 0 if default_currency != "INR" else self.sum_group_amt(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.previous_fiscal_year)
# 		prev_year_purchases = (
# 			self.sum_group_amt(company, "Material consumed", "Cost of Goods Sold", self.previous_fiscal_year)
# 			+ (0 if default_currency != "INR" else (prev_year_closing_wip - closing_wip_pre_previous))
# 			+ (prev_year_closing_stock - closing_stock_pre_previous)
# 			- pre_purchase_sit
# 		)

# 		prev_year_cost_consumed = closing_stock_pre_previous + prev_year_purchases - prev_year_closing_stock

# 		# --- Currency Conversion ---
# 		if default_currency != self.currency:
# 			current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, 'average_rate')
# 			previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, 'average_rate')
# 			prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'average_rate')
# 			pre_prev_year_fx = self.get_fx_rate(default_currency, cls_month, pre_year, 'average_rate')

# 			# Apply conversion
# 			cost_consumed_current *= current_fx
# 			cost_consumed_previous *= previous_fx
# 			ftm_cost_consumed *= current_fx  # assumption: FTM aligned to current period rate
# 			prev_year_cost_consumed *= prev_year_fx

# 			opening_stock *= previous_fx
# 			purchases_current *= current_fx
# 			purchases_previous *= previous_fx
# 			closing_stock_current *= current_fx
# 			closing_stock_previous *= previous_fx
# 			prev_year_purchases *= prev_year_fx
# 			closing_stock_pre_previous *= pre_prev_year_fx

# 		# --- If only returning totals ---
# 		if total:
# 			if field == 'cost_consumed_current':
# 				return cost_consumed_current
# 			elif field == 'cost_consumed_previous':
# 				return cost_consumed_previous
# 			elif field == 'ftm_cost_consumed':
# 				return ftm_cost_consumed
# 			elif field == 'prev_year_cost_consumed':
# 				return prev_year_cost_consumed
# 			else:
# 				return 0

# 		# --- Final Rows ---
# 		rows.extend([
# 			{"particulars": "Opening Stock","current_month_amt": opening_stock,"previous_month_amt": opening_stock,"ftm_amt": 0,"previous_year_amt": closing_stock_pre_previous,"is_subtotal": False},
# 			{"particulars": "Add: purchases & other related costs","current_month_amt": purchases_current,"previous_month_amt": purchases_previous,"ftm_amt": ftm_purchases,"previous_year_amt": prev_year_purchases,"is_subtotal": False},
# 			{"particulars": "Less: closing stock","current_month_amt": closing_stock_current,"previous_month_amt": closing_stock_previous,"ftm_amt": ftm_closing_stock,"previous_year_amt": opening_stock,"is_subtotal": False},
# 			{"particulars": "Cost of Materials Consumed","current_month_amt": cost_consumed_current,"previous_month_amt": cost_consumed_previous,"ftm_amt": ftm_cost_consumed,"previous_year_amt": prev_year_cost_consumed,"is_subtotal": True}
# 		])


# 		# Generate HTML table
# 		html = f'''
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">
# 			<thead>
# 				<tr style="border-bottom:2px solid #222;">
# 					<th style="border:1px solid #222; color: #4472C4; text-align:left; width:40%; padding:6px 8px;"><b>Particulars</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>{month_end_label}</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>FTM</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>{current_fiscal_year_end_label}</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>{previous_fiscal_year_end_label}</b></th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		'''

# 		for row in rows:
# 			# Format amounts
# 			current_month_amt_str = round(row['current_month_amt'], self.show_decimal_value) if row['current_month_amt'] else "-"
# 			ftm_amt_str = round(row['ftm_amt'], self.show_decimal_value) if row['ftm_amt'] else "-"
# 			previous_month_amt_str = round(row['previous_month_amt'], self.show_decimal_value) if row['previous_month_amt'] else "-"
# 			previous_year_amt = round(row['previous_year_amt'], self.show_decimal_value) if row['previous_year_amt'] else "-"

# 			# Style for totals
# 			bold_style = "font-weight: bold;" if row["is_subtotal"] else ""
# 			border_style = "border:1px solid #222;" if row["is_subtotal"] else "border:1px solid #222; border-top:none; border-bottom:none;"

# 			html += f'''
# 				<tr>
# 					<td style="{border_style} text-align:left; padding:6px 8px; {bold_style}">{row['particulars']}</td>
# 					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style} background-color:#e8f5e8;">{current_month_amt_str}</td>
# 					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{ftm_amt_str}</td>
# 					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{previous_month_amt_str}</td>
# 					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{previous_year_amt}</td>
# 				</tr>
# 			'''
		
# 		html += "</tbody></table>"
# 		return section_description.replace("{{note_table}}", html)

# 	@frappe.whitelist()
# 	def get_monthly_purchases_of_stock_in_trade(self, company, section_description, total, field=None):
# 		cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 		default_currency = frappe.get_value("Company", company, 'default_currency')
# 		opening_stock = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", cls_month, self.previous_fiscal_year)
# 		closing_stock_current = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", self.current_month, self.fiscal_year)
# 		closing_stock_previous = self.get_sum_grouping_amount(company, "Inventories", "Raw Materials and Packing Material", self.previous_month, self.fiscal_year)

# 		purchases_current = (
# 			self.get_sum_grouping_amount(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.current_month, self.fiscal_year)
# 			- self.get_monthly_finished_goods_and_wip(company, "Changes in inventories of Finished Goods and Work-In-Progress", total=True, field='net_increase_total')
# 			+ (closing_stock_current - opening_stock)
# 		)
# 		purchases_previous = (
# 			self.get_sum_grouping_amount(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.previous_month, self.fiscal_year)
# 			- self.get_monthly_finished_goods_and_wip(company, "Changes in inventories of Finished Goods and Work-In-Progress", total=True, field='previous_month_amt')
# 			+ (closing_stock_previous - opening_stock)
# 		)

# 		closing_stock_pre_previous = self.sum_group_amt(company, "Inventories", "Raw Materials and Packing Material", pre_year)
# 		prev_year_closing_stock = self.sum_group_amt(company, "Inventories", "Raw Materials and Packing Material", self.previous_fiscal_year)

# 		closing_wip_pre_previous = (
# 			self.sum_group_amt(company, "Inventories", "Work in Progress", pre_year) + self.sum_group_amt(company, "Inventories", "Finished Goods", pre_year)
# 			+ self.sum_group_amt(company, "Inventories", "Stock In Trade", pre_year)
# 		)
# 		prev_year_closing_wip = (
# 			self.sum_group_amt(company, "Inventories", "Work in Progress", self.previous_fiscal_year) + self.sum_group_amt(company, "Inventories", "Finished Goods", self.previous_fiscal_year)
# 			+ self.sum_group_amt(company, "Inventories", "Stock In Trade", self.previous_fiscal_year)
# 		)

# 		prev_year_purchases = (
# 			self.sum_group_amt(company, "Purchases of Stock in Trade", "Purchases of Stock in Trade", self.previous_fiscal_year)
# 			+ (prev_year_closing_wip - closing_wip_pre_previous) + (prev_year_closing_stock - closing_stock_pre_previous)
# 		)

# 		if default_currency != self.currency:
# 			current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, 'average_rate')
# 			previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, 'average_rate')
# 			prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'average_rate')
# 			purchases_current = round(purchases_current * current_fx, self.show_decimal_value) or 1
# 			purchases_previous = round(purchases_previous * previous_fx, self.show_decimal_value) or 1
# 			prev_year_purchases = round(prev_year_purchases * prev_year_fx, self.show_decimal_value) or 1

# 		if total:
# 			if field == "purchases_current": return purchases_current
# 			if field == "purchases_previous": return purchases_previous
# 			if field == "prev_year_purchases": return prev_year_purchases

# 		data.append({"account": account, "current_month_amount": purchases_current, "previous_month_amount": purchases_previous,
# 			"ftm_amount": (purchases_current - purchases_previous), "previous_year": prev_year_purchases, "indent": indent, "is_bold": 0
# 		})
# 		table_data = self.monthly_table_for_note_template_1(data)
# 		return section_description.replace("{{note_table}}", table_data)

# 	@frappe.whitelist()
# 	def get_monthly_consolidation_note_data(self, primary_group):
# 		self._init_report_caches()
# 		data = []
# 		companies = frappe.get_all("Company", pluck="name")
# 		group_info = self._get_cached_standalone_group(primary_group)
# 		show_reversed_value = group_info.show_reversed_value
# 		group_type = group_info.group_type
# 		def format_amount(val):
# 			return round(flt(-val if show_reversed_value and val < 0 else val or 0), self.show_decimal_value)

# 		def append_data(account, cm, pm, ftm, py, indent=0):
# 			data.append({"account": account, "current_month_amount": format_amount(cm), "previous_month_amount": format_amount(pm),
# 				"ftm_amount": format_amount(ftm), "previous_year": format_amount(py), "indent": indent, "is_bold": 0
# 			})

# 		if group_type in ("Other Income", "Other Expense"):
# 			primary_groups = frappe.get_list("Standalone Group",filters={"is_primary_group": 1, "group_type": ["in", ["Other Income", "Other Expense"]]},pluck="name")
# 		else:
# 			primary_groups = [primary_group]
# 		cls_month = self._closing_month
# 		for primary_group in primary_groups:
# 			secondary_groups = frappe.db.get_list("GL Group Mapping", {"primary_group": ["in", primary_group], "report_type": self.report_type}, pluck="secondary_group")
# 			secondary_groups = sorted(set(filter(None, secondary_groups)))
# 			custom_order = frappe.db.get_value("Schedule Reorder",{"primary_group": primary_group},"name")
# 			if custom_order:
# 				ordered_rows = frappe.get_all("Schedule Reorder Details",filters={"parent": custom_order},fields=["standalone_group"],order_by="idx asc")
# 				ordered_groups = [r.standalone_group for r in ordered_rows if r.standalone_group]
# 				secondary_consolidation_groups = [g for g in ordered_groups if g in secondary_groups]
# 				missing_groups = [g for g in secondary_groups if g not in ordered_groups]
# 				secondary_consolidation_groups.extend(sorted(missing_groups))
# 			else:
# 				secondary_consolidation_groups = secondary_groups

# 			sg_info = self._get_cached_standalone_group(primary_group)
# 			report_type = sg_info.report_type if sg_info else None

# 			for sec in secondary_consolidation_groups:
# 				cm = pm = py = 0
# 				for company in companies:
# 					default_currency = frappe.get_value("Company", company, "default_currency")
# 					if default_currency != self.currency:
# 						if report_type == "Balance Sheet":
# 							field_name = "closing_rate"
# 						elif report_type == "Profit & Loss":
# 							field_name = "average_rate"
# 						else:
# 							field_name = "closing_rate"
# 					else:
# 						field_name = None

# 					current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, field_name) if field_name else 1
# 					previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, field_name) if field_name else 1
# 					prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, field_name) if field_name else 1

# 					cm += (self.get_sum_grouping_amount(company, primary_group, sec, self.current_month, self.fiscal_year) or 0) * current_fx
# 					pm += (self.get_sum_grouping_amount(company, primary_group, sec, self.previous_month, self.fiscal_year) or 0) * previous_fx
# 					py += (self.get_sum_grouping_amount(company, primary_group, sec, cls_month, self.previous_fiscal_year) or 0) * prev_year_fx
# 				ftm = round(cm - pm, self.show_decimal_value)
# 				has_hg_sec_group = []
# 				for company in companies:
# 					has_hg_sec_group.extend(self._get_cached_hg_sec_groups(company, primary_group, sec))
# 				has_hg_sec_group = list(set(has_hg_sec_group))
# 				if group_type in ("Other Income", "Other Expense"):
# 					if group_type == "Other Income":
# 						cm = cm if cm < 0 else 0
# 						pm = pm if pm < 0 else 0
# 						py = py if py < 0 else 0
# 					elif group_type == "Other Expense":
# 						cm = cm if cm > 0 else 0
# 						pm = pm if pm > 0 else 0
# 						py = py if py > 0 else 0

# 				if any(val != 0 for val in (cm, pm, py)) or has_hg_sec_group:
# 					append_data(sec, cm, pm, ftm, py)

# 				for hg_sec in has_hg_sec_group:
# 					cm = pm = py = 0
# 					for company in companies:
# 						default_currency = frappe.get_value("Company", company, "default_currency")
# 						current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, "closing_rate") if default_currency != self.currency else 1
# 						previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, "closing_rate") if default_currency != self.currency else 1
# 						prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, "closing_rate") if default_currency != self.currency else 1

# 						cm += (self.get_sum_grouping_amount(company, primary_group, sec, self.current_month, self.fiscal_year, hg_sec_group=hg_sec) or 0) * current_fx
# 						pm += (self.get_sum_grouping_amount(company, primary_group, sec, self.previous_month, self.fiscal_year, hg_sec_group=hg_sec) or 0) * previous_fx
# 						py += (self.get_sum_grouping_amount(company, primary_group, sec, cls_month, self.previous_fiscal_year, hg_sec_group=hg_sec) or 0) * prev_year_fx

# 					if any(val != 0 for val in (cm, pm, py)):
# 						append_data(hg_sec, cm, pm, round(cm - pm, self.show_decimal_value), py, indent=1)

# 		return data

# 	def render_monthly_balance_sheet(self, template_name, data=None):
# 		"""Render monthly balance sheet with note-style UI"""
# 		if not data:
# 			data = self.get_monthly_balance_sheet_data(template_name)
# 		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()

# 		html = f"""
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; margin-top: -25pt; border:1px solid #000; background-color:#fff;">
# 			<thead>
# 				<tr style="color: #4472C4; border-bottom:2px solid #222; background-color:#fff;">
# 					<th colspan="2" style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:left; padding: 5px; width: 45%; background-color:#fff;'>Particulars</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; width: 10%; background-color:#fff;'>Note No.</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; width: 15%; background-color:#fff;'>{month_end_label}</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; width: 10%; background-color:#fff;'>{previous_fiscal_year_end_label}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		# Counters for structured index generation
# 		header_counter = 0
# 		group_counter = 0
# 		group_stack = [{'alpha_counter': 0, 'roman_counter': 0, 'indent': 0, 'last_indent_1': None}]

# 		# Helpers for indices
# 		def to_alpha(idx): return f"({chr(65+idx)})"
# 		def to_roman(idx): return f"({['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX'][idx]})"
# 		def to_lower_alpha(idx): return f"({chr(97+idx)})"
# 		def to_lower_roman(idx): return f"({['i','ii','iii','iv','v','vi','vii','viii','ix','x','xi','xii','xiii','xiv','xv','xvi','xvii','xviii','xix','xx'][idx]})"

# 		for row in data:
# 			indent_val = int(row.get("indent", 0))
# 			indent = "&nbsp;" * (indent_val * 4)
# 			bold = "font-weight: bold;" if row.get("is_bold") else ""
# 			account_label = row.get("account") or ""
# 			note_no = row.get("note_no")
# 			schedule = row.get("schedule")
# 			index = ""
			
# 			# Section Headers
# 			if row.get("header"):
# 				index = to_alpha(header_counter)
# 				header_counter += 1
# 				group_stack = [{'alpha_counter': 0, 'roman_counter': 0, 'indent': 0, 'last_indent_1': None}]
# 			elif row.get("group"):
# 				index = to_roman(group_counter)
# 				group_counter += 1
# 				group_stack.append({'alpha_counter': 0, 'roman_counter': 0, 'indent': indent_val, 'last_indent_1': None})
# 			elif not row.get("is_bold"):
# 				if indent_val == 0:
# 					alpha_idx = group_stack[-1]['alpha_counter']
# 					account_label = f"{to_lower_alpha(alpha_idx)} {account_label}"
# 					group_stack[-1]['alpha_counter'] += 1
# 				elif indent_val == 1:
# 					if group_stack[-1]['last_indent_1'] != 1:
# 						group_stack[-1]['roman_counter'] = 0
# 					roman_idx = group_stack[-1]['roman_counter']
# 					account_label = f"{to_lower_roman(roman_idx)} {account_label}"
# 					group_stack[-1]['roman_counter'] += 1
# 					group_stack[-1]['last_indent_1'] = 1
# 				else:
# 					group_stack[-1]['last_indent_1'] = indent_val

# 			# Add data-schedule attribute and clickable styling for account rows
# 			schedule_attr = f' data-schedule="{note_no}"' if note_no else ""
# 			clickable_style = "cursor: pointer;" if note_no else ""

# 			# Add anchor link if schedule exists
# 			account_text = account_label
# 			if schedule and note_no:
# 				note_id = self.generate_note_id(note_no, account_label)
# 				account_text = f'<a href="#{note_id}" style="color: #000000;">{account_label}</a>'

# 			# Final row - only vertical borders for regular rows, add horizontal border for sub-total (bold) rows
# 			horizontal_border = "border-top:1px solid #222; border-bottom:1px solid #222;" if row.get("is_bold") and not row.get("header") and not row.get("group") else ""
# 			html += f"""
# 			<tr{schedule_attr} class="clickable-row" style="{clickable_style} line-height: 1;">
# 				<td style='text-align:center; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {bold}'>{index}</td>
# 				<td style='text-align:left; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {bold}'>{indent}{account_text}</td>
# 				<td style='text-align:center; padding: 2px; border-left:1px solid #222; border-right:1px solid #222 '>{note_no or ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} background-color: #e8f5e8; {bold}'>{ round(row.get("current_month_amount", 0),3) if row.get("current_month_amount") else ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} {bold}'>{ round(row.get("previous_year", 0),3) if row.get("previous_year") else ""}</td>
# 			</tr>
# 			"""

# 		html += "</tbody></table>"
# 		return json.dumps(data), html

# 	def render_monthly_profit_and_loss(self, template_name, data=None):
# 		"""Render monthly profit and loss with note-style UI"""
# 		current_month_end, previous_month_end, previous_fiscal_year_end_label = self.get_monthly_dates()
# 		if data is None:
# 			data = self.get_monthly_profit_and_loss_data(template_name)

# 		html = f"""
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; margin-top: -25pt; border:1px solid #000; background-color:#fff;">
# 			<thead>
# 				<tr style="color: #4472C4; border-bottom:2px solid #222; background-color:#fff;">
# 					<th colspan="2" style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:left; padding: 5px; font-size: 12px; width: 35%; background-color:#fff;'>Particulars</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; font-size: 12px; width: 10%; background-color:#fff;'>Note No.</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; font-size: 12px; width: 15%; background-color:#fff;'>{current_month_end}</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; font-size: 12px; width: 10%; background-color:#fff;'>FTM</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; font-size: 12px; width: 10%; background-color:#fff;'>{previous_month_end}</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; font-size: 12px; width: 10%; background-color:#fff;'>{previous_fiscal_year_end_label}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		def to_roman(idx):
# 			romans = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX']
# 			return f"({romans[idx]})" if idx < len(romans) else f"({idx+1})"
		
# 		group_counter = 0
# 		for row in data:
# 			note_no = row.get("note_no")
# 			indent_val = int(row.get("indent", 0))
# 			indent = "&nbsp;" * (indent_val * 4)
# 			bold = "font-weight: bold;" if row.get("is_bold") else ""
# 			index = to_roman(group_counter) if row.get("group") else ""
# 			if row.get("group"): group_counter += 1

# 			# Add data-schedule attribute and clickable styling for account rows
# 			schedule_attr = f' data-schedule="{note_no}"' if note_no else ""
# 			clickable_style = "cursor: pointer;" if note_no else ""
			
# 			# Handle anchor link for schedule
# 			account_text = row.get("account") or ""
# 			schedule = row.get("schedule")
# 			if schedule and note_no:
# 				note_id = self.generate_note_id(note_no, account_text)
# 				if note_id:
# 					account_text = f'<a href="#' + note_id + '" style="color: #000000;">' + account_text + '</a>'

# 			# Only vertical borders for regular rows, add horizontal border for total (bold) rows
# 			horizontal_border = "border-top:1px solid #222; border-bottom:1px solid #222;" if row.get("is_bold") and not row.get("group") else ""
# 			html += f"""
# 			<tr{schedule_attr} class="clickable-row" style="{clickable_style}">
# 				<td style='text-align:center; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {bold}'>{index}</td>
# 				<td style='text-align:left; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {bold}'>{indent}{account_text}</td>
# 				<td style='text-align:center; padding: 2px; border-left:1px solid #222; border-right:1px solid #222;'>{note_no or ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} background-color: #e8f5e8; {bold}'>{ round(row.get("current_month_amount", 0),3) if row.get("current_month_amount") else ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} {bold}'>{ round(row.get("ftm_amount", 0),3) if row.get("ftm_amount") else ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} {bold}'>{ round(row.get("previous_month_amount", 0),3) if row.get("previous_month_amount") else ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} {bold}'>{ round(row.get("previous_year", 0),3) if row.get("previous_year") else ""}</td>
# 			</tr>
# 			"""

# 		html += "</tbody></table>"
# 		return json.dumps(data), html

# 	def render_monthly_cash_flow(self, template_name):
# 		"""Render monthly cash flow with note-style UI"""
# 		data = self.get_monthly_cash_flow_data(template_name)
# 		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()

# 		html = f"""
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; margin-top: -25pt; border:1px solid #000; background-color:#fff;">
# 			<thead>
# 				<tr style="color: #4472C4; border-bottom:2px solid #222; background-color:#fff;">
# 					<th colspan="2" style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:left; padding: 5px; width: 35%; background-color:#fff;'>Particulars</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; width: 15%; background-color:#fff;'>{month_end_label}</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; width: 10%; background-color:#fff;'>FTM</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; width: 10%; background-color:#fff;'>{current_fiscal_year_end_label}</th>
# 					<th style='border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; text-align:center; padding: 5px; width: 10%; background-color:#fff;'>{previous_fiscal_year_end_label}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		"""

# 		def to_roman(idx):
# 			romans = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX']
# 			return f"({romans[idx]})" if idx < len(romans) else f"({idx+1})"

# 		group_counter = 0
# 		for row in data:
# 			indent = "&nbsp;" * (int(row.get("indent", 0)) * 4)
# 			bold = "font-weight: bold;" if row.get("is_bold") else ""
# 			index = to_roman(group_counter) if row.get("group") else ""
# 			if row.get("group"): group_counter += 1

# 			account_text = row.get("account") or ""

# 			# Only vertical borders for regular rows, add horizontal border for total (bold) rows
# 			horizontal_border = "border-top:1px solid #222; border-bottom:1px solid #222;" if row.get("is_bold") and not row.get("group") else ""
# 			html += f"""
# 			<tr>
# 				<td style='text-align:center; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {bold}'>{index}</td>
# 				<td style='text-align:left; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {bold}'>{indent}{account_text}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} background-color: #e8f5e8; {bold}'>{'{:,.2f}'.format(row.get("current_month_amount", 0)) if row.get("current_month_amount") else ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} {bold}'>{'{:,.2f}'.format(row.get("ftm_amount", 0)) if row.get("ftm_amount") else ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} {bold}'>{'{:,.2f}'.format(row.get("previous_month_amount", 0)) if row.get("previous_month_amount") else ""}</td>
# 				<td style='text-align:right; padding: 2px; border-left:1px solid #222; border-right:1px solid #222; {horizontal_border} {bold}'>{'{:,.2f}'.format(row.get("previous_year", 0)) if row.get("previous_year") else ""}</td>
# 			</tr>
# 			"""

# 		html += "</tbody></table>"
# 		return json.dumps(data), html

# 	def render_monthly_equity_share_table(self):
# 		"""Render monthly equity share table with optimized structure"""
# 		rows = [
# 			{"particular": "As at 1st April, 2023", "shares": "5,93,60,000", "amount": "5,936", "bold": 1},
# 			{"particular": "Changes in equity share capital during the year", "shares": "-", "amount": "-", "bold": 0},
# 			{"particular": "Balance as at 31st March, 2024", "shares": "5,93,60,000", "amount": "5,936", "bold": 1},
# 			{"particular": "Changes in equity share capital during the year", "shares": "-", "amount": "-", "bold": 0},
# 			{"particular": "Balance as at 31st March, 2025", "shares": "5,93,60,000", "amount": "5,936", "bold": 1},
# 		]

# 		html = '''
# 		<h5 style="text-align: left; font-weight: bold; padding: 8px;">A. Equity share capital (Amount in ₹ Lacs)</h5>
# 		<table style="width: 60%; border-collapse: collapse; border: 1px solid #000; font-family: Arial, sans-serif; font-size: 13px;">
# 		<thead>
# 			<tr style = "border-bottom:2px solid #222;">
# 				<th style="padding: 8px; border: 1px solid black; width: 50%;">Particulars</th>
# 				<th style="padding: 8px; text-align: right; border: 1px solid black; width: 25%;">Number of Shares</th>
# 				<th style="padding: 8px; text-align: right; border: 1px solid black; width: 25%; background-color: #e8f5e8;">Equity share capital</th>
# 			</tr>
# 		</thead>
# 		<tbody>
# 		'''

# 		for idx, row in enumerate(rows):
# 			bold_class = 'font-weight: bold;' if row["bold"] == 1 else ''
# 			# For the last row, treat as footer with full border
# 			if idx == len(rows) - 1:
# 				html += f'''
# 				<tr>
# 					<td style="padding: 8px; border: 1px solid black; {bold_class} width: 50%;">{row['particular']}</td>
# 					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 25%;">{row['shares']}</td>
# 					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 25%; background-color: #e8f5e8;">{row['amount']}</td>
# 				</tr>
# 			'''
# 			else:
# 				html += f'''
# 				<tr>
# 					<td style="padding: 8px; border: 1px solid black; {bold_class} width: 50%;">{row['particular']}</td>
# 					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 25%;">{row['shares']}</td>
# 					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 25%; background-color: #e8f5e8;">{row['amount']}</td>
# 				</tr>
# 			'''

# 		html += "</tbody>\n</table>"
# 		return html

# 	def monthly_table_for_note_template_1(self, data):
# 		"""Optimized monthly table for note template 1"""
# 		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()

# 		note_table = f'''
# 		<table style="width:100%; border-collapse:collapse; border-spacing:0; font-size:13px; margin-top: 20pt; border:1px solid #000; background-color:#fff;">
# 			<thead>
# 				<tr style="color: #4472C4; background-color:#fff;">
# 					<th style='border:1px solid #222; text-align:left; padding: 2px 5px; width: 40%; background-color:#fff;'>Particulars</th>
# 					<th style='border:1px solid #222; text-align:center; padding: 2px 5px; width: 15%; background-color:#fff;'>{month_end_label}</th>
# 					<th style='border:1px solid #222; text-align:center; padding: 2px 5px; width: 15%; background-color:#fff;'>FTM</th>
# 					<th style='border:1px solid #222; text-align:center; padding: 2px 5px; width: 15%; background-color:#fff;'>{current_fiscal_year_end_label}</th>
# 					<th style='border:1px solid #222; text-align:center; padding: 2px 5px; width: 15%; background-color:#fff;'>{previous_fiscal_year_end_label}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		'''

# 		total_current_month = 0
# 		total_previous_month = 0
# 		total_ftm = 0
# 		total_previous_year = 0
# 		for i, row in enumerate(data):
# 			indent = "&nbsp;" * (int(row.get("indent", 0)) * 4)
# 			bold = "font-weight: bold;" if row.get("is_bold") else ""
# 			current_month_amount = row.get('current_month_amount') or 0
# 			previous_month_amount = row.get('previous_month_amount') or 0
# 			ftm_amount = row.get('ftm_amount') or 0
# 			previous_year = row.get('previous_year') or 0
# 			total_current_month += current_month_amount
# 			total_previous_month += previous_month_amount
# 			total_ftm += ftm_amount
# 			total_previous_year += previous_year
# 			# First row after header should have bottom border
# 			top_border = "border-top:1px solid #222;" if i == 0 else "border-top:none;"
# 			note_table += f'''
# 			<tr style="line-height: 1; border:none;">
# 				<td style='text-align:left; padding: 2px 5px; border-left:1px solid #222; border-right:1px solid #222; border-bottom:none; {top_border} {bold}'>{indent}{row.get("account") or ""}</td>
# 				<td style='text-align:right; padding: 2px 5px; border-left:1px solid #222; border-right:1px solid #222; border-bottom:none; {top_border} background-color: #e8f5e8; {bold}'>{current_month_amount if current_month_amount else 0}</td>
# 				<td style='text-align:right; padding: 2px 5px; border-left:1px solid #222; border-right:1px solid #222; border-bottom:none; {top_border} {bold}'>{ftm_amount if ftm_amount else 0}</td>
# 				<td style='text-align:right; padding: 2px 5px; border-left:1px solid #222; border-right:1px solid #222; border-bottom:none; {top_border} {bold}'>{previous_month_amount if previous_month_amount else 0}</td>
# 				<td style='text-align:right; padding: 2px 5px; border-left:1px solid #222; border-right:1px solid #222; border-bottom:none; {top_border} {bold}'>{previous_year if previous_year else 0}</td>
# 			</tr>
# 			'''
# 		# Add total row as footer
# 		note_table += f'''
# 			<tr style="line-height: 1;">
# 				<td style='text-align:left; padding: 2px 5px; border:1px solid #222; font-weight: bold;'>Total</td>
# 				<td style='text-align:right; padding: 2px 5px; border:1px solid #222; font-weight: bold; background-color: #e8f5e8;'>{round(total_current_month, self.show_decimal_value)}</td>
# 				<td style='text-align:right; padding: 2px 5px; border:1px solid #222; font-weight: bold;'>{round(total_ftm, self.show_decimal_value)}</td>
# 				<td style='text-align:right; padding: 2px 5px; border:1px solid #222; font-weight: bold;'>{round(total_previous_month, self.show_decimal_value)}</td>
# 				<td style='text-align:right; padding: 2px 5px; border:1px solid #222; font-weight: bold;'>{round(total_previous_year, self.show_decimal_value)}</td>
# 			</tr>
# 		'''
# 		note_table += "</tbody></table>"
# 		return note_table

# 	@frappe.whitelist()
# 	def get_monthly_profit_and_loss_data(self, template_name, fetch_for_other_equity=False):
# 		"""Optimized: Get monthly P&L data with current month, previous month, FTM, and previous year amounts"""
# 		self._init_report_caches()
# 		profit_and_loss_doc = frappe.get_doc("Profit And Loss Template", template_name)
# 		cls_month = self._closing_month
# 		amount_cache = {}
# 		companies = frappe.get_all("Company", pluck="name")
# 		get_fr_section = self._get_cached_fr_section
# 		get_fr_particular = self._get_cached_fr_particular
# 		get_standalone_group = self._get_cached_standalone_group
# 		get_secondary_groups = self._get_cached_secondary_groups

# 		def calc_amount(company, particular_name, month, year,default_currency, is_current=False, is_yearly=False, fx_rate=1):
# 			cache_key = (company, particular_name, month, year, is_current, is_yearly, fx_rate, default_currency)
# 			if cache_key in amount_cache:
# 				return amount_cache[cache_key]

# 			fr_particular = get_fr_particular(particular_name)
# 			amount = 0

# 			if fr_particular.is_total:
# 				for idx, p in enumerate(fr_particular.particulars or []):
# 					child_amount = calc_amount(company, p.particular, month, year,default_currency, is_current, is_yearly, fx_rate)
# 					if fr_particular.to_subtract:
# 						amount = (child_amount if idx == 0 and amount == 0 else amount - child_amount)
# 					else:
# 						amount += child_amount

# 			elif fr_particular.fetch_from_schedule:
# 				note_type = get_fr_section(fr_particular.schedule).note_type
# 				if note_type == "Changes in inventories of Finished Goods and Work-In-Progress":
# 					field = 'net_increase_total' if is_current else ('prev_year_amt' if is_yearly else 'previous_month_amt')
# 					amount = self.get_monthly_finished_goods_and_wip(company, note_type, get_face=True, total=True, field=field)
# 				elif note_type == "Cost of Materials Consumed":
# 					field = 'cost_consumed_current' if is_current else ('prev_year_cost_consumed' if is_yearly else 'cost_consumed_previous')
# 					amount = self.get_monthly_cost_of_material_consumed(company, note_type, total=True, field=field)
# 				elif note_type == "Purchases of Stock in Trade":
# 					field = 'purchases_current' if is_current else ('prev_year_purchases' if is_yearly else 'purchases_previous')
# 					amount = self.get_monthly_purchases_of_stock_in_trade(company, note_type, total=True, field=field)

# 			elif fr_particular.schedule:
# 				fr_section = get_fr_section(fr_particular.schedule)
# 				if fr_section.fetch_data_from_trial_balance:
# 					group_info = get_standalone_group(fr_section.primary_consolidation_group)
# 					group_type = group_info.group_type
# 					primary_groups = (
# 						set(frappe.get_list("Standalone Group", filters={"is_primary_group": 1, "group_type": ["in", ["Other Income", "Other Expense"]]}, pluck="name"))
# 						if group_type in ("Other Income", "Other Expense") else {fr_section.primary_consolidation_group}
# 					)

# 					for pg in primary_groups:
# 						for sec in get_secondary_groups(pg):
# 							face_amount = self.get_sum_grouping_amount(company, pg, sec, month, year)
# 							has_hg_sec_group = self._get_cached_hg_sec_groups(company, pg, sec)
# 							for hg_sec in has_hg_sec_group:
# 								face_amount += self.get_sum_grouping_amount(company, pg, sec, month, year, hg_sec_group=hg_sec)
# 							if group_type == "Other Income":
# 								face_amount = face_amount if face_amount < 0 else 0
# 							if group_type == "Other Expense":
# 								face_amount = face_amount if face_amount > 0 else 0
# 							if (group_type == "Other Income" and face_amount < 0) or (group_type == "Other Expense" and face_amount > 0) or (group_type not in ("Other Income", "Other Expense") and face_amount != 0):
# 								amount += face_amount
# 					amount = amount * fx_rate
# 				else:
# 					gl_accounts = self._get_gl_accounts_for_mappings(company, fr_particular.get('primary_and_secondary_group_mapping'))
# 					if gl_accounts:
# 						placeholders = ','.join(['%s'] * len(gl_accounts))
# 						erp_type = self.get_erp_type()
# 						if erp_type == "ERPNext":
# 							start_date, end_date = self.get_month_date_range(month, year)
# 							if start_date:
# 								query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company = %s AND posting_date BETWEEN %s AND %s AND account IN ({placeholders})"
# 								params = [company, start_date, end_date] + gl_accounts
# 								amount = ((frappe.db.sql(query, params)[0][0] or 0) / 100000)
# 						else:
# 							query = f"""
# 								SELECT SUM(uploaded_amount) FROM `tabFR Trial Balance Entry`
# 								WHERE company = %s AND fiscal_year = %s AND month = %s AND gl_account IN ({placeholders})
# 							"""
# 							params = [company, year, month] + gl_accounts
# 							amount = ((frappe.db.sql(query, params)[0][0] or 0) / 100000)

# 			elif fr_particular.type == "Deferred Tax" and default_currency != self.currency:
# 				cls_month, prev_year = self.get_previous_year_cls_month(year)
# 				gl_accounts = self._get_gl_accounts_for_mappings(company, fr_particular.get('primary_and_secondary_group_mapping'))
# 				if gl_accounts:
# 					placeholders = ','.join(['%s'] * len(gl_accounts))
# 					query = f"""
# 							SELECT SUM(uploaded_amount) FROM `tabFR Trial Balance Entry`
# 							WHERE company = %s AND fiscal_year = %s AND month = %s AND gl_account IN ({placeholders})
# 						"""
# 					curr_params = [company, year, month] + gl_accounts
# 					cur_amount = (frappe.db.sql(query, curr_params)[0][0] or 0)

# 					prev_params = [company, prev_year, cls_month] + gl_accounts
# 					prev_amount = (frappe.db.sql(query, prev_params)[0][0] or 0)
# 					amount = ((cur_amount - prev_amount) / 100000)
# 				else:
# 					amount = 0
# 			else:
# 				gl_accounts = self._get_gl_accounts_for_mappings(company, fr_particular.get('primary_and_secondary_group_mapping'))
# 				if gl_accounts:
# 					placeholders = ','.join(['%s'] * len(gl_accounts))
# 					erp_type = self.get_erp_type()
# 					if erp_type == "ERPNext":
# 						start_date, end_date = self.get_month_date_range(month, year)
# 						if start_date:
# 							query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company = %s AND posting_date BETWEEN %s AND %s AND account IN ({placeholders})"
# 							params = [company, start_date, end_date] + gl_accounts
# 							amount = ((frappe.db.sql(query, params)[0][0] or 0) / 100000)
# 					else:
# 						query = f"""
# 							SELECT SUM(uploaded_amount) FROM `tabFR Trial Balance Entry`
# 							WHERE company = %s AND fiscal_year = %s AND month = %s AND gl_account IN ({placeholders})
# 						"""
# 						params = [company, year, month] + gl_accounts
# 						amount = ((frappe.db.sql(query, params)[0][0] or 0) / 100000) 
			
# 			if fr_particular.show_reversed_value:
# 				amount = -amount

# 			amount_cache[cache_key] = flt(round(amount, self.show_decimal_value))
# 			return amount_cache[cache_key]

# 		grouped_data = []
# 		for row in profit_and_loss_doc.profit_and_loss_template_details:
# 			current_month_amount, previous_month_amount, previous_year_amount = 0, 0, 0
# 			if not row.account:
# 				continue

# 			company_currency_map = dict((d.name, d.default_currency) for d in frappe.get_all("Company", fields=["name", "default_currency"]))
# 			for company in companies:
# 				default_currency = company_currency_map.get(company)
# 				current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, 'average_rate') if self.currency != default_currency else 1
# 				previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, 'average_rate') if self.currency != default_currency else 1
# 				prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'average_rate') if self.currency != default_currency else 1

# 				current_month_amount += calc_amount(company, row.account, self.current_month, self.fiscal_year,default_currency, is_current=True, fx_rate=current_fx)
# 				previous_month_amount += calc_amount(company, row.account, self.previous_month, self.fiscal_year,default_currency, fx_rate=previous_fx)
# 				previous_year_amount += calc_amount(company, row.account, cls_month, self.previous_fiscal_year, default_currency, is_yearly=True, fx_rate=prev_year_fx)

# 			ftm_amount = round((current_month_amount - previous_month_amount), self.show_decimal_value)
# 			fr_particular = get_fr_particular(row.account)
# 			schedule = getattr(fr_particular, "schedule", "")
# 			note_no = self.get_note_number_for_schedule(schedule) if schedule else ""

# 			grouped_data.append({
# 				"id": row.account,
# 				"account": row.particular_name,
# 				"note_no": note_no or "",
# 				"current_month_amount": current_month_amount,
# 				"previous_month_amount": previous_month_amount,
# 				"ftm_amount": ftm_amount,
# 				"previous_year": previous_year_amount,
# 				"indent": int(row.indent_level or 0),
# 				"is_bold": row.is_bold,
# 				"group": row.group,
# 				"schedule": schedule,
# 			})
	
# 		if fetch_for_other_equity:
# 			account = profit_and_loss_doc.profit_and_loss_template_details[-1].account
# 			total_current, total_prev, total_prev_year = 0, 0, 0
# 			for company in companies:
# 				default_currency = frappe.get_value("Company", company, 'default_currency')
# 				current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, 'average_rate') if default_currency != self.currency else 1
# 				previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, 'average_rate') if default_currency != self.currency else 1
# 				prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'average_rate') if default_currency != self.currency else 1

# 				total_current += calc_amount(company, account, self.current_month, self.fiscal_year,default_currency, is_current=True, fx_rate=current_fx)
# 				total_prev += calc_amount(company, account, self.previous_month, self.fiscal_year,default_currency, fx_rate=previous_fx)
# 				total_prev_year += calc_amount(company, account, cls_month, self.previous_fiscal_year,default_currency, is_yearly=True, fx_rate=prev_year_fx)
# 			return (total_current, total_prev, total_prev_year)

# 		return grouped_data

# 	def get_monthly_balance_sheet_data(self, template_name, for_other_equity=False, account=None):
# 		"""Get monthly balance sheet data with current month, previous month, and FTM amounts"""
# 		self._init_report_caches()
# 		balance_sheet_doc = frappe.get_doc("Balance Sheet Template", template_name)
# 		amount_cache = {}
# 		companies = frappe.get_all("Company", pluck="name")

# 		get_fr_particular = self._get_cached_fr_particular
# 		get_fr_section = self._get_cached_fr_section
# 		get_standalone_group = self._get_cached_standalone_group
# 		get_secondary_groups = self._get_cached_secondary_groups

# 		def get_grouped_gl_amount(company, gl_accounts, year, month=None):
# 			if not gl_accounts:
# 				return 0
# 			placeholders = ','.join(['%s'] * len(gl_accounts))
# 			erp_type = self.get_erp_type()

# 			if erp_type == "ERPNext":
# 				if month:
# 					start_date, end_date = self.get_month_date_range(month, year)
# 					if not start_date: return 0
# 					query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN ({placeholders})"
# 					params = [company, start_date, end_date] + gl_accounts
# 				else:
# 					fy_start, fy_end = self.get_fiscal_year_dates(year)
# 					if not fy_start: return 0
# 					query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN ({placeholders})"
# 					params = [company, fy_start, fy_end] + gl_accounts
# 			else:
# 				query = f"""
# 					SELECT SUM(uploaded_amount) FROM `tabFR Trial Balance Entry`
# 					WHERE company=%s AND fiscal_year=%s AND gl_account IN ({placeholders})
# 				"""
# 				params = [company, year] + gl_accounts
# 				if month:
# 					query += " AND month=%s"
# 					params.append(month)
# 			return (frappe.db.sql(query, params)[0][0] or 0) / 100000

# 		def calc_amount_for_particular_monthly(company, particular_name, month, year,default_currency, is_current=False, is_yearly=False, fx_rate=1, convert=True):
# 			cache_key = (company, particular_name, month, year, fx_rate)
# 			if cache_key in amount_cache:
# 				return amount_cache[cache_key]

# 			fr_particular = get_fr_particular(particular_name)
# 			amount = 0

# 			if fr_particular.is_total:
# 				for p in fr_particular.get("particulars", []):
# 					amount += calc_amount_for_particular_monthly(company, p.particular, month, year, is_current, is_yearly, fx_rate, convert)

# 			elif fr_particular.particular_type == "Equity Share Capital" and default_currency != self.currency:
# 				amount = frappe.get_value("FR Investment Entry",{'company': company, 'category': "Equity Shares", 'default_currency': default_currency},'investment_value')

# 			elif fr_particular.fetch_from_schedule:
# 				note_type = get_fr_section(fr_particular.schedule).note_type if fr_particular.schedule else None
# 				if note_type == "Other Equity":
# 					field = 'grand_total_current' if is_current else 'grand_total_prev_year'
# 					amount = self._get_other_equity_total_only(company, field)
# 				else:
# 					amount = 0
# 				# if note_type == "Changes in inventories of Finished Goods and Work-In-Progress":
# 				# 	field = 'ftm_total' if is_current else 'net_increase_total'
# 				# 	amount = self.get_monthly_finished_goods_and_wip(company, note_type, total=True, field=field)
# 				# elif note_type == "Cost of Materials Consumed":
# 				# 	field = 'cost_consumed_previous' if is_current else 'cost_consumed_current'
# 				# 	amount = self.get_monthly_cost_of_material_consumed(company, note_type, total=True, field=field)
# 				# elif note_type == "Other Equity" and not for_other_equity and not account:
# 				# 	field = 'grand_total_current' if is_current else 'grand_total_prev_year'
# 				# 	amount = self.get_monthly_other_equity_note_data(company, note_type, total=True, field=field)
# 				# elif note_type == "Borrowings (Non-current)":
# 				# 	field = 'total_current_month_amt' if is_current else 'total_previous_year'
# 				# 	primary_group = get_fr_section(fr_particular.schedule).primary_consolidation_group
# 				# 	amount = self.get_monthly_borrowing_non_current_note_data(company, note_type, primary_group, total=True, field=field)
# 				# elif note_type == "Investments (Non-current)":
# 				# 	field = 'total_current' if is_current else 'total_previous_year'
# 				# 	amount = self.get_monthly_investment_non_current_note_data(company, note_type, total=True, field=field)

# 			elif fr_particular.schedule:
# 				fr_section = get_fr_section(fr_particular.schedule)
# 				if fr_section.fetch_data_from_trial_balance:
# 					group_info = get_standalone_group(fr_section.primary_consolidation_group)
# 					group_type = group_info.group_type
# 					primary_groups = (set(frappe.get_list("Standalone Group", filters={"is_primary_group": 1,"group_type": ["in", ["Current Tax Liabilities", "Income Tax Assets"]]}, pluck="name"))if group_type in ("Current Tax Liabilities", "Income Tax Assets") else {fr_section.primary_consolidation_group})
# 					for pg in primary_groups:
# 						for sec in get_secondary_groups(pg):
# 							face_amount = self.get_sum_grouping_amount(company, pg, sec, month, year)
# 							has_hg_sec_group = self._get_cached_hg_sec_groups(company, pg, sec)
# 							for hg_sec in has_hg_sec_group:
# 								face_amount += self.get_sum_grouping_amount(company, pg, sec, month, year, hg_sec_group=hg_sec)

# 							if ((group_type == "Current Tax Liabilities" and face_amount < 0) or(group_type == "Income Tax Assets" and face_amount > 0) or
# 								(group_type not in ("Current Tax Liabilities", "Income Tax Assets") and face_amount != 0)):
# 								amount += face_amount
# 				else:
# 					gl_accounts = self._get_gl_accounts_for_mappings(company, fr_particular.get('primary_and_secondary_group_mapping'))
# 					amount = get_grouped_gl_amount(company, gl_accounts, year, month)
# 			else:
# 				gl_accounts = self._get_gl_accounts_for_mappings(company, fr_particular.get('primary_and_secondary_group_mapping'))
# 				amount = get_grouped_gl_amount(company, gl_accounts, year, month)

# 			# Reverse if required
# 			if fr_particular.show_reversed_value and not (fr_particular.particular_type == "Equity Share Capital" and default_currency != self.currency):
# 				amount = -amount

# 			# Apply FX only on leaf nodes (not totals, not schedule fetches)
# 			if convert and not fr_particular.is_total and (not fr_particular.fetch_from_schedule or fr_particular.is_purchase_of_stock_in_trade) and not (fr_particular.particular_type == "Equity Share Capital" and default_currency != self.currency):
# 				amount *= fx_rate

# 			amount_cache[cache_key] = flt(round(amount if amount else 0, self.show_decimal_value))
# 			return amount_cache[cache_key]

# 		# --- Main loop ---
# 		data = []
# 		cls_month = self._closing_month

# 		for row in balance_sheet_doc.balance_sheet_template_details:
# 			current_month_amount, previous_month_amount, previous_year_amount = 0, 0, 0
# 			if not row.account:
# 				continue

# 			fr_particular = get_fr_particular(row.account)
# 			particular_type = getattr(fr_particular, "particular_type", "")

# 			for company in companies:
# 				default_currency = frappe.get_value("Company", company, 'default_currency')
# 				current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, "closing_rate") if self.currency != default_currency else 1
# 				previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, "closing_rate") if self.currency != default_currency else 1
# 				prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, "closing_rate") if self.currency != default_currency else 1

# 				if default_currency != self.currency and particular_type == "Equity Share Capital":
# 					_, current_month_date = self.get_month_date_range(self.current_month, self.fiscal_year)
# 					current_value = frappe.get_value(
# 		                "FR Equity Entry",
# 		                {
# 		                	"company": company,
# 		                	"type": "Issued",
# 		                	"date": ["<=", current_month_date]
# 		                },
# 		                "SUM(investment_inr)"
# 	                )
# 					current_month_amount += round(
# 		                flt(current_value or 0) / 100000,
# 		                self.show_decimal_value
# 	                )
# 					previous_month_amount += current_month_amount
# 					prev_year_value = frappe.get_value(
# 		                "FR Equity Entry",
# 		                {
# 		                	"company": company,
# 		                	"type": "Issued",
# 		                	"date": ["<=", self.previous_year_ending_date]
# 		                },
# 		                "SUM(investment_inr)"
# 	                )
# 					previous_year_amount += round(
# 		                flt(prev_year_value or 0) / 100000,
# 		                self.show_decimal_value
# 	                )
# 				else:
# 					current_month_amount += calc_amount_for_particular_monthly(company, row.account, self.current_month, self.fiscal_year, default_currency, is_current=True, fx_rate=current_fx) or 0
# 					previous_month_amount += calc_amount_for_particular_monthly(company, row.account, self.previous_month, self.fiscal_year, default_currency, fx_rate=previous_fx) or 0
# 					previous_year_amount += calc_amount_for_particular_monthly(company, row.account, cls_month, self.previous_fiscal_year, default_currency, is_yearly=True, fx_rate=prev_year_fx) or 0

# 			ftm_amount = current_month_amount - previous_month_amount
# 			schedule = getattr(fr_particular, "schedule", "")
# 			note_no = self.get_note_number_for_schedule(schedule) if schedule else ""

# 			data.append({
# 				"id": row.account,
# 				"account": row.particular_name,
# 				"note_no": note_no,
# 				"current_month_amount": current_month_amount,
# 				"previous_month_amount": previous_month_amount,
# 				"ftm_amount": ftm_amount,
# 				"previous_year": previous_year_amount,
# 				"indent": int(row.indent_level or 0),
# 				"is_bold": row.is_bold,
# 				"header": row.header,
# 				"group": row.group,
# 				"schedule": schedule,
# 			})

# 		if for_other_equity and account:
# 			return next((row for row in data if row["id"] == account), None)

# 		return data

# 	def get_monthly_cash_flow_data(self, template_name):
# 		"""Get monthly cash flow data with current month, previous month, and FTM amounts"""
# 		self._init_report_caches()
# 		cash_flow_doc = frappe.get_doc("Cash Flow Template", template_name)
# 		amount_cache = {}
# 		companies = frappe.get_all("Company", pluck="name")
# 		get_fr_particular = self._get_cached_fr_particular

# 		def calc_amount_for_particular_monthly(company, particular_name, month, year, default_currency, fx_rate=1):
# 			cache_key = (company, particular_name, month, year, fx_rate)
# 			if cache_key in amount_cache:
# 				return amount_cache[cache_key]

# 			fr_particular = get_fr_particular(particular_name)
# 			amount = 0
# 			if getattr(fr_particular, "is_total", 1):
				
# 				for p in getattr(fr_particular, "particulars", []):
# 					amount += calc_amount_for_particular_monthly(company, p.particular, month, year, default_currency, fx_rate)
				
# 			else:
# 				gl_accounts = self._get_gl_accounts_for_mappings(company, fr_particular.get('primary_and_secondary_group_mapping'))

# 				if len(gl_accounts) == 0:
# 					amount = 0
# 				else:
# 					placeholders = ','.join(['%s'] * len(gl_accounts))
# 					erp_type = self.get_erp_type()
# 					if erp_type == "ERPNext":
# 						start_date, _ = self.get_month_date_range(month, year)
# 						fy_start, fy_end = self.get_fiscal_year_dates(year)
# 						if start_date and fy_end:
# 							query = f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN ({placeholders})"
# 							params = [company, start_date, fy_end] + gl_accounts
# 							amount = (frappe.db.sql(query, params)[0][0] or 0)
# 						else:
# 							amount = 0
# 					else:
# 						query = f"""
# 							SELECT SUM(amount) FROM `tabFR Trial Balance Entry`
# 							WHERE company=%s AND fiscal_year=%s AND account IN ({placeholders})
# 							AND month >= %s
# 						"""
# 						params = [company, year] + gl_accounts + [month]
# 						amount = (frappe.db.sql(query, params)[0][0] or 0)

# 			# Apply value reversal if show_reversed_value is checked
# 			if getattr(fr_particular, "show_reversed_value", 0):
# 				amount = -amount

# 			if not getattr(fr_particular, "is_total", 1):
# 				amount *= fx_rate

# 			amount_cache[cache_key] = flt(round((amount / 100000), self.show_decimal_value))
# 			return amount_cache[cache_key]

# 		data = []
# 		for row in cash_flow_doc.cash_flow_template_details:
# 			if not row.account:
# 				continue
# 			current_month_amount = 0
# 			previous_month_amount = 0

# 			for company in companies:
# 				default_currency = frappe.get_value("Company", company, "default_currency")
# 				current_fx = (self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, "closing_rate") if default_currency != self.currency else 1)
# 				previous_fx = (self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, "closing_rate") if default_currency != self.currency else 1)
# 				current_month_amount += calc_amount_for_particular_monthly(
# 				    company,
# 				    row.account,
# 				    self.current_month,
# 				    self.fiscal_year,
# 				    default_currency,
# 				    current_fx
# 			    )
# 				previous_month_amount += calc_amount_for_particular_monthly(
# 				    company,
# 				    row.account,
# 				    self.previous_month,
# 				    self.fiscal_year,
# 				    default_currency,
# 				    previous_fx
# 			    )
			
# 			ftm_amount = current_month_amount - previous_month_amount
# 			data.append({
# 				"account": row.particular_name,
# 				"note_no": getattr(row, "note", None),
# 				"current_month_amount": current_month_amount,
# 				"previous_month_amount": previous_month_amount,
# 				"ftm_amount": ftm_amount,
# 				"previous_year": 0,
# 				"indent": int(row.indent_level or 0),
# 				"is_bold": row.is_bold,
# 				"group": row.group,
# 			})
# 		return data

# 	def get_monthly_borrowing_non_current_note_data(self, company, section_description, primary_group, total=False, field=None):
# 		"""Get monthly borrowing non-current note data with optimized structure"""
# 		rows = []
# 		total_current_month_amt = 0
# 		total_previous_month_amt = 0
# 		total_ftm_amt = 0
# 		total_previous_year = 0
# 		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		secondary_groups = sorted(set(g for g in frappe.get_list("GL Group Mapping", {"primary_group": primary_group, "company": company}, pluck="secondary_group") if g))

# 		for secondary_group in secondary_groups:
# 			ind_as_description = frappe.get_value("Standalone Group", secondary_group, 'ind_as_description')
# 			html_particulars = f"<b>{secondary_group}</b><br>{ind_as_description or ''}"
			
# 			current_month_amt = self.get_sum_grouping_amount(company, primary_group, secondary_group, self.current_month, self.fiscal_year)
# 			previous_month_amt = self.get_sum_grouping_amount(company, primary_group, secondary_group, self.previous_month, self.fiscal_year)
# 			ftm_amt = current_month_amt - previous_month_amt
# 			previous_year = self.get_sum_grouping_amount(company, primary_group, secondary_group, cls_month, self.previous_fiscal_year)

# 			if current_month_amt < 0:
# 				current_month_amt = -current_month_amt
# 			if previous_month_amt < 0:
# 				previous_month_amt = -previous_month_amt
# 			if ftm_amt < 0:
# 				ftm_amt = -ftm_amt
# 			if previous_year < 0:
# 				previous_year = -previous_year

# 			rows.append({
# 				"particulars": html_particulars,
# 				"current_month_amt": f"{current_month_amt:,.0f}" if current_month_amt else "-",
# 				"previous_month_amt": f"{previous_month_amt:,.0f}" if previous_month_amt else "-",
# 				"ftm_amt": f"{ftm_amt:,.0f}" if ftm_amt else "-",
# 				"previous_year": f"{previous_year:,.0f}" if previous_year else "-",
# 				"group": False
# 			})

# 			total_current_month_amt += current_month_amt or 0
# 			total_previous_month_amt += previous_month_amt or 0
# 			total_ftm_amt += ftm_amt or 0
# 			total_previous_year += previous_year or 0

# 		if total:
# 			if field == "total_current_month_amt":
# 				return total_current_month_amt
# 			elif field == "total_previous_year":
# 				return total_previous_year
# 			else:
# 				return 0

# 		# HTML rendering with optimized structure
# 		html = f'''
# 		<table style="width:100%; border-collapse:collapse; font-size:13px; margin-top: -25pt; border:1px solid #000;">
# 			<thead>
# 				<tr style = "border-bottom:2px solid #222;">
# 					<th style="border:1px solid #222; color: #4472C4; text-align:left; width:40%; padding:6px 8px;"><b>Particulars</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>{month_end_label}</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>FTM</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>{current_fiscal_year_end_label}</b></th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; padding:6px 8px;"><b>{previous_fiscal_year_end_label}</b></th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		'''

# 		for row in rows:
# 			bold = "font-weight: bold;" if row.get("group") else ""
# 			html += f'''
# 				<tr>
# 					<td style="border:1px solid #222; border-top:none; border-bottom:none; text-align:left; padding:6px 8px; {bold}">{row['particulars']}</td>
# 					<td style="border:1px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; background-color:#e8f5e8;">{row['current_month_amt']}</td>
# 					<td style="border:1px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row['ftm_amt']}</td>
# 					<td style="border:1px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row['previous_month_amt']}</td>
# 					<td style="border:1px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row['previous_year']}</td>
# 				</tr>
# 			'''

# 		# Append total row
# 		html += f'''
# 			<tr>
# 				<td style="border:1px solid #222; text-align:left; font-weight:bold; padding:6px 8px;">Total</td>
# 				<td style="border:1px solid #222; text-align:right; font-weight:bold; padding:6px 8px; background-color:#e8f5e8;">{total_current_month_amt:,.0f}</td>
# 				<td style="border:1px solid #222; text-align:right; font-weight:bold; padding:6px 8px;">{total_ftm_amt:,.0f}</td>
# 				<td style="border:1px solid #222; text-align:right; font-weight:bold; padding:6px 8px;">{total_previous_month_amt:,.0f}</td>
# 				<td style="border:1px solid #222; text-align:right; font-weight:bold; padding:6px 8px;">{total_previous_year:,.0f}</td>
# 			</tr>
# 		'''
# 		html += "</tbody></table>"
# 		return section_description.replace("{{note_table}}", html)

# 	def update_forgein_exchange_reserves_in_other_equity_data(self, current_month, previous_month, previous_year):
# 		data = self.get('financial_report_details',{'section_type': "Profit & Loss"})
# 		if not data:
# 			return []

# 		account = frappe.get_value("FR Particular",{'template_type': "Profit & Loss", 'type': "Foreign Exchange Difference"},'name')
# 		table_data_str = data[0].table_data or "[]"

# 		try:
# 			table_data = json.loads(table_data_str)
# 		except (json.JSONDecodeError, TypeError):
# 			table_data = []

# 		# ✅ INIT FLAG
# 		found_account = False

# 		# 1️⃣ Update Foreign Exchange Difference row
# 		for row in table_data:
# 			if row.get("id") == account:
# 				row["current_month_amount"] = round(current_month, self.show_decimal_value)
# 				row["previous_month_amount"] = round(previous_month, self.show_decimal_value)
# 				row["previous_year_amount"] = round(previous_year, self.show_decimal_value)
# 				row["ftm_amount"] = round(current_month - previous_month, self.show_decimal_value)
# 				found_account = True
# 			elif found_account:
# 				is_total = frappe.get_value("FR Particular", row.get("id"), "is_total")
# 				is_sub = frappe.get_value("FR Particular", row.get("id"), "to_subtract")
# 				if is_total and not is_sub:
# 					row["current_month_amount"] = round((row.get("current_month_amount") or 0) + current_month, self.show_decimal_value)
# 					row["previous_month_amount"] = round((row.get("previous_month_amount") or 0) + previous_month, self.show_decimal_value)
# 					row["previous_year_amount"] = round((row.get("previous_year_amount") or 0) + previous_year, self.show_decimal_value)
# 					row["ftm_amount"] = round(row["current_month_amount"] - row["previous_month_amount"], self.show_decimal_value)
# 				if is_total and is_sub:
# 					row["current_month_amount"] = round((row.get("current_month_amount") or 0) - current_month, self.show_decimal_value)
# 					row["previous_month_amount"] = round((row.get("previous_month_amount") or 0) - previous_month, self.show_decimal_value)
# 					row["previous_year_amount"] = round((row.get("previous_year_amount") or 0) - previous_year, self.show_decimal_value)
# 					row["ftm_amount"] = round(((row.get("current_month_amount") or 0) - current_month) - ((row.get("previous_month_amount") or 0) - previous_month), self.show_decimal_value)
# 		data[0].table_data = json.dumps(table_data)
# 		_, data[0].section_description = self.render_monthly_profit_and_loss(data[0].section, table_data)

# 	def update_other_equity(self, current_month, previous_month, previous_year):
# 		bs_data = self.get('financial_report_details',{'section_type': "Balance Sheet"})
# 		other_equity_account = frappe.get_value("FR Particular",{'template_type': "Balance Sheet", 'particular_type': "Other Equity"},'name')
# 		equity_share_cap_account = frappe.get_value("FR Particular",{'template_type': "Balance Sheet", 'particular_type': "Equity Share Capital"},'name')
# 		total_equity_account = frappe.get_value("FR Particular",{'template_type': "Balance Sheet", 'particular_type': "Total Equity"},'name')
# 		tot_cur_liab = frappe.get_value("FR Particular",{'template_type': "Balance Sheet", 'particular_type': "Total Current Liabilities"},'name')
# 		tot_non_cur_liab = frappe.get_value("FR Particular",{'template_type': "Balance Sheet", 'particular_type': "Total Non Current Liabilities"},'name')
# 		tot_liab = frappe.get_value("FR Particular",{'template_type': "Balance Sheet", 'particular_type': "Total Liabilities"},'name')
# 		bs_table_data_str = bs_data[0].table_data if bs_data else "[]"
# 		try:
# 			bs_table_data = json.loads(bs_table_data_str)
# 		except (json.JSONDecodeError, TypeError):
# 			bs_table_data = []
		
# 		for row in bs_table_data:
# 			if row.get("id") == equity_share_cap_account:
# 				equity_share_cap_current = row.get("current_month_amount") or 0
# 				equity_share_cap_previous_year = row.get("previous_year_amount") or 0
# 			elif row.get("id") == other_equity_account:
# 				row["current_month_amount"] = current_month
# 				row["previous_year_amount"] = previous_year
# 			elif row.get("id") == total_equity_account:
# 				row["current_month_amount"] = round(equity_share_cap_current + current_month, self.show_decimal_value)
# 				row["previous_year_amount"] = round(equity_share_cap_previous_year + previous_year, self.show_decimal_value)
# 			elif row.get("id") == tot_cur_liab:
# 				tot_cur_liab_current = row.get("current_month_amount") or 0
# 				tot_cur_liab_previous_year = row.get("previous_year_amount") or 0
# 			elif row.get("id") == tot_non_cur_liab:
# 				tot_non_cur_liab_current = row.get("current_month_amount") or 0
# 				tot_non_cur_liab_previous_year = row.get("previous_year_amount") or 0
# 			elif row.get("id") == tot_liab:
# 				row["current_month_amount"] = round(tot_cur_liab_current + tot_non_cur_liab_current + equity_share_cap_current + current_month, self.show_decimal_value)
# 				row["previous_year_amount"] = round(tot_cur_liab_previous_year + tot_non_cur_liab_previous_year + equity_share_cap_previous_year + previous_year, self.show_decimal_value)
# 		bs_data[0].table_data = json.dumps(bs_table_data)
# 		_, bs_data[0].section_description = self.render_monthly_balance_sheet(bs_data[0].section, bs_table_data)
	
# 	def get_monthly_other_equity_note_data(self, company, note_type, total=False, field=None):
# 		cache_key = f"{company}_{note_type}"

# 		if cache_key in self._other_equity_full_cache:
# 			data = self._other_equity_full_cache[cache_key]
# 		else:
# 			# ---- Securities Premium ----
# 			sp_previous_year = 0
# 			sp_current = 0
# 			sp_previous = 0

# 			# ---- Forex ----
# 			forex_open = 0
# 			forex_add_curr = 0
# 			forex_add_prev = 0
# 			forex_add_prev_year = 0

# 			forex_close_curr = forex_open + forex_add_curr
# 			forex_close_prev = forex_open + forex_add_prev

# 			# ---- Retained Earnings ----
# 			bal_current = 0
# 			bal_previous = 0
# 			bal_prev_year = 0

# 			net_current, net_prev, net_prev_year = self.get_monthly_profit_and_loss_data(
# 				None, fetch_for_other_equity=True
# 			)

# 			oci_current = 0
# 			oci_previous = 0
# 			oci_prev_year = 0

# 			retained_current = bal_current + net_current + oci_current
# 			retained_prev = bal_previous + net_prev + oci_previous
# 			retained_prev_year = bal_prev_year + net_prev_year + oci_prev_year

# 			# ---- Capital Contribution ----
# 			cc_open_curr = 0
# 			cc_open_prev = 0
# 			cc_open_prev_year = 0

# 			cc_add_curr = 0
# 			cc_add_prev = 0
# 			cc_add_prev_year = 0

# 			cc_close_curr = cc_open_curr + cc_add_curr
# 			cc_close_prev = cc_open_prev + cc_add_prev
# 			cc_close_prev_year = cc_open_prev_year + cc_add_prev_year

# 			# ---- TOTAL ----
# 			total_current = sp_current + forex_close_curr + retained_current + cc_close_curr
# 			total_previous = sp_previous + forex_close_prev + retained_prev + cc_close_prev
# 			total_prev_year = sp_previous_year + forex_open + retained_prev_year + cc_close_prev_year

# 			data = {
# 				"sp": {"current": sp_current, "previous": sp_previous, "previous_year": sp_previous_year},
# 				"forex": {
# 					"opening": {"current": forex_open, "previous": forex_open, "previous_year": forex_open},
# 					"addition": {"current": forex_add_curr, "previous": forex_add_prev, "previous_year": forex_add_prev_year},
# 					"closing": {"current": forex_close_curr, "previous": forex_close_prev, "previous_year": forex_open},
# 				},
# 				"retained": {
# 					"opening": {"current": bal_current, "previous": bal_previous, "previous_year": bal_prev_year},
# 					"net": {"current": net_current, "previous": net_prev, "previous_year": net_prev_year},
# 					"oci": {"current": oci_current, "previous": oci_previous, "previous_year": oci_prev_year},
# 					"closing": {"current": retained_current, "previous": retained_prev, "previous_year": retained_prev_year},
# 				},
# 				"cc": {
# 					"opening": {"current": cc_open_curr, "previous": cc_open_prev, "previous_year": cc_open_prev_year},
# 					"addition": {"current": cc_add_curr, "previous": cc_add_prev, "previous_year": cc_add_prev_year},
# 					"closing": {"current": cc_close_curr, "previous": cc_close_prev, "previous_year": cc_close_prev_year},
# 				},
# 				"total": {"current": total_current, "previous": total_previous, "previous_year": total_prev_year},
# 			}

# 			self._other_equity_full_cache[cache_key] = data

# 		if total:
# 			return data["total"].get(field.replace("grand_total_", ""), 0)

# 		return data
# 	# def get_monthly_other_equity_note_data(self, company, section_description, total=False, field=None):
# 	# 	"""Generate monthly Other Equity note table (Retained Earnings & Capital Contribution)"""
# 	# 	cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 	# 	month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
# 	# 	p_and_l_template = self.get('financial_report_details', {'section_type': "Profit & Loss"})[0].section
# 	# 	bs_template = self.get('financial_report_details', {'section_type': "Balance Sheet"})[0].section
# 	# 	net_current_mnt, net_previous_mnt, net_previous_year = self.get_monthly_profit_and_loss_data(p_and_l_template, fetch_for_other_equity=True)

# 	# 	default_currency = frappe.get_value("Company", company, 'default_currency')
# 	# 	if default_currency != self.currency:
# 	# 		sp_previous_year = round(frappe.get_value("Other Equity Opening Entry", {'company': company, 'fiscal_year': pre_year}, 'share_premium_inr') or 0, self.show_decimal_value) or 0
# 	# 		bal_previous_year = round(frappe.get_value("Other Equity Opening Entry", {'company': company, 'fiscal_year': pre_year}, 'pl_inr') or 0, self.show_decimal_value) or 0

# 	# 		tot_asset = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account=frappe.get_value("FR Particular", {'particular_type': 'Total Assets'}, 'name'))
# 	# 		curr_mnt_tot_asset = tot_asset['current_month_amount']
# 	# 		prev_mnt_tot_asset = tot_asset['previous_month_amount']
# 	# 		prev_yr_mnt_tot_asset = tot_asset['previous_year']

# 	# 		tot_cur_lib = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account=frappe.get_value("FR Particular", {'particular_type': 'Total Current Liabilities'}, 'name'))
# 	# 		curr_mnt_tot_cur_lib = tot_cur_lib['current_month_amount']
# 	# 		prev_mnt_tot_cur_lib = tot_cur_lib['previous_month_amount']
# 	# 		prev_yr_mnt_tot_cur_lib = tot_cur_lib['previous_year']

# 	# 		tot_n_cur_lib = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account=frappe.get_value("FR Particular", {'particular_type': 'Total Non Current Liabilities'}, 'name'))
# 	# 		curr_mnt_tot_n_cur_lib = tot_n_cur_lib['current_month_amount']
# 	# 		prev_mnt_tot_n_cur_lib = tot_n_cur_lib['previous_month_amount']
# 	# 		prev_yr_mnt_tot_n_cur_lib = tot_n_cur_lib['previous_year']

# 	# 		equity_share = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True,account=frappe.get_value("FR Particular", {'particular_type': 'Equity Share Capital'}, 'name'))
# 	# 		curr_mnt_equity_share = equity_share['current_month_amount']
# 	# 		prev_mnt_equity_share = equity_share['previous_month_amount']
# 	# 		prev_yr_mnt_equity_share = equity_share['previous_year']

# 	# 	else:
# 	# 		sp_previous_year = round(self.get_sum_grouping_amount(company, "Other Equity", "Other equity - Share Premium", cls_month, self.previous_fiscal_year, self.show_decimal_value), self.show_decimal_value) or 0
# 	# 		sp_previous_year = -sp_previous_year if sp_previous_year < 0 else sp_previous_year
# 	# 		bal_previous_year = -round(self.get_sum_grouping_amount(company, "Other Equity", "Other equity - Retained earnings", cls_month, self.previous_fiscal_year, self.show_decimal_value), self.show_decimal_value) or 0

# 	# 	# --- Retained Earnings ---
# 	# 	oci_previous_year = round(self.get_sum_grouping_amount(company, "OCI", "OCI", cls_month, self.previous_fiscal_year), self.show_decimal_value) or 0
# 	# 	retained_tot_prev_year = round(bal_previous_year + net_previous_year + oci_previous_year, self.show_decimal_value)

# 	# 	bal_current_mnt = retained_tot_prev_year
# 	# 	bal_previous_mnt = retained_tot_prev_year

# 	# 	oci_current_mnt = round(self.get_sum_grouping_amount(company, "OCI", "OCI", self.current_month, self.fiscal_year), self.show_decimal_value) or 0
# 	# 	oci_previous_mnt = round(self.get_sum_grouping_amount(company, "OCI", "OCI", self.previous_month, self.fiscal_year), self.show_decimal_value) or 0

# 	# 	retained_tot_current = round(bal_current_mnt + net_current_mnt + oci_current_mnt, self.show_decimal_value)
# 	# 	retained_tot_prev = round(bal_previous_mnt + net_previous_mnt + oci_previous_mnt, self.show_decimal_value)

# 	# 	# --- Capital Contribution ---
# 	# 	cc_opening_previous_year = round(self.get_sum_grouping_amount(company, "Other Equity", "Other equity - Capital Contribution", cls_month, pre_year), self.show_decimal_value) or 0
# 	# 	cc_add_previous_year = (round(self.get_sum_grouping_amount(company, "Other Equity", "Other equity - Capital Contribution", cls_month, self.previous_fiscal_year), self.show_decimal_value) or 0) - cc_opening_previous_year
# 	# 	cc_closing_previous_year = round(cc_opening_previous_year + cc_add_previous_year, self.show_decimal_value)
# 	# 	cc_opening_current = cc_closing_previous_year
# 	# 	cc_opening_previous = cc_closing_previous_year

# 	# 	cc_add_current = round((self.get_sum_grouping_amount(company, "Other Equity", "Other equity - Capital Contribution", self.current_month, self.fiscal_year) or 0) - cc_opening_current, self.show_decimal_value)
# 	# 	cc_add_previous = round((self.get_sum_grouping_amount(company, "Other Equity", "Other equity - Capital Contribution", self.previous_month, self.fiscal_year) or 0) - cc_opening_previous, self.show_decimal_value)

# 	# 	cc_closing_current = round(cc_opening_current + cc_add_current, self.show_decimal_value)
# 	# 	cc_closing_previous = round(cc_opening_previous + cc_add_previous, self.show_decimal_value)

# 	# 	bal_sp_tot_current = sp_previous_year
# 	# 	bal_sp_tot_prev = sp_previous_year

# 	# 	# --- Surplus in Foreign Exchange Reserves ---
# 	# 	if default_currency != self.currency:
# 	# 		for_exc_previous_year = 0
# 	# 		curr_add_for_exc_res = round(curr_mnt_tot_asset - (curr_mnt_tot_cur_lib + curr_mnt_tot_n_cur_lib + curr_mnt_equity_share) - retained_tot_current - sp_previous_year, self.show_decimal_value) or 0
# 	# 		prev_add_for_exc_res = round(prev_mnt_tot_asset - (prev_mnt_tot_cur_lib + prev_mnt_tot_n_cur_lib + prev_mnt_equity_share) - retained_tot_prev - sp_previous_year, self.show_decimal_value) or 0
# 	# 		add_for_exc_previous_year = round(prev_yr_mnt_tot_asset - (prev_yr_mnt_tot_cur_lib + prev_yr_mnt_tot_n_cur_lib + prev_yr_mnt_equity_share) - retained_tot_prev_year - sp_previous_year, self.show_decimal_value) or 0
# 	# 	else:
# 	# 		for_exc_previous_year = -round(self.get_sum_grouping_amount(company, "Other Equity", "Opening - Currency Fluctuation", cls_month, self.previous_fiscal_year), self.show_decimal_value) or 0
# 	# 		add_for_exc_previous_year = -round(self.get_sum_grouping_amount(company, "Other Equity", "Currency Fluctuation", cls_month, self.previous_fiscal_year), self.show_decimal_value) or 0
# 	# 		curr_add_for_exc_res = -round(self.get_sum_grouping_amount(company, "Other Equity", "Currency Fluctuation", self.current_month, self.fiscal_year), self.show_decimal_value) or 0
# 	# 		prev_add_for_exc_res = -round(self.get_sum_grouping_amount(company, "Other Equity", "Currency Fluctuation", self.previous_month, self.fiscal_year), self.show_decimal_value) or 0

# 	# 	prev_year_for_exc_res_tot = round(for_exc_previous_year + add_for_exc_previous_year, self.show_decimal_value)
# 	# 	curr_add_for_exc_res = curr_add_for_exc_res - prev_year_for_exc_res_tot
# 	# 	prev_add_for_exc_res = prev_add_for_exc_res - prev_year_for_exc_res_tot
# 	# 	curr_for_exc_res_tot = round(prev_year_for_exc_res_tot + curr_add_for_exc_res, self.show_decimal_value)
# 	# 	prev_for_exc_res_tot = round(prev_year_for_exc_res_tot + prev_add_for_exc_res, self.show_decimal_value)

# 	# 	# --- Grand Totals ---
# 	# 	grand_total_current = round(retained_tot_current + cc_closing_current + sp_previous_year + curr_for_exc_res_tot, self.show_decimal_value)
# 	# 	grand_total_previous = round(retained_tot_prev + cc_closing_previous + sp_previous_year + prev_for_exc_res_tot, self.show_decimal_value)
# 	# 	grand_total_prev_year = round(retained_tot_prev_year + cc_closing_previous_year + sp_previous_year + prev_year_for_exc_res_tot, self.show_decimal_value)

# 	# 	# --- Return if only total requested ---
# 	# 	if total and field:
# 	# 		if field == "grand_total_current":
# 	# 			return grand_total_current
# 	# 		elif field == "grand_total_prev_year":
# 	# 			return grand_total_prev_year
# 	# 		else:
# 	# 			return 0

# 	# 	# self.update_forgein_exchange_reserves_in_other_equity_data(curr_add_for_exc_res, prev_add_for_exc_res, add_for_exc_previous_year)
# 	# 	# self.update_other_equity(grand_total_current, grand_total_previous, grand_total_prev_year)

# 	# 	return {
# 	# 		"sp": {
# 	# 			"current": sp_current_month, "previous": sp_current_fy, "previous_year": sp_previous_year,
# 	# 		},
# 	# 		"forex": {
# 	# 			"opening": {
# 	# 				"current": prev_year_for_exc_res, "previous": prev_year_for_exc_res, "previous_year": prev_year_for_exc_res,
# 	# 			},
# 	# 			"addition": {
# 	# 				"current": curr_add_for_exc_res, "previous": prev_add_for_exc_res, "previous_year": add_for_exc_previous_year,
# 	# 			},
# 	# 			"closing": {
# 	# 				"current": curr_for_exc_res_tot, "previous": prev_for_exc_res_tot, "previous_year": prev_year_for_exc_res,
# 	# 			},
# 	# 		},
# 	# 		"retained": {
# 	# 			"opening": {
# 	# 				"current": bal_current_mnt, "previous": bal_previous_mnt, "previous_year": bal_previous_year,
# 	# 			},
# 	# 			"net": {
# 	# 				"current": net_current_mnt, "previous": net_previous_mnt, "previous_year": net_previous_year,
# 	# 			},
# 	# 			"oci": {
# 	# 				"current": oci_current_mnt, "previous": oci_previous_mnt, "previous_year": oci_previous_year,
# 	# 			},
# 	# 			"closing": {
# 	# 				"current": retained_tot_current, "previous": retained_tot_prev, "previous_year": retained_tot_prev_year,
# 	# 			},
# 	# 		},
# 	# 		"cc": {
# 	# 			"opening": {
# 	# 				"current": cc_opening_current, "previous": cc_opening_previous, "previous_year": cc_opening_previous_year,
# 	# 			},
# 	# 			"addition": {
# 	# 				"current": cc_add_current, "previous": cc_add_previous, "previous_year": cc_add_previous_year,
# 	# 			},
# 	# 			"closing": {
# 	# 				"current": cc_closing_current, "previous": cc_closing_previous, "previous_year": cc_closing_previous_year,
# 	# 			},
# 	# 		},
# 	# 		"total": {
# 	# 			"current": grand_total_current, "previous": grand_total_previous, "previous_year": grand_total_prev_year,
# 	# 		}
# 	#	}
		

# 	def get_monthly_equity_share_capital_note_data(self, company, section_description):
# 		_, current_month_date = self.get_month_date_range(self.current_month, self.fiscal_year)
# 		month_end_label, prev_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
# 		current_date = month_end_label.replace("Year Ended ", "").replace("/", "-")
# 		previous_date = previous_fiscal_year_end_label.replace("Year Ended ", "").replace("/", "-")

# 		company_currency = frappe.get_value("Company", company, "default_currency")
# 		currency = self.currency if self.currency != company_currency else company_currency

# 		headers = ["Particulars",f"As at {current_date}", "",f"As at {previous_date}", ""]
# 		sub_headers = ["","No. of shares", f"{currency} in Lacs","No. of shares", f"{currency} in Lacs"]

# 		def get_equity_data(entry_type, date, amt_field):
# 			data = frappe.db.get_values("FR Equity Entry", {"company": company, "type": entry_type, "date": ["<=", date]}, ["sum(no_of_shares) as shares", f"sum({amt_field}) as amount", "face_value"], as_dict=True)
# 			row = data[0] if data else {}
# 			return (row.get("face_value") or "-",row.get("shares") or 0, round(row.get("amount")/100000, self.show_decimal_value or 0))

# 		amt_field = "investment_inr" if self.currency != company_currency else "investment_value"

# 		face_value, curr_auth_shares, curr_auth_amt = get_equity_data("Authorised", current_month_date, amt_field)
# 		_, curr_issue_shares, curr_issue_amt = get_equity_data("Issued", current_month_date, amt_field)
# 		_, pre_auth_shares, pre_auth_amt = get_equity_data("Authorised", self.previous_year_ending_date, amt_field)
# 		_, pre_issue_shares, pre_issue_amt = get_equity_data("Issued", self.previous_year_ending_date, amt_field)

# 		rows = [
# 			["Equity Share Capital", "", "", "", ""],
# 			["Authorised", "", "", "", ""],
# 			[f"Equity Shares of {face_value} each",curr_auth_shares, curr_auth_amt,pre_auth_shares, pre_auth_amt],
# 			["Issued, Subscribed and Fully Paid", "", "", "", ""],
# 			[f"Equity Shares of {face_value} each",curr_issue_shares, curr_issue_amt,pre_issue_shares, pre_issue_amt],
# 			["Total", curr_issue_shares, curr_issue_amt,pre_issue_shares, pre_issue_amt],
# 		]

# 		html = """<table style="width:100%; border-collapse:collapse; font-size:13px;">
# 		<thead>"""

# 		html += "<tr>"
# 		for idx, h in enumerate(headers):
# 			colspan = " colspan='2'" if idx in (1, 3) else ""
# 			width = "width:30%;" if idx == 0 else ""
# 			if h:
# 				html += f"<th{colspan} style='border:1px solid #000; padding:5px; text-align:center; {width}'>{h}</th>"
# 		html += "</tr>"

# 		html += "<tr>"
# 		for idx, sh in enumerate(sub_headers):
# 			width = "width:30%;" if idx == 0 else ""
# 			html += f"<th style='border:1px solid #000; padding:5px; text-align:center; {width}'>{sh}</th>"
# 		html += "</tr>"

# 		html += "</thead><tbody>"

# 		for row in rows:
# 			is_section = row[0] and all(not c for c in row[1:])
# 			html += "<tr>"
# 			for idx, col in enumerate(row):
# 				width = "width:30%;" if idx == 0 else ""
# 				style = "font-weight:bold;" if is_section and idx == 0 else ""
# 				html += f"<td style='border:1px solid #000; padding:5px; {width} {style}'>{col}</td>"
# 			html += "</tr>"

# 		html += "</tbody></table>"
# 		return section_description.replace("{{note_table}}", html)

# 	def get_monthly_trade_and_other_receivables_note_data(self, section_description):
# 		"""Get monthly trade and other receivables note data with optimized structure"""
# 		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
# 		cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")
# 		companies = frappe.get_all("Company", pluck="name")
# 		credit_impaired_current = credit_impaired_previous = credit_impaired_prev_year = 0
# 		trade_receivables_current = trade_receivables_previous = trade_receivables_prev_year = 0
# 		other_receivables_current = other_receivables_previous = other_receivables_prev_year = 0

# 		for company in companies:
# 			default_currency = frappe.get_value("Company", company, 'default_currency')
# 			current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, "closing_rate") if default_currency != self.currency else 1
# 			previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, "closing_rate") if default_currency != self.currency else 1
# 			prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, "closing_rate") if default_currency != self.currency else 1

# 			credit_impaired_current += ((self.get_sum_grouping_amount(company, "Trade Receivables - credit Impaired", "Trade Receivables - credit Impaired", self.current_month, self.fiscal_year)) or 0) * current_fx
# 			credit_impaired_previous += ((self.get_sum_grouping_amount(company, "Trade Receivables - credit Impaired", "Trade Receivables - credit Impaired", self.previous_month, self.fiscal_year)) or 0) * previous_fx
# 			credit_impaired_prev_year += ((self.get_sum_grouping_amount(company, "Trade Receivables - credit Impaired", "Trade Receivables - credit Impaired", cls_month, self.previous_fiscal_year)) or 0) * prev_year_fx

# 			trade_receivables_current += ((self.get_sum_grouping_amount(company, "Trade Receivables", "Trade Receivables", self.current_month, self.fiscal_year)) or 0) * current_fx
# 			trade_receivables_previous += ((self.get_sum_grouping_amount(company, "Trade Receivables", "Trade Receivables", self.previous_month, self.fiscal_year)) or 0) * previous_fx
# 			trade_receivables_prev_year += ((self.get_sum_grouping_amount(company, "Trade Receivables", "Trade Receivables", cls_month, self.previous_fiscal_year)) or 0) * prev_year_fx

# 			other_receivables_current += ((self.get_sum_grouping_amount(company, "Trade Receivables", "Other Trade receivables", self.current_month, self.fiscal_year)) or 0) * current_fx
# 			other_receivables_previous += ((self.get_sum_grouping_amount(company, "Trade Receivables", "Other Trade receivables", self.previous_month, self.fiscal_year)) or 0) * previous_fx
# 			other_receivables_prev_year += ((self.get_sum_grouping_amount(company, "Trade Receivables", "Other Trade receivables", cls_month, self.previous_fiscal_year)) or 0) * prev_year_fx


# 		credit_impaired_current = round(credit_impaired_current, self.show_decimal_value)
# 		credit_impaired_previous = round(credit_impaired_previous, self.show_decimal_value)
# 		credit_impaired_prev_year = round(credit_impaired_prev_year, self.show_decimal_value)

# 		trade_receivables_current = round(trade_receivables_current, self.show_decimal_value)
# 		trade_receivables_previous = round(trade_receivables_previous, self.show_decimal_value)
# 		trade_receivables_prev_year = round(trade_receivables_prev_year, self.show_decimal_value)

# 		other_receivables_current = round(other_receivables_current, self.show_decimal_value)
# 		other_receivables_previous = round(other_receivables_previous, self.show_decimal_value)
# 		other_receivables_prev_year = round(other_receivables_prev_year, self.show_decimal_value)

# 		unsecured_good_current = trade_receivables_current + credit_impaired_current
# 		unsecured_good_previous = trade_receivables_previous + credit_impaired_previous
# 		unsecured_good_prev_year = trade_receivables_prev_year + credit_impaired_prev_year

# 		total_current = unsecured_good_current + other_receivables_current
# 		total_previous = unsecured_good_previous + other_receivables_previous
# 		total_prev_year = unsecured_good_prev_year + other_receivables_prev_year

# 		main_table = [
# 		    ("Unsecured, considered good", unsecured_good_current, unsecured_good_previous, unsecured_good_prev_year, False),
# 		    ("Credit impaired", -credit_impaired_current, credit_impaired_previous, credit_impaired_prev_year, False),
# 		    ("", trade_receivables_current, trade_receivables_previous, trade_receivables_prev_year, False),
# 		    ("Less: Provision for credit impaired trade receivables", -credit_impaired_current, credit_impaired_previous, credit_impaired_prev_year, False),
# 		    ("Other receivables", "", "", "", True),
# 		    ("Unsecured, considered good", other_receivables_current, other_receivables_previous, other_receivables_prev_year, False),
# 		    ("Total", total_current, total_previous, total_prev_year, True),
# 	    ]


# 		# Main Table
# 		html = f'''
# 		<table style="width:100%; border-collapse:collapse; border-spacing:0; font-size:13px; margin-top:-25pt; border:1px solid #000;">
# 			<thead>
# 				<tr style="color: #4472C4; background-color: #E8F5E8;">
# 					<th style="border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; width:40%; padding:2px 5px; text-align:left;">Particulars</th>
# 					<th style="border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:2px 5px; text-align:center; background-color: #E8F5E8;">{month_end_label}</th>
# 					<th style="border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:2px 5px; text-align:center;">{current_fiscal_year_end_label}</th>
# 					<th style="border-left:1px solid #222; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:2px 5px; text-align:center;">{previous_fiscal_year_end_label}</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		'''
# 		for i, row in enumerate(main_table):
# 			is_last = i == len(main_table) - 1
# 			style = "font-weight:bold;" if row[4] else ""
# 			# Only vertical borders for regular rows, full borders for last (Total) row
# 			if is_last:
# 				border = "border:1px solid #222;"
# 			else:
# 				border = "border-left:1px solid #222; border-right:1px solid #222; border-top:none; border-bottom:none;"

# 			html += f'''
# 			<tr style="line-height: 1; border:none;">
# 				<td style="{border} padding:2px 5px; text-align:left; {style}">{row[0]}</td>
# 				<td style="{border} padding:2px 5px; text-align:right; {style} background-color: #E8F5E8;">{row[1]}</td>
# 				<td style="{border} padding:2px 5px; text-align:right; {style}">{row[2]}</td>
# 				<td style="{border} padding:2px 5px; text-align:right; {style}">{row[3]}</td>
# 			</tr>
# 			'''
# 		html += "</tbody></table>"
# 		return section_description.replace("{{note_table}}", html)

# 	def get_monthly_investment_non_current_note_data(self, holding_company, section_description, total=False, field=None):
# 		_, current_month_date = self.get_month_date_range(self.current_month, self.fiscal_year)
# 		_, previous_month_date = self.get_month_date_range(self.previous_month, self.fiscal_year)

# 		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
# 		total_current = total_previous = total_previous_year = 0
# 		prev_fs_year_end_date = self.previous_year_ending_date
# 		data = [{
# 			"particulars": "Investment in equity Instruments of subsidiaries measured at Cost (Unquoted, Fully paid Up)",
# 			"face_value": "", "shares_current": "", "amount_current": "","shares_previous": "", "amount_previous": "","shares_previous_year": "", "amount_previous_year": "","bold": 1
# 		}]

# 		all_companies = set(frappe.get_list("FR Investment Entry",filters={"holding_company": holding_company},pluck="company"))
# 		for company in all_companies:
# 			default_currency = frappe.get_value("Company", company, "default_currency")
# 			current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, "closing_rate") if default_currency != "INR" else 1
# 			previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, "closing_rate") if default_currency != "INR" else 1
# 			prev_year_fx = self.get_fx_rate(default_currency, self._closing_month, self.previous_fiscal_year, "closing_rate") if default_currency != "INR" else 1

# 			e_previous_year = self.fetch_equity_data(holding_company, company, ["<=", prev_fs_year_end_date])
# 			e_previous = self.fetch_equity_data(holding_company, company, ["<=", previous_month_date])
# 			e_current = self.fetch_equity_data(holding_company, company, ["<=", current_month_date])

# 			e_previous_year = e_previous_year[0] if e_previous_year else {}
# 			e_previous = e_previous[0] if e_previous else {}
# 			e_current = e_current[0] if e_current else {}

# 			shares_current = e_current.get("no_of_shares", 0) or 0
# 			shares_previous = e_previous.get("no_of_shares", 0) or 0
# 			shares_previous_year = e_previous_year.get("no_of_shares", 0) or 0

# 			current_val = e_current.get("investment_value_fc", 0) or 0
# 			previous_val = e_previous.get("investment_value_fc", 0) or 0
# 			prev_year_val = e_previous_year.get("investment_value_fc", 0) or 0

# 			amount_current = current_val * current_fx
# 			amount_previous = previous_val * previous_fx
# 			amount_previous_year = prev_year_val * prev_year_fx

# 			total_current += amount_current
# 			total_previous += amount_previous
# 			total_previous_year += amount_previous_year
# 			face_value = f"{e_current.get('face_value', 0)} {default_currency}"

# 			data.append({
# 			    "particulars": company,
# 			    "face_value": face_value,
# 			    "shares_current": shares_current,
# 			    "amount_current": flt(round(amount_current / 100000, self.show_decimal_value)),
# 			    "shares_previous": shares_previous,
# 			    "amount_previous": flt(round(amount_previous / 100000, self.show_decimal_value)),
# 			    "shares_previous_year": shares_previous_year,
# 			    "amount_previous_year": flt(round(amount_previous_year / 100000, self.show_decimal_value)),
# 			    "bold": 0
# 		    })

# 		if total:
# 			if field == "total_current":
# 				return total_current / 100000
# 			if field == "total_previous_year":
# 				return total_previous_year / 100000

# 		data.append({
# 		    "particulars": "Total of Equity Instruments Measured at cost",
# 		    "face_value": "",
# 		    "shares_current": "",
# 		    "amount_current": f"{total_current/100000:,.2f}",
# 		    "shares_previous": "",
# 		    "amount_previous": f"{total_previous/100000:,.2f}",
# 		    "shares_previous_year": "",
# 		    "amount_previous_year": f"{total_previous_year/100000:,.2f}",
# 		    "bold": 1
# 	    })
		
# 		# HTML table
# 		table = f'''
# 		<table style="width:100%; border-collapse:collapse; font-size:12px; margin-top:-25pt; border:1px solid #000; background-color:#fff;">
# 			<thead>
# 				<tr style="border-bottom:2px solid #222; background-color:#fff;">
# 					<th rowspan="2" style="border:1px solid #222; color: #4472C4; width:25%; text-align:left; padding:6px 8px; background-color:#fff;"><b>Particulars</b></th>
# 					<th rowspan="2" style="border:1px solid #222; color: #4472C4; width:10%; text-align:center; background-color:#fff;"><b>Face Value</b></th>
# 					<th colspan="2" style="border:1px solid #222; color: #4472C4; text-align:center; background-color:#fff;"><b>{month_end_label}</b></th>
# 					<th colspan="2" style="border:1px solid #222; color: #4472C4; text-align:center; background-color:#fff;"><b>{current_fiscal_year_end_label}</b></th>
# 					<th colspan="2" style="border:1px solid #222; color: #4472C4; text-align:center; background-color:#fff;"><b>{previous_fiscal_year_end_label}</b></th>
# 				</tr>
# 				<tr style="background-color:#fff;">
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; background-color:#fff;">No. of Shares</th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; background-color:#fff;">(₹ in lacs)</th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; background-color:#fff;">No. of Shares</th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; background-color:#fff;">(₹ in lacs)</th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; background-color:#fff;">No. of Shares</th>
# 					<th style="border:1px solid #222; color: #4472C4; text-align:center; background-color:#fff;">(₹ in lacs)</th>
# 				</tr>
# 			</thead>
# 			<tbody>
# 		'''

# 		for row in data:
# 			bold = "font-weight: bold;" if row["bold"] else ""

# 			table += f'''
# 			<tr style="background-color:#fff;">
# 				<td style="border:1px solid #222; padding:6px 8px; text-align:left; background-color:#fff; {bold}">{row["particulars"]}</td>
# 				<td style="border:1px solid #222; text-align:center; background-color:#fff;">{row["face_value"]}</td>
# 				<td style="border:1px solid #222; text-align:right; background-color:#fff;">{row["shares_current"]}</td>
# 				<td style="border:1px solid #222; text-align:right; background-color:#fff;">{row["amount_current"]}</td>
# 				<td style="border:1px solid #222; text-align:right; background-color:#fff;">{row["shares_previous"]}</td>
# 				<td style="border:1px solid #222; text-align:right; background-color:#fff;">{row["amount_previous"]}</td>
# 				<td style="border:1px solid #222; text-align:right; background-color:#fff;">{row["shares_previous_year"]}</td>
# 				<td style="border:1px solid #222; text-align:right; background-color:#fff;">{row["amount_previous_year"]}</td>
# 			</tr>
# 			'''

# 		table += "</tbody></table>"
# 		return section_description.replace("{{note_type}}", table)

# 	@frappe.whitelist()
# 	def export_to_excel(self):
# 		"""Export financial report to Excel with multiple tabs"""
# 		doc = frappe.get_doc("Financial Report", self.name)
# 		wb = openpyxl.Workbook()
# 		wb.remove(wb.active)
# 		sch_counter = 4
		
# 		# Debug: Print all sections
# 		frappe.logger().info(f"Total sections: {len(doc.financial_report_details)}")
		
# 		for section_detail in doc.financial_report_details:
# 			if not section_detail.section_description:
# 				continue
# 			if section_detail.section_type == "Consolidation Note":
# 				sheet_name = f"SCH-{sch_counter}"
# 				if section_detail.section_name:
# 					section_title = f" Note {sch_counter}: {section_detail.section_name}"
# 				else:
# 					continue
# 				sch_counter += 1
# 			else:
# 				sheet_name = section_detail.section_type.replace(" & ", "_").replace(" ", "_")
# 				section_title = section_detail.section_type
			
# 			ws = wb.create_sheet(title=sheet_name)
			
# 			title_cell = ws.cell(row=1, column=1, value=section_title)
# 			title_cell.font = Font(bold=True, size=14)
# 			title_cell.alignment = Alignment(horizontal='left')
			
# 			# Merge cells for title (assuming max 10 columns)
# 			ws.merge_cells('A1:E1')
			
# 			row_offset = 2
# 			section_description = section_detail.section_description
			
# 			soup = BeautifulSoup(section_description, 'html.parser')
# 			table = soup.find('table')
			
# 			if table:
# 				rows = table.find_all('tr')
# 				for row_idx, row in enumerate(rows, 1):
# 					cells = row.find_all(['td', 'th'])
# 					for col_idx, cell in enumerate(cells, 1):
# 						cell_value = cell.get_text(strip=True)
# 						ws.cell(row=row_idx + row_offset, column=col_idx, value=cell_value)
						
# 						cell_obj = ws.cell(row=row_idx + row_offset, column=col_idx)
						
# 						# Check if it's a header (th) or has background color
# 						if cell.name == 'th' or 'background-color: #e8f5e8' in str(cell):
# 							cell_obj.fill = PatternFill(start_color="E8F5E8", end_color="E8F5E8", fill_type="solid")
# 							cell_obj.font = Font(bold=True)
						
# 						# Apply borders
# 						thin_border = Border(
# 							left=Side(style='thin'),
# 							right=Side(style='thin'),
# 							top=Side(style='thin'),
# 							bottom=Side(style='thin')
# 						)
# 						cell_obj.border = thin_border
						
# 						# Center align headers
# 						if cell.name == 'th':
# 							cell_obj.alignment = Alignment(horizontal='center', vertical='center')
# 						else:
# 							# Right align numeric values
# 							if cell_value and cell_value.replace(',', '').replace('-', '').replace('.', '').isdigit():
# 								cell_obj.alignment = Alignment(horizontal='right')
# 							else:
# 								cell_obj.alignment = Alignment(horizontal='left')
				
# 				# Auto-adjust column widths
# 				for column in ws.columns:
# 					max_length = 0
# 					column_letter = get_column_letter(column[0].column)
# 					for cell in column:
# 						try:
# 							if len(str(cell.value)) > max_length:
# 								max_length = len(str(cell.value))
# 						except:
# 							pass
# 					adjusted_width = min(max_length + 2, 50)
# 					ws.column_dimensions[column_letter].width = adjusted_width
# 			else:
# 				frappe.logger().warning(f"No table found in HTML for section: {section_detail.section_type}")
		
# 		# Save the workbook
# 		file_name = f"Financial_Report_{self.name}_{frappe.utils.nowdate()}.xlsx"
# 		file_path = os.path.join(get_site_path(), 'private', 'files', file_name)
		
# 		# Ensure directory exists
# 		os.makedirs(os.path.dirname(file_path), exist_ok=True)
		
# 		wb.save(file_path)
		
# 		# Create file document
# 		file_doc = frappe.get_doc({
# 			"doctype": "File",
# 			"file_name": file_name,
# 			"file_url": f"/private/files/{file_name}",
# 			"is_private": 1,
# 			"attached_to_doctype": "Financial Report",
# 			"attached_to_name": self.name
# 		})
# 		file_doc.insert(ignore_permissions=True)
		
# 		return {
# 			"file_url": file_doc.file_url,
# 			"file_name": file_name
# 		}

		
# 	def export_to_pdf(self):
# 		from frappe.utils import get_site_path
# 		from frappe.utils.pdf import get_pdf
# 		from frappe.utils.jinja import render_template
# 		from frappe.utils.file_manager import save_file

# 		doc = frappe.get_doc("Financial Report", self.name)

# 		# Render the print format (replace 'Financial Report' with your Print Format name if different)
# 		html = frappe.get_print(
# 			doctype="Financial Report",
# 			name=self.name,
# 			print_format="Financial Report",
# 			style="Standard"
# 		)

# 		# Generate PDF content
# 		pdf_content = get_pdf(html)

# 		# Save PDF to File Doc
# 		file_doc = save_file(
# 			f"Financial_Report_{self.name}.pdf",
# 			pdf_content,
# 			"Financial Report",
# 			self.name,
# 			is_private=True
# 		)
	
# 	@frappe.whitelist()
# 	def test_clickable_functionality(self):
# 		"""Test method to verify clickable functionality is working"""
# 		try:
# 			# Get a sample financial report
# 			reports = frappe.get_all("Financial Report", limit=1)
# 			if not reports:
# 				return {"status": "error", "message": "No financial reports found"}
			
# 			report_name = reports[0].name
# 			doc = frappe.get_doc("Financial Report", report_name)
			
# 			# Check if the report has data
# 			if not doc.financial_report_details:
# 				return {"status": "error", "message": "Financial report has no details"}
			
# 			# Check for schedules in the data
# 			schedules_found = []
# 			for detail in doc.financial_report_details:
# 				if detail.section_type == "Balance Sheet":
# 					# Get balance sheet data to check for schedules
# 					data = self.get_balance_sheet_data(detail.section) if detail.section else []
# 					for row in data:
# 						if row.get("schedule"):
# 							schedules_found.append(row["schedule"])
			
# 			return {
# 				"status": "success", 
# 				"message": f"Clickable functionality test completed. Found {len(schedules_found)} schedules: {schedules_found[:5]}",
# 				"schedules_found": schedules_found
# 			}
			
# 		except Exception as e:
# 			frappe.log_error(f"Clickable functionality test error: {str(e)}", "Financial Report Clickable Test Error")
# 			return {"status": "error", "message": str(e)}