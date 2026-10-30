# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from financial_report_tool.financial_report_tool.contingent_note import (
	CONTINGENT_DEFAULTS,
	ROWS,
	default_heading,
	get_previous_doc,
	get_texts,
	resolved_rows,
	table_html,
)

# FR Financial Settings.amount_display_unit -> (divisor, label word); same values as the Financial Report
AMOUNT_UNITS = {
	"Actual": (1, "Actuals"),
	"Hundreds": (100, "Hundreds"),
	"Thousands": (1000, "Thousands"),
	"Lakhs": (100000, "Lacs"),
	"Millions": (1000000, "Millions"),
	"Crores": (10000000, "Crores"),
}


class FRContingentLiabilities(Document):
	def onload(self):
		"""Show the standard texts in cells that were never filled."""
		self.fill_defaults()

	def validate(self):
		self.fill_defaults()
		self.fill_previous_year_amounts()
		self.calculate_totals()

	def fill_defaults(self):
		for fieldname, default in CONTINGENT_DEFAULTS.items():
			if not self.get(fieldname):
				self.set(fieldname, default)
		if self.fiscal_year:
			if not self.cl_head_current:
				self.cl_head_current = default_heading(self.fiscal_year)
			if not self.cl_head_previous:
				self.cl_head_previous = default_heading(self.fiscal_year, previous=True)

	def fill_previous_year_amounts(self):
		"""A previous-year amount left at 0 takes the current-year amount of the previous Fiscal Year master."""
		previous = get_previous_doc(self.company, self.fiscal_year, self.month)
		if not previous:
			return
		for suffix, _ in ROWS:
			if not self.get(f"cl_{suffix}_previous"):
				self.set(f"cl_{suffix}_previous", previous.get(f"cl_{suffix}_current") or 0)

	def calculate_totals(self):
		self.cl_total_current = sum(flt(self.get(f"cl_{suffix}_current")) for suffix, _ in ROWS)
		self.cl_total_previous = sum(flt(self.get(f"cl_{suffix}_previous")) for suffix, _ in ROWS)

	def get_note_html(self):
		"""Note 50 HTML for the print format: this record is the current year, its previous fiscal year the comparative."""
		unit = frappe.db.get_single_value("FR Financial Settings", "amount_display_unit") or "Lakhs"
		divisor, unit_word = AMOUNT_UNITS.get(unit, AMOUNT_UNITS["Lakhs"])
		texts = get_texts(
			self, default_heading(self.fiscal_year), default_heading(self.fiscal_year, previous=True)
		)
		rows = resolved_rows(self, get_previous_doc(self.company, self.fiscal_year, self.month))
		return f'<p style="text-align:right; font-size:12px;">(₹ in {unit_word})</p>' + table_html(texts, rows, divisor)
