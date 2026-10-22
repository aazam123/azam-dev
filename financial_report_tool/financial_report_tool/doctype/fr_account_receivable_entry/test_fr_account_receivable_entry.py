# Copyright (c) 2025, Hybrowlabs Pvt Ltd and Contributors
# See license.txt

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from financial_report_tool.financial_report_tool.doctype.fr_account_receivable_entry.fr_account_receivable_entry import (
    FRAccountReceivableEntry,
)


class TestFRAccountReceivableEntry(FrappeTestCase):
    def test_year_end_fx_and_ageing_follow_fiscal_year(self):
        for closing_month, end_date, expected_due_days in (
            ("December", date(2025, 12, 31), 31),
            ("March", date(2026, 3, 31), 121),
        ):
            with self.subTest(closing_month=closing_month), patch(
                "financial_report_tool.financial_report_tool.doctype.fr_account_receivable_entry.fr_account_receivable_entry.get_closing_month",
                return_value=closing_month,
            ), patch(
                "financial_report_tool.financial_report_tool.doctype.fr_account_receivable_entry.fr_account_receivable_entry.frappe.get_value",
                return_value=2,
            ) as exchange_rate, patch(
                "financial_report_tool.financial_report_tool.doctype.fr_account_receivable_entry.fr_account_receivable_entry.frappe.db.get_value",
                return_value=end_date,
            ):
                entry = SimpleNamespace(
                    gl_account=None, nature="Receivable", closing_ex_rate=None,
                    currency="USD", company="Example Co", fiscal_year="2025-2026",
                    amount_in_dc=10, amount_in_lc=25, due_date=date(2025, 12, 1),
                    posting_date=None, provision_percentage=0,
                )
                FRAccountReceivableEntry.before_save(entry)

                self.assertEqual(entry.due_days, expected_due_days)
                self.assertEqual(entry.restated_value, 20)
                exchange_rate.assert_called_once_with(
                    "FR Foreign Exchange Rate",
                    {
                        "from_currency": "USD", "to_currency": "INR",
                        "month": closing_month, "fiscal_year": "2025-2026",
                    },
                    "closing_rate",
                )
