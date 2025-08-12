# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
import calendar
from frappe.model.document import Document
from frappe.utils import nowdate


class FRTrialBalanceEntry(Document):
    def before_save(self):
        if not self.date:
            self.date = nowdate()

        if self.gl_account and self.fiscal_year and self.month:
            filters = {"gl_account": self.gl_account,"fiscal_year": self.fiscal_year,"month": self.month}
            if self.company:
                filters["company"] = self.company

            # Get fiscal year start month
            fiscal_year_doc = frappe.get_doc("Fiscal Year", self.fiscal_year)
            start_month_name = fiscal_year_doc.year_start_date.strftime("%B")
            months = list(calendar.month_name)[1:]
            start_idx = months.index(start_month_name)
            fy_months = months[start_idx:] + months[:start_idx]

            # Find index of current month
            try:
                current_month_index = fy_months.index(self.month)
            except ValueError:
                frappe.throw(f"Invalid month '{self.month}' for fiscal year starting in {start_month_name}")
                return

            # Calculate previous months total
            if current_month_index > 0:
                previous_months = fy_months[:current_month_index]
                prev_filters = {"gl_account": self.gl_account,"fiscal_year": self.fiscal_year,"month": ["in", previous_months]}
                if self.company:
                    prev_filters["company"] = self.company

                previous_entries = frappe.get_all("FR Trial Balance Entry",filters=prev_filters,fields=["amount"])
                previous_sum = sum((entry.get("amount") or 0) for entry in previous_entries)
            else:
                previous_sum = 0

            # Set adjusted amount
            self.amount = (self.uploaded_amount or 0) - previous_sum
