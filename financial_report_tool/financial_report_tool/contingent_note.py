"""Note 50 (Contingent Liabilities): editable texts, defaults and the standalone HTML builder used by the
FR Contingent Liabilities print format. The Financial Report reads the same texts from the master."""

import frappe
from frappe.utils import escape_html, flt

MASTER_DOCTYPE = "FR Contingent Liabilities"
NOTE_MARKER = "<p><strong>Note:</strong></p>"

# Editable texts of the master: fieldname -> standard text
CONTINGENT_DEFAULTS = {
    "cl_note_title": "Note 50. Contingent Liabilities",
    "cl_head_particulars": "Particulars",
    "cl_head_asat": "As at",
    "cl_label_a": "a) Bank guarantees given to excise authorities and other institutions",
    "cl_label_b": "b) Disputed Custom duty matters",
    "cl_label_d": "d) Claims against the company not acknowledged as debt, Amount indeterminate (Refer Note (ii) below), Amount indeterminate (Refer Note (ii) below)",
    "cl_total_label": "TOTAL",
    "cl_note_head": "Note:",
    "cl_note_i": "i) Future ultimate outflow of resources embodying economic benefits in respect of the above matters are uncertain as it depends on the final outcome of the matters involved.",
    "cl_note_ii": "ii) The competitor has initiated litigation proceedings against the Company in certain overseas countries for infringement of patents for certain products of Company. The management is continuously monitoring the proceeding of litigation, the Company believes that the factors considered are reasonable under the current circumstances and information available upto the date of approval of the accounts. However, the uncertainty caused by such litigation and related events could further influence the ultimate obligation of the Company based on outcome of proceedings with the court or the mutual settlement as the case may be.",
}

CONTINGENT_FIELDS = tuple(CONTINGENT_DEFAULTS)


def get_texts(doc=None):
    """Editable texts of a master record; empty cells fall back to the standard text."""
    texts = dict(CONTINGENT_DEFAULTS)
    if doc:
        for fieldname in CONTINGENT_FIELDS:
            if doc.get(fieldname):
                texts[fieldname] = doc.get(fieldname)
    return texts


def get_previous_fiscal_year(fiscal_year):
    return frappe.db.get_value("FR Previous Fiscal Year", {"current_fiscal_year": fiscal_year}, "previous_fiscal_year")

def note_html(texts):
    """The 'Note:' block (heading + points i, ii) from texts."""
    return (
        f'<p><strong>{escape_html(texts["cl_note_head"])}</strong></p>'
        f'<p>{escape_html(texts["cl_note_i"])}</p><p>{escape_html(texts["cl_note_ii"])}</p>'
    )


def format_amount(value, divisor=1):
    """Same display as the report: divided by the display unit, no decimals; text and blanks pass through."""
    if value in (None, "", "-"):
        return "-"
    if isinstance(value, str):
        return value
    return f"{flt(value) / divisor:,.0f}"


def year_end_label(fiscal_year):
    end = frappe.db.get_value("Fiscal Year", fiscal_year, "year_end_date") if fiscal_year else None
    return end.strftime("%d-%m-%Y") if end else ""


def build_contingent_html(texts, current, previous, current_date="", previous_date="", unit_word="", divisor=1):
    """Standalone Note 50: table with the master's current and comparative amounts, then the note points."""
    base = "border:1px solid #000; padding:6px; font-size:13px; vertical-align:top;"
    head = f"{base} font-weight:bold; color:#4472C4;"
    green = f"{base} text-align:right; background-color:#E8F5E8;"
    plain = f"{base} text-align:right;"
    asat = escape_html(texts["cl_head_asat"])
    rows = (
        (texts["cl_label_a"], "bank_guarantees"),
        (texts["cl_label_b"], "disputed_custom_duty_matters"),
        ("c) " + (current.get("company_imported_label") or ""), "company_imported"),
        (texts["cl_label_d"], "claim_against"),
    )
    html = f'<p style="text-align:right; font-size:12px;">(₹ in {escape_html(unit_word)})</p>' if unit_word else ""
    html += '<table style="width:100%; border-collapse:collapse; border:1px solid #000;">'
    html += f'<tr><th style="{head} width:65%;">{escape_html(texts["cl_head_particulars"])}</th>'
    html += f'<th style="{head} background-color:#E8F5E8; width:17.5%;">{asat} {escape_html(current_date)}</th>'
    html += f'<th style="{head} width:17.5%;">{asat} {escape_html(previous_date)}</th></tr>'
    combined = bool(current.get("cl_combined_layout"))
    if combined:
        particulars = escape_html(current.get("cl_combined_particulars") or "").replace("\n", "<br>")
    for index, (label, fieldname) in enumerate(rows):
        if combined:
            label_cell = f'<td rowspan="4" style="{base}">{particulars}</td>' if index == 0 else ""
        else:
            label_cell = f'<td style="{base}">{escape_html(label)}</td>'
        html += (
            f'<tr>{label_cell}'
            f'<td style="{green}">{format_amount(current.get(fieldname), divisor)}</td>'
            f'<td style="{plain}">{format_amount(previous.get(fieldname), divisor)}</td></tr>'
        )
    totals = [
        flt(d.get("bank_guarantees")) + flt(d.get("company_imported")) for d in (current, previous)
    ]
    html += (
        f'<tr><td style="{base} font-weight:bold;">{escape_html(texts["cl_total_label"])}</td>'
        f'<td style="{green} font-weight:bold;">{format_amount(totals[0], divisor)}</td>'
        f'<td style="{plain} font-weight:bold;">{format_amount(totals[1], divisor)}</td></tr></table>'
    )
    return html if combined else html + note_html(texts)
