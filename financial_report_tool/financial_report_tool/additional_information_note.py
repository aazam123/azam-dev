# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

"""Note 60 (Additional Information, Schedule III): master fields <-> table HTML."""

import html as html_lib
import re

import frappe

MASTER = "FR Additional Information Schedule III"
ROW_DOCTYPE = "FR Additional Information Row"

TEXT_FIELDS = (
    "heading",
    "period_text",
    "sr_no_label",
    "enterprise_label",
    "net_assets_heading",
    "profit_heading",
    "oci_heading",
    "tci_heading",
    "net_assets_pct_label",
    "profit_pct_label",
    "oci_pct_label",
    "tci_pct_label",
    "net_assets_amount_label",
    "profit_amount_label",
    "oci_amount_label",
    "tci_amount_label",
    "footer_note",
)
# (percentage field, amount field) for the four value column pairs, left to right.
VALUE_PAIRS = (
    ("net_assets_pct", "net_assets_amount"),
    ("profit_pct", "profit_amount"),
    ("oci_pct", "oci_amount"),
    ("tci_pct", "tci_amount"),
)
ROW_FIELDS = ("sr_no", "enterprise_name") + tuple(field for pair in VALUE_PAIRS for field in pair)

CELL = "border:1px solid #777;padding:4px;text-align:{align};{extra}"
GREEN = "background-color:#E8F5E8;"
STYLE = (
    "<style>.sch55-table{width:100%;border-collapse:collapse;font-size:10px}"
    ".sch55-table th{border:1px solid #777;padding:4px;color:#4472C4;background:#eef4fa}</style>"
)


def _esc(value):
    return frappe.utils.escape_html(value or "")


def note_html(texts, rows):
    """Build the Note 60 HTML from header wording (dict) and row dicts."""
    texts = {field: texts.get(field) or "" for field in TEXT_FIELDS}
    th = lambda key: f"<th>{_esc(texts[key])}</th>"  # noqa: E731
    head = (
        f'<tr><th rowspan="2">{_esc(texts["sr_no_label"])}</th>'
        f'<th rowspan="2" style="min-width:220px;">{_esc(texts["enterprise_label"])}</th>'
        f'<th colspan="2">{_esc(texts["net_assets_heading"])}</th>'
        f'<th colspan="2">{_esc(texts["profit_heading"])}</th>'
        f'<th colspan="2">{_esc(texts["oci_heading"])}</th>'
        f'<th colspan="2">{_esc(texts["tci_heading"])}</th></tr>'
        f'<tr>{th("net_assets_pct_label")}{th("net_assets_amount_label")}'
        f'{th("profit_pct_label")}{th("profit_amount_label")}'
        f'{th("oci_pct_label")}{th("oci_amount_label")}'
        f'{th("tci_pct_label")}{th("tci_amount_label")}</tr>'
    )
    body = ""
    for row in rows:
        get = row.get
        cells = [
            f'<td style="{CELL.format(align="left", extra="")}">{_esc(get("sr_no"))}</td>',
            f'<td style="{CELL.format(align="left", extra="")}">{_esc(get("enterprise_name"))}</td>',
        ]
        for pct, amt in VALUE_PAIRS:
            cells.append(f'<td style="{CELL.format(align="right", extra="")}">{_esc(get(pct))}</td>')
            cells.append(f'<td style="{CELL.format(align="right", extra=GREEN)}">{_esc(get(amt))}</td>')
        bold = ' style="font-weight:bold;"' if get("is_bold") else ""
        body += f"<tr{bold}>{''.join(cells)}</tr>"
    out = STYLE + f"<h4>{_esc(texts['heading'])}</h4><p>{_esc(texts['period_text'])}</p>"
    out += f'<div style="overflow-x:auto;"><table class="sch55-table"><thead>{head}</thead><tbody>{body}</tbody></table></div>'
    if texts["footer_note"]:
        out += f'<p style="font-size:11px;">{_esc(texts["footer_note"])}</p>'
    return out


def master_html(doc):
    return note_html({field: doc.get(field) for field in TEXT_FIELDS}, doc.get("rows") or [])


def _text(fragment):
    return html_lib.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def parse_note_html(content):
    """Read the stored Note 60 HTML back into master fields and rows; None if it is not the standard table."""
    content = content or ""
    table = re.search(r"<table[^>]*sch55-table[\s\S]*?</table>", content)
    if not table:
        return None
    trs = re.findall(r"(<tr[^>]*>)([\s\S]*?)</tr>", table.group(0))
    heads = [[_text(c) for c in re.findall(r"<th[^>]*>([\s\S]*?)</th>", inner)] for _tag, inner in trs[:2]]
    if len(heads) < 2 or len(heads[0]) != 6 or len(heads[1]) != 8:
        return None
    paragraphs = re.findall(r"<p[^>]*>([\s\S]*?)</p>", content)
    heading = re.search(r"<h4[^>]*>([\s\S]*?)</h4>", content)
    texts = {
        "heading": _text(heading.group(1)) if heading else "",
        "period_text": _text(paragraphs[0]) if paragraphs else "",
        "sr_no_label": heads[0][0],
        "enterprise_label": heads[0][1],
        "net_assets_heading": heads[0][2],
        "profit_heading": heads[0][3],
        "oci_heading": heads[0][4],
        "tci_heading": heads[0][5],
        "net_assets_pct_label": heads[1][0],
        "profit_pct_label": heads[1][2],
        "oci_pct_label": heads[1][4],
        "tci_pct_label": heads[1][6],
        "net_assets_amount_label": heads[1][1],
        "profit_amount_label": heads[1][3],
        "oci_amount_label": heads[1][5],
        "tci_amount_label": heads[1][7],
        "footer_note": _text(paragraphs[-1]) if len(paragraphs) > 1 else "",
    }
    rows = []
    for tag, inner in trs[2:]:
        cells = [_text(c) for c in re.findall(r"<td[^>]*>([\s\S]*?)</td>", inner)]
        if len(cells) != len(ROW_FIELDS):
            return None
        row = dict(zip(ROW_FIELDS, cells))
        row["is_bold"] = 1 if "font-weight:bold" in tag else 0
        rows.append(row)
    return {"texts": texts, "rows": rows}
