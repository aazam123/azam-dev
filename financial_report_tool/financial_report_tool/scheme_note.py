# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

"""Note 62 "Scheme of Arrangement in the nature of Amalgamation": field defaults and the one HTML builder.

Used by the report (FR Financial Report row) and by the FR Scheme of Arrangement master / its print format."""

import frappe

SCHEME_NOTE_TYPE = "Scheme of Arrangement"
SCHEME_DEFAULTS = {
    "sch_text_pre_h": "Considering the effective date in point (f) above as April 01, 2024 authorised share capital for comparative period FY 2024-25 has also been changed to 19,30,82,200 Equity Shares of Rs.10/- each to give effect of the Scheme.",
    "sch_text_h": "<p>h) Description and number of shares issued of each entity\u2019s equity shares before merger</p>",
    "sch_ac_asat": "As at March 31, 2026",
    "sch_ac_col_shares": "Number of Shares and face value per share",
    "sch_ac_col_amount": "Amount",
    "sch_ac_tee_head": "Authorised Share Capital of the Transferee Company",
    "sch_ac_tee_eq_label": "10,00,00,000 Equity Shares of Rs.10/- each",
    "sch_ac_tee_eq_amt": "1,00,00,00,000",
    "sch_ac_tee_pref_label": "4,00,00,000 Redeemable Preference Shares of Rs.10/- each",
    "sch_ac_tee_pref_amt": "40,00,00,000",
    "sch_ac_tor_head": "Authorised Share Capital of the Transferor Company",
    "sch_ac_tor_eq_label": "50,50,000 Equity Shares of Rs.10 each",
    "sch_ac_tor_eq_amt": "5,05,00,000",
    "sch_ac_tor_pref1_label": "1,72,000 Preference Shares of Rs. 2000 each",
    "sch_ac_tor_pref1_amt": "34,40,00,000",
    "sch_ac_tor_pref2_label": "13,63,220 Preference Shares of Rs. 100 each",
    "sch_ac_tor_pref2_amt": "13,63,22,000",
    "sch_m1_caption": "Micro Life Sciences Private Limited",
    "sch_m1_particulars": "Particulars",
    "sch_m1_asat": "As at 31st March 2026",
    "sch_m1_col_shares": "No. of shares",
    "sch_m1_col_amount": "Amount in \u20b9 Lakhs",
    "sch_m1_issued": "Issued, Subscribed and Fully Paid:",
    "sch_m1_equity_label": "Equity Shares of Rs.10 each",
    "sch_m1_shares": "49,97,136",
    "sch_m1_amount": "500",
    "sch_m2_caption": "Meril Life Sciences Private Limited, held 100% by Micro Life Sciences Private Limited",
    "sch_m2_particulars": "Particulars",
    "sch_m2_asat": "As at 31st March 2026",
    "sch_m2_col_shares": "No. of shares",
    "sch_m2_col_amount": "Amount in \u20b9 Lakhs",
    "sch_m2_issued": "Issued, Subscribed and Fully Paid:",
    "sch_m2_equity_label": "Equity Shares of 10/-each",
    "sch_m2_shares": "5,93,60,000",
    "sch_m2_amount": "5,936",
    "sch_s_title": "(iii) Summary of Accounting treatment pursuant to scheme of amalgamation",
    "sch_s_calc": "Calculation of number of shares to be issued:",
    "sch_t1_h0": "Particulars",
    "sch_t1_h1": "31-Mar-25",
    "sch_t1_h2": "New shares issued during the period",
    "sch_t1_h3": "31-Mar-26",
    "sch_t1_r1_0": "Equity share of Micro Life Sciences Private Limited (No. of Shares)",
    "sch_t1_r1_1": "49,20,612",
    "sch_t1_r1_2": "76,524",
    "sch_t1_r1_3": "49,97,136",
    "sch_t1_r2_0": "Equivalent 38 shares of Meril Life Sciences Private Limited (No. of Shares)",
    "sch_t1_r2_1": "18,69,83,256",
    "sch_t1_r2_2": "29,07,912",
    "sch_t1_r2_3": "18,98,91,168",
    "sch_t1_r3_0": "Paid up Equity Share capital(Rs. In Lakhs) - Pending issuance",
    "sch_t1_r3_1": "18,698.33",
    "sch_t1_r3_2": "290.79",
    "sch_t1_r3_3": "18,989.12",
    "sch_t2_fy1": "FY 2024-25",
    "sch_t2_amt": "Amount (Rs. in lakhs)",
    "sch_t2_a_l": "Value of shares issued in terms of Scheme (A) (4920612*38)",
    "sch_t2_a_v": "18,698",
    "sch_t2_b_l": "Value of net identifiable assets acquired as at March 31, 2025 (B)",
    "sch_t2_b_v": "492",
    "sch_t2_ba_l": "Capital Reserve on account of business combination (B-A)",
    "sch_t2_ba_v": "(18,206)",
    "sch_t2_fy2": "FY 2025-26",
    "sch_t2_c_l": "Value of shares issued in terms of Scheme (C)",
    "sch_t2_c_v": "291",
    "sch_t2_d_l": "Value of net identifiable assets acquired (Refer note below) as at March 31, 2026 (D)",
    "sch_t2_d_v": "8",
    "sch_t2_dc_l": "Capital Reserve on account of business combination (D-C)",
    "sch_t2_dc_v": "(283)",
    "sch_t2_tot_l": "Capital Reserve on account of Business combination as at March 31, 2026",
    "sch_t2_tot_v": "(18,489)",
    "sch_n_head": "Note -",
    "sch_n_text": "The equity shares are to be issued subsequent to the year ended March 31, 2026. As the number of equity shares to be issued is fixed in accordance with the Scheme, \u20b918,989 lakhs has been classified as \"Share Pending Issuance\" under equity as at March 31, 2026. The corresponding amount as at March 31, 2025 was 18,698 lakhs.",
    "sch_n_iv": "(iv) The Company is in the process of transferring the ownership of investments in the equity instruments of its subsidiaries from Micro Life Sciences Private Limited to Meril Life Sciences Private Limited.",
    "sch_n_v": "(v) The title deeds of Micro Life Sciences Private Limited (\"the Transferor Company\") are currently in the process of being transferred to Meril Life Sciences Private Limited (\"the Company\" or \"Transferee Company\") pursuant to the merger order received after March 31, 2026.",
}


