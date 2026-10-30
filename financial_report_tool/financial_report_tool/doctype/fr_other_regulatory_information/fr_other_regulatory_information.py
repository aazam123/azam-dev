# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from financial_report_tool.financial_report_tool.note_masters import get_static_note_content, update_static_note_rows


class FROtherRegulatoryInformation(Document):
    def validate(self):
        duplicate = frappe.db.exists(
            self.doctype, {"company": self.company, "fiscal_year": self.fiscal_year, "name": ["!=", self.name]}
        )
        if duplicate:
            frappe.throw(_("{0} already exists for {1}, {2}").format(duplicate, self.company, self.fiscal_year))
        if not self.note_content:
            self.note_content = get_static_note_content(self.doctype, self.company, self.fiscal_year)

    def on_update(self):
        update_static_note_rows(self.doctype, self.company, self.fiscal_year, self.note_content)

    def get_note_html(self):
        return self.note_content
