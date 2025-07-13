# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import math
import frappe
from datetime import datetime
from collections import defaultdict
from frappe.model.document import Document


class FinancialReport(Document):
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

	def before_save(self):
		for i in self.financial_report_details:
			if i.section_type == "Balance Sheet":
				i.table_data = self.render_balance_sheet(i.section)
			if i.section_type == "Profit & Loss":
				i.table_data = self.render_profit_and_loss(i.section)
			if i.section_type == "Consolidation Note":
				section_data = frappe.db.get_value("FR Section", i.section, ["section_type_description", "fetch_data_from_trial_balance", "primary_consolidation_group"], as_dict=True)
				section_description = section_data.section_type_description if section_data else ""
				fetch_data_from_trial_balance = section_data.fetch_data_from_trial_balance if section_data else ""
				primary_consolidation_group = section_data.primary_consolidation_group if section_data else ""

				if fetch_data_from_trial_balance == 1:
					data = self.get_consolidation_note_data(primary_consolidation_group)
					note_table = self.table_for_note_template_1(data)
					context = {"note_table": note_table}
					i.section_description = frappe.render_template(section_description or "", context)

	def sum_group_amt(self, primary_group, group, year):
		return (frappe.db.sql("""
			SELECT SUM(amount) FROM `tabFR Trail Balance Entry`
			WHERE company=%s AND fiscal_year=%s AND primary_consolidation_group=%s AND consolidation_group=%s
		""", (self.company, year, primary_group, group))[0][0] or 0) / 100000

	def get_consolidation_note_data(self, primary_consolidation_group):
		secondary_consolidation_groups = frappe.db.get_list("Consolidation Group", {"parent_consolidation_group": primary_consolidation_group}, pluck="name")
		data = []
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
		current_year_date, previous_year_date = self.get_current_and_prevous_year_date()

		note_table = f"""
		<table style="width:100%; border-collapse: collapse; font-size: 13px; border: 1px solid black;">
			<thead>
				<tr style="background-color: #f1f1f1;">
					<th style='text-align:left; padding: 8px; width: 60%; border: 1px solid black;'>Particulars</th>
					<th style='text-align:center; padding: 8px; width: 20%; border: 1px solid black;'>Year Ended <br> {current_year_date}</th>
					<th style='text-align:center; padding: 8px; width: 20%; border: 1px solid black;'>Year Ended <br> {previous_year_date}</th>
				</tr>
			</thead>
			<tbody>
		"""

		for row in data:
			indent = "&nbsp;" * (int(row.get("indent", 0)) * 4)
			bold = "font-weight: bold;" if row.get("is_bold") else ""
			note_table += f"""
				<tr>
					<td style='text-align:left; padding: 8px; border: 1px solid black; {bold}'>{indent}{row.get("account") or ""}</td>
					<td style='text-align:right; padding: 8px; border: 1px solid black;'>{'{:,.2f}'.format(row['amount']) if row.get('amount') else ''}</td>
					<td style='text-align:right; padding: 8px; border: 1px solid black;'>{'{:,.2f}'.format(row['previous_year_amount']) if row.get('previous_year_amount') else ''}</td>
				</tr>
			"""

		# Add total row
		total_amount = sum(row.get('amount', 0) or 0 for row in data)
		total_prev_amount = sum(row.get('previous_year_amount', 0) or 0 for row in data)
		note_table += f"""
			<tr>
				<td style='text-align:left; padding: 8px; border: 1px solid black; font-weight: bold;'>Total</td>
				<td style='text-align:right; padding: 8px; border: 1px solid black; font-weight: bold;'>{'{:,.2f}'.format(total_amount)}</td>
				<td style='text-align:right; padding: 8px; border: 1px solid black; font-weight: bold;'>{'{:,.2f}'.format(total_prev_amount)}</td>
			</tr>
		"""

		note_table += "</tbody></table>"
		return note_table


	def get_profit_and_loss_data(self, template_name):
		profit_and_loss_doc = frappe.get_doc("Profit And Loss Template", template_name)
		grouped_data = []

		for row in profit_and_loss_doc.profit_and_loss_template_details:
			current_yr_amount, previous_yr_amount = 0, 0

			fr_particular = frappe.get_doc("FR Particular", row.account)
			is_total = fr_particular.is_total
			particulars = fr_particular.particulars
			consolidation_group = fr_particular.consolidation_groups

			# Case 1: Total row → Sum from all child particulars
			if is_total and particulars:
				for p in particulars:
					child_groups = frappe.get_doc("FR Particular", {'name': p.particular})
					
					for con_grp in child_groups.consolidation_groups:
						amount = frappe.db.sql(
							"""
							SELECT SUM(amount) FROM `tabFR Trail Balance Entry`
							WHERE fiscal_year=%s AND company=%s AND consolidation_group = %s
							""",
							(self.fiscal_year, self.company, con_grp.consolidation_group)
						)[0][0] or 0
						current_yr_amount += amount

			# Case 2: Single consolidation group
			elif consolidation_group:
				con_current_year = 0
				for con_grp in consolidation_group:
					amount = frappe.db.sql(
						"""
						SELECT SUM(amount) FROM `tabFR Trail Balance Entry`
						WHERE fiscal_year=%s AND company=%s AND consolidation_group = %s
						""",
						(self.fiscal_year, self.company, con_grp.consolidation_group)
					)[0][0] or 0
					current_yr_amount += amount
				
			# Append to result
			grouped_data.append({
				"account": row.particular_name,
				"note_no": row.note,
				"amount": current_yr_amount/100000,
				"previous_year_amount": previous_yr_amount,
				"indent": int(row.indent_level or 0),
				"is_bold": row.is_bold,
				"index": row.index,
			})

		return grouped_data

	def render_profit_and_loss(self, template_name):
		data = self.get_profit_and_loss_data(template_name)
		current_year_date, previous_year_date = self.get_current_and_prevous_year_date()

		html = f"""
		<table style="width:100%; border-collapse: collapse; font-size: 13px; border: 1px solid black;">
			<thead>
				<tr style="background-color: #f1f1f1;">
					<th style='text-align:left; padding: 8px; width: 5%; border: 1px solid black;'></th>
					<th style='text-align:left; padding: 8px; width: 45%; border: 1px solid black;'>Particulars</th>
					<th style='text-align:center; padding: 8px; width: 10%; border: 1px solid black;'>Note No.</th>
					<th style='text-align:center; padding: 8px; width: 20%; border: 1px solid black;'>Year Ended <br> {current_year_date}</th>
					<th style='text-align:center; padding: 8px; width: 20%; border: 1px solid black;'>Year Ended <br> {previous_year_date}</th>
				</tr>
			</thead>
			<tbody>
		"""



		for row in data:
			indent = "&nbsp;" * (int(row.get("indent_level", 0)) * 4)
			bold = "font-weight: bold;" if row.get("is_bold") else ""
			html += f"""
				<tr>
					<td style='text-align:left; padding: 8px; border: 1px solid black;'>{row.get("index") or ""}</td>
					<td style='text-align:left; padding: 8px; border: 1px solid black; {bold}'>{indent}{row.get("particular_name") or row.get("account") or ""}</td>
					<td style='text-align:center; padding: 8px; border: 1px solid black;'>{row.get("note_no") or ""}</td>
					<td style='text-align:right; padding: 8px; border: 1px solid black;'>{"{:,.2f}".format(row["amount"]) if row.get("amount") else ""}</td>
					<td style='text-align:right; padding: 8px; border: 1px solid black;'>{"{:,.2f}".format(row["previous_year_amount"]) if row.get("previous_year_amount") else ""}</td>
				</tr>
			"""

		html += "</tbody></table>"
		return html


	def get_balance_sheet_data(self, template_name):
		balance_sheet_doc = frappe.get_doc("Balance Sheet Template", template_name)
		data = []
		for row in balance_sheet_doc.balance_sheet_template_details:
			data.append({
				"account": row.particular_name,
				"note_no": row.note,
				"amount_2024": row.amount,
				"amount_2023": row.previous_year_amount,
				"indent": int(row.indent_level or 0),
				"is_bold": row.is_bold,
				"header": row.header,
				"group": row.group,
			})
		return data

	def render_balance_sheet(self, template_name):
		data = self.get_balance_sheet_data(template_name)
		current_year_date, previous_year_date = self.get_current_and_prevous_year_date()

		html = f"""
		<table style="width:100%; border-collapse: collapse; font-size: 13px; border: 1px solid black;">
			<thead>
				<tr style="background-color: #f1f1f1;">
					<th style='text-align:left; padding: 8px; width: 5%; border: 1px solid black;'>Index</th>
					<th style='text-align:left; padding: 8px; width: 45%; border: 1px solid black;'>Particulars</th>
					<th style='text-align:center; padding: 8px; width: 10%; border: 1px solid black;'>Note No.</th>
					<th style='text-align:center; padding: 8px; width: 20%; border: 1px solid black;'>As at <br> {current_year_date}</th>
					<th style='text-align:center; padding: 8px; width: 20%; border: 1px solid black;'>As at <br> {previous_year_date}</th>
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

			html += f"""
			<tr>
				<td style='text-align:left; padding: 8px; border: 1px solid black; {bold}'>{index}</td>
				<td style='text-align:left; padding: 8px; border: 1px solid black; {bold}'>{indent}{account_label}</td>
				<td style='text-align:center; padding: 8px; border: 1px solid black;'>{row.get("note_no") or ""}</td>
				<td style='text-align:right; padding: 8px; border: 1px solid black;'>{'{:,.2f}'.format(row["amount_2024"]) if row.get("amount_2024") else ""}</td>
				<td style='text-align:right; padding: 8px; border: 1px solid black;'>{'{:,.2f}'.format(row["amount_2023"]) if row.get("amount_2023") else ""}</td>
			</tr>
			"""

		html += "</tbody></table>"
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
			subsection_desc = frappe.render_template(d.subsection_description or "", context)
			
			self.append('financial_report_details', {
				'section_type': d.section_type,
				'doctype_name': d.doctype_name,
				'section': d.section,
				'subsection': d.subsection,
				'section_description': section_desc,
				'subsection_description': subsection_desc,
			})