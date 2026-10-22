"""In-memory regression tests for deriving Apr-Mar balances from SAP snapshots."""

from datetime import date
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from financial_report_tool.financial_report_tool import derive_trial_balance as derived


COMPANY = "Calendar Subsidiary"
REPORT_FY = "2025-2026"
CALENDAR_FYS = {2025: "CAL-2025", 2026: "CAL-2026"}
ACCOUNT_TYPES = {"Revenue": "Profit and Loss", "Assets": "Balance Sheet", "Equity": "Balance Sheet"}


def snapshot(pl, assets, equity):
    return {"Revenue": pl, "Assets": assets, "Equity": equity}


class FakeStore:
    def __init__(self, snapshots, existing=()):
        self.snapshots = snapshots
        self.existing = list(existing)
        self.inserted = []
        self.saved = []
        self.deleted = []

    def get_all(self, doctype, filters=None, pluck=None, fields=None):
        if doctype == "Fiscal Year":
            year = filters["year_start_date"].year
            return [CALENDAR_FYS[year]]
        if doctype == "Fiscal Year Company":
            assert filters["company"] == COMPANY
            return [name for name in filters["parent"][1]]
        if doctype == "FR Sync SAP Trial Balance":
            key = (filters["fiscal_year"], filters["month"])
            return [f"SAP-{key[0]}-{key[1]}"] if key in self.snapshots else []
        if doctype == "FR Trial Balance Entry":
            if "month" not in filters:
                return self.existing
            return [SimpleNamespace(gl_account=account, uploaded_amount=amount, currency="INR")
                    for account, amount in self.snapshots[(filters["fiscal_year"], filters["month"])].items()]
        if doctype == "Account":
            return [SimpleNamespace(name=account, report_type=ACCOUNT_TYPES[account],
                                    account_currency="INR", company=COMPANY)
                    for account in filters["name"][1]]
        raise AssertionError(doctype)

    def get_value(self, doctype, name, field, as_dict=False):
        if doctype == "Fiscal Year":
            return SimpleNamespace(year_start_date=date(2025, 4, 1), year_end_date=date(2026, 3, 31))
        if doctype == "FR SAP Company Mapping":
            return "Equity"
        raise AssertionError(doctype)

    def get_doc(self, value, name=None):
        if isinstance(value, dict):
            store = self
            class NewEntry:
                def insert(self, ignore_permissions=False):
                    store.inserted.append(value)
            return NewEntry()
        store = self
        class ExistingEntry:
            def save(self, ignore_permissions=False):
                store.saved.append(name)
        return ExistingEntry()

    def delete(self, doctype, filters):
        self.deleted.append((doctype, filters))


class TestDeriveAprMarTrialBalance(TestCase):
    def derive(self, store, month):
        fake_frappe = SimpleNamespace(
            get_all=store.get_all,
            get_doc=store.get_doc,
            has_permission=lambda *args: True,
            PermissionError=PermissionError,
            throw=lambda message, *args: (_ for _ in ()).throw(ValueError(message)),
            db=SimpleNamespace(get_value=store.get_value, delete=store.delete),
        )
        with patch.object(derived, "frappe", fake_frappe), \
             patch.object(derived, "_", side_effect=lambda message: message), \
             patch("financial_report_tool.financial_report_tool.fiscal_cycle.get_start_month", return_value="January"):
            return derived.derive_apr_mar_tb.__wrapped__(COMPANY, REPORT_FY, month)

    def test_june_uses_current_less_march_and_rebalances_equity(self):
        store = FakeStore({("CAL-2025", "March"): snapshot(20, -120, 100),
                           ("CAL-2025", "June"): snapshot(60, -160, 100)})
        result = self.derive(store, "June")
        amounts = {entry["gl_account"]: entry["uploaded_amount"] for entry in store.inserted}
        self.assertEqual(amounts, snapshot(40, -160, 120))
        self.assertEqual(sum(amounts.values()), 0)
        self.assertEqual(result["accounts"], 3)
        self.assertIn("SAP-CAL-2025-March", result["source_sap_tbs"])
        self.assertIn("SAP-CAL-2025-June", result["source_sap_tbs"])
        self.assertTrue(all(entry["tb_source"] == "Derived Jan-Dec" for entry in store.inserted))

    def test_february_adds_prior_december_less_prior_march(self):
        store = FakeStore({("CAL-2025", "March"): snapshot(20, -120, 100),
                           ("CAL-2025", "December"): snapshot(90, -190, 100),
                           ("CAL-2026", "February"): snapshot(30, -130, 100)})
        result = self.derive(store, "February")
        amounts = {entry["gl_account"]: entry["uploaded_amount"] for entry in store.inserted}
        self.assertEqual(amounts, snapshot(100, -130, 30))
        self.assertEqual(sum(amounts.values()), 0)
        self.assertIn("SAP-CAL-2025-December", result["source_sap_tbs"])
        self.assertIn("SAP-CAL-2026-February", result["source_sap_tbs"])

    def test_missing_snapshot_fails_without_writes(self):
        store = FakeStore({("CAL-2025", "June"): snapshot(60, -160, 100)})
        with self.assertRaisesRegex(ValueError, "Expected one created SAP TB"):
            self.derive(store, "June")
        self.assertEqual(store.inserted, [])
        self.assertEqual(store.deleted, [])

    def test_replacing_month_refreshes_later_deltas_in_fiscal_order(self):
        existing = [SimpleNamespace(name=name, month=month, tb_source="Derived Jan-Dec")
                    for name, month in (("feb", "February"), ("may", "May"),
                                        ("jul", "July"), ("jan", "January"))]
        store = FakeStore({("CAL-2025", "March"): snapshot(20, -120, 100),
                           ("CAL-2025", "June"): snapshot(60, -160, 100)}, existing)
        self.derive(store, "June")
        self.assertEqual(store.saved, ["jul", "jan", "feb"])
        self.assertEqual(store.deleted, [("FR Trial Balance Entry", {
            "company": COMPANY, "fiscal_year": REPORT_FY, "month": "June",
        })])
