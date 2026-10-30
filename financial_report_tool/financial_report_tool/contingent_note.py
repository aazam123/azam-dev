"""Note 50 (Contingent Liabilities): the three table rows, headings and the HTML builder shared by the
FR Contingent Liabilities print format and the Financial Report."""

import frappe
from frappe.utils import escape_html, flt

MASTER_DOCTYPE = "FR Contingent Liabilities"
# The Section text of the note is `{{note_table}}` followed by this block; points i) and ii) are table rows now.
NOTE_MARKER = "<p><strong>Note:</strong></p>"

# Rows of the table in print order: (field suffix, standard text). Fields: cl_<suffix>_label / _current / _previous.
ROWS = (
	("a", "a) Claims against the company not acknowledged as debt"),
	(
		"i",
		"i) It is not practicable for the Company to estimate the timings of cash outflows, if any, in respect of the above pending resolution of the respective proceedings. The Company does not expect any reimbursements in respect of the above contingent liabilities. Future cash outflows in respect of the above are determinable only on receipt of judgments/ decisions pending with various forums/authorities. The Company does not expect any outflow of economic resources in respect of the above and therefore no provision is made in respect thereof.",
	),
	(
		"ii",
		"ii) The competitor has initiated litigation proceedings against the Group in certain overseas countries for infringement of patents for certain products of Group. The management is continuously monitoring the proceeding of litigation, the Group believes that the factors considered are reasonable under the current circumstances and information available upto the date of approval of the accounts. However, the uncertainty caused by such litigation and related events could further influence the ultimate obligation of the Group.",
	),
)

# Editable texts of the master: fieldname -> standard text
CONTINGENT_DEFAULTS = {
	"cl_note_title": "Note 50. Contingent Liabilities",
	"cl_head_particulars": "Particulars",
	"cl_total_label": "TOTAL",
	**{f"cl_{suffix}_label": text for suffix, text in ROWS},
}

BASE = "padding:6px; font-size:13px; vertical-align:top;"
SIDES = "border-left:1px solid #000; border-right:1px solid #000; border-top:none; border-bottom:none;"
FULL = "border:1px solid #000;"
GREEN = "background-color:#E8F5E8;"
BLUE = "font-weight:bold; color:#4472C4;"


def year_end_label(fiscal_year):
	end = frappe.db.get_value("Fiscal Year", fiscal_year, "year_end_date") if fiscal_year else None
	return end.strftime("%d-%m-%Y") if end else ""


def get_previous_fiscal_year(fiscal_year):
	return frappe.db.get_value("FR Previous Fiscal Year", {"current_fiscal_year": fiscal_year}, "previous_fiscal_year")


def default_heading(fiscal_year, previous=False):
	"""'As at 31-03-2025' for the fiscal year, or for its previous fiscal year."""
	year = get_previous_fiscal_year(fiscal_year) if previous else fiscal_year
	return f"As at {year_end_label(year)}".strip()


def get_texts(doc=None, current_heading="", previous_heading=""):
	"""Editable texts of a master record; empty cells fall back to the standard text and 'As at <year end>'."""
	texts = dict(CONTINGENT_DEFAULTS)
	texts["cl_head_current"] = current_heading
	texts["cl_head_previous"] = previous_heading
	if doc:
		for fieldname in (*texts, "cl_head_current", "cl_head_previous"):
			if doc.get(fieldname):
				texts[fieldname] = doc.get(fieldname)
	return texts


def get_previous_doc(company, fiscal_year, month):
	"""The master of the same company and month in the previous Fiscal Year, if any."""
	previous_year = get_previous_fiscal_year(fiscal_year)
	if not previous_year:
		return None
	name = frappe.db.get_value(MASTER_DOCTYPE, {"company": company, "fiscal_year": previous_year, "month": month})
	return frappe.get_doc(MASTER_DOCTYPE, name) if name else None


def resolved_rows(doc, previous_doc=None):
	"""[(particulars, current, previous)] of the three rows; a previous-year amount left at 0 takes the earlier master's current amount."""
	rows = []
	for suffix, text in ROWS:
		current = flt(doc.get(f"cl_{suffix}_current")) if doc else 0
		previous = flt(doc.get(f"cl_{suffix}_previous")) if doc else 0
		if not previous and previous_doc:
			previous = flt(previous_doc.get(f"cl_{suffix}_current"))
		rows.append(((doc.get(f"cl_{suffix}_label") if doc else None) or text, current, previous))
	return rows


def format_amount(value, divisor=1):
	"""Divided by the display unit, no decimals; zero prints as "-", like the rest of the report."""
	return f"{flt(value) / divisor:,.0f}" if value else "-"


def table_html(texts, rows, divisor=1, margin=""):
	"""Note 50 table: heading, the rows [(particulars, current, previous)], TOTAL of all rows."""
	html = f'<table style="{margin} width:100%; border-collapse:collapse; font-size:13px; border:1px solid #000;">'
	html += (
		f'<tr><th style="{FULL} {BASE} {BLUE} width:65%; text-align:left;">{escape_html(texts["cl_head_particulars"])}</th>'
		f'<th style="{FULL} {BASE} {BLUE} {GREEN} width:17.5%;">{escape_html(texts["cl_head_current"])}</th>'
		f'<th style="{FULL} {BASE} {BLUE} width:17.5%;">{escape_html(texts["cl_head_previous"])}</th></tr>'
	)
	for particulars, current, previous in rows:
		html += (
			f'<tr><td style="{SIDES} {BASE}">{escape_html(particulars).replace(chr(10), "<br>")}</td>'
			f'<td style="{SIDES} {BASE} text-align:right; {GREEN}">{format_amount(current, divisor)}</td>'
			f'<td style="{SIDES} {BASE} text-align:right;">{format_amount(previous, divisor)}</td></tr>'
		)
	html += (
		f'<tr><td style="{FULL} {BASE} font-weight:bold;">{escape_html(texts["cl_total_label"])}</td>'
		f'<td style="{FULL} {BASE} text-align:right; font-weight:bold; {GREEN}">{format_amount(sum(r[1] for r in rows), divisor)}</td>'
		f'<td style="{FULL} {BASE} text-align:right; font-weight:bold;">{format_amount(sum(r[2] for r in rows), divisor)}</td></tr></table>'
	)
	return html
