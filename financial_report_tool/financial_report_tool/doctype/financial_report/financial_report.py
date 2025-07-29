# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import re
import os
import math
import frappe
import openpyxl
from frappe.utils import flt
from bs4 import BeautifulSoup
from collections import defaultdict
from frappe.utils import get_site_path
from datetime import datetime, timedelta
from frappe.model.document import Document
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side


class FinancialReport(Document):
	def before_save(self):
		self.update_consolidation_note_numbers()
		for i in self.financial_report_details:
			if i.section_type == "Consolidation Note" and i.section:
				i.section_name = frappe.get_value("FR Section", i.section, 'section_type_name')

	def generate_note_id(self, note_no, note_title):
		"""Generate consistent ID for note anchors"""
		if not note_no or not note_title:
			return ""
		# Clean the title for use as ID (remove special chars, replace spaces with underscores)
		clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', note_title).strip()
		clean_title = re.sub(r'\s+', '_', clean_title).lower()
		return f"note_{note_no}_{clean_title}"

	def get_note_number_for_schedule(self, schedule_name):
		"""Get the note number for a given schedule"""
		if not schedule_name:
			return ""
		
		note_counter = 4
		for i in self.financial_report_details:
			if i.section_type == "Consolidation Note" and i.section:
				# Check if the FR Section has is_schedule = 1
				section_data = frappe.db.get_value("FR Section", i.section, ["is_schedule"], as_dict=True)
				if section_data and section_data.is_schedule == 1:
					if i.section == schedule_name:
						return str(note_counter)
					note_counter += 1
		return ""

	def update_consolidation_note_numbers(self):
		"""Update note numbers for consolidation notes starting from 4"""
		note_counter = 4
		for i in self.financial_report_details:
			if i.section_type == "Consolidation Note" and i.section:
				# Check if the FR Section has is_schedule = 1
				section_data = frappe.db.get_value("FR Section", i.section, ["is_schedule"], as_dict=True)
				if section_data and section_data.is_schedule == 1:
					i.note_no = str(note_counter)
					note_counter += 1
				else:
					i.note_no = ""
			else:
				i.note_no = ""

	def on_update_after_submit(self):
		"""Update note numbers when rows are modified after submit"""
		self.update_consolidation_note_numbers()
		self.save()

	@frappe.whitelist()
	def update_note_numbers(self):
		"""Update note numbers for consolidation notes"""
		self.update_consolidation_note_numbers()
		self.save()
		frappe.msgprint("Note numbers updated successfully!")

	def get_fiscal_year_by_date(self, date_str):
		"""Get fiscal year name by date"""
		if isinstance(date_str, str):
			date_obj = datetime.strptime(date_str, "%Y-%m-%d")
		else:
			date_obj = date_str
		
		formatted_date = date_obj.strftime("%Y-%m-%d")
		fiscal_year = frappe.db.exists("Fiscal Year", {
			'year_start_date': ["<=", formatted_date], 
			'year_end_date': [">=", formatted_date]
		})
		return fiscal_year

	def get_fiscal_year_before(self, fiscal_year_name):
		"""Get the fiscal year that comes before the given fiscal year"""
		if not fiscal_year_name:
			return None
		
		fiscal_year_doc = frappe.get_doc("Fiscal Year", fiscal_year_name)
		# Get the fiscal year that ends on the start date of the given fiscal year
		previous_fiscal_year = frappe.db.exists("Fiscal Year", {'year_end_date': fiscal_year_doc.year_start_date})
		return previous_fiscal_year

	def get_current_and_prevous_year_date(self):
		if isinstance(self.current_year_ending_date, str):
			current_year_date_obj = datetime.strptime(self.current_year_ending_date, "%Y-%m-%d")
		else:
			current_year_date_obj = self.current_year_ending_date

		if isinstance(self.previous_year_ending_date, str):
			previous_year_date_obj = datetime.strptime(self.previous_year_ending_date, "%Y-%m-%d")
		else:
			previous_year_date_obj = self.previous_year_ending_date

		current_year_date = current_year_date_obj.strftime("%d-%m-%Y")
		previous_year_date = previous_year_date_obj.strftime("%d-%m-%Y")
		return current_year_date, previous_year_date

	def sum_group_amt(self, primary_group, group, year):
		gl_accounts = frappe.get_list("GL Group Mapping",{"company":self.company,"report_type": self.report_type, 'primary_group': primary_group, 'secondary_group': group},pluck = 'gl_account')
		if len(gl_accounts) > 0:
			placeholders = ','.join(['%s'] * len(gl_accounts))
			query = f"""
				SELECT SUM(amount) FROM `tabFR Trail Balance Entry`
				WHERE company=%s AND fiscal_year=%s AND gl_account IN ({placeholders})
			"""
			params = [self.company, year] + gl_accounts
			return (frappe.db.sql(query, params)[0][0] or 0) / 100000
		else:
			return 0

	def sum_group_amt_monthly(self, primary_group, group, month, year, is_ftm=False):
		"""Calculate amount for a specific month or FTM (Fiscal Year to Month)"""
		gl_accounts = frappe.get_list("GL Group Mapping",{"company":self.company,"report_type": self.report_type, 'primary_group': primary_group, 'secondary_group': group},pluck = 'gl_account')
		if len(gl_accounts) > 0:
			placeholders = ','.join(['%s'] * len(gl_accounts))
			if is_ftm:
				query = f"""
					SELECT SUM(amount) FROM `tabFR Trail Balance Entry`
					WHERE company=%s AND fiscal_year=%s AND gl_account IN ({placeholders})
					AND month = %s
				"""
			else:
				query = f"""
					SELECT SUM(uploaded_amount) FROM `tabFR Trail Balance Entry`
					WHERE company=%s AND fiscal_year=%s AND gl_account IN ({placeholders})
					AND month = %s
				"""
			params = [self.company, year] + gl_accounts + [month]
			return (frappe.db.sql(query, params)[0][0] or 0) / 100000
		else:
			return 0

	@frappe.whitelist()
	def generate_report(self):
		if self.report_type == "Monthly":
			for i in self.financial_report_details:
				if i.section_type == "Balance Sheet":
					i.table_data = self.render_monthly_balance_sheet(i.section)
					i.section_description = i.table_data
				if i.section_type == "Profit & Loss":
					i.table_data = self.render_monthly_profit_and_loss(i.section)
					i.section_description = i.table_data
				if i.section_type == "Cash Flow":
					i.table_data = self.render_monthly_cash_flow(i.section)
					i.section_description = i.table_data
				if i.section_type == "Equity":
					i.table_data = self.render_monthly_equity_share_table()
					i.section_description = i.table_data
				if i.section_type == "Consolidation Note":
					section_data = frappe.db.get_value("FR Section", i.section, ["section_type_description", "fetch_data_from_trial_balance", "primary_consolidation_group", "note_type"], as_dict=True)
					section_description = section_data.section_type_description if section_data else ""
					fetch_data_from_trial_balance = section_data.fetch_data_from_trial_balance if section_data else ""
					primary_consolidation_group = section_data.primary_consolidation_group if section_data else ""
					note_type = section_data.note_type if section_data else ""
					note_table = None

					if fetch_data_from_trial_balance == 1:
						if primary_consolidation_group:
							data = self.get_monthly_consolidation_note_data(primary_consolidation_group)
						else:
							data = []
						note_table = self.monthly_table_for_note_template_1(data)
						
					if note_type == "Investments (Non-current)":
						note_table = self.get_monthly_investment_non_current_note_data()
					if note_type == "Trade & Other receivables":
						note_table = self.get_monthly_trade_and_other_receivables_note_data()
					if note_type == "Equity Share Capital":
						note_table = self.get_monthly_equity_share_capital_note_data()
					if note_type == "Other Equity":
						note_table = self.get_monthly_other_equity_note_data()
					if note_type == "Borrowings (Non-current)":
						note_table = self.get_monthly_borrowing_non_current_note_data(note_type)
					if note_type == "Changes in inventories of Finished Goods and Work-In-Progress":
						note_table = self.get_monthly_finished_goods_and_wip(note_type, total = False, field=None)
					if note_type == "Cost of Materials Consumed":
						note_table = self.get_monthly_cost_of_material_consumed(note_type, total = False, field=None)
						
					if note_table:
						context = {"note_table": note_table}
						i.table_data = frappe.render_template(section_description or "", context)	
						i.section_description = frappe.render_template(section_description or "", context)	

					context = {
						"company": self.company
					}
					i.section_description = frappe.render_template(i.section_description or "", context)
					i.subsection_description = frappe.render_template(i.subsection_description or "", context)
					
					# Wrap consolidation note with anchor ID for PDF navigation
					if i.note_no and i.section_name:
						note_id = self.generate_note_id(i.note_no, i.section_name)
						if note_id:
							i.table_data = f'<div id="{note_id}" class="note-anchor">{i.table_data}</div>' if i.table_data else f'<div id="{note_id}" class="note-anchor"></div>'
		else:
			for i in self.financial_report_details:
				if i.section_type == "Balance Sheet":
					i.table_data = self.render_balance_sheet(i.section)
				if i.section_type == "Profit & Loss":
					i.table_data = self.render_profit_and_loss(i.section)
				if i.section_type == "Cash Flow":
					i.table_data = self.render_cash_flow(i.section)
				if i.section_type == "Equity":
					i.table_data = self.render_equity_share_table()
				if i.section_type == "Consolidation Note":
					section_data = frappe.db.get_value("FR Section", i.section, ["section_type_description", "fetch_data_from_trial_balance", "primary_consolidation_group", "note_type"], as_dict=True)
					section_description = section_data.section_type_description if section_data else ""
					fetch_data_from_trial_balance = section_data.fetch_data_from_trial_balance if section_data else ""
					primary_consolidation_group = section_data.primary_consolidation_group if section_data else ""
					note_type = section_data.note_type if section_data else ""
					note_table = None

					if fetch_data_from_trial_balance == 1:
						data = self.get_consolidation_note_data(primary_consolidation_group)
						note_table = self.table_for_note_template_1(data)
						
					if note_type == "Investments (Non-current)":
						note_table = self.get_investment_non_current_note_data()
					if note_type == "Trade & Other receivables":
						note_table = self.get_trade_and_other_receivables_note_data()
					if note_type == "Equity Share Capital":
						note_table = self.get_equity_share_capital_note_data()
					if note_type == "Other Equity":
						note_table = self.get_other_equity_note_data()
					if note_type == "Borrowings (Non-current)":
						note_table = self.get_borrowing_non_current_note_data("Borrowings (Non-current)")
					if note_type == "Changes in inventories of Finished Goods and Work-In-Progress":
						note_table = self.get_finished_goods_and_wip(note_type, total = False, field=None)
					if note_type == "Cost of Materials Consumed":
						note_table = self.get_cost_of_material_consumed(note_type, total = False, field=None)
						
					if note_table:
						context = {"note_table": note_table}
						i.section_description = frappe.render_template(section_description or "", context)	
					context = {
						"company": self.company
					}
					i.section_description = section_desc = frappe.render_template(i.section_description or "", context)
					i.section_description = f'<div style="text-align: justify;">{i.section_description}</div>'
					i.subsection_description = frappe.render_template(i.subsection_description or "", context)
					i.subsection_description = f'<div style="text-align: justify;">{i.subsection_description}</div>'
					
					# Wrap consolidation note with anchor ID for PDF navigation
					if i.note_no and i.section_name:
						note_id = self.generate_note_id(i.note_no, i.section_name)
						if note_id:
							i.table_data = f'<div id="{note_id}" class="note-anchor">{i.table_data}</div>' if i.table_data else f'<div id="{note_id}" class="note-anchor"></div>'

		self.save()		
		return {
			"success": True,
			"message": "Financial Report generated successfully!",
			"doc": self.as_dict()
		}

	def get_cost_of_material_consumed(self, note_type, total, field):
		rows = []
		current_year_date, previous_year_date = self.get_current_and_prevous_year_date()

		closing_stock_previous = self.sum_group_amt("Inventories", "Raw Materials and Packing Material", self.previous_fiscal_year)
		closing_stock_current = self.sum_group_amt("Inventories", "Raw Materials and Packing Material", self.fiscal_year)
		purchases_current = self.sum_group_amt("Material consumed", "Cost of goods sold", self.fiscal_year) - self.get_finished_goods_and_wip(note_type, total = True, field='net_increase_total') + (closing_stock_current - closing_stock_previous)
		cost_consumed_current = closing_stock_previous + purchases_current - closing_stock_current

		fiscal_year = self.get_fiscal_year_by_date(self.previous_year_ending_date)
		fiscal_year_before_previous = self.get_fiscal_year_before(fiscal_year)
		if fiscal_year_before_previous:
			closing_stock_pre_previous = self.sum_group_amt("Inventories", "Raw Materials and Packing Material", fiscal_year_before_previous)
		else:
			closing_stock_pre_previous =  12343
		closing_stock_previous = self.sum_group_amt("Inventories", "Raw Materials and Packing Material", self.previous_fiscal_year)
		purchases_previous = self.sum_group_amt("Material consumed", "Cost of goods sold", self.previous_fiscal_year) - self.get_finished_goods_and_wip(note_type, total = True, field='net_increase_previous_year_total') + (closing_stock_previous - closing_stock_pre_previous)
		cost_consumed_previous = closing_stock_pre_previous + purchases_previous - closing_stock_previous
		
		if total:
			if field == 'cost_consumed_current':
				return cost_consumed_current
			elif field == 'cost_consumed_previous':
				return cost_consumed_previous
			else:
				return 0
		
		rows.extend([
			{"particulars": "Opening Stock", "current_amt": closing_stock_previous, "previous_amt": closing_stock_pre_previous, "is_subtotal": False},
			{"particulars": "Add: purchases & other related costs", "current_amt": purchases_current, "previous_amt": purchases_previous, "is_subtotal": False},
			{"particulars": "Less: closing stock", "current_amt": closing_stock_current, "previous_amt": closing_stock_previous, "is_subtotal": False},
			{"particulars": "Cost of Materials Consumed", "current_amt": cost_consumed_current, "previous_amt": cost_consumed_previous, "is_subtotal": True}
		])
		
		# Generate HTML table
		html = f'''
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr>
					<th style="border:2px solid #222; text-align:left; width:50%; padding:6px 8px;"><b>Particulars</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>{current_year_date}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px;"><b>{previous_year_date}</b></th>
				</tr>
			</thead>
			<tbody>
		'''
		
		for row in rows:
			# Format amounts
			current_amt_str = f"{row['current_amt']:,.0f}" if row['current_amt'] else "-"
			previous_amt_str = f"{row['previous_amt']:,.0f}" if row['previous_amt'] else "-"
			
			# Style for totals
			bold_style = "font-weight: bold;" if row["is_subtotal"] else ""
			border_style = "border:2px solid #222;" if row["is_subtotal"] else "border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;"
			
			html += f'''
				<tr>
					<td style="{border_style} text-align:left; padding:6px 8px; {bold_style}">{row['particulars']}</td>
					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style} background-color:#e8f5e8;">{current_amt_str}</td>
					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{previous_amt_str}</td>
				</tr>
			'''
		
		html += "</tbody></table>"
		return html

	def get_finished_goods_and_wip(self, note_type, total, field):
		rows = []
		current_year_date, previous_year_date = self.get_current_and_prevous_year_date()
		
		end_of_year_finished_goods = self.sum_group_amt("Inventories", "Finished Goods", self.fiscal_year)
		end_of_year_wip = self.sum_group_amt("Inventories", "Work in Progress", self.fiscal_year)
		end_of_year_total = end_of_year_finished_goods + end_of_year_wip
		
		beginning_of_year_finished_goods = self.sum_group_amt("Inventories", "Finished Goods", self.previous_fiscal_year)
		beginning_of_year_wip = self.sum_group_amt("Inventories", "Work in Progress", self.previous_fiscal_year)
		beginning_of_year_total = beginning_of_year_finished_goods + beginning_of_year_wip

		fiscal_year = self.get_fiscal_year_by_date(self.previous_year_ending_date)
		fiscal_year_before_previous = self.get_fiscal_year_before(fiscal_year)
		
		if not fiscal_year_before_previous:
			beginning_of_previous_year_finished_goods = 0
			beginning_of_previous_year_wip = 0
		else:
			beginning_of_previous_year_finished_goods = self.sum_group_amt("Inventories", "Finished Goods", fiscal_year_before_previous)
			beginning_of_previous_year_wip = self.sum_group_amt("Inventories", "Work in Progress", fiscal_year_before_previous)
		beginning_of_previous_year_total = beginning_of_previous_year_finished_goods + beginning_of_previous_year_wip
		
		net_increase_finished_goods = end_of_year_finished_goods - beginning_of_year_finished_goods
		net_increase_wip = end_of_year_wip - beginning_of_year_wip
		net_increase_total = beginning_of_year_total - end_of_year_total
		
		net_increase_previous_year_finished_goods = beginning_of_year_finished_goods - beginning_of_previous_year_finished_goods
		net_increase_previous_year_wip = beginning_of_year_wip - beginning_of_previous_year_wip
		net_increase_previous_year_total = beginning_of_previous_year_total - beginning_of_year_total
		if total:
			if field == 'net_increase_total':
				return net_increase_total
			elif field == 'net_increase_previous_year_total':
				return net_increase_previous_year_total
			else:
				return 0
		
		rows.extend([
			{"particulars": "Inventories at the end of the year","current_amt": 0,"previous_amt": 0,"is_subtotal": True},
			{"particulars": "Finished goods","current_amt": end_of_year_finished_goods,"previous_amt": beginning_of_year_finished_goods,"is_subtotal": False},
			{"particulars": "Work-in-progress","current_amt": end_of_year_wip,"previous_amt": beginning_of_year_wip,"is_subtotal": False},
			{"particulars": "","current_amt": end_of_year_total,"previous_amt": beginning_of_year_total,"is_subtotal": False},
			{"particulars": "Inventories at the beginning of the year","current_amt": 0,"previous_amt": 0,"is_subtotal": True},
			{"particulars": "Finished goods","current_amt": beginning_of_year_finished_goods,"previous_amt": beginning_of_previous_year_finished_goods,"is_subtotal": False},
			{"particulars": "Work-in-progress","current_amt": beginning_of_year_wip,"previous_amt": beginning_of_previous_year_wip,"is_subtotal": False},
			{"particulars": "","current_amt": beginning_of_year_total,"previous_amt": beginning_of_previous_year_total,"is_subtotal": False},
			{"particulars": "Net increase","current_amt": net_increase_total,"previous_amt": net_increase_previous_year_total,"is_subtotal": True}
		])
		
		# Generate HTML table
		html = f'''
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr>
					<th style="border:2px solid #222; text-align:left; width:50%; padding:6px 8px;"><b>Particulars</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>{current_year_date}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px;"><b>{previous_year_date}</b></th>
				</tr>
			</thead>
			<tbody>
		'''
		
		for row in rows:
			# Format amounts
			current_amt_str = f"{row['current_amt']:,.0f}" if row['current_amt'] else "-"
			previous_amt_str = f"{row['previous_amt']:,.0f}" if row['previous_amt'] else "-"
			
			# Style for totals
			bold_style = "font-weight: bold;" if row["is_subtotal"] else ""
			border_style = "border:2px solid #222;" if row["is_subtotal"] else "border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;"
			
			html += f'''
				<tr>
					<td style="{border_style} text-align:left; padding:6px 8px; {bold_style}">{row['particulars']}</td>
					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style} background-color:#e8f5e8;">{current_amt_str}</td>
					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{previous_amt_str}</td>
				</tr>
			'''
		
		html += "</tbody></table>"
		return html

	def get_borrowing_non_current_note_data(self, primary_group):
		rows = []
		
		if self.report_type == "Monthly":
			total_current_month_amt = 0
			total_previous_month_amt = 0
			total_ftm_amt = 0
			current_month_date, previous_month_date, ftm_date = self.get_monthly_dates()
		else:
			total_current_amt = 0
			total_previous_amt = 0

		secondary_group = frappe.get_all("Standalone Group",filters={"parent_consolidation_group": primary_group},
			fields=["name", "ind_as_description"]
		)

		for g in secondary_group:
			html_particulars = f"<b>{g.name}</b><br>{g.ind_as_description or ''}"
			
			if self.report_type == "Monthly":
				current_month_amt = self.sum_group_amt_monthly(primary_group, g.name, self.current_month, self.fiscal_year)
				previous_month_amt = self.sum_group_amt_monthly(primary_group, g.name, self.previous_month, self.fiscal_year)
				ftm_amt = current_month_amt - previous_month_amt

				rows.append({
					"particulars": html_particulars,
					"current_month_amt": f"{current_month_amt:,.0f}" if current_month_amt else "-",
					"previous_month_amt": f"{previous_month_amt:,.0f}" if previous_month_amt else "-",
					"ftm_amt": f"{ftm_amt:,.0f}" if ftm_amt else "-",
					"group": False
				})

				total_current_month_amt += current_month_amt or 0
				total_previous_month_amt += previous_month_amt or 0
				total_ftm_amt += ftm_amt or 0
			else:
				current_amt = self.sum_group_amt(primary_group, g.name, self.fiscal_year)
				previous_amt = self.sum_group_amt(primary_group, g.name, self.previous_fiscal_year)

				rows.append({
					"particulars": html_particulars,
					"current_amt": f"{current_amt:,.0f}" if current_amt else "-",
					"previous_amt": f"{previous_amt:,.0f}" if previous_amt else "-",
					"group": False
				})

				total_current_amt += current_amt or 0
				total_previous_amt += previous_amt or 0

		# HTML rendering
		if self.report_type == "Monthly":
			html = f'''
			<table style="width:100%; border-collapse:collapse; font-size:13px;">
				<thead>
					<tr>
						<th style="border:2px solid #222; text-align:left; width:50%; padding:6px 8px;"><b>Particulars</b></th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>{current_month_date}</b></th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px;"><b>{previous_month_date}</b></th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px;"><b>{ftm_date}</b></th>
					</tr>
				</thead>
				<tbody>
			'''

			for row in rows:
				bold = "font-weight: bold;" if row.get("group") else ""
				html += f'''
					<tr>
						<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:left; padding:6px 8px; {bold}">{row['particulars']}</td>
						<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; background-color:#e8f5e8;">{row['current_month_amt']}</td>
						<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row['previous_month_amt']}</td>
						<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row['ftm_amt']}</td>
					</tr>
				'''

			# Append total row
			html += f'''
				<tr>
					<td style="border:2px solid #222; text-align:left; font-weight:bold; padding:6px 8px;">Total</td>
					<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px; background-color:#e8f5e8;">{total_current_month_amt:,.0f}</td>
					<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px;">{total_previous_month_amt:,.0f}</td>
					<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px;">{total_ftm_amt:,.0f}</td>
				</tr>
			'''
		else:
			# Original yearly report logic
			html = '''
			<table style="width:100%; border-collapse:collapse; font-size:13px;">
				<thead>
					<tr>
						<th style="border:2px solid #222; text-align:left; width:70%; padding:6px 8px;"><b>Particulars</b></th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>As at 31-03-2025</b></th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px;"><b>As at 31-03-2024</b></th>
					</tr>
				</thead>
				<tbody>
			'''

			for row in rows:
				bold = "font-weight: bold;" if row.get("group") else ""
				html += f'''
					<tr>
						<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:left; padding:6px 8px; {bold}">{row['particulars']}</td>
						<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; background-color:#e8f5e8;">{row['current_amt']}</td>
						<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row['previous_amt']}</td>
					</tr>
				'''

			# Append total row
			html += f'''
				<tr>
					<td style="border:2px solid #222; text-align:left; font-weight:bold; padding:6px 8px;">Total</td>
					<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px; background-color:#e8f5e8;">{total_current_amt:,.0f}</td>
					<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px;">{total_previous_amt:,.0f}</td>
				</tr>
			'''

		html += "</tbody></table>"
		return html

	def get_other_equity_note_data(self):
		data = [
			("Retained earnings", "", "", True),
			("Balance as at the beginning of the year", "59,183", "41,144", False),
			("Net Profit for the year", "42,545", "18,111", False),
			("Other comprehensive income", "(142)", "(72)", False),
			("Balance as at the end of the year", "1,01,586", "59,183", True),
			("Capital Contribution", "", "", True),
			("Balance as at the beginning of the year", "4,459", "4,459", False),
			("Add: Equity contribution on financial guarantee taken", "3", "-", False),
			("<b>Balance as at the end of the year</b>", "4,462", "4,459", True),
			("<b>Total</b>", "1,06,048", "63,642", True),
		]
		html = '''
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr>
					<th style="border:2px solid #222; text-align:left; width:70%; padding:6px 8px; background:#f2f2f0;"><b>Particulars</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#f2f2f0;"><b>As at 31-03-2025</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#f2f2f0;"><b>As at 31-03-2024</b></th>
				</tr>
			</thead>
			<tbody>
		'''
		for i, (particulars, amt_2025, amt_2024, bold) in enumerate(data):
			is_last = i == len(data) - 1
			if is_last:
				html += f'''
				<tr>
					<td style="border:2px solid #222; text-align:left; font-weight:bold; padding:6px 8px; background:#fff;">{particulars}</td>
					<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px; background:#e8f5e8;">{amt_2025}</td>
					<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px; background:#fff;">{amt_2024}</td>
					<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px; background:#fff;">{amt_2025}</td>
				</tr>
				'''
			else:
				bold = "font-weight: bold;" if bold else ""
				html += f'''
				<tr>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:left; padding:6px 8px; {bold}">{particulars}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; background:#e8f5e8;">{amt_2025}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; background:#fff;">{amt_2024}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; background:#fff;">{amt_2025}</td>
				</tr>
				'''
		html += "</tbody></table>"
		return html

	def get_equity_share_capital_note_data(self):
		pass

	def get_trade_and_other_receivables_note_data(self):
		credit_impaired = round(self.sum_group_amt("Trade Receivables - credit Impaired", "Trade Receivables - credit Impaired", self.fiscal_year)) or 0
		prev_credit_impaired = round(self.sum_group_amt("Trade Receivables - credit Impaired", "Trade Receivables - credit Impaired", self.previous_fiscal_year)) or 0

		trade_receivables = round(self.sum_group_amt("Trade receivables", "Trade receivables", self.fiscal_year)) or 0
		prev_trade_receivables = round(self.sum_group_amt("Trade receivables", "Trade receivables", self.previous_fiscal_year)) or 0

		unsecured_good = trade_receivables - credit_impaired
		prev_unsecured_good = prev_trade_receivables - prev_credit_impaired

		provision = credit_impaired
		prev_provision = prev_credit_impaired

		other_receivables = round(self.sum_group_amt("Other Receivables", "Other Receivables", self.fiscal_year)) or 0
		prev_other_receivables = round(self.sum_group_amt("Other Receivables", "Other Receivables", self.previous_fiscal_year)) or 0

		total = unsecured_good + other_receivables
		prev_total = prev_unsecured_good + prev_other_receivables

		main_table = [
			("Unsecured, considered good", unsecured_good, prev_unsecured_good, False),
			("Credit impaired", credit_impaired, prev_credit_impaired, False),
			("", trade_receivables, prev_trade_receivables, False),
			("Less: Provision for credit impaired trade receivables", provision, prev_provision, False),
			("Other receivables", "", "", True),
			("Unsecured, considered good", other_receivables, prev_other_receivables, False),
			("Total", total, prev_total, True),
		]
		related_parties = [
			("Meril Life Sciences India Private Limited", "11,411", "12,865"),
			("Meril Endo Surgery Private limited", "51", "240"),
			("Meril Healthcare Private limited", "132", ""),
			("Doc Med Comercio Importacao E Exportacao Ltda., Brazil", "10,118", "9,871"),
			("Meril GmbH Germany", "3,951", "302"),
			("Meril UK Ltd", "4,748", "825"),
			("Meril Tibbi Cihazlar Imalat ve Ticaret Anonim Sirketi, Turkey", "6,227", "4,709"),
			("Meril Bangladesh Pvt. Ltd., Bangladesh", "4,145", "1,509"),
			("Meril Medical LLC, Russia", "1,106", "1,404"),
			("Meril SA Pty. Ltd, South Africa", "9,328", "2,140"),
			("Meril Italy SRL", "2,150", "227"),
			("Meril Medical Innovations Private Limited", "51", ""),
			("Micro Life Sciences Private Limited", "272", ""),
			("Meril Malaysia sdn bhd", "94", ""),
			("Meril Poland SP.ZOO ,Poland", "2,150", ""),
			("Meril Sweden AB", "4", ""),
			("Meril (Vietnam) Company Limited", "15", ""),
			("Meril Medical Surgical Articles & Requisites L.L.C, UAE", "", ""),
		]
		ageing_2025 = [
			("Undisputed trade receivables – considered good", "56,851", "30,577", "9,181", "3,607", "579", "59", "1,00,216"),
			("Undisputed trade receivables – considered doubtful", "-", "-", "-", "-", "-", "62", "700"),
			("Disputed trade receivables considered good", "-", "-", "-", "-", "-", "-", "-"),
			("Disputed Trade Receivables considered doubtful", "-", "-", "-", "-", "-", "-", "-"),
		]
		ageing_2024 = [
			("Undisputed trade receivables – considered good", "31,385", "16,087", "5,959", "1,699", "380", "71", "55,130"),
			("Undisputed trade receivables – considered doubtful", "-", "144", "-", "-", "-", "105", "700"),
			("Disputed trade receivables considered good", "-", "-", "-", "-", "-", "-", "-"),
			("Disputed Trade Receivables considered doubtful", "-", "-", "-", "-", "-", "-", "-"),
		]

		# Main Table
		html = '''
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr>
					<th style="border:2px solid #222; text-align:left; width:50%; padding:6px 8px; background:#fafbfc;"><b>Particulars</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#e8f5e8;"><b>As at 31-03-2025</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;"><b>As at 31-03-2024</b></th>
				</tr>
			</thead>
			<tbody>
		'''
		for i, row in enumerate(main_table):
			is_last = i == len(main_table) - 1
			style = "font-weight:bold;" if row[3] else ""
			if is_last:
				html += f'''
				<tr>
					<td style="border:2px solid #222; text-align:left; width:50%; padding:6px 8px; {style}">{row[0]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px; {style} background-color:#e8f5e8;">{row[1]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px; {style}">{row[2]}</td>
				</tr>
			'''
			else:
				html += f'''
				<tr>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:left; width:50%; padding:6px 8px; {style}">{row[0]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; {style} background-color:#e8f5e8;">{row[1]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; {style}">{row[2]}</td>
				</tr>
			'''
		html += "</tbody></table>"

		# Related Parties Table
		html += '''
		<div style="margin-top:8px; font-size:13px;">
			<b>Refer note 15 & 20 - trade receivables pledged as security.</b><br>
			<b>Trade receivables include the following amounts receivable from related parties:</b>
			<table style="width:100%; border-collapse:collapse; font-size:13px; margin-top:4px;">
				<thead>
					<tr>
						<th style="border:2px solid #222; text-align:left; width:70%; padding:6px 8px; background:#fafbfc;">Party</th>
						<th style="border:2px solid #222; text-align:right; padding:6px 8px; background:#fafbfc;">As at 31-03-2025</th>
						<th style="border:2px solid #222; text-align:right; padding:6px 8px; background:#fafbfc;">As at 31-03-2024</th>
					</tr>
				</thead>
				<tbody>
		'''
		for i, (party, amt_2025, amt_2024) in enumerate(related_parties):
			is_last = i == len(related_parties) - 1
			if is_last:
				html += f'''
				<tr>
					<td style="border:2px solid #222; text-align:left; width:70%; padding:6px 8px;">{party}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{amt_2025}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{amt_2024}</td>
				</tr>
			'''
			else:
				html += f'''
				<tr>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:left; width:70%; padding:6px 8px;">{party}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{amt_2025}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{amt_2024}</td>
				</tr>
			'''
		html += "</tbody></table></div>"

		# Ageing Table 2025
		html += '''
		<div style="margin-top:16px; font-size:13px;">
			<b>Ageing for trade & other receivables outstanding as at 31st March, 2025</b>
			<table style="width:100%; border-collapse:collapse; font-size:13px; margin-top:4px;">
				<thead>
					<tr>
						<th style="border:2px solid #222; text-align:left; width:30%; padding:6px 8px; background:#fafbfc;" rowspan="2">Particulars</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;" rowspan="2">Not Due</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;" colspan="5">Outstanding for following periods from due date of payment as on 31-03-2025</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;" rowspan="2">Total</th>
					</tr>
					<tr>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;">Less than 6 Month</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;">6 Month - 1 Year</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;">1 Year - 2 Year</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;">2 Year - 3 Year</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;">More than 3 Year</th>
					</tr>
				</thead>
				<tbody>
		'''
		for i, row in enumerate(ageing_2025):
			is_last = i == len(ageing_2025) - 1
			if is_last:
				html += f'''
				<tr>
					<td style="border:2px solid #222; text-align:left; width:30%; padding:6px 8px;">{row[0]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[1]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[2]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[3]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[4]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[5]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[6]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[7]}</td>
				</tr>
			'''
			else:
				html += f'''
				<tr>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:left; width:30%; padding:6px 8px;">{row[0]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[1]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[2]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[3]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[4]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[5]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[6]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[7]}</td>
				</tr>
			'''
		html += "</tbody></table></div>"

		# Ageing Table 2024
		html += '''
		<div style="margin-top:16px; font-size:13px;">
			<b>Ageing for trade & other receivables outstanding as at 31st March, 2024</b>
			<table style="width:100%; border-collapse:collapse; font-size:13px; margin-top:4px;">
				<thead>
					<tr>
						<th style="border:2px solid #222; text-align:left; width:30%; padding:6px 8px; background:#fafbfc;" rowspan="2">Particulars</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;" rowspan="2">Not Due</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;" colspan="5">Outstanding for following periods from due date of payment as on 31-03-2024</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;" rowspan="2">Total</th>
					</tr>
					<tr>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;">Less than 6 Month</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;">6 Month - 1 Year</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;">1 Year - 2 Year</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;">2 Year - 3 Year</th>
						<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;">More than 3 Year</th>
					</tr>
				</thead>
				<tbody>
		'''
		for i, row in enumerate(ageing_2024):
			is_last = i == len(ageing_2024) - 1
			if is_last:
				html += f'''
				<tr>
					<td style="border:2px solid #222; text-align:left; width:30%; padding:6px 8px;">{row[0]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[1]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[2]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[3]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[4]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[5]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[6]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px;">{row[7]}</td>
				</tr>
			'''
			else:
				html += f'''
				<tr>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:left; width:30%; padding:6px 8px;">{row[0]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[1]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[2]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[3]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[4]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[5]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[6]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row[7]}</td>
				</tr>
			'''
		html += "</tbody></table></div>"

		return html

	def get_investment_non_current_note_data(self):
		data = [{"particulars": "Investment in equity Instruments of subsidiaries measured at Cost (Unquoted, Fully paid Up)", "face_value": "", "shares_current": "", "amount_current": "", "shares_previous": "", "amount_previous": "", "bold": 1}]
		current_year_date, previous_year_date = self.get_current_and_prevous_year_date()
		fiscal_doc = frappe.get_doc("Fiscal Year", self.fiscal_year)
		prev_fiscal_doc = frappe.get_doc("Fiscal Year", self.previous_fiscal_year)
		all_companies = frappe.get_list("Company", {"parent_company": self.company}, pluck="name")
		total_current = 0
		total_previous = 0

		for company in all_companies:
			current_equity_entries = frappe.get_all("FR Equity Entry", 
				filters={"company": company, "holding_company": self.company, "category": "Equity Shares", "posting_date": ["Between", [fiscal_doc.year_start_date, fiscal_doc.year_end_date]]},
				fields=["company", "no_of_shares", "face_value", "investment_value", "posting_date"], 
				order_by="posting_date desc")

			previous_equity_entries = frappe.get_all("FR Equity Entry", 
				filters={"company": company, "holding_company": self.company, "category": "Equity Shares", "posting_date": ["Between", [prev_fiscal_doc.year_start_date, prev_fiscal_doc.year_end_date]]},
				fields=["company", "no_of_shares", "face_value", "investment_value", "posting_date"], 
				order_by="posting_date desc")

			# Get the latest entry for each period
			e_current = current_equity_entries[0] if current_equity_entries else None
			e_previous = previous_equity_entries[0] if previous_equity_entries else None

			face_value = e_current.get("face_value") if e_current else (e_previous.get("face_value") if e_previous else None)
			shares_current = e_current.get("no_of_shares") if e_current else 0
			amount_current = e_current.get("investment_value") if e_current else 0
			shares_previous = e_previous.get("no_of_shares") if e_previous else 0
			amount_previous = e_previous.get("investment_value") if e_previous else 0

			shares_current_str = f"{shares_current:,.0f}" if shares_current else "0"
			amount_current_str = f"{amount_current:,.0f}" if amount_current else "0"
			shares_previous_str = f"{shares_previous:,.0f}" if shares_previous else "0"
			amount_previous_str = f"{amount_previous:,.0f}" if amount_previous else "0"

			total_current += amount_current
			total_previous += amount_previous

			data.append({
				"particulars": company,
				"face_value": f"₹ {face_value:.0f}" if face_value else "NA",
				"shares_current": shares_current_str,
				"amount_current": amount_current_str,
				"shares_previous": shares_previous_str,
				"amount_previous": amount_previous_str,
				"bold": 0
			})

		data.append({
			"particulars": "Total of Equity Instruments Measured at cost",
			"face_value": "",
			"shares_current": "",
			"amount_current": f"{total_current:,.0f}",
			"shares_previous": "",
			"amount_previous": f"{total_previous:,.0f}",
			"bold": 1
		})

		table = '''
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr>
					<th style="border:2px solid #222; text-align:left; width:50%; padding:6px 8px; background:#fafbfc;"><b>Particulars</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;"><b>Face Value</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#e8f5e8;" colspan="2"><b>As at 31-03-2025</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;" colspan="2"><b>As at 31-03-2024</b></th>
				</tr>
				<tr>
					<th style="border:2px solid #222; background:#fafbfc;"></th>
					<th style="border:2px solid #222; text-align:center; background:#fafbfc;"></th>
					<th style="border:2px solid #222; text-align:center; background:#e8f5e8;"><b>No. of shares</b></th>
					<th style="border:2px solid #222; text-align:center; background:#e8f5e8;"><b>(₹ in lacs)</b></th>
					<th style="border:2px solid #222; text-align:center; background:#fafbfc;"><b>No. of shares</b></th>
					<th style="border:2px solid #222; text-align:center; background:#fafbfc;"><b>(₹ in lacs)</b></th>
				</tr>
			</thead>
			<tbody>
		'''
		for i, row in enumerate(data):
			bold = "font-weight: bold;" if row["bold"] else ""
			is_last = i == len(data) - 1
			
			if is_last:
				# Footer row with full borders
				table += f'''
				<tr>
					<td style="border:2px solid #222; text-align:left; width:50%; {bold}">{row['particulars']}</td>
					<td style="border:2px solid #222; text-align:center;">{row['face_value']}</td>
					<td style="border:2px solid #222; text-align:right; background-color:#e8f5e8;">{row['shares_current']}</td>
					<td style="border:2px solid #222; text-align:right; background-color:#e8f5e8;">{row['amount_current']}</td>
					<td style="border:2px solid #222; text-align:right;">{row['shares_previous']}</td>
					<td style="border:2px solid #222; text-align:right;">{row['amount_previous']}</td>
				</tr>
				'''
			else:
				# Regular rows with only left and right borders
				table += f'''
				<tr>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:left; width:50%; {bold}">{row['particulars']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:center;">{row['face_value']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; background-color:#e8f5e8;">{row['shares_current']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; background-color:#e8f5e8;">{row['amount_current']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right;">{row['shares_previous']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right;">{row['amount_previous']}</td>
				</tr>
				'''
		table += "</tbody></table>"
		return table

	def get_consolidation_note_data(self, primary_consolidation_group):
		secondary_consolidation_groups = frappe.db.get_list("Standalone Group", {"parent_consolidation_group": primary_consolidation_group}, pluck="name")
		data = []
		
		if self.report_type == "Monthly":
			# For monthly reports, get current month, previous month, and FTM data
			for sec in secondary_consolidation_groups:
				current_month_amount = self.sum_group_amt_monthly(primary_consolidation_group, sec, self.current_month, self.fiscal_year)
				previous_month_amount = self.sum_group_amt_monthly(primary_consolidation_group, sec, self.previous_month, self.fiscal_year)
				ftm_amount = current_month_amount - previous_month_amount
				
				data.append({
					"account": sec,
					"current_month_amount": current_month_amount,
					"previous_month_amount": previous_month_amount,
					"ftm_amount": ftm_amount,
					"indent": 0,
					"is_bold": 0
				})
		else:
			# For yearly reports, get current year and previous year data
			for sec in secondary_consolidation_groups:
				amount = self.sum_group_amt(primary_consolidation_group, sec, self.fiscal_year)
				previous_year_amount = self.sum_group_amt(primary_consolidation_group, sec, self.previous_fiscal_year)
				data.append({
					"account": sec,
					"amount": amount,
					"previous_year_amount": previous_year_amount,
					"indent": 0,
					"is_bold": 0
				})
		return data
	
	def table_for_note_template_1(self, data):
		if self.report_type == "Monthly":
			current_month_date, previous_month_date, ftm_date = self.get_monthly_dates()
			
			note_table = f'''
			<table style="width:100%; border-collapse:collapse; font-size:13px;">
				<thead>
					<tr style="background-color: #f1f1f1;">
						<th style='border:2px solid #222; text-align:left; padding: 5px; width: 40%;'>Particulars</th>
						<th style='border:2px solid #222; text-align:center; padding: 5px; width: 20%; background-color: #e8f5e8;'>{current_month_date}</th>
						<th style='border:2px solid #222; text-align:center; padding: 5px; width: 20%;'>{previous_month_date}</th>
						<th style='border:2px solid #222; text-align:center; padding: 5px; width: 20%;'>{ftm_date}</th>
					</tr>
				</thead>
				<tbody>
			'''

			total_current_month = 0
			total_previous_month = 0
			total_ftm = 0
			for i, row in enumerate(data):
				indent = "&nbsp;" * (int(row.get("indent", 0)) * 4)
				bold = "font-weight: bold;" if row.get("is_bold") else ""
				current_month_amount = row.get('current_month_amount') or 0
				previous_month_amount = row.get('previous_month_amount') or 0
				ftm_amount = row.get('ftm_amount') or 0
				total_current_month += current_month_amount
				total_previous_month += previous_month_amount
				total_ftm += ftm_amount
				note_table += f'''
				<tr>
					<td style='text-align:left; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; {bold}'>{indent}{row.get("account") or ""}</td>
					<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; background-color: #e8f5e8;'>{'{:,.2f}'.format(current_month_amount) if current_month_amount else ''}</td>
					<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(previous_month_amount) if previous_month_amount else ''}</td>
					<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(ftm_amount) if ftm_amount else ''}</td>
				</tr>
				'''
			# Add total row as footer
			note_table += f'''
				<tr>
					<td style='text-align:left; padding: 5px; border:2px solid #222; font-weight: bold;'>Total</td>
					<td style='text-align:right; padding: 5px; border:2px solid #222; font-weight: bold; background-color: #e8f5e8;'>{'{:,.0f}'.format(total_current_month)}</td>
					<td style='text-align:right; padding: 5px; border:2px solid #222; font-weight: bold;'>{'{:,.0f}'.format(total_previous_month)}</td>
					<td style='text-align:right; padding: 5px; border:2px solid #222; font-weight: bold;'>{'{:,.0f}'.format(total_ftm)}</td>
				</tr>
			'''
			note_table += "</tbody></table>"
			return note_table
		else:
			# Original yearly report logic
			current_year_date, previous_year_date = self.get_current_and_prevous_year_date()

			note_table = f'''
			<table style="width:100%; border-collapse:collapse; font-size:13px;">
				<thead>
					<tr style="background-color: #f1f1f1;">
						<th style='border:2px solid #222; text-align:left; padding: 5px; width: 60%;'>Particulars</th>
						<th style='border:2px solid #222; text-align:center; padding: 5px; width: 20%; background-color: #e8f5e8;'>Year Ended <br> {current_year_date}</th>
						<th style='border:2px solid #222; text-align:center; padding: 5px; width: 20%;'>Year Ended <br> {previous_year_date}</th>
					</tr>
				</thead>
				<tbody>
			'''

			total_amount = 0
			total_prev_amount = 0
			for i, row in enumerate(data):
				indent = "&nbsp;" * (int(row.get("indent", 0)) * 4)
				bold = "font-weight: bold;" if row.get("is_bold") else ""
				amount = row.get('amount') or 0
				prev_amount = row.get('previous_year_amount') or 0
				total_amount += amount
				total_prev_amount += prev_amount
				note_table += f'''
				<tr>
					<td style='text-align:left; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; {bold}'>{indent}{row.get("account") or ""}</td>
					<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; background-color: #e8f5e8;'>{'{:,.2f}'.format(amount) if amount else ''}</td>
					<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(prev_amount) if prev_amount else ''}</td>
				</tr>
				'''
			# Add total row as footer
			note_table += f'''
				<tr>
					<td style='text-align:left; padding: 5px; border:2px solid #222; font-weight: bold;'>Total</td>
					<td style='text-align:right; padding: 5px; border:2px solid #222; font-weight: bold; background-color: #e8f5e8;'>{'{:,.2f}'.format(total_amount)}</td>
					<td style='text-align:right; padding: 5px; border:2px solid #222; font-weight: bold;'>{'{:,.2f}'.format(total_prev_amount)}</td>
				</tr>
			'''
			note_table += "</tbody></table>"
			return note_table

	def get_profit_and_loss_data(self, template_name):
		profit_and_loss_doc = frappe.get_doc("Profit And Loss Template", template_name)
		amount_cache = {}

		def calc_amount_for_particular(particular_name, year, current=0):
			cache_key = (particular_name, year)
			if cache_key in amount_cache:
				return amount_cache[cache_key]
			amount = 0
			fr_particular = frappe.get_doc("FR Particular", particular_name)
			if getattr(fr_particular, "is_total", 0):
				for p in getattr(fr_particular, "particulars", []):
					child_name = p.particular
					amount += calc_amount_for_particular(child_name, year)
				amount = amount * 100000
			elif getattr(fr_particular, "fetch_from_schedule", 1):
				note_type = frappe.get_value("FR Section", fr_particular.schedule, 'note_type')
				if note_type == "Changes in inventories of Finished Goods and Work-In-Progress":
					field = 'net_increase_total' if current else 'net_increase_previous_year_total'
					amount = self.get_finished_goods_and_wip(note_type, total = True, field=field) 
				if note_type == "Cost of Materials Consumed":
					field = 'cost_consumed_current' if current else 'cost_consumed_previous'
					amount = self.get_cost_of_material_consumed(note_type, total = True, field=field)
				amount = amount * 100000
			else:
				gl_accounts = []
				for g in fr_particular.get('primary_and_secondary_group_mapping'):
					gl_account = frappe.get_list("GL Group Mapping", {"company": self.company, "report_type": self.report_type, 'primary_group': g.primary_group, 'secondary_group': g.secondary_group}, pluck = 'gl_account')
					gl_accounts.extend(gl_account)
				
				if len(gl_accounts) == 0:
					amount = 0
				else:
					placeholders = ','.join(['%s'] * len(gl_accounts))
					query = f"""
						SELECT SUM(amount) FROM `tabFR Trail Balance Entry`
						WHERE company=%s AND fiscal_year=%s AND gl_account IN ({placeholders})
					"""
					params = [self.company, year] + gl_accounts
					amount = (frappe.db.sql(query, params)[0][0] or 0)
			
			# Apply value reversal if show_reversed_value is checked
			if getattr(fr_particular, "show_reversed_value", 0):
				amount = -amount
			
			amount_cache[cache_key] = int(round(amount / 100000))
			return amount_cache[cache_key]

		grouped_data = []
		for row in profit_and_loss_doc.profit_and_loss_template_details:
			if not row.account:
				continue
			
			amount_current = calc_amount_for_particular(row.account, self.fiscal_year, 1)
			amount_previous = calc_amount_for_particular(row.account, self.previous_fiscal_year, 0)
			
			# Get the schedule from FR Particular
			fr_particular = frappe.get_doc("FR Particular", row.account)
			schedule = getattr(fr_particular, "schedule", "")
			
			# Get note number for schedule if it exists
			note_no = row.note
			if schedule:
				schedule_note_no = self.get_note_number_for_schedule(schedule)
				if schedule_note_no:
					note_no = schedule_note_no
			
			grouped_data.append({
				"account": row.particular_name,
				"note_no": note_no,
				"amount": amount_current,
				"previous_year_amount": amount_previous,
				"indent": int(row.indent_level or 0),
				"is_bold": row.is_bold,
				"group": row.group,
				"schedule": schedule,
			})
		return grouped_data

	def render_profit_and_loss(self, template_name):
		data = self.get_profit_and_loss_data(template_name)
		current_year_date, previous_year_date = self.get_current_and_prevous_year_date()

		html = f"""
		<table style="width:100%; border-collapse: collapse; font-size: 13px; border: 1px solid black;">
			<thead>
				<tr style="background-color: #f1f1f1;">
					<th style='text-align:left; padding: 5px; width: 5%; border: 1px solid black;'></th>
					<th style='text-align:left; padding: 5px; width: 45%; border: 1px solid black;'>Particulars</th>
					<th style='text-align:center; padding: 5px; width: 10%; border: 1px solid black;'>Note No.</th>
					<th style='text-align:center; padding: 5px; width: 20%; border: 1px solid black; background-color: #e8f5e8;'>Year Ended <br> {current_year_date}</th>
					<th style='text-align:center; padding: 5px; width: 20%; border: 1px solid black;'>Year Ended <br> {previous_year_date}</th>
				</tr>
			</thead>
			<tbody>
		"""
		
		def to_roman(idx):
			romans = [
				'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
				'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX'
			]
			return romans[idx] if idx < len(romans) else str(idx+1)


		group_counter = 0
		for row in data:
			indent = "&nbsp;" * (int(row.get("indent", 0)) * 4)
			bold = "font-weight: bold;" if row.get("is_bold") else ""
			# Only group accounts get an index
			if row.get("group"):
				index = to_roman(group_counter)
				group_counter += 1
			else:
				index = ""
			
		schedule_attr = f' data-schedule="{row.get("note_no", "")}"' if row.get("note_no") else ""
		clickable_style = "cursor: pointer; background-color: #f8f9fa;" if row.get("note_no") else ""
		hover_style = "background-color: #e9ecef;" if row.get("note_no") else ""
			
		account_text = row.get("particular_name") or row.get("account") or ""
		if row.get("schedule") and row.get("note_no"):
			note_id = self.generate_note_id(row.get("note_no"), account_text)
			if note_id:
				account_text = f'<a href="#{note_id}" style="color: #000000;">{account_text}</a>'
		
		html += f"""
			<tr{schedule_attr} class="clickable-row" style="{clickable_style}">
				<td style='text-align:center; padding: 5px; border-left: 1px solid black; border-right: 1px solid black;'>{index}</td>
				<td style='text-align:left; padding: 5px; border-left: 1px solid black; border-right: 1px solid black; {bold}'>{indent}{account_text}</td>
				<td style='text-align:center; padding: 5px; border-left: 1px solid black; border-right: 1px solid black;'>{row.get("note_no") or ""}</td>
				<td style='text-align:right; padding: 5px; border-left: 1px solid black; border-right: 1px solid black; background-color: #e8f5e8;'>{'{:,.0f}'.format(row["amount"]) if row.get("amount") else ""}</td>
				<td style='text-align:right; padding: 5px; border-left: 1px solid black; border-right: 1px solid black;'>{'{:,.0f}'.format(row["previous_year_amount"]) if row.get("previous_year_amount") else ""}</td>
			</tr>
		"""

		html += "</tbody></table>"
		return html

	def get_balance_sheet_data(self, template_name):
		balance_sheet_doc = frappe.get_doc("Balance Sheet Template", template_name)
		amount_cache = {}

		def calc_amount_for_particular(particular_name, year):
			cache_key = (particular_name, year)
			if cache_key in amount_cache:
				return amount_cache[cache_key]

			fr_particular = frappe.get_doc("FR Particular", particular_name)
			if getattr(fr_particular, "is_total", 1):
				amount = 0
				for p in getattr(fr_particular, "particulars", []):
					child_name = p.particular
					amount += calc_amount_for_particular(child_name, year)
				amount = amount * 100000
			else:
				gl_accounts = []
				for g in fr_particular.get('primary_and_secondary_group_mapping'):
					gl_account = frappe.get_list("GL Group Mapping", {"company": self.company,"report_type": self.report_type, 'primary_group': g.primary_group, 'secondary_group': g.secondary_group}, pluck = 'gl_account')
					gl_accounts.extend(gl_account)
				if len(gl_accounts) == 0:
					amount = 0
				else:
					placeholders = ','.join(['%s'] * len(gl_accounts))
					query = f"""
						SELECT SUM(amount) FROM `tabFR Trail Balance Entry`
						WHERE company=%s AND fiscal_year=%s AND gl_account IN ({placeholders})
					"""
					params = [self.company, year] + gl_accounts
					amount = (frappe.db.sql(query, params)[0][0] or 0)
			
			# Apply value reversal if show_reversed_value is checked
			if getattr(fr_particular, "show_reversed_value", 0):
				amount = -amount
			
			amount_cache[cache_key] = int(round(amount / 100000))
			return amount_cache[cache_key]

		data = []
		for row in balance_sheet_doc.balance_sheet_template_details:
			if not row.account:
				continue
			amount_2024 = calc_amount_for_particular(row.account, self.fiscal_year)
			amount_2023 = calc_amount_for_particular(row.account, self.previous_fiscal_year)
			
			# Get the schedule from FR Particular
			fr_particular = frappe.get_doc("FR Particular", row.account)
			schedule = getattr(fr_particular, "schedule", "")
			
			# Get note number for schedule if it exists
			note_no = row.note
			if schedule:
				schedule_note_no = self.get_note_number_for_schedule(schedule)
				if schedule_note_no:
					note_no = schedule_note_no
			
			data.append({
				"account": row.particular_name,
				"note_no": note_no,
				"amount_2024": amount_2024,
				"amount_2023": amount_2023,
				"indent": int(row.indent_level or 0),
				"is_bold": row.is_bold,
				"header": row.header,
				"group": row.group,
				"schedule": schedule,
			})
		return data

	def render_balance_sheet(self, template_name):
		data = self.get_balance_sheet_data(template_name)
		current_year_date, previous_year_date = self.get_current_and_prevous_year_date()

		html = f"""
		<table style="width:100%; border-collapse: collapse; font-size: 13px; border: 1px solid black;">
			<thead>
				<tr style="background-color: #f1f1f1;">
					<th style='text-align:center; padding: 5px; width: 5%; border: 1px solid black;'></th>
					<th style='text-align:left; padding: 5px; width: 45%; border: 1px solid black;'>Particulars</th>
					<th style='text-align:center; padding: 5px; width: 10%; border: 1px solid black;'>Note No.</th>
					<th style='text-align:center; padding: 5px; width: 20%; border: 1px solid black; background-color: #e8f5e8;'>As at <br> {current_year_date}</th>
					<th style='text-align:center; padding: 5px; width: 20%; border: 1px solid black;'>As at <br> {previous_year_date}</th>
				</tr>
			</thead>
			<tbody>
		"""

		header_counter = 0
		group_counter = 0
		def to_alpha(idx):
			return f"({chr(65+idx)})"
		def to_roman(idx):
			romans = [
				'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
				'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX'
			]
			return f"({romans[idx]})" if idx < len(romans) else f"({idx+1})"
		def to_lower_alpha(idx):
			return f"({chr(97+idx)})"
		def to_lower_roman(idx):
			romans = [
				'i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x',
				'xi', 'xii', 'xiii', 'xiv', 'xv', 'xvi', 'xvii', 'xviii', 'xix', 'xx'
			]
			return f"({romans[idx]})" if idx < len(romans) else f"({idx+1})"

		# Stack to track group/indent context
		# Each stack entry: {'alpha_counter': int, 'roman_counter': int, 'indent': int, 'last_indent_1': int}
		group_stack = []
		# Top-level group
		group_stack.append({'alpha_counter': 0, 'roman_counter': 0, 'indent': 0, 'last_indent_1': None})

		for idx, row in enumerate(data):
			indent_val = int(row.get("indent", 0))
			indent = "&nbsp;" * (indent_val * 4)
			bold = "font-weight: bold;" if row.get("is_bold") else ""
			index = ""
			account_label = row.get('account') or ''

			# Handle header
			if row.get("header"):
				index = to_alpha(header_counter)
				header_counter += 1
				# Reset group stack for new header
				group_stack = [{'alpha_counter': 0, 'roman_counter': 0, 'indent': 0, 'last_indent_1': None}]
			# Handle group
			elif row.get("group"):
				index = to_roman(group_counter)
				group_counter += 1
				# New group context: push new counters
				group_stack.append({'alpha_counter': 0, 'roman_counter': 0, 'indent': indent_val, 'last_indent_1': None})
			# Only non-bold, non-group, non-header accounts get index prefix
			elif not row.get("is_bold"):
				# For indent=0, not header/group: use (a), (b), ...
				if indent_val == 0:
					alpha_idx = group_stack[-1]['alpha_counter']
					account_label = f"{to_lower_alpha(alpha_idx)} {account_label}"
					group_stack[-1]['alpha_counter'] += 1
				# For indent=1, not header/group: use (i), (ii), ...
				elif indent_val == 1:
					if group_stack[-1]['last_indent_1'] != 1:
						group_stack[-1]['roman_counter'] = 0
					roman_idx = group_stack[-1]['roman_counter']
					account_label = f"{to_lower_roman(roman_idx)} {account_label}"
					group_stack[-1]['roman_counter'] += 1
					group_stack[-1]['last_indent_1'] = 1
				else:
					group_stack[-1]['last_indent_1'] = indent_val
			else:
				# For bold, non-group, non-header, do not prefix any index
				if indent_val == 1:
					group_stack[-1]['last_indent_1'] = 1
				else:
					group_stack[-1]['last_indent_1'] = indent_val

			# Add data-schedule attribute and clickable styling for account rows
			schedule_attr = f' data-schedule="{row.get("note_no", "")}"' if row.get("note_no") else ""
			clickable_style = "cursor: pointer; background-color: #f8f9fa;" if row.get("note_no") else ""
			hover_style = "background-color: #e9ecef;" if row.get("note_no") else ""
			
			# Add anchor link for schedule navigation
			account_text = account_label
			if row.get("schedule") and row.get("note_no"):
				note_id = self.generate_note_id(row.get("note_no"), account_label)
				if note_id:
					account_text = f'<a href="#{note_id}" style="color: #000000;">{account_label}</a>'

			html += f"""
				<tr{schedule_attr} class="clickable-row" style="{clickable_style}">
					<td style='text-align:center; padding: 5px; border-left: 1px solid black; border-right: 1px solid black; {bold}'>{index}</td>
					<td style='text-align:left; padding: 5px; border-left: 1px solid black; border-right: 1px solid black; {bold}'>{indent}{account_text}</td>
					<td style='text-align:center; padding: 5px; border-left: 1px solid black; border-right: 1px solid black;'>{row.get("note_no") or ""}</td>
					<td style='text-align:right; padding: 5px; border-left: 1px solid black; border-right: 1px solid black; background-color: #e8f5e8;'>{'{:,.0f}'.format(row["amount_2024"]) if row.get("amount_2024") else ""}</td>
					<td style='text-align:right; padding: 5px; border-left: 1px solid black; border-right: 1px solid black;'>{'{:,.0f}'.format(row["amount_2023"]) if row.get("amount_2023") else ""}</td>
				</tr>
			"""

		html += "</tbody></table>"
		return html

	def get_cash_flow_data(self, template_name):
		cash_flow_doc = frappe.get_doc("Cash Flow Template", template_name)
		amount_cache = {}

		def calc_amount_for_particular(particular_name, year):
			cache_key = (particular_name, year)
			if cache_key in amount_cache:
				return amount_cache[cache_key]

			fr_particular = frappe.get_doc("FR Particular", particular_name)
			if getattr(fr_particular, "is_total", 1):
				amount = 0
				for p in getattr(fr_particular, "particulars", []):
					child_name = p.particular
					amount += calc_amount_for_particular(child_name, year)
				amount = amount * 100000
			else:
				gl_accounts = []
				for g in fr_particular.get('primary_and_secondary_group_mapping'):
					gl_account = frappe.get_list("GL Group Mapping", {"company": self.company,"report_type": self.report_type, 'primary_group': g.primary_group, 'secondary_group': g.secondary_group}, pluck = 'gl_account')
					gl_accounts.extend(gl_account)

				if len(gl_accounts) == 0:
					amount = 0
				else:
					placeholders = ','.join(['%s'] * len(gl_accounts))
					query = f"""
						SELECT SUM(amount) FROM `tabFR Trail Balance Entry`
						WHERE company=%s AND fiscal_year=%s AND account IN ({placeholders})
					"""
					params = [self.company, year] + gl_accounts
					amount = (frappe.db.sql(query, params)[0][0] or 0)
			
			# Apply value reversal if show_reversed_value is checked
			if getattr(fr_particular, "show_reversed_value", 0):
				amount = -amount
			
			amount_cache[cache_key] = int(round(amount / 100000))
			return amount_cache[cache_key]

		data = []
		for row in cash_flow_doc.cash_flow_template_details:
			if not row.account:
				continue
			amount_current = calc_amount_for_particular(row.account, self.fiscal_year)
			amount_previous = calc_amount_for_particular(row.account, self.previous_fiscal_year)
			data.append({
				"account": row.particular_name,
				"note_no": getattr(row, "note", None),
				"amount": amount_current,
				"previous_year_amount": amount_previous,
				"indent": int(row.indent_level or 0),
				"is_bold": row.is_bold,
				"group": row.group,
			})
		return data

	def render_cash_flow(self, template_name):
		data = self.get_cash_flow_data(template_name)
		current_year_date, previous_year_date = self.get_current_and_prevous_year_date()

		html = f"""
		<table style="width:100%; border-collapse: collapse; font-size: 13px; border: 1px solid black;">
			<thead>
				<tr style="background-color: #f1f1f1;">
					<th style='text-align:center; padding: 5px; width: 5%; border: 1px solid black;'></th>
					<th style='text-align:left; padding: 5px; width: 45%; border: 1px solid black;'>Particulars</th>
					<th style='text-align:center; padding: 5px; width: 20%; border: 1px solid black; background-color: #e8f5e8;'>As at <br> {current_year_date}</th>
					<th style='text-align:center; padding: 5px; width: 20%; border: 1px solid black;'>As at <br> {previous_year_date}</th>
				</tr>
			</thead>
			<tbody>
		"""

		def to_roman(idx):
			romans = [
				'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
				'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX'
			]
			return romans[idx] if idx < len(romans) else str(idx+1)

		group_counter = 0
		for row in data:
			indent = "&nbsp;" * (int(row.get("indent", 0)) * 4)
			bold = "font-weight: bold;" if row.get("is_bold") else ""
			if row.get("group"):
				index = to_roman(group_counter)
				group_counter += 1
			else:
				index = ""
			html += f"""
				<tr>
					<td style='text-align:center; padding: 5px; border-left: 1px solid black; border-right: 1px solid black; {bold}'>{index}</td>
					<td style='text-align:left; padding: 5px; border-left: 1px solid black; border-right: 1px solid black; {bold}'>{indent}{row.get("account") or ""}</td>
					<td style='text-align:right; padding: 5px; border-left: 1px solid black; border-right: 1px solid black; background-color: #e8f5e8;'>{'{:,.0f}'.format(row["amount"]) if row.get("amount") else ""}</td>
					<td style='text-align:right; padding: 5px; border-left: 1px solid black; border-right: 1px solid black;'>{'{:,.0f}'.format(row["previous_year_amount"]) if row.get("previous_year_amount") else ""}</td>
				</tr>
			"""
		html += "</tbody></table>"
		return html

	def render_equity_share_table(self):
		rows = [
			{"particular": "As at 1st April, 2023", "shares": "5,93,60,000", "amount": "5,936", "bold": 1},
			{"particular": "Changes in equity share capital during the year", "shares": "-", "amount": "-", "bold": 0},
			{"particular": "Balance as at 31st March, 2024", "shares": "5,93,60,000", "amount": "5,936", "bold": 1},
			{"particular": "Changes in equity share capital during the year", "shares": "-", "amount": "-", "bold": 0},
			{"particular": "Balance as at 31st March, 2025", "shares": "5,93,60,000", "amount": "5,936", "bold": 1},
		]

		html = '''
		<h5 style="text-align: left; font-weight: bold; padding: 8px; margin-bottom: -50px">A. Equity share capital (Amount in ₹ Lacs)</h5>
		<table style="width: 60%; border-collapse: collapse; border: 1px solid #000; font-family: Arial, sans-serif; font-size: 13px;">
		<thead>
			<tr>
				<th style="padding: 8px; border: 1px solid black; width: 50%;">Particulars</th>
				<th style="padding: 8px; text-align: right; border: 1px solid black; width: 25%;">Number of Shares</th>
				<th style="padding: 8px; text-align: right; border: 1px solid black; width: 25%; background-color: #e8f5e8;">Equity share capital</th>
			</tr>
		</thead>
		<tbody>
		'''

		for idx, row in enumerate(rows):
			bold_class = 'font-weight: bold;' if row["bold"] == 1 else ''
			# For the last row, treat as footer with full border
			if idx == len(rows) - 1:
				html += f'''
				<tr>
					<td style="padding: 8px; border: 1px solid black; {bold_class} width: 50%;">{row['particular']}</td>
					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 25%;">{row['shares']}</td>
					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 25%; background-color: #e8f5e8;">{row['amount']}</td>
				</tr>
			'''
			else:
				html += f'''
				<tr>
					<td style="padding: 8px; border-left: 1px solid black; border-right: 1px solid black; {bold_class} width: 50%;">{row['particular']}</td>
					<td style="padding: 8px; text-align: right; border-left: 1px solid black; border-right: 1px solid black; width: 25%;">{row['shares']}</td>
					<td style="padding: 8px; text-align: right; border-left: 1px solid black; border-right: 1px solid black; width: 25%; background-color: #e8f5e8;">{row['amount']}</td>
				</tr>
			'''

		html += "</tbody>\n</table>"
		return html

	@frappe.whitelist()
	def get_financial_report_template(self):
		self.financial_report_details.clear()

		if not self.financial_report_template:
			frappe.throw("Please select a Financial Report Template before fetching.")

		template = frappe.get_doc("Financial Report Template", self.financial_report_template)

		for d in template.financial_report_template_details:
			context = {
				"company": self.company
			}
			section_desc = frappe.render_template(d.section_description or "", context)
			section_desc = f'<div style="text-align: justify;">{section_desc}</div>'
			subsection_desc = frappe.render_template(d.subsection_description or "", context)
			subsection_desc = f'<div style="text-align: justify;">{subsection_desc}</div>'
			
			self.append('financial_report_details', {
				'section_type': d.section_type,
				'doctype_name': d.doctype_name,
				'section': d.section,
				'subsection': d.subsection,
				'section_description': section_desc,
				'subsection_description': subsection_desc,
			})

	"""	    ################################################################################################
		    ################################################################################################
		#######################                                                              #####################
		#######################                                                              #####################
		#######################                Monthly Financial Report Logic                #####################
		#######################                                                              #####################
		#######################                                                              #####################
		    ################################################################################################
		    ################################################################################################        """

	def get_monthly_dates(self, only_dates=False):
		"""Get formatted dates for monthly reports with proper column labels"""
		if not self.current_month or not self.previous_month:
			return "", "", ""
		
		current_year = int(self.current_year_ending_date.split("-")[0] if self.current_year_ending_date else datetime.now().year) -1
		month_num = {
			'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
			'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
		}
		
		current_month_num = month_num.get(self.current_month, 1)
		previous_month_num = month_num.get(self.previous_month, 1)
		
		if current_month_num == 12:
			month_end_date = datetime(int(current_year) + 1, 1, 1) - timedelta(days=1)
		else:
			month_end_date = datetime(int(current_year), current_month_num + 1, 1) - timedelta(days=1)
		
		if previous_month_num == 12:
			previous_month_end_date = datetime(int(current_year), 12, 31)
		elif previous_month_num == 1:
			previous_month_end_date = datetime(int(current_year) - 1, 12, 31)
		else:
			previous_month_end_date = datetime(int(current_year), previous_month_num + 1, 1) - timedelta(days=1)

		if only_dates:
			return month_end_date, previous_month_end_date

		month_end_label = f"Year Ended {month_end_date.strftime('%d/%m/%Y')}"
		current_fiscal_year_end_label = f"Year Ended {previous_month_end_date.strftime('%d/%m/%Y')}"
		if self.previous_year_ending_date:
			if isinstance(self.previous_year_ending_date, str):
				previous_year_date_obj = datetime.strptime(self.previous_year_ending_date, "%Y-%m-%d")
			else:
				previous_year_date_obj = self.previous_year_ending_date
			previous_fiscal_year_end_label = f"Year Ended {previous_year_date_obj.strftime('%d/%m/%Y')}"
		else:
			previous_fiscal_year_end_label = ""
		
		return month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label


	def get_monthly_finished_goods_and_wip(self, note_type, total, field=None):
		rows = []
		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
		
		current_month_finished_goods = self.sum_group_amt_monthly("Inventories", "Finished Goods", self.current_month, self.fiscal_year)
		current_month_wip = self.sum_group_amt_monthly("Inventories", "Work in Progress", self.current_month, self.fiscal_year)
		current_month_total = current_month_finished_goods + current_month_wip

		cls_previous_month_finished_goods = self.sum_group_amt_monthly("Inventories", "Finished Goods", self.previous_month, self.fiscal_year)
		cls_previous_month_wip = self.sum_group_amt_monthly("Inventories", "Work in Progress", self.previous_month, self.fiscal_year)
		cls_previous_month_total = cls_previous_month_finished_goods + cls_previous_month_wip
		
		previous_month_finished_goods = self.sum_group_amt_monthly("Inventories", "Finished Goods", "March", self.previous_fiscal_year)
		previous_month_wip = self.sum_group_amt_monthly("Inventories", "Work in Progress", "March", self.previous_fiscal_year)
		previous_month_total = previous_month_finished_goods + previous_month_wip
		
		ftm_finished_goods = cls_previous_month_finished_goods - current_month_finished_goods
		ftm_wip = cls_previous_month_wip - current_month_wip
		ftm_total = ftm_finished_goods + ftm_wip
		
		net_increase_finished_goods = current_month_finished_goods - previous_month_finished_goods
		net_increase_wip = previous_month_wip - current_month_wip
		net_increase_total = previous_month_total - current_month_total

		prev_net_total = previous_month_total - cls_previous_month_total
		
		if total:
			if field == 'net_increase_total':
				return net_increase_total
			elif field == 'ftm_total':
				return ftm_total
			elif field == 'previous_month_amt':
				return prev_net_total
			else:
				return 0
		
		rows.extend([
			{"particulars": "Inventories at the end of the month","current_month_amt": 0,"previous_month_amt": 0,"ftm_amt": 0,"is_subtotal": True},
			{"particulars": "Finished goods","current_month_amt": current_month_finished_goods,"previous_month_amt": cls_previous_month_finished_goods ,"ftm_amt": ftm_finished_goods,"is_subtotal": False},
			{"particulars": "Work-in-progress","current_month_amt": current_month_wip,"previous_month_amt": cls_previous_month_wip,"ftm_amt": ftm_wip,"is_subtotal": False},
			{"particulars": "","current_month_amt": current_month_total,"previous_month_amt": cls_previous_month_total ,"ftm_amt": ftm_total,"is_subtotal": False},
			{"particulars": "Inventories at the beginning of the month","current_month_amt": 0,"previous_month_amt": 0,"ftm_amt": 0,"is_subtotal": True},
			{"particulars": "Finished goods","current_month_amt": previous_month_finished_goods,"previous_month_amt": previous_month_finished_goods,"ftm_amt": 0,"is_subtotal": False},
			{"particulars": "Work-in-progress","current_month_amt": previous_month_wip,"previous_month_amt": previous_month_wip,"ftm_amt": 0,"is_subtotal": False},
			{"particulars": "","current_month_amt": previous_month_total,"previous_month_amt": previous_month_total,"ftm_amt": 0,"is_subtotal": False},
			{"particulars": "Net increase","current_month_amt": net_increase_total,"previous_month_amt": prev_net_total,"ftm_amt": prev_net_total - net_increase_total,"is_subtotal": True}
		])
		
		html = f'''
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr>
					<th style="border:2px solid #222; text-align:left; width:40%; padding:6px 8px;"><b>Particulars</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px;"><b>{month_end_label}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px;"><b>FTM</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px;"><b>{current_fiscal_year_end_label}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px;"><b>{previous_fiscal_year_end_label}</b></th>
				</tr>
			</thead>
			<tbody>
		'''
		
		for row in rows:
			# Format amounts
			current_month_amt_str = f"{row['current_month_amt']:,.0f}" if row['current_month_amt'] else ""
			previous_month_amt_str = f"{row['previous_month_amt']:,.0f}" if row['previous_month_amt'] else ""
			ftm_amt_str = f"{row['ftm_amt']:,.0f}" if row['ftm_amt'] else ""
			
			# Style for totals
			bold_style = "font-weight: bold;" if row["is_subtotal"] else ""
			border_style = "border:2px solid #222;" if row["is_subtotal"] else "border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;"
			
			html += f'''
				<tr>
					<td style="{border_style} text-align:left; padding:6px 8px; {bold_style}">{row['particulars']}</td>
					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style} background-color:#e8f5e8;">{current_month_amt_str}</td>
					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{ftm_amt_str}</td>
					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{previous_month_amt_str}</td>
					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style}"></td>
				</tr>
			'''
		
		html += "</tbody></table>"
		return html

	def get_monthly_cost_of_material_consumed(self, note_type, total, field=None):
		rows = []
		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
		
		# Get opening stock (beginning of month)
		opening_stock = self.sum_group_amt_monthly("Inventories", "Raw Materials and Packing Material", "March", self.previous_fiscal_year)
		
		# Get closing stock (end of month)
		closing_stock_current = self.sum_group_amt_monthly("Inventories", "Raw Materials and Packing Material", self.current_month, self.fiscal_year)
		closing_stock_previous = self.sum_group_amt_monthly("Inventories", "Raw Materials and Packing Material", self.previous_month, self.fiscal_year)
		
		# Get purchases and other related costsMaterial consumed
		purchases_current = self.sum_group_amt_monthly("Material consumed", "Cost of Goods Sold", self.current_month, self.fiscal_year)  - self.get_monthly_finished_goods_and_wip(note_type, total = True, field='net_increase_total') + (closing_stock_current - opening_stock)
		purchases_previous = self.sum_group_amt_monthly("Material consumed", "Cost of Goods Sold", self.previous_month, self.fiscal_year) - self.get_monthly_finished_goods_and_wip(note_type, total = True, field='previous_month_amt') + (closing_stock_previous - opening_stock)
		# frappe.throw(f"{self.sum_group_amt_monthly('Material consumed', 'Cost of Goods Sold', self.previous_month, self.fiscal_year)},  {self.get_monthly_finished_goods_and_wip(note_type, total = True, field='previous_month_amt')}, {closing_stock_previous},  {opening_stock}")

		# Calculate cost of materials consumed
		cost_consumed_current = opening_stock + purchases_current - closing_stock_current
		cost_consumed_previous = opening_stock + purchases_previous - closing_stock_previous
		
		# FTM calculations
		ftm_purchases = purchases_current - purchases_previous
		ftm_closing_stock = closing_stock_current - closing_stock_previous
		ftm_cost_consumed = cost_consumed_current - cost_consumed_previous
		
		if total:
			if field == 'cost_consumed_current':
				return cost_consumed_current
			elif field == 'cost_consumed_previous':
				return cost_consumed_previous
			elif field == 'ftm_cost_consumed':
				return ftm_cost_consumed
			else:
				return 0
		
		rows.extend([
			{"particulars": "Opening Stock", "current_month_amt": opening_stock, "previous_month_amt": opening_stock, "ftm_amt": 0, "is_subtotal": False},
			{"particulars": "Add: purchases & other related costs", "current_month_amt": purchases_current, "previous_month_amt": purchases_previous, "ftm_amt": ftm_purchases, "is_subtotal": False},
			{"particulars": "Less: closing stock", "current_month_amt": closing_stock_current, "previous_month_amt":  closing_stock_previous, "ftm_amt": ftm_closing_stock, "is_subtotal": False},
			{"particulars": "Cost of Materials Consumed", "current_month_amt": cost_consumed_current, "previous_month_amt": cost_consumed_previous, "ftm_amt": ftm_cost_consumed, "is_subtotal": True}
		])

		# Generate HTML table
		html = f'''
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr>
					<th style="border:2px solid #222; text-align:left; width:40%; padding:6px 8px;"><b>Particulars</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>{month_end_label}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>FTM</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>{current_fiscal_year_end_label}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>{previous_fiscal_year_end_label}</b></th>
				</tr>
			</thead>
			<tbody>
		'''
		
		for row in rows:
			# Format amounts
			current_month_amt_str = f"{row['current_month_amt']:,.0f}" if row['current_month_amt'] else "-"
			ftm_amt_str = f"{row['ftm_amt']:,.0f}" if row['ftm_amt'] else "-"
			previous_month_amt_str = f"{row['previous_month_amt']:,.0f}" if row['previous_month_amt'] else "-"
			
			# Style for totals
			bold_style = "font-weight: bold;" if row["is_subtotal"] else ""
			border_style = "border:2px solid #222;" if row["is_subtotal"] else "border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;"
			
			html += f'''
				<tr>
					<td style="{border_style} text-align:left; padding:6px 8px; {bold_style}">{row['particulars']}</td>
					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style} background-color:#e8f5e8;">{current_month_amt_str}</td>
					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{ftm_amt_str}</td>
					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{previous_month_amt_str}</td>
					<td style="{border_style} text-align:right; padding:6px 8px; {bold_style}"></td>
				</tr>
			'''
		
		html += "</tbody></table>"
		return html

	@frappe.whitelist()
	def get_monthly_consolidation_note_data(self, primary_consolidation_group):
		"""Get monthly consolidation note data with current month, previous month, and FTM amounts"""
		secondary_groups = frappe.db.get_list("GL Group Mapping", {"primary_group": primary_consolidation_group}, pluck="secondary_group")
		secondary_consolidation_groups = set(sorted([g for g in secondary_groups if g]))
		data = []
		
		for sec in secondary_consolidation_groups:
			current_month_amount = self.sum_group_amt_monthly(primary_consolidation_group, sec, self.current_month, self.fiscal_year)
			previous_month_amount = self.sum_group_amt_monthly(primary_consolidation_group, sec, self.previous_month, self.fiscal_year)
			ftm_amount = current_month_amount - previous_month_amount
			previous_year_amount = self.sum_group_amt(primary_consolidation_group, sec, self.previous_fiscal_year)
			
			data.append({
				"account": sec,
				"current_month_amount": current_month_amount,
				"previous_month_amount": previous_month_amount,
				"ftm_amount": ftm_amount,
				"previous_year": previous_year_amount,
				"indent": 0,
				"is_bold": 0
			})
		return data

	def render_monthly_balance_sheet(self, template_name):
		"""Render monthly balance sheet with note-style UI"""
		data = self.get_monthly_balance_sheet_data(template_name)
		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()

		html = f"""
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr style="background-color: #f1f1f1;">
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 5%;'></th>
					<th style='border:2px solid #222; text-align:left; padding: 5px; width: 40%;'>Particulars</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 10%;'>Note No.</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 15%; background-color: #e8f5e8;'>{month_end_label}</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 10%;'>FTM</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 10%;'>{current_fiscal_year_end_label}</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 10%;'>{previous_fiscal_year_end_label}</th>
				</tr>
			</thead>
			<tbody>
		"""

		# Counters for structured index generation
		header_counter = 0
		group_counter = 0
		group_stack = [{'alpha_counter': 0, 'roman_counter': 0, 'indent': 0, 'last_indent_1': None}]

		# Helpers for indices
		def to_alpha(idx): return f"({chr(65+idx)})"
		def to_roman(idx): return f"({['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX'][idx]})"
		def to_lower_alpha(idx): return f"({chr(97+idx)})"
		def to_lower_roman(idx): return f"({['i','ii','iii','iv','v','vi','vii','viii','ix','x','xi','xii','xiii','xiv','xv','xvi','xvii','xviii','xix','xx'][idx]})"

		for row in data:
			indent_val = int(row.get("indent", 0))
			indent = "&nbsp;" * (indent_val * 4)
			bold = "font-weight: bold;" if row.get("is_bold") else ""
			account_label = row.get("account") or ""
			note_no = row.get("note_no")
			schedule = row.get("schedule")
			index = ""

			# Section Headers
			if row.get("header"):
				index = to_alpha(header_counter)
				header_counter += 1
				group_stack = [{'alpha_counter': 0, 'roman_counter': 0, 'indent': 0, 'last_indent_1': None}]
			elif row.get("group"):
				index = to_roman(group_counter)
				group_counter += 1
				group_stack.append({'alpha_counter': 0, 'roman_counter': 0, 'indent': indent_val, 'last_indent_1': None})
			elif not row.get("is_bold"):
				if indent_val == 0:
					alpha_idx = group_stack[-1]['alpha_counter']
					account_label = f"{to_lower_alpha(alpha_idx)} {account_label}"
					group_stack[-1]['alpha_counter'] += 1
				elif indent_val == 1:
					if group_stack[-1]['last_indent_1'] != 1:
						group_stack[-1]['roman_counter'] = 0
					roman_idx = group_stack[-1]['roman_counter']
					account_label = f"{to_lower_roman(roman_idx)} {account_label}"
					group_stack[-1]['roman_counter'] += 1
					group_stack[-1]['last_indent_1'] = 1
				else:
					group_stack[-1]['last_indent_1'] = indent_val

			# Add data-schedule attribute and clickable styling for account rows
			schedule_attr = f' data-schedule="{note_no}"' if note_no else ""
			clickable_style = "cursor: pointer; background-color: #f8f9fa;" if note_no else ""
			
			# Add anchor link if schedule exists
			account_text = account_label
			if schedule and note_no:
				note_id = self.generate_note_id(note_no, account_label)
				account_text = f'<a href="#{note_id}" style="color: #000000;">{account_label}</a>'

			# Final row
			html += f"""
			<tr{schedule_attr} class="clickable-row" style="{clickable_style}">
				<td style='text-align:center; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; {bold}'>{index}</td>
				<td style='text-align:left; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; {bold}'>{indent}{account_text}</td>
				<td style='text-align:center; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{note_no or ""}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; background-color: #e8f5e8;'>{'{:,.2f}'.format(row.get("current_month_amount", 0)) if row.get("current_month_amount") else ""}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(row.get("ftm_amount", 0)) if row.get("ftm_amount") else ""}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(row.get("previous_month_amount", 0)) if row.get("previous_month_amount") else ""}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(row.get("previous_year", 0)) if row.get("previous_year") else ""}</td>
			</tr>
			"""

		html += "</tbody></table>"
		return html


	def render_monthly_profit_and_loss(self, template_name):
		"""Render monthly profit and loss with note-style UI"""
		current_month_end, previous_month_end, previous_fiscal_year_end_label = self.get_monthly_dates()
		data = self.get_monthly_profit_and_loss_data(template_name)

		html = f"""
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr style="background-color: #f1f1f1;">
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 5%;'></th>
					<th style='border:2px solid #222; text-align:left; padding: 5px; width: 40%;'>Particulars</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 10%;'>Note No.</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 15%; background-color: #e8f5e8;'>{current_month_end}</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 10%;'>FTM</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 10%;'>{previous_month_end}</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 10%;'>{previous_fiscal_year_end_label}</th>
				</tr>
			</thead>
			<tbody>
		"""

		def to_roman(idx):
			romans = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX']
			return f"({romans[idx]})" if idx < len(romans) else f"({idx+1})"
		
		group_counter = 0
		for row in data:
			note_no = row.get("note_no")
			indent_val = int(row.get("indent", 0))
			indent = "&nbsp;" * (indent_val * 4)
			bold = "font-weight: bold;" if row.get("is_bold") else ""
			index = to_roman(group_counter) if row.get("group") else ""
			if row.get("group"): group_counter += 1

			# Add data-schedule attribute and clickable styling for account rows
			schedule_attr = f' data-schedule="{note_no}"' if note_no else ""
			clickable_style = "cursor: pointer; background-color: #f8f9fa;" if note_no else ""
			
			# Handle anchor link for schedule
			account_text = row.get("account") or ""
			schedule = row.get("schedule")
			if schedule and note_no:
				note_id = self.generate_note_id(note_no, account_text)
				if note_id:
					account_text = f'<a href="#' + note_id + '" style="color: #000000;">' + account_text + '</a>'

			html += f"""
			<tr{schedule_attr} class="clickable-row" style="{clickable_style}">
				<td style='text-align:center; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; {bold}'>{index}</td>
				<td style='text-align:left; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; {bold}'>{indent}{account_text}</td>
				<td style='text-align:center; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{note_no or ""}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; background-color: #e8f5e8;'>{'{:,.2f}'.format(row.get("current_month_amount", 0)) if row.get("current_month_amount") else ""}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(row.get("ftm_amount", 0)) if row.get("ftm_amount") else ""}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(row.get("previous_month_amount", 0)) if row.get("previous_month_amount") else ""}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(row.get("previous_year", 0)) if row.get("previous_year") else ""}</td>
			</tr>
			"""

		html += "</tbody></table>"
		return html

	def render_monthly_cash_flow(self, template_name):
		"""Render monthly cash flow with note-style UI"""
		data = self.get_monthly_cash_flow_data(template_name)
		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()

		html = f"""
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr style="background-color: #f1f1f1;">
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 5%;'></th>
					<th style='border:2px solid #222; text-align:left; padding: 5px; width: 40%;'>Particulars</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 15%; background-color: #e8f5e8;'>{month_end_label}</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 10%;'>FTM</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 10%;'>{current_fiscal_year_end_label}</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 10%;'>{previous_fiscal_year_end_label}</th>
				</tr>
			</thead>
			<tbody>
		"""

		def to_roman(idx):
			romans = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX']
			return f"({romans[idx]})" if idx < len(romans) else f"({idx+1})"

		group_counter = 0
		for row in data:
			indent = "&nbsp;" * (int(row.get("indent", 0)) * 4)
			bold = "font-weight: bold;" if row.get("is_bold") else ""
			index = to_roman(group_counter) if row.get("group") else ""
			if row.get("group"): group_counter += 1

			account_text = row.get("account") or ""

			html += f"""
			<tr>
				<td style='text-align:center; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; {bold}'>{index}</td>
				<td style='text-align:left; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; {bold}'>{indent}{account_text}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; background-color: #e8f5e8;'>{'{:,.2f}'.format(row.get("current_month_amount", 0)) if row.get("current_month_amount") else ""}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(row.get("ftm_amount", 0)) if row.get("ftm_amount") else ""}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(row.get("previous_month_amount", 0)) if row.get("previous_month_amount") else ""}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(row.get("previous_year", 0)) if row.get("previous_year") else ""}</td>
			</tr>
			"""

		html += "</tbody></table>"
		return html

	def render_monthly_equity_share_table(self):
		"""Render monthly equity share table with optimized structure"""
		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
		
		# For equity, we'll use the same data as it's typically static
		rows = [
			{"particular": "As at 1st April, 2023", "shares": "5,93,60,000", "amount": "5,936", "bold": 1},
			{"particular": "Changes in equity share capital during the year", "shares": "-", "amount": "-", "bold": 0},
			{"particular": "Balance as at 31st March, 2024", "shares": "5,93,60,000", "amount": "5,936", "bold": 1},
			{"particular": "Changes in equity share capital during the year", "shares": "-", "amount": "-", "bold": 0},
			{"particular": "Balance as at 31st March, 2025", "shares": "5,93,60,000", "amount": "5,936", "bold": 1},
		]

		html = f'''
		<h5 style="text-align: left; font-weight: bold; padding: 8px; margin-bottom: -50px">A. Equity share capital (Amount in ₹ Lacs)</h5>
		<table style="width: 100%; border-collapse: collapse; border: 1px solid #000; font-family: Arial, sans-serif; font-size: 13px;">
		<thead>
			<tr>
				<th style="padding: 8px; border: 1px solid black; width: 40%;">Particulars</th>
				<th style="padding: 8px; text-align: right; border: 1px solid black; width: 20%;">Number of Shares</th>
				<th style="padding: 8px; text-align: right; border: 1px solid black; width: 13%; background-color: #e8f5e8;">{month_end_label}</th>
				<th style="padding: 8px; text-align: right; border: 1px solid black; width: 13%;">{current_fiscal_year_end_label}</th>
				<th style="padding: 8px; text-align: right; border: 1px solid black; width: 14%;">{previous_fiscal_year_end_label}</th>
			</tr>
		</thead>
		<tbody>
		'''

		for idx, row in enumerate(rows):
			bold_class = 'font-weight: bold;' if row["bold"] == 1 else ''
			if idx == len(rows) - 1:
				html += f'''
				<tr>
					<td style="padding: 8px; border: 1px solid black; {bold_class} width: 40%;">{row['particular']}</td>
					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 20%;">{row['shares']}</td>
					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 13%; background-color: #e8f5e8;">{row['amount']}</td>
					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 13%;">{row['amount']}</td>
					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 14%;">{row['amount']}</td>
				</tr>
			'''
			else:
				html += f'''
				<tr>
					<td style="padding: 8px; border-left: 1px solid black; border-right: 1px solid black; {bold_class} width: 40%;">{row['particular']}</td>
					<td style="padding: 8px; text-align: right; border-left: 1px solid black; border-right: 1px solid black; width: 20%;">{row['shares']}</td>
					<td style="padding: 8px; text-align: right; border-left: 1px solid black; border-right: 1px solid black; width: 13%; background-color: #e8f5e8;">{row['amount']}</td>
					<td style="padding: 8px; text-align: right; border: 1px solid black; width: 13%;">{row['amount']}</td>
					<td style="padding: 8px; text-align: right; border-left: 1px solid black; border-right: 1px solid black; width: 14%;">{row['amount']}</td>
				</tr>
			'''

		html += "</tbody>\n</table>"
		return html

	def monthly_table_for_note_template_1(self, data):
		"""Optimized monthly table for note template 1"""
		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
		
		note_table = f'''
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr style="background-color: #f1f1f1;">
					<th style='border:2px solid #222; text-align:left; padding: 5px; width: 40%;'>Particulars</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 20%; background-color: #e8f5e8;'>{month_end_label}</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 20%;'>FTM</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 20%;'>{current_fiscal_year_end_label}</th>
					<th style='border:2px solid #222; text-align:center; padding: 5px; width: 20%;'>{previous_fiscal_year_end_label}</th>
				</tr>
			</thead>
			<tbody>
		'''

		total_current_month = 0
		total_previous_month = 0
		total_ftm = 0
		total_previous_year = 0
		for i, row in enumerate(data):
			indent = "&nbsp;" * (int(row.get("indent", 0)) * 4)
			bold = "font-weight: bold;" if row.get("is_bold") else ""
			current_month_amount = row.get('current_month_amount') or 0
			previous_month_amount = row.get('previous_month_amount') or 0
			ftm_amount = row.get('ftm_amount') or 0
			previous_year = row.get('previous_year') or 0
			total_current_month += current_month_amount
			total_previous_month += previous_month_amount
			total_ftm += ftm_amount
			total_previous_year += previous_year
			note_table += f'''
			<tr>
				<td style='text-align:left; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; {bold}'>{indent}{row.get("account") or ""}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; background-color: #e8f5e8;'>{'{:,.2f}'.format(current_month_amount) if current_month_amount else ''}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(ftm_amount) if ftm_amount else ''}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(previous_month_amount) if previous_month_amount else ''}</td>
				<td style='text-align:right; padding: 5px; border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none;'>{'{:,.2f}'.format(previous_year) if previous_year else ''}</td>
			</tr>
			'''
		# Add total row as footer
		note_table += f'''
			<tr>
				<td style='text-align:left; padding: 5px; border:2px solid #222; font-weight: bold;'>Total</td>
				<td style='text-align:right; padding: 5px; border:2px solid #222; font-weight: bold; background-color: #e8f5e8;'>{'{:,.2f}'.format(total_current_month)}</td>
				<td style='text-align:right; padding: 5px; border:2px solid #222; font-weight: bold;'>{'{:,.2f}'.format(total_ftm)}</td>
				<td style='text-align:right; padding: 5px; border:2px solid #222; font-weight: bold;'>{'{:,.2f}'.format(total_previous_month)}</td>
				<td style='text-align:right; padding: 5px; border:2px solid #222; font-weight: bold;'>{'{:,.2f}'.format(total_previous_year)}</td>
			</tr>
		'''
		note_table += "</tbody></table>"
		return note_table

	def get_monthly_profit_and_loss_data(self, template_name):
		"""Get monthly P&L data with current month, previous month, and FTM amounts"""
		profit_and_loss_doc = frappe.get_doc("Profit And Loss Template", template_name)
		amount_cache = {}

		def calc_amount_for_particular_monthly(particular_name, month, year, is_current=False, is_yearly=False):
			cache_key = (particular_name, year)
			if cache_key in amount_cache:
				return amount_cache[cache_key]

			fr_particular = frappe.get_doc("FR Particular", particular_name)
			if getattr(fr_particular, "is_total", 1):
				amount = 0
				for p in getattr(fr_particular, "particulars", []):
					child_name = p.particular
					if getattr(fr_particular, "to_subtract", 1):
						if amount == 0:
							amount = calc_amount_for_particular_monthly(child_name, month, year, is_current, is_yearly)
						else:
							amount -= calc_amount_for_particular_monthly(child_name, month, year, is_current, is_yearly)
					else:
						amount += calc_amount_for_particular_monthly(child_name, month, year, is_current, is_yearly)
				amount = amount * 100000
			elif getattr(fr_particular, "fetch_from_schedule", 1):
				amount = 0
				note_type = frappe.get_value("FR Section", fr_particular.schedule, 'note_type')
				if note_type == "Changes in inventories of Finished Goods and Work-In-Progress":
					field = 'net_increase_total' if is_current else 'ftm_amt'
					amount = self.get_monthly_finished_goods_and_wip(note_type, total = True, field=field)
				elif note_type == "Cost of Materials Consumed":
					field = 'cost_consumed_current' if is_current else 'cost_consumed_previous'
					amount = self.get_monthly_cost_of_material_consumed(note_type, total = True, field=field)
					
				amount = amount * 100000
			else:
				gl_accounts = []
				for g in fr_particular.get('primary_and_secondary_group_mapping'):
					gl_account = frappe.get_list("GL Group Mapping", {"company": self.company, "report_type": self.report_type, 'primary_group': g.primary_group, 'secondary_group': g.secondary_group}, pluck = 'gl_account')
					gl_accounts.extend(gl_account)
				
				if len(gl_accounts) == 0:
					amount = 0
				else:
					placeholders = ','.join(['%s'] * len(gl_accounts))
					query = f"""
						SELECT SUM(uploaded_amount) FROM `tabFR Trail Balance Entry`
						WHERE company = %s AND fiscal_year = %s AND gl_account IN ({placeholders})
					"""
					params = [self.company, year] + gl_accounts

					if not is_yearly:
						query += " AND month = %s"
						params.append(month)

					amount = (frappe.db.sql(query, params)[0][0] or 0)
			
			if getattr(fr_particular, "show_reversed_value", 0):
				amount = -amount
			
			amount_cache[cache_key] = int(round(amount / 100000))
			return amount_cache[cache_key]
		 
		grouped_data = []
		for row in profit_and_loss_doc.profit_and_loss_template_details:
			if not row.account:
				continue
			current_month_amount = calc_amount_for_particular_monthly(row.account, self.current_month, self.fiscal_year, is_current = True)
			previous_month_amount = calc_amount_for_particular_monthly(row.account, self.previous_month, self.fiscal_year)
			ftm_amount = current_month_amount - previous_month_amount
			previous_year_amount = calc_amount_for_particular_monthly(row.account, self.previous_month, self.previous_fiscal_year, is_yearly = True)
			
			# Get the schedule from FR Particular
			fr_particular = frappe.get_doc("FR Particular", row.account)
			schedule = getattr(fr_particular, "schedule", "")
			
			# Get note number for schedule if it exists
			note_no = ""
			if schedule:
				schedule_note_no = self.get_note_number_for_schedule(schedule)
				if schedule_note_no:
					note_no = schedule_note_no
			
			grouped_data.append({
				"account": row.particular_name,
				"note_no": note_no,
				"current_month_amount": current_month_amount,
				"previous_month_amount": previous_month_amount,
				"ftm_amount": ftm_amount,
				"previous_year": previous_year_amount,
				"indent": int(row.indent_level or 0),
				"is_bold": row.is_bold,
				"group": row.group,
				"schedule": schedule,
			})
		return grouped_data

	def get_monthly_balance_sheet_data(self, template_name):
		"""Get monthly balance sheet data with current month, previous month, and FTM amounts"""
		balance_sheet_doc = frappe.get_doc("Balance Sheet Template", template_name)
		amount_cache = {}

		def calc_amount_for_particular_monthly(particular_name, month, year, is_current=False, is_yearly=False):
			cache_key = (particular_name, month, year)
			if cache_key in amount_cache:
				return amount_cache[cache_key]

			fr_particular = frappe.get_doc("FR Particular", particular_name)
			def get_schedule_amount():
				note_type = frappe.get_value("FR Section", fr_particular.schedule, 'note_type')
				if note_type == "Changes in inventories of Finished Goods and Work-In-Progress":
					field = 'ftm_total' if is_current else 'net_increase_total'
					return self.get_monthly_finished_goods_and_wip(note_type, total=True, field=field)
				elif note_type == "Cost of Materials Consumed":
					field = 'cost_consumed_previous' if is_current else 'cost_consumed_current'
					return self.get_monthly_cost_of_material_consumed(note_type, total=True, field=field)
				return 0

			def get_grouped_gl_amount():
				gl_accounts = []
				for g in fr_particular.get('primary_and_secondary_group_mapping'):
					accounts = frappe.get_list("GL Group Mapping", filters={"company": self.company, "report_type": self.report_type, "primary_group": g.primary_group, "secondary_group": g.secondary_group}, pluck="gl_account")
					gl_accounts.extend(accounts)

				if not gl_accounts:
					return 0

				placeholders = ','.join(['%s'] * len(gl_accounts))
				base_query = f"""
					SELECT SUM(uploaded_amount) FROM `tabFR Trail Balance Entry`
					WHERE company = %s AND fiscal_year = %s AND gl_account IN ({placeholders})
				"""
				params = [self.company, year] + gl_accounts

				if not is_yearly:
					base_query += " AND month = %s"
					params.append(month)

				return frappe.db.sql(base_query, params)[0][0] or 0

			# Main logic
			if getattr(fr_particular, "is_total", 1):
				amount = sum(calc_amount_for_particular_monthly(p.particular, month, year)for p in fr_particular.get("particulars", [])) * 100000
			elif getattr(fr_particular, "fetch_from_schedule", 1):
				amount = get_schedule_amount()
			else:
				amount = get_grouped_gl_amount()

			if getattr(fr_particular, "show_reversed_value", 0):
				amount = -amount

			amount_cache[cache_key] = int(round(amount / 100000))
			return amount_cache[cache_key]

		data = []
		for row in balance_sheet_doc.balance_sheet_template_details:
			if not row.account:
				continue
			current_month_amount = calc_amount_for_particular_monthly(row.account, self.current_month, self.fiscal_year)
			previous_month_amount = calc_amount_for_particular_monthly(row.account, self.previous_month, self.fiscal_year)
			ftm_amount = current_month_amount - previous_month_amount
			previous_year_amount = calc_amount_for_particular_monthly(row.account, self.previous_month, self.previous_fiscal_year, is_yearly = True)
			
			# Get the schedule from FR Particular
			fr_particular = frappe.get_doc("FR Particular", row.account)
			schedule = getattr(fr_particular, "schedule", "")
			
			# Get note number for schedule if it exists
			note_no = ""
			if schedule:
				schedule_note_no = self.get_note_number_for_schedule(schedule)
				if schedule_note_no:
					note_no = schedule_note_no
			
			data.append({
				"account": row.particular_name,
				"note_no": note_no,
				"current_month_amount": current_month_amount,
				"previous_month_amount": previous_month_amount,
				"ftm_amount": ftm_amount,
				"previous_year": previous_year_amount,
				"indent": int(row.indent_level or 0),
				"is_bold": row.is_bold,
				"header": row.header,
				"group": row.group,
				"schedule": schedule,
			})
		return data

	def get_monthly_cash_flow_data(self, template_name):
		"""Get monthly cash flow data with current month, previous month, and FTM amounts"""
		cash_flow_doc = frappe.get_doc("Cash Flow Template", template_name)
		amount_cache = {}

		def calc_amount_for_particular_monthly(particular_name, month, year):
			cache_key = (particular_name, month, year)
			if cache_key in amount_cache:
				return amount_cache[cache_key]

			fr_particular = frappe.get_doc("FR Particular", particular_name)
			if getattr(fr_particular, "is_total", 1):
				amount = 0
				for p in getattr(fr_particular, "particulars", []):
					child_name = p.particular
					amount += calc_amount_for_particular_monthly(child_name, month, year)
				amount = amount * 100000
			else:
				gl_accounts = []
				for g in fr_particular.get('primary_and_secondary_group_mapping'):
					gl_account = frappe.get_list("GL Group Mapping", {"company": self.company,"report_type": self.report_type, 'primary_group': g.primary_group, 'secondary_group': g.secondary_group}, pluck = 'gl_account')
					gl_accounts.extend(gl_account)
					
				if len(gl_accounts) == 0:
					amount = 0
				else:
					placeholders = ','.join(['%s'] * len(gl_accounts))
					query = f"""
						SELECT SUM(amount) FROM `tabFR Trail Balance Entry`
						WHERE company=%s AND fiscal_year=%s AND account IN ({placeholders})
						AND month >= %s
					"""
					params = [self.company, year] + gl_accounts + [month]
					
					amount = (frappe.db.sql(query, params)[0][0] or 0)
			
			# Apply value reversal if show_reversed_value is checked
			if getattr(fr_particular, "show_reversed_value", 0):
				amount = -amount
			
			amount_cache[cache_key] = int(round(amount / 100000))
			return amount_cache[cache_key]

		data = []
		for row in cash_flow_doc.cash_flow_template_details:
			if not row.account:
				continue
			current_month_amount = calc_amount_for_particular_monthly(row.account, self.current_month, self.fiscal_year)
			previous_month_amount = calc_amount_for_particular_monthly(row.account, self.previous_month, self.fiscal_year)
			ftm_amount = current_month_amount - previous_month_amount
			data.append({
				"account": row.particular_name,
				"note_no": getattr(row, "note", None),
				"current_month_amount": current_month_amount,
				"previous_month_amount": previous_month_amount,
				"ftm_amount": ftm_amount,
				"previous_year": 0,
				"indent": int(row.indent_level or 0),
				"is_bold": row.is_bold,
				"group": row.group,
			})
		return data

	def get_monthly_borrowing_non_current_note_data(self, primary_group):
		"""Get monthly borrowing non-current note data with optimized structure"""
		rows = []
		total_current_month_amt = 0
		total_previous_month_amt = 0
		total_ftm_amt = 0
		total_previous_year = 0
		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()

		secondary_group = frappe.get_all("Standalone Group",filters={"parent_consolidation_group": primary_group},
			fields=["name", "ind_as_description"]
		)

		for g in secondary_group:
			html_particulars = f"<b>{g.name}</b><br>{g.ind_as_description or ''}"
			
			current_month_amt = self.sum_group_amt_monthly(primary_group, g.name, self.current_month, self.fiscal_year)
			previous_month_amt = self.sum_group_amt_monthly(primary_group, g.name, self.previous_month, self.fiscal_year)
			ftm_amt = current_month_amt - previous_month_amt
			previous_year = 0

			rows.append({
				"particulars": html_particulars,
				"current_month_amt": f"{current_month_amt:,.0f}" if current_month_amt else "-",
				"previous_month_amt": f"{previous_month_amt:,.0f}" if previous_month_amt else "-",
				"ftm_amt": f"{ftm_amt:,.0f}" if ftm_amt else "-",
				"previous_year": f"{previous_year:,.0f}" if previous_year else "-",
				"group": False
			})

			total_current_month_amt += current_month_amt or 0
			total_previous_month_amt += previous_month_amt or 0
			total_ftm_amt += ftm_amt or 0
			total_previous_year += previous_year or 0

		# HTML rendering with optimized structure
		html = f'''
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr>
					<th style="border:2px solid #222; text-align:left; width:50%; padding:6px 8px;"><b>Particulars</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>{month_end_label}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background-color:#e8f5e8;"><b>FTM</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px;"><b>{current_fiscal_year_end_label}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px;"><b>{previous_fiscal_year_end_label}</b></th>
				</tr>
			</thead>
			<tbody>
		'''

		for row in rows:
			bold = "font-weight: bold;" if row.get("group") else ""
			html += f'''
				<tr>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:left; padding:6px 8px; {bold}">{row['particulars']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; background-color:#e8f5e8;">{row['current_month_amt']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row['ftm_amt']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row['previous_month_amt']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px;">{row['previous_year']}</td>
				</tr>
			'''

		# Append total row
		html += f'''
			<tr>
				<td style="border:2px solid #222; text-align:left; font-weight:bold; padding:6px 8px;">Total</td>
				<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px; background-color:#e8f5e8;">{total_current_month_amt:,.0f}</td>
				<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px;">{total_ftm_amt:,.0f}</td>
				<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px;">{total_previous_month_amt:,.0f}</td>
				<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px;">{total_previous_year:,.0f}</td>
			</tr>
		'''

		html += "</tbody></table>"
		return html

	def get_monthly_other_equity_note_data(self):
		"""Get monthly other equity note data with optimized structure"""
		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
		
		# For equity notes, we'll use the same data as it's typically static
		data = [
			("Retained earnings", "", "", True),
			("Balance as at the beginning of the year", "59,183", "41,144", False),
			("Net Profit for the year", "42,545", "18,111", False),
			("Other comprehensive income", "(142)", "(72)", False),
			("Balance as at the end of the year", "1,01,586", "59,183", True),
			("Capital Contribution", "", "", True),
			("Balance as at the beginning of the year", "4,459", "4,459", False),
			("Add: Equity contribution on financial guarantee taken", "3", "-", False),
			("<b>Balance as at the end of the year</b>", "4,462", "4,459", True),
			("<b>Total</b>", "1,06,048", "63,642", True),
		]
		
		html = f'''
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr>
					<th style="border:2px solid #222; text-align:left; width:40%; padding:6px 8px; background:#f2f2f0;"><b>Particulars</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#e8f5e8;"><b>{month_end_label}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#f2f2f0;"><b>{current_fiscal_year_end_label}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#f2f2f0;"><b>{previous_fiscal_year_end_label}</b></th>
				</tr>
			</thead>
			<tbody>
		'''
		for i, (particulars, amt_2025, amt_2024, bold) in enumerate(data):
			is_last = i == len(data) - 1
			if is_last:
				html += f'''
				<tr>
					<td style="border:2px solid #222; text-align:left; font-weight:bold; padding:6px 8px; background:#fff;">{particulars}</td>
					<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px; background:#e8f5e8;">{amt_2025}</td>
					<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px; background:#fff;">{amt_2024}</td>
					<td style="border:2px solid #222; text-align:right; font-weight:bold; padding:6px 8px; background:#fff;">{amt_2025}</td>
				</tr>
				'''
			else:
				bold = "font-weight: bold;" if bold else ""
				html += f'''
				<tr>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:left; padding:6px 8px; {bold}">{particulars}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; background:#e8f5e8;">{amt_2025}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; background:#fff;">{amt_2024}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; background:#fff;">{amt_2025}</td>
				</tr>
				'''
		html += "</tbody></table>"
		return html

	def get_monthly_equity_share_capital_note_data(self):
		"""Get monthly equity share capital note data with optimized structure"""
		# This method can be implemented based on your specific requirements
		# For now, returning a placeholder
		return self.get_monthly_other_equity_note_data()

	def get_monthly_trade_and_other_receivables_note_data(self):
		"""Get monthly trade and other receivables note data with optimized structure"""
		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
		
		# Calculate amounts for current month, previous month, and FTM
		credit_impaired_current = round(self.sum_group_amt_monthly("Trade Receivables - credit Impaired", "Trade Receivables - credit Impaired", self.current_month, self.fiscal_year)) or 0
		credit_impaired_previous = round(self.sum_group_amt_monthly("Trade Receivables - credit Impaired", "Trade Receivables - credit Impaired", self.previous_month, self.fiscal_year)) or 0
		credit_impaired_ftm = credit_impaired_current - credit_impaired_previous

		trade_receivables_current = round(self.sum_group_amt_monthly("Trade receivables", "Trade receivables", self.current_month, self.fiscal_year)) or 0
		trade_receivables_previous = round(self.sum_group_amt_monthly("Trade receivables", "Trade receivables", self.previous_month, self.fiscal_year)) or 0
		trade_receivables_ftm = trade_receivables_current - trade_receivables_previous

		unsecured_good_current = trade_receivables_current - credit_impaired_current
		unsecured_good_previous = trade_receivables_previous - credit_impaired_previous
		unsecured_good_ftm = trade_receivables_ftm - credit_impaired_ftm

		other_receivables_current = round(self.sum_group_amt_monthly("Other Receivables", "Other Receivables", self.current_month, self.fiscal_year)) or 0
		other_receivables_previous = round(self.sum_group_amt_monthly("Other Receivables", "Other Receivables", self.previous_month, self.fiscal_year)) or 0
		other_receivables_ftm = other_receivables_current - other_receivables_previous

		total_current = unsecured_good_current + other_receivables_current
		total_previous = unsecured_good_previous + other_receivables_previous
		total_ftm = unsecured_good_ftm + other_receivables_ftm

		main_table = [
			("Unsecured, considered good", unsecured_good_current, unsecured_good_previous, unsecured_good_ftm, False),
			("Credit impaired", credit_impaired_current, credit_impaired_previous, credit_impaired_ftm, False),
			("", trade_receivables_current, trade_receivables_previous, trade_receivables_ftm, False),
			("Less: Provision for credit impaired trade receivables", credit_impaired_current, credit_impaired_previous, credit_impaired_ftm, False),
			("Other receivables", "", "", "", True),
			("Unsecured, considered good", other_receivables_current, other_receivables_previous, other_receivables_ftm, False),
			("Total", total_current, total_previous, total_ftm, True),
		]

		# Main Table
		html = f'''
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr>
					<th style="border:2px solid #222; text-align:left; width:40%; padding:6px 8px; background:#fafbfc;"><b>Particulars</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#e8f5e8;"><b>{month_end_label}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;"><b>{current_fiscal_year_end_label}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;"><b>{previous_fiscal_year_end_label}</b></th>
				</tr>
			</thead>
			<tbody>
		'''
		for i, row in enumerate(main_table):
			is_last = i == len(main_table) - 1
			style = "font-weight:bold;" if row[4] else ""
			if is_last:
				html += f'''
				<tr>
					<td style="border:2px solid #222; text-align:left; width:40%; padding:6px 8px; {style}">{row[0]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px; {style} background-color:#e8f5e8;">{row[1]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px; {style}">{row[2]}</td>
					<td style="border:2px solid #222; text-align:right; padding:6px 8px; {style}">{row[3]}</td>
				</tr>
			'''
			else:
				html += f'''
				<tr>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:left; width:40%; padding:6px 8px; {style}">{row[0]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; {style} background-color:#e8f5e8;">{row[1]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; {style}">{row[2]}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; padding:6px 8px; {style}">{row[3]}</td>
				</tr>
			'''
		html += "</tbody></table>"
		return html

	def get_monthly_investment_non_current_note_data(self):
		"""Get monthly investment non-current note data with optimized structure"""
		month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
		
		# For investments, we'll use the same data as it's typically static
		data = [{"particulars": "Investment in equity Instruments of subsidiaries measured at Cost (Unquoted, Fully paid Up)", "face_value": "", "shares_current": "", "amount_current": "", "shares_previous": "", "amount_previous": "", "shares_ftm": "", "amount_ftm": "", "bold": 1}]
		
		fiscal_doc = frappe.get_doc("Fiscal Year", self.fiscal_year)
		all_companies = frappe.get_list("Company", {"parent_company": self.company}, pluck="name")
		total_current = 0
		total_previous = 0
		total_ftm = 0
		total_previous_year = 0

		for company in all_companies:
			current_equity_entries = frappe.get_all("FR Equity Entry", 
				filters={"company": company, "holding_company": self.company, "category": "Equity Shares", "posting_date": ["Between", [fiscal_doc.year_start_date, fiscal_doc.year_end_date]]},
				fields=["company", "no_of_shares", "face_value", "investment_value", "posting_date"], 
				order_by="posting_date desc")

			e_current = current_equity_entries[0] if current_equity_entries else None

			face_value = e_current.get("face_value") if e_current else None
			shares_current = e_current.get("no_of_shares") if e_current else 0
			amount_current = e_current.get("investment_value") if e_current else 0
			shares_previous = shares_current  # Same as current for monthly
			amount_previous = amount_current  # Same as current for monthly
			shares_ftm = shares_current  # Same as current for monthly
			amount_ftm = amount_current  # Same as current for monthly

			shares_current_str = f"{shares_current:,.0f}" if shares_current else "0"
			amount_current_str = f"{amount_current:,.0f}" if amount_current else "0"
			shares_previous_str = f"{shares_previous:,.0f}" if shares_previous else "0"
			amount_previous_str = f"{amount_previous:,.0f}" if amount_previous else "0"
			shares_ftm_str = f"{shares_ftm:,.0f}" if shares_ftm else "0"
			amount_ftm_str = f"{amount_ftm:,.0f}" if amount_ftm else "0"

			total_current += amount_current
			total_previous += amount_previous
			total_ftm += amount_ftm
			total_previous_year += amount_previous
			data.append({
				"particulars": company,
				"face_value": f"₹ {face_value:.0f}" if face_value else "NA",
				"shares_current": shares_current_str,
				"amount_current": amount_current_str,
				"shares_previous": shares_previous_str,
				"amount_previous": amount_previous_str,
				"shares_ftm": shares_ftm_str,
				"amount_ftm": amount_ftm_str,
				"shares_previous_year": shares_ftm_str,
				"amount_previous_year": amount_ftm_str,
				"bold": 0
			})

		data.append({
			"particulars": "Total of Equity Instruments Measured at cost",
			"face_value": "",
			"shares_current": "",
			"amount_current": f"{total_current:,.0f}",
			"shares_previous": "",
			"amount_previous": f"{total_previous:,.0f}",
			"shares_ftm": "",
			"amount_ftm": f"{total_ftm:,.0f}",
			"shares_previous_year": f"{total_ftm:,.0f}",
			"amount_previous_year": f"{total_ftm:,.0f}",
			"bold": 1
		})

		table = f'''
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr>
					<th style="border:2px solid #222; text-align:left; width:40%; padding:6px 8px; background:#fafbfc;"><b>Particulars</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;"><b>Face Value</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#e8f5e8;" colspan="2"><b>{month_end_label}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;" colspan="2"><b>FTM</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;" colspan="2"><b>{current_fiscal_year_end_label}</b></th>
					<th style="border:2px solid #222; text-align:center; padding:6px 8px; background:#fafbfc;" colspan="2"><b>{previous_fiscal_year_end_label}</b></th>
				</tr>
				<tr>
					<th style="border:2px solid #222; background:#fafbfc;"></th>
					<th style="border:2px solid #222; text-align:center; background:#fafbfc;"></th>
					<th style="border:2px solid #222; text-align:center; background:#e8f5e8;"><b>No. of shares</b></th>
					<th style="border:2px solid #222; text-align:center; background:#e8f5e8;"><b>(₹ in lacs)</b></th>
					<th style="border:2px solid #222; text-align:center; background:#fafbfc;"><b>No. of shares</b></th>
						<th style="border:2px solid #222; text-align:center; background:#fafbfc;"><b>(₹ in lacs)</b></th>
						<th style="border:2px solid #222; text-align:center; background:#fafbfc;"><b>No. of shares</b></th>
						<th style="border:2px solid #222; text-align:center; background:#fafbfc;"><b>(₹ in lacs)</b></th>
						<th style="border:2px solid #222; text-align:center; background:#fafbfc;"><b>No. of shares</b></th>
						<th style="border:2px solid #222; text-align:center; background:#fafbfc;"><b>(₹ in lacs)</b></th>
				</tr>
			</thead>
			<tbody>
		'''
		for i, row in enumerate(data):
			bold = "font-weight: bold;" if row["bold"] else ""
			is_last = i == len(data) - 1
			
			if is_last:
				table += f'''
				<tr>
					<td style="border:2px solid #222; text-align:left; width:40%; {bold}">{row['particulars']}</td>
					<td style="border:2px solid #222; text-align:center;">{row['face_value']}</td>
					<td style="border:2px solid #222; text-align:right; background-color:#e8f5e8;">{row['shares_current']}</td>
					<td style="border:2px solid #222; text-align:right; background-color:#e8f5e8;">{row['amount_current']}</td>
					<td style="border:2px solid #222; text-align:right;">{row['shares_ftm']}</td>
					<td style="border:2px solid #222; text-align:right;">{row['amount_ftm']}</td>
					<td style="border:2px solid #222; text-align:right;">{row['shares_previous']}</td>
					<td style="border:2px solid #222; text-align:right;">{row['amount_previous']}</td>
					<td style="border:2px solid #222; text-align:right;">{row['shares_previous_year']}</td>
					<td style="border:2px solid #222; text-align:right;">{row['amount_previous_year']}</td>
				</tr>
				'''
			else:
				table += f'''
				<tr>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:left; width:40%; {bold}">{row['particulars']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:center;">{row['face_value']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; background-color:#e8f5e8;">{row['shares_current']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right; background-color:#e8f5e8;">{row['amount_current']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right;">{row['shares_ftm']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right;">{row['amount_ftm']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right;">{row['shares_previous']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right;">{row['amount_previous']}</td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right;"></td>
					<td style="border-left:2px solid #222; border-right:2px solid #222; border-top:none; border-bottom:none; text-align:right;"></td>
				</tr>
				'''
		table += "</tbody></table>"
		return table

	@frappe.whitelist()
	def export_to_excel(self):
		"""Export financial report to Excel with multiple tabs"""
		doc = frappe.get_doc("Financial Report", self.name)
		wb = openpyxl.Workbook()
		wb.remove(wb.active)
		sch_counter = 4
		
		# Debug: Print all sections
		frappe.logger().info(f"Total sections: {len(doc.financial_report_details)}")
		
		for section_detail in doc.financial_report_details:
			if not section_detail.table_data:
				continue
			if section_detail.section_type == "Consolidation Note":
				sheet_name = f"SCH-{sch_counter}"
				if section_detail.section_name:
					section_title = f" Note {sch_counter}: {section_detail.section_name}"
				else:
					continue
				sch_counter += 1
			else:
				sheet_name = section_detail.section_type.replace(" & ", "_").replace(" ", "_")
				section_title = section_detail.section_type
			
			ws = wb.create_sheet(title=sheet_name)
			
			title_cell = ws.cell(row=1, column=1, value=section_title)
			title_cell.font = Font(bold=True, size=14)
			title_cell.alignment = Alignment(horizontal='left')
			
			# Merge cells for title (assuming max 10 columns)
			ws.merge_cells('A1:E1')
			
			row_offset = 2
			table_data = section_detail.table_data
			
			soup = BeautifulSoup(table_data, 'html.parser')
			table = soup.find('table')
			
			if table:
				rows = table.find_all('tr')
				for row_idx, row in enumerate(rows, 1):
					cells = row.find_all(['td', 'th'])
					for col_idx, cell in enumerate(cells, 1):
						cell_value = cell.get_text(strip=True)
						ws.cell(row=row_idx + row_offset, column=col_idx, value=cell_value)
						
						cell_obj = ws.cell(row=row_idx + row_offset, column=col_idx)
						
						# Check if it's a header (th) or has background color
						if cell.name == 'th' or 'background-color: #e8f5e8' in str(cell):
							cell_obj.fill = PatternFill(start_color="E8F5E8", end_color="E8F5E8", fill_type="solid")
							cell_obj.font = Font(bold=True)
						
						# Apply borders
						thin_border = Border(
							left=Side(style='thin'),
							right=Side(style='thin'),
							top=Side(style='thin'),
							bottom=Side(style='thin')
						)
						cell_obj.border = thin_border
						
						# Center align headers
						if cell.name == 'th':
							cell_obj.alignment = Alignment(horizontal='center', vertical='center')
						else:
							# Right align numeric values
							if cell_value and cell_value.replace(',', '').replace('-', '').replace('.', '').isdigit():
								cell_obj.alignment = Alignment(horizontal='right')
							else:
								cell_obj.alignment = Alignment(horizontal='left')
				
				# Auto-adjust column widths
				for column in ws.columns:
					max_length = 0
					column_letter = get_column_letter(column[0].column)
					for cell in column:
						try:
							if len(str(cell.value)) > max_length:
								max_length = len(str(cell.value))
						except:
							pass
					adjusted_width = min(max_length + 2, 50)
					ws.column_dimensions[column_letter].width = adjusted_width
			else:
				frappe.logger().warning(f"No table found in HTML for section: {section_detail.section_type}")
		
		# Save the workbook
		file_name = f"Financial_Report_{self.name}_{frappe.utils.nowdate()}.xlsx"
		file_path = os.path.join(get_site_path(), 'private', 'files', file_name)
		
		# Ensure directory exists
		os.makedirs(os.path.dirname(file_path), exist_ok=True)
		
		wb.save(file_path)
		
		# Create file document
		file_doc = frappe.get_doc({
			"doctype": "File",
			"file_name": file_name,
			"file_url": f"/private/files/{file_name}",
			"is_private": 1,
			"attached_to_doctype": "Financial Report",
			"attached_to_name": self.name
		})
		file_doc.insert(ignore_permissions=True)
		
		return {
			"file_url": file_doc.file_url,
			"file_name": file_name
		}

	@frappe.whitelist()
	def export_to_pdf(self):
		from frappe.utils import get_site_path
		from frappe.utils.pdf import get_pdf
		from frappe.utils.jinja import render_template
		from frappe.utils.file_manager import save_file

		doc = frappe.get_doc("Financial Report", self.name)

		# Render the print format (replace 'Financial Report' with your Print Format name if different)
		html = frappe.get_print(
			doctype="Financial Report",
			name=self.name,
			print_format="Financial Report",
			style="Standard"
		)

		# Generate PDF content
		pdf_content = get_pdf(html)

		# Save PDF to File Doc
		file_doc = save_file(
			f"Financial_Report_{self.name}.pdf",
			pdf_content,
			"Financial Report",
			self.name,
			is_private=True
		)
	
	@frappe.whitelist()
	def test_clickable_functionality(self):
		"""Test method to verify clickable functionality is working"""
		try:
			# Get a sample financial report
			reports = frappe.get_all("Financial Report", limit=1)
			if not reports:
				return {"status": "error", "message": "No financial reports found"}
			
			report_name = reports[0].name
			doc = frappe.get_doc("Financial Report", report_name)
			
			# Check if the report has data
			if not doc.financial_report_details:
				return {"status": "error", "message": "Financial report has no details"}
			
			# Check for schedules in the data
			schedules_found = []
			for detail in doc.financial_report_details:
				if detail.section_type == "Balance Sheet":
					# Get balance sheet data to check for schedules
					data = self.get_balance_sheet_data(detail.section) if detail.section else []
					for row in data:
						if row.get("schedule"):
							schedules_found.append(row["schedule"])
			
			return {
				"status": "success", 
				"message": f"Clickable functionality test completed. Found {len(schedules_found)} schedules: {schedules_found[:5]}",
				"schedules_found": schedules_found
			}
			
		except Exception as e:
			frappe.log_error(f"Clickable functionality test error: {str(e)}", "Financial Report Clickable Test Error")
			return {"status": "error", "message": str(e)}

		return {
			"file_url": file_doc.file_url,
			"file_name": file_doc.file_name
		}

