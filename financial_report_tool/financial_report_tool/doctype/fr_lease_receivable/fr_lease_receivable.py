# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from financial_report_tool.financial_report_tool.note_masters import (
    LEASE_RECEIVABLE_BUCKETS,
    LEASE_RECEIVABLE_AMOUNT_FIELDS,
    LEASE_RECEIVABLE_FIELDS,
    LEASE_RECEIVABLE_PERIODS,
    get_lease_receivable_texts,
    lease_receivable_html,
)


class FRLeaseReceivable(Document):
    def validate(self):
        duplicate = frappe.db.exists(
            self.doctype, {"company": self.company, "fiscal_year": self.fiscal_year, "name": ["!=", self.name]}
        )
        if duplicate:
            frappe.throw(_("{0} already exists for {1}, {2}").format(duplicate, self.company, self.fiscal_year))
        defaults = get_lease_receivable_texts(self.company, self.fiscal_year)
        for fieldname in LEASE_RECEIVABLE_FIELDS:
            if not self.get(fieldname):
                self.set(fieldname, defaults[fieldname])
        self.set_amounts()

    def set_amounts(self):
        """Keep the printed total cells equal to the values entered in their respective rows."""
        for period in LEASE_RECEIVABLE_PERIODS:
            self.set(
                f"total_{period}_amount",
                sum(self.get(f"{key}_{period}_amount") or 0 for key, _group in LEASE_RECEIVABLE_BUCKETS),
            )

    def get_note_html(self):
        return lease_receivable_html(
            self.company,
            self.fiscal_year,
            {fieldname: self.get(fieldname) for fieldname in LEASE_RECEIVABLE_FIELDS},
            self.month,
            {fieldname: self.get(fieldname) for fieldname in LEASE_RECEIVABLE_AMOUNT_FIELDS},
        )
