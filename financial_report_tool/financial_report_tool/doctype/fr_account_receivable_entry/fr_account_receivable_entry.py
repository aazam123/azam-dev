# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, today


class FRAccountReceivableEntry(Document):

    def before_insert(self):
        if self.report_type == "Yearly":
            customer_sum = frappe.db.sql("""
                SELECT COALESCE(SUM(amount_in_lc), 0)
                FROM `tabFR Account Receivable Entry`
                WHERE customer = %s
            """, (self.customer,))[0][0] or 0

            customer_sum += flt(self.amount_in_lc)

            self.nature = "Advance" if customer_sum < 0 else "Receivable"

    def before_save(self):

        # ✅ TB Nature Logic
        if self.gl_account:
            if str(self.gl_account).startswith("1"):
                self.tb_nature = "Advance"
            elif str(self.gl_account).startswith("2"):
                self.tb_nature = "Receivable"

        # ✅ Forex & Restatement
        if self.nature == "Receivable":
            if not self.closing_ex_rate:
                self.closing_ex_rate = frappe.get_value(
                    "FR Foreign Exchange Rate",
                    {
                        "from_currency": self.currency,
                        "to_currency": "INR",
                        "month": "March",
                        "fiscal_year": self.fiscal_year
                    },
                    "closing_rate"
                ) or 1

            self.restated_value = flt(self.amount_in_dc) * flt(self.closing_ex_rate)
            self.gainloss = flt(self.amount_in_lc) - flt(self.restated_value)

        # ✅ FIX: Proper Date Handling
        if self.due_date:
            due_date = getdate(self.due_date)
            if self.posting_date:
                today_date = getdate(self.posting_date)
            else:
                year = str(self.fiscal_year).split("-")[-1]
                today_date = getdate(f"{year}-03-31")

            self.due_days = (today_date - due_date).days + 1
        else:
            self.ageing_days = 0

        # ✅ Ageing Bucket Logic
        if self.due_days <= 0:
            self.ageing = "Not Due"
        elif 0 < self.due_days <= 180:
            self.ageing = "0-6 Months"
        elif 180 < self.due_days <= 365:
            self.ageing = "6-12 Months"
        elif 365 < self.due_days <= 730:
            self.ageing = "1-2 Years"
        elif 730 < self.due_days <= 1095:
            self.ageing = "2-3 Years"
        else:
            self.ageing = "More Than 3 Years"

        # ✅ Provision Calculation (safe)
        self.provision_amount = (
            flt(self.restated_value) * flt(self.provision_percentage)
        ) / 100 if self.restated_value else 0

    def on_update(self):

        if self.report_type == "Yearly":
            customer_sum = frappe.db.sql("""
                SELECT COALESCE(SUM(amount_in_lc), 0)
                FROM `tabFR Account Receivable Entry`
                WHERE customer = %s
            """, (self.customer,))[0][0] or 0

            self.nature = "Advance" if customer_sum < 0 else "Receivable"

        elif self.report_type == "Monthly":
            if self.special_gl_ind in ["A", "B"]:
                self.nature = "Advance"
            else:
                self.nature = "Receivable"

        # ✅ Recalculate provision safely
        self.provision_amount = (
            flt(self.restated_value) * flt(self.provision_percentage)
        ) / 100 if self.restated_value else 0