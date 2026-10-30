# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from financial_report_tool.financial_report_tool.additional_information_note import (
    TEXT_FIELDS,
    master_html,
    parse_note_html,
)
from financial_report_tool.financial_report_tool.note_masters import (
    STATIC_NOTE_SECTIONS,
    section_description,
    update_static_note_rows,
)


class FRAdditionalInformationScheduleIII(Document):
    def validate(self):
        duplicate = frappe.db.exists(
            self.doctype, {"company": self.company, "fiscal_year": self.fiscal_year, "name": ["!=", self.name]}
        )
        if duplicate:
            frappe.throw(_("{0} already exists for {1}, {2}").format(duplicate, self.company, self.fiscal_year))
        self.seed_from_section()

    def seed_from_section(self):
        """A new record starts from the Note 60 text kept on its FR Section, split into fields and rows."""
        if self.rows or any(self.get(field) for field in TEXT_FIELDS):
            return
        parsed = parse_note_html(section_description(STATIC_NOTE_SECTIONS[self.doctype]))
        if not parsed:
            return
        for fieldname, value in parsed["texts"].items():
            self.set(fieldname, value)
        for row in parsed["rows"]:
            self.append("rows", row)

    def on_update(self):
        update_static_note_rows(self.doctype, self.company, self.fiscal_year, self.get_note_html())

    def get_note_html(self):
        return master_html(self)