def build_scheme_html(texts):
    """HTML of the whole note from a dict of sch_* values (already defaulted)."""
    def esc(key):
        return frappe.utils.escape_html(texts.get(key) or "")

    line = "1px solid #000"
    base = f"padding:6px; border:{line}; font-size:13px;"
    head = f"{base} background-color:#EEEEEE; color:#3498DB; font-weight:bold; text-align:center;"
    green = f"{base} background-color:#E8F5E8; text-align:right;"

    def table(width, rows):
        return (
            f'<table style="width:{width}; border-collapse:collapse; border:{line}; margin:6px 0 12px 0;">'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )

    def authorised(label_key, amount_key):
        return f'<tr><td style="{base}">{esc(label_key)}</td><td style="{green}">{esc(amount_key)}</td></tr>'

    def sub_head(key):
        return f'<tr><td colspan="2" style="{head}">{esc(key)}</td></tr>'

    html = f'<div class="scheme-amalgamation">{texts["sch_text_before"]}'
    html += table("70%", [
        sub_head("sch_ac_asat"),
        sub_head("sch_ac_tee_head"),
        f'<tr><td style="{head} width:65%;">{esc("sch_ac_col_shares")}</td>'
        f'<td style="{head} width:35%;">{esc("sch_ac_col_amount")}</td></tr>',
        authorised("sch_ac_tee_eq_label", "sch_ac_tee_eq_amt"),
        authorised("sch_ac_tee_pref_label", "sch_ac_tee_pref_amt"),
        sub_head("sch_ac_tor_head"),
        authorised("sch_ac_tor_eq_label", "sch_ac_tor_eq_amt"),
        authorised("sch_ac_tor_pref1_label", "sch_ac_tor_pref1_amt"),
        authorised("sch_ac_tor_pref2_label", "sch_ac_tor_pref2_amt"),
    ])
    html += f'<p>{esc("sch_text_pre_h")}</p>'
    html += texts["sch_text_h"]
    for p in ("sch_m1_", "sch_m2_"):
        html += f'<p><strong>{esc(p + "caption")}</strong></p>'
        html += table("100%", [
            f'<tr><td rowspan="2" style="{head} width:45%; vertical-align:middle;">{esc(p + "particulars")}</td>'
            f'<td colspan="2" style="{head}">{esc(p + "asat")}</td></tr>',
            f'<tr><td style="{head} width:28%;">{esc(p + "col_shares")}</td>'
            f'<td style="{head} width:27%;">{esc(p + "col_amount")}</td></tr>',
            f'<tr><td colspan="3" style="{base} font-weight:bold;">{esc(p + "issued")}</td></tr>',
            f'<tr><td style="{base}">{esc(p + "equity_label")}</td>'
            f'<td style="{green}">{esc(p + "shares")}</td>'
            f'<td style="{green}">{esc(p + "amount")}</td></tr>',
        ])
    html += f'<p><strong>{esc("sch_s_title")}</strong></p>'
    html += f'<p><strong>{esc("sch_s_calc")}</strong></p>'
    html += table("100%", [
        "<tr>" + "".join(
            f'<td style="{head}{" width:40%;" if c == 0 else " width:20%;"}">{esc(f"sch_t1_h{c}")}</td>' for c in range(4)
        ) + "</tr>"
    ] + [
        f'<tr><td style="{base}">{esc(f"sch_t1_r{r}_0")}</td>'
        + "".join(f'<td style="{green}">{esc(f"sch_t1_r{r}_{c}")}</td>' for c in (1, 2, 3)) + "</tr>"
        for r in (1, 2, 3)
    ])
    def amount_rows(keys, bold_last=False):
        out = []
        for n, k in enumerate(keys):
            weight = " font-weight:bold;" if bold_last and n == len(keys) - 1 else ""
            out.append(
                f'<tr><td style="{base}{weight}">{esc(f"sch_t2_{k}_l")}</td>'
                f'<td style="{green}{weight}">{esc(f"sch_t2_{k}_v")}</td></tr>'
            )
        return out
    html += table("80%", [
        f'<tr><td style="{head} width:70%;">{esc("sch_t2_fy1")}</td><td style="{head} width:30%;">{esc("sch_t2_amt")}</td></tr>',
        *amount_rows(("a", "b", "ba")),
        f'<tr><td colspan="2" style="{head}">{esc("sch_t2_fy2")}</td></tr>',
        *amount_rows(("c", "d", "dc", "tot"), bold_last=True),
    ])
    html += f'<p><strong>{esc("sch_n_head")}</strong></p>'
    for key in ("sch_n_text", "sch_n_iv", "sch_n_v"):
        html += f'<p>{esc(key)}</p>'
    return html + "</div>"

MASTER_DOCTYPE = "FR Scheme of Arrangement"
# sch_text_before is not in SCHEME_DEFAULTS: when empty it falls back to the FR Section description.
SCHEME_FIELDS = tuple(SCHEME_DEFAULTS) + ("sch_text_before",)


def get_master_values(company, fiscal_year):
    """Values of the FR Scheme of Arrangement record of this company and fiscal year; empty fields (or no record)
    fall back to SCHEME_DEFAULTS."""
    values = dict(SCHEME_DEFAULTS)
    values["sch_text_before"] = ""
    name = frappe.db.get_value(MASTER_DOCTYPE, {"company": company, "fiscal_year": fiscal_year})
    if name:
        master = frappe.get_cached_doc(MASTER_DOCTYPE, name)
        for fieldname in SCHEME_FIELDS:
            if master.get(fieldname):
                values[fieldname] = master.get(fieldname)
    return values


def push_master_to_rows(company, fiscal_year, changed):
    """Master -> the Scheme of Arrangement rows of the reports of this company and fiscal year: write the changed
    sch_* fields and rebuild each row's stored section_description. Fields that were not changed in the master keep
    the row's own value."""
    sections = frappe.get_all("FR Section", filters={"note_type": SCHEME_NOTE_TYPE}, pluck="name")
    reports = frappe.get_all("FR Financial Report", filters={"company": company, "fiscal_year": fiscal_year}, pluck="name")
    if not sections or not reports or not changed:
        return 0
    rows = frappe.get_all(
        "FR Financial Report Details",
        filters={"section": ["in", sections], "parenttype": "FR Financial Report", "parent": ["in", reports]},
        fields=["name", "section", *SCHEME_FIELDS],
    )
    master = get_master_values(company, fiscal_year)
    for row in rows:
        frappe.db.set_value("FR Financial Report Details", row.name, changed, update_modified=False)
        row.update(changed)
        texts = dict(master)
        for fieldname in SCHEME_FIELDS:
            if row.get(fieldname):
                texts[fieldname] = row[fieldname]
        if not texts.get("sch_text_before"):
            texts["sch_text_before"] = frappe.db.get_value("FR Section", row.section, "section_type_description") or ""
        frappe.db.set_value(
            "FR Financial Report Details", row.name, "section_description", build_scheme_html(texts), update_modified=False
        )
    return len(rows)


