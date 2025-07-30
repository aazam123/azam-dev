# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FRTrialBalanceEntry(Document):
    def before_insert(self):
        if not self.date:
            import datetime
            self.date = datetime.date.today().isoformat()

        if self.gl_account and self.fiscal_year and self.month:
            filters = {
                "gl_account": self.gl_account,
                "fiscal_year": self.fiscal_year,
                "month": self.month
            }
            if self.company:
                filters["company"] = self.company
            
            fiscal_year = frappe.get_doc("Fiscal Year", self.fiscal_year)
            start_date = fiscal_year.year_start_date
            # Get month name from start_date
            import datetime
            start_month = datetime.datetime.strptime(str(start_date), "%Y-%m-%d").strftime("%B")
            months = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            # Rotate months so that fiscal year starts from start_month
            start_idx = months.index(start_month)
            fy_months = months[start_idx:] + months[:start_idx]
            try:
                current_month_index = fy_months.index(self.month)
            except ValueError:
                current_month_index = -1
            if current_month_index > 0:
                previous_months = fy_months[:current_month_index]
                prev_filters = {
                    "gl_account": self.gl_account,
                    "fiscal_year": self.fiscal_year,
                    "month": ["in", previous_months]
                }
                if self.company:
                    prev_filters["company"] = self.company
                previous_entries = frappe.get_all(
                    "FR Trial Balance Entry",
                    filters=prev_filters,
                    fields=["amount", "month"]
                )
                previous_sum = sum(entry["amount"] or 0 for entry in previous_entries)
                self.amount = (self.uploaded_amount or 0) - previous_sum
