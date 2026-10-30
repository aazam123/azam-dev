# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

"""Shared data and HTML helpers for editable yearly-note masters."""

from datetime import date

import frappe

LEASE_RECEIVABLE_SECTION = "Lease receivable"
LEASE_RECEIVABLE_MASTER = "FR Lease Receivable"
LEASE_RECEIVABLE_FIELDS = (
    "intro_text",
    "particulars_label",
    "current_year_heading",
    "previous_year_heading",
    "lt_1_label",
    "one_to_five_label",
    "gt_5_label",
    "total_label",
    "footer_note",
)
LEASE_RECEIVABLE_PRIMARY_GROUP = "Lease Receivable Maturity"
LEASE_RECEIVABLE_BUCKETS = (
    ("lt_1", "Lease Receivable - Less than one year"),
    ("one_to_five", "Lease Receivable - One to five years"),
    ("gt_5", "Lease Receivable - More than five years"),
)
LEASE_RECEIVABLE_PERIODS = ("current", "previous")
LEASE_RECEIVABLE_AMOUNT_FIELDS = tuple(
    f"{key}_{period}_amount" for key in ("lt_1", "one_to_five", "gt_5", "total") for period in LEASE_RECEIVABLE_PERIODS
)
STATIC_NOTE_SECTIONS = {
    "FR Additional Information Schedule III": "Additional Information (Schedule III) - Yearly",
    "FR Other Regulatory Information": "Other regulatory information required by Schedule III",
}


def section_description(section):
    return frappe.db.get_value("FR Section", section, "section_type_description") or ""


def get_static_note_content(doctype, company, fiscal_year):
    name = frappe.db.get_value(doctype, {"company": company, "fiscal_year": fiscal_year})
    if name:
        doc = frappe.get_doc(doctype, name)
        return doc.get_note_html() or ""
    return section_description(STATIC_NOTE_SECTIONS[doctype])


def get_lease_receivable_texts(company, fiscal_year):
    """Master wording, falling back to the existing FR Section text row."""
    values = {}
    name = frappe.db.get_value(LEASE_RECEIVABLE_MASTER, {"company": company, "fiscal_year": fiscal_year})
    if name:
        values = frappe.db.get_value(LEASE_RECEIVABLE_MASTER, name, list(LEASE_RECEIVABLE_FIELDS), as_dict=True) or {}
    if not values:
        values = frappe.db.get_value(
            "Section Description",
            {"parent": LEASE_RECEIVABLE_SECTION, "parenttype": "FR Section", "parentfield": "section_description_details"},
            list(LEASE_RECEIVABLE_FIELDS),
            as_dict=True,
        ) or {}
    return {field: values.get(field) or "" for field in LEASE_RECEIVABLE_FIELDS}


def has_lease_receivable_master(company, fiscal_year):
    return bool(frappe.db.exists(LEASE_RECEIVABLE_MASTER, {"company": company, "fiscal_year": fiscal_year}))


def get_lease_receivable_manual_amounts(company, fiscal_year):
    """Amounts entered on the Lease Receivable master."""
    name = frappe.db.get_value(LEASE_RECEIVABLE_MASTER, {"company": company, "fiscal_year": fiscal_year})
    if not name:
        return None
    return frappe.db.get_value(LEASE_RECEIVABLE_MASTER, name, list(LEASE_RECEIVABLE_AMOUNT_FIELDS), as_dict=True)


def get_lease_receivable_trial_balance_amounts(company, fiscal_year, month):
    """Bucket amounts for both periods from mapped Trial Balance, in the configured display unit."""
    month = month or frappe.get_single_value("FR Financial Settings", "closing_month") or "March"
    previous_fiscal_year = get_previous_fiscal_year(fiscal_year)
    amounts = {}
    for key, group in LEASE_RECEIVABLE_BUCKETS:
        for period, year in zip(LEASE_RECEIVABLE_PERIODS, (fiscal_year, previous_fiscal_year)):
            amounts[f"{key}_{period}_amount"] = _lease_amount(company, year, month, group) if year else 0
    for period in LEASE_RECEIVABLE_PERIODS:
        amounts[f"total_{period}_amount"] = sum(amounts[f"{key}_{period}_amount"] for key, _group in LEASE_RECEIVABLE_BUCKETS)
    return amounts


def get_previous_fiscal_year(fiscal_year):
    """Find the fiscal year immediately preceding this Fiscal Year.

    ERPNext's Fiscal Year DocType does not carry a previous_fiscal_year link."""
    start_date = frappe.db.get_value("Fiscal Year", fiscal_year, "year_start_date")
    if not start_date:
        return None
    return frappe.db.get_value("Fiscal Year", {"year_end_date": frappe.utils.add_days(start_date, -1)}, "name")


def get_amount_configuration():
    unit = frappe.get_single_value("FR Financial Settings", "amount_display_unit") or "Lakhs"
    divisor, label = {
        "Actual": (1, "Actuals"),
        "Hundreds": (100, "Hundreds"),
        "Thousands": (1000, "Thousands"),
        "Lakhs": (100000, "Lacs"),
        "Millions": (1000000, "Millions"),
        "Crores": (10000000, "Crores"),
    }.get(unit, (100000, "Lacs"))
    return divisor, label