# The note text above the tables is one HTML block on FR Section / on the report row (sch_text_before). The master
# edits it as separate paragraph fields and composes the block back. (fieldname, kind, index of the paragraph in the
# FR Section HTML); kind "html" keeps inline markup, "head" is printed bold, "text" is plain text.
# None-index entries are the blank spacer paragraphs of the original block.
PARAGRAPHS = (
    (None, "space", 0),
    ("sch_p_intro", "html", 1),
    (None, "space", 2),
    ("sch_p_i_head", "head", 3),
    ("sch_p_micro_head", "head", 4),
    ("sch_p_micro_text", "text", 5),
    ("sch_p_meril_head", "head", 6),
    ("sch_p_meril_text", "text", 7),
    (None, "space", 8),
    ("sch_p_ii_head", "head", 9),
    ("sch_p_ii_intro", "text", 10),
    ("sch_p_a", "text", 11),
    ("sch_p_b", "text", 12),
    ("sch_p_c", "text", 13),
    ("sch_p_d", "text", 14),
    ("sch_p_e", "text", 15),
    ("sch_p_f", "text", 16),
    ("sch_p_g", "text", 17),
)
PARAGRAPH_FIELDS = tuple(f for f, _kind, _i in PARAGRAPHS if f)
TITLE_DEFAULT = "Note 62. Scheme of Arrangement in the nature of Amalgamation"


def split_before_text(html):
    """Paragraph field values from the FR Section HTML ({} if the block is not the expected 18 paragraphs)."""
    from bs4 import BeautifulSoup

    paragraphs = BeautifulSoup(html or "", "html.parser").find_all("p")
    if len(paragraphs) != len(PARAGRAPHS):
        return {}
    values = {}
    for (fieldname, kind, index) in PARAGRAPHS:
        if not fieldname:
            continue
        p = paragraphs[index]
        values[fieldname] = p.decode_contents() if kind == "html" else p.get_text()
    return values


def compose_before_text(values):
    """The sch_text_before HTML block from paragraph field values ('' when every paragraph is empty)."""
    if not any(values.get(f) for f in PARAGRAPH_FIELDS):
        return ""
    out = []
    for (fieldname, kind, _index) in PARAGRAPHS:
        if kind == "space":
            out.append("<p>&nbsp;</p>")
            continue
        value = values.get(fieldname) or ""
        if kind == "html":
            out.append(f"<p>{value}</p>")
        elif kind == "head":
            out.append(f"<p><strong>{frappe.utils.escape_html(value)}</strong></p>")
        else:
            out.append(f"<p>{frappe.utils.escape_html(value)}</p>")
    return "".join(out)
