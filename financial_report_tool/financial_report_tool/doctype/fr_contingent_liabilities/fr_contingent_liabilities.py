# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from financial_report_tool.financial_report_tool.contingent_note import (
	CONTINGENT_DEFAULTS,
	build_contingent_html,
	get_previous_fiscal_year,
	get_texts,
	year_end_label,
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
		"""Show the standard text in cells that were never filled (records created before these fields existed)."""
		for fieldname, default in CONTINGENT_DEFAULTS.items():
			if not self.get(fieldname):
				self.set(fieldname, default)

	def validate(self):
		for fieldname, default in CONTINGENT_DEFAULTS.items():
			if not self.get(fieldname):
				self.set(fieldname, default)

	def get_note_html(self):
		"""Note 50 HTML for the print format: this record is the current year, its previous fiscal year the comparative."""
		unit = frappe.db.get_single_value("FR Financial Settings", "amount_display_unit") or "Lakhs"
		divisor, unit_word = AMOUNT_UNITS.get(unit, AMOUNT_UNITS["Lakhs"])
		previous_year = get_previous_fiscal_year(self.fiscal_year)
		previous = frappe._dict()
		if previous_year:
			name = frappe.db.get_value(
				"FR Contingent Liabilities",
				{"company": self.company, "fiscal_year": previous_year, "month": self.month},
			)
			if name:
				previous = frappe.get_doc("FR Contingent Liabilities", name)
		return build_contingent_html(
			get_texts(self),
			self,
			previous,
			year_end_label(self.fiscal_year),
			year_end_label(previous_year),
			unit_word,
			divisor,
		)
