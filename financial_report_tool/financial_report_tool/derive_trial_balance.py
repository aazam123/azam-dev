"""Derive an April–March reporting TB from a subsidiary's SAP calendar-year TBs."""

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.utils import getdate


MONTHS = list(calendar.month_name)[1:]


def _calendar_fy(company, year):
    years = frappe.get_all(
        "Fiscal Year",
        filters={"year_start_date": date(year, 1, 1), "year_end_date": date(year, 12, 31)},
        pluck="name",
    )
    assigned = frappe.get_all(
        "Fiscal Year Company", filters={"company": company, "parent": ["in", years]}, pluck="parent"
    ) if years else []
    if len(assigned) != 1:
        frappe.throw(_("Expected one Jan-Dec Fiscal Year assigned to {0} for {1}; found {2}.").format(company, year, len(assigned)))
    return assigned[0]


def _snapshot(company, fiscal_year, month):
    # A missing row is a valid zero for an individual GL, but a missing snapshot
    # must never silently turn the whole month's TB into zero.
    syncs = frappe.get_all(
        "FR Sync SAP Trial Balance",
        filters={"company": company, "fiscal_year": fiscal_year, "month": month, "tb_created": 1},
        pluck="name",
    )
    if len(syncs) != 1:
        frappe.throw(_("Expected one created SAP TB for {0}, {1} ({2}); found {3}.").format(company, fiscal_year, month, len(syncs)))
    rows = frappe.get_all(
        "FR Trial Balance Entry",
        filters={"company": company, "fiscal_year": fiscal_year, "month": month},
        fields=["gl_account", "uploaded_amount", "currency"],
    )
    values = {}
    for row in rows:
        if row.gl_account in values:
            frappe.throw(_("Duplicate GL {0} in {1} {2}.").format(row.gl_account, fiscal_year, month))
        values[row.gl_account] = (row.uploaded_amount or 0, row.currency)
    return values, syncs[0]


@frappe.whitelist()
def derive_apr_mar_tb(company, fiscal_year, month):
    """Rebuild an Apr-Mar month from Jan-Dec cumulative TB snapshots.

    Profit and loss: Apr-Dec = current - March; Jan-Mar = previous
    December - previous March + current. Balance sheet: same-date snapshot.
    """
    from financial_report_tool.financial_report_tool.fiscal_cycle import get_start_month
    if not frappe.has_permission("FR Trial Balance Entry", "create") or not frappe.has_permission("FR Trial Balance Entry", "delete"):
        frappe.throw(_("Not permitted to derive trial balance entries."), frappe.PermissionError)

    if get_start_month(company) != "January":
        frappe.throw(_("Apr-Mar derivation is only available for Jan-Dec SAP companies."))
    fy = frappe.db.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"], as_dict=True)
    if not fy:
        frappe.throw(_("Fiscal Year {0} not found.").format(fiscal_year))
    start, end = getdate(fy.year_start_date), getdate(fy.year_end_date)
    if (start.month, start.day, end.month, end.day, end.year) != (4, 1, 3, 31, start.year + 1):
        frappe.throw(_("Select a full April–March Fiscal Year."))
    if month not in MONTHS:
        frappe.throw(_("Invalid month {0}.").format(month))
    month_number = MONTHS.index(month) + 1
    year = start.year if month_number >= 4 else end.year
    jan_fy = _calendar_fy(company, year)
    current, current_sync = _snapshot(company, jan_fy, month)
    march_fy = _calendar_fy(company, start.year)
    march, march_sync = _snapshot(company, march_fy, "March")
    december = {}
    sources = [march_sync, current_sync]
    if year != start.year:
        december, december_sync = _snapshot(company, march_fy, "December")
        sources.append(december_sync)

    accounts = set(current) | set(march) | set(december)
    if not accounts:
        frappe.throw(_("Source SAP trial balances have no account rows."))
    account_types = frappe.get_all(
        "Account", filters={"name": ["in", list(accounts)]},
        fields=["name", "report_type", "account_currency", "company"],
    )
    account_by_name = {account.name: account for account in account_types}
    if set(account_by_name) != accounts:
        frappe.throw(_("A source TB account no longer exists."))
    amounts = {}
    for account in accounts:
        info = account_by_name[account]
        if info.company != company or info.report_type not in ("Profit and Loss", "Balance Sheet"):
            frappe.throw(_("Invalid source TB account {0}.").format(account))
        currencies = {value[1] for snapshot in (current, march, december) if (value := snapshot.get(account))}
        if len(currencies) > 1:
            frappe.throw(_("Currency differs between source TBs for {0}.").format(account))
        if currencies and info.account_currency not in currencies:
            frappe.throw(_("Account currency differs from source TB for {0}.").format(account))
        present = current.get(account, (0, None))[0]
        if info.report_type == "Balance Sheet":
            amount = present
        else:
            amount = present - march.get(account, (0, None))[0]
            if year != start.year:
                amount += december.get(account, (0, None))[0]
        amounts[account] = amount

    # Reclassify the source calendar-year P&L excluded from the reporting
    # Apr-Mar P&L into the designated equity GL (signed SAP balances).
    retained = frappe.db.get_value("FR SAP Company Mapping", {"company": company}, "retained_earnings_account")
    if not retained or retained not in account_by_name or account_by_name[retained].report_type != "Balance Sheet":
        frappe.throw(_("Configure a Balance Sheet retained earnings account present in the SAP TB for {0}.").format(company))
    current_pl = sum(current.get(account, (0, None))[0] for account in accounts
                     if account_by_name[account].report_type == "Profit and Loss")
    derived_pl = sum(amounts[account] for account in accounts
                     if account_by_name[account].report_type == "Profit and Loss")
    amounts[retained] += current_pl - derived_pl
    if abs(sum(amounts.values())) > 0.01:
        frappe.throw(_("Derived TB does not balance. Check that SAP source TB includes all signed accounts."))

    # Replacing a historical cumulative changes every later monthly delta.
    # Reject accidental overwrite of manually imported or SAP-fetched TBs.
    existing = frappe.get_all(
        "FR Trial Balance Entry", filters={"company": company, "fiscal_year": fiscal_year},
        fields=["name", "month", "gl_account", "tb_source", "uploaded_amount"],
    )
    later = []
    position = (month_number - 4) % 12
    for row in existing:
        if row.tb_source != "Derived Jan-Dec":
            frappe.throw(_("Apr-Mar FY contains non-derived TB entries; cannot overwrite them."))
        if (MONTHS.index(row.month) + 1 - 4) % 12 > position:
            later.append(row)
    frappe.db.delete("FR Trial Balance Entry", {"company": company, "fiscal_year": fiscal_year, "month": month})
    provenance = ", ".join(dict.fromkeys(sources))
    for account, amount in amounts.items():
        frappe.get_doc({
            "doctype": "FR Trial Balance Entry", "company": company,
            "fiscal_year": fiscal_year, "month": month, "gl_account": account,
            "currency": account_by_name[account].account_currency,
            "uploaded_amount": amount, "tb_source": "Derived Jan-Dec",
            "source_sap_tbs": provenance,
        }).insert(ignore_permissions=True)
    # Re-evaluate monthly deltas in fiscal order; no cumulative values change.
    for row in sorted(later, key=lambda entry: (MONTHS.index(entry.month) + 1 - 4) % 12):
        frappe.get_doc("FR Trial Balance Entry", row.name).save(ignore_permissions=True)
    return {"accounts": len(amounts), "source_sap_tbs": provenance}
