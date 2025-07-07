# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from collections import defaultdict
from frappe.model.document import Document


class FinancialReport(Document):
	def before_save(self):
		for i in self.financial_report_details:
			if i.section_type == "Balance Sheet":
				i.table_data = self.render_balance_sheet(i.section)

	def get_balance_sheet_data(self, template_name):
		balance_sheet_doc = frappe.get_doc("Balance Sheet Template", template_name)
		
		grouped_data = defaultdict(list)
		for row in balance_sheet_doc.balance_sheet_template_details:
			grouped_data[row.section].append({
				"account": row.particular_name,
				"note_no": row.note,
				"amount_2024": row.amount,
				"amount_2023": row.previous_year_amount,
				"indent": int(row.indent_level or 0),
				"is_bold": row.is_bold
			})
		
		return grouped_data


	def render_balance_sheet(self, template_name):
		grouped_data = self.get_balance_sheet_data(template_name)

		html = """
			<table style="width:100%; border-collapse: collapse; margin-bottom: 1rem; font-size: 13px; border: 1px solid black;">
				<thead>
					<tr style="border: 1px solid black;">
						<th style='text-align:left; padding: 8px; width: 50%; border: 1px solid black;'>Particulars</th>
						<th style='text-align:center; padding: 8px; width: 10%; border: 1px solid black;'>Note No.</th>
						<th style='text-align:right; padding: 8px; width: 20%; border: 1px solid black;'>As at 31-Mar-2024</th>
						<th style='text-align:right; padding: 8px; width: 20%; border: 1px solid black;'>As at 31-Mar-2023</th>
					</tr>
				</thead>
				<tbody>
		"""

		for section_title, items in grouped_data.items():
			html += f"""
				<tr style="border: 1px solid black;">
					<td colspan="4" style="font-weight: bold; padding: 8px; border: 1px solid black; background-color: #f1f1f1;">{section_title}</td>
				</tr>
			"""
			for item in items:
				indent = "&nbsp;" * (item["indent"] * 4)
				bold = "font-weight: bold;" if item["is_bold"] else ""
				html += f"""
					<tr style="border: 1px solid black;">
						<td style='text-align:left; padding: 8px; {bold} border: 1px solid black;'>{indent}{item['account']}</td>
						<td style='text-align:center; padding: 8px; border: 1px solid black;'>{item.get('note_no') or ''}</td>
						<td style='text-align:right; padding: 8px; border: 1px solid black;'>{f"{item['amount_2024']:,.2f}" if item['amount_2024'] else ''}</td>
						<td style='text-align:right; padding: 8px; border: 1px solid black;'>{f"{item['amount_2023']:,.2f}" if item['amount_2023'] else ''}</td>
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