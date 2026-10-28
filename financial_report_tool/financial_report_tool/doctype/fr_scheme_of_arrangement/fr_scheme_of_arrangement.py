# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from financial_report_tool.financial_report_tool.scheme_note import (
	PARAGRAPH_FIELDS,
	SCHEME_DEFAULTS,
	SCHEME_FIELDS,
	SCHEME_NOTE_TYPE,
	build_scheme_html,
	compose_before_text,
	push_master_to_rows,
	split_before_text,
)


def get_section_description():
	"""Standard text above the tables: description of the FR Section whose note type is Scheme of Arrangement."""
	return frappe.db.get_value("FR Section", {"note_type": SCHEME_NOTE_TYPE}, "section_type_description") or ""


class FRSchemeofArrangement(Document):
	def validate(self):
		duplicate = frappe.db.exists(
			"FR Scheme of Arrangement",
			{"company": self.company, "fiscal_year": self.fiscal_year, "name": ["!=", self.name]},
		)
		if duplicate:
			frappe.throw(
				_("{0} already exists for {1}, {2}").format(duplicate, self.company, self.fiscal_year),
				title=_("Duplicate Scheme of Arrangement"),
			)
		# Empty fields start from the standard text so that the form never shows blank cells
		for fieldname, default in SCHEME_DEFAULTS.items():
			if not self.get(fieldname):
				self.set(fieldname, default)
		if not any(self.get(f) for f in PARAGRAPH_FIELDS):
			for fieldname, value in split_before_text(get_section_description()).items():
				self.set(fieldname, value)
		self.sch_text_before = compose_before_text({f: self.get(f) for f in PARAGRAPH_FIELDS})

	def on_update(self):
		"""Master -> reports: push the fields changed in this save to the Scheme of Arrangement rows of every
		report of this company and fiscal year. A new record counts as the standard text, so creating it does not
		overwrite report edits; only a real difference is pushed."""
		before = self.get_doc_before_save()
		standard_before = compose_before_text(split_before_text(get_section_description()))
		changed = {}
		for f in SCHEME_FIELDS:
			if f == "sch_text_before":
				old = (before.get(f) if before else None) or standard_before
			else:
				old = (before.get(f) if before else None) or SCHEME_DEFAULTS.get(f) or ""
			new = self.get(f) or ""
			if old != new:
				changed[f] = new
		push_master_to_rows(self.company, self.fiscal_year, changed)

	def get_note_html(self):
		"""Coloured Note 62 HTML for the print format."""
		texts = {f: self.get(f) or "" for f in SCHEME_FIELDS}
		if not texts["sch_text_before"]:
			texts["sch_text_before"] = get_section_description()
		return build_scheme_html(texts)