def get_year_end_label(fiscal_year):
    end_date = frappe.db.get_value("Fiscal Year", fiscal_year, "year_end_date")
    return f"Year Ended {frappe.utils.formatdate(end_date, 'dd-MM-yyyy')}" if end_date else ""


def _lease_amount(company, fiscal_year, month, secondary_group):
    accounts = frappe.get_all(
        "FR GL Group Mapping",
        filters={
            "company": company,
            "report_type": "Yearly",
            "primary_group": LEASE_RECEIVABLE_PRIMARY_GROUP,
            "secondary_group": secondary_group,
        },
        pluck="gl_account",
    )
    if not accounts:
        return 0
    divisor, _unit = get_amount_configuration()
    erp_type = frappe.get_single_value("FR Financial Settings", "erp_type") or "SAP"
    if erp_type == "ERPNext":
        fy = frappe.db.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"], as_dict=True)
        if not fy:
            return 0
        month_number = list(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")).index(month) + 1
        year = fy.year_start_date.year if month_number >= fy.year_start_date.month else fy.year_end_date.year
        start_date = date(year, month_number, 1)
        end_date = frappe.utils.get_last_day(start_date)
        return (frappe.db.sql(
            """select sum(debit) - sum(credit) from `tabGL Entry`
            where company=%s and posting_date between %s and %s and account in %(accounts)s""",
            {"company": company, "start_date": start_date, "end_date": end_date, "accounts": tuple(accounts)},
        )[0][0] or 0) / divisor
    return (frappe.db.sql(
        """select sum(uploaded_amount) from `tabFR Trial Balance Entry`
        where company=%s and fiscal_year=%s and month=%s and gl_account in %(accounts)s""",
        {"company": company, "fiscal_year": fiscal_year, "month": month, "accounts": tuple(accounts)},
    )[0][0] or 0) / divisor


def lease_receivable_html(company, fiscal_year, texts=None, month=None, amounts=None):
    """Render the Note 59 table from editable wording and mapped Trial Balance amounts."""
    texts = texts or get_lease_receivable_texts(company, fiscal_year)
    month = month or frappe.get_single_value("FR Financial Settings", "closing_month") or "March"
    previous_fiscal_year = get_previous_fiscal_year(fiscal_year)
    _divisor, unit = get_amount_configuration()

    def fmt(value):
        return "-" if not value else frappe.utils.fmt_money(value, precision=0, currency="").strip()

    if amounts is None:
        amounts = get_lease_receivable_manual_amounts(company, fiscal_year) or get_lease_receivable_trial_balance_amounts(
            company, fiscal_year, month
        )
    amounts = {
        (key, period): fmt(amounts.get(f"{key}_{period}_amount"))
        for key in ("lt_1", "one_to_five", "gt_5", "total")
        for period in LEASE_RECEIVABLE_PERIODS
    }

    def esc(value):
        return frappe.utils.escape_html(value or "").replace("\n", "<br>")

    line = "1px solid #000"
    pad = "padding:7px 8px;"
    head = f"{pad} border:{line}; background-color:#EEEEEE; color:#3498DB; font-weight:bold;"
    body = f"{pad} border-left:{line}; border-right:{line}; border-top:none; border-bottom:none;"
    foot = f"{pad} border:{line}; font-weight:bold;"
    green = " background-color:#E8F5E8;"

    def row(style, label, key):
        return (
            f'<tr><td style="{style} text-align:left; width:60%;">{esc(label)}</td>'
            f'<td style="{style} text-align:right; width:20%;{green}">{amounts[key, "current"]}</td>'
            f'<td style="{style} text-align:right; width:20%;">{amounts[key, "previous"]}</td></tr>'
        )

    current_heading = texts.get("current_year_heading") or f"{get_year_end_label(fiscal_year)} (₹ in {unit.lower()})"
    previous_heading = texts.get("previous_year_heading") or f"{get_year_end_label(previous_fiscal_year)} (₹ in {unit.lower()})"
    html = f'<p>{esc(texts.get("intro_text"))}</p><table style="width:100%; border-collapse:collapse; font-size:13px; border:{line};"><tbody>'
    html += f'<tr><td style="{head} text-align:left; width:60%;">{esc(texts.get("particulars_label"))}</td><td style="{head} text-align:right; width:20%;">{esc(current_heading)}</td><td style="{head} text-align:right; width:20%;">{esc(previous_heading)}</td></tr>'
    html += row(body, texts.get("lt_1_label"), "lt_1")
    html += row(body, texts.get("one_to_five_label"), "one_to_five")
    html += row(body, texts.get("gt_5_label"), "gt_5")
    html += row(foot, texts.get("total_label"), "total") + "</tbody></table>"
    if texts.get("footer_note"):
        html += f'<p>{esc(texts["footer_note"])}</p>'
    return html


def update_static_note_rows(doctype, company, fiscal_year, note_content):
    section = STATIC_NOTE_SECTIONS[doctype]
    reports = frappe.get_all("FR Financial Report", filters={"company": company, "fiscal_year": fiscal_year}, pluck="name")
    if not reports:
        return 0
    rows = frappe.get_all(
        "FR Financial Report Details",
        filters={"parenttype": "FR Financial Report", "parent": ["in", reports], "section": section},
        pluck="name",
    )
    for row in rows:
        frappe.db.set_value("FR Financial Report Details", row, "section_description", note_content, update_modified=False)
    return len(rows)
