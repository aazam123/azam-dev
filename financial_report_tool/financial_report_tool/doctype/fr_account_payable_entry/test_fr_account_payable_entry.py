# Copyright (c) 2025, Hybrowlabs Pvt Ltd and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from financial_report_tool.financial_report_tool.doctype.fr_account_payable_entry.fr_account_payable_entry import (
    FRAccountPayableEntry,
)


class TestFRAccountPayableEntry(FrappeTestCase):
    def test_opening_fx_month_follows_fiscal_year(self):
        module = "financial_report_tool.financial_report_tool.doctype.fr_account_payable_entry.fr_account_payable_entry"
        for start_month in ("January", "April"):
            with self.subTest(start_month=start_month), patch(
                f"{module}.get_start_month", return_value=start_month,
            ), patch(
                f"{module}.get_or_create_reconciliation_account", return_value="Recon Account",
            ), patch(
                f"{module}.frappe.get_all", return_value=[],
            ), patch(
                f"{module}.frappe.get_value", side_effect=[2, None],
            ) as get_value:
                entry = SimpleNamespace(
                    company="Example Co", fiscal_year="2025-2026", country="IN",
                    amount_in_lc=-25, amount_in_dc=-10, special_gl_ind=None,
                    purchase_order=None, supplier="Supplier", document_type=None,
                    due_days=0, closing_exchange_rate=None, currency="USD",
                    grouping=None, nature=None,
                )
                FRAccountPayableEntry.before_save(entry)

                self.assertEqual(entry.restated_value, -20)
                get_value.assert_any_call(
                    "FR Foreign Exchange Rate",
                    {
                        "from_currency": "USD", "to_currency": "INR",
                        "month": start_month, "fiscal_year": "2025-2026",
                    },
                    "closing_rate",
                )
