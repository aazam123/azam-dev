"""Resolve a company's fiscal months, preferring the selected Fiscal Year's dates."""

import calendar

import frappe
from frappe.utils import getdate


_CYCLE_CLOSING_MONTH = {"Apr-Mar": 3, "Jan-Dec": 12}


def _configured_closing_month(company):
	if company:
		mapping = frappe.db.get_value(
			"FR SAP Company Mapping", {"company": company}, ["name", "fiscal_cycle"], as_dict=True
		)
		if mapping:
			return _CYCLE_CLOSING_MONTH.get(mapping.fiscal_cycle, 3)

	closing_month = frappe.get_single_value("FR Financial Settings", "closing_month")
	if closing_month:
		try:
			return list(calendar.month_name).index(closing_month)
		except ValueError:
			pass
	return 3  # Legacy Apr-Mar cycle when neither setting supplies a month.


def _fiscal_year_month(fiscal_year, date_field):
	if fiscal_year:
		date = frappe.db.get_value("Fiscal Year", fiscal_year, date_field)
		if date:
			return getdate(date).month
	return None


def get_closing_month(company, fiscal_year=None):
	"""Return the full closing month name; selected Fiscal Year end dates win."""
	month = _fiscal_year_month(fiscal_year, "year_end_date")
	return calendar.month_name[month or _configured_closing_month(company)]


def get_start_month(company, fiscal_year=None):
	"""Return the full starting month name; selected Fiscal Year start dates win."""
	month = _fiscal_year_month(fiscal_year, "year_start_date")
	if not month:
		month = _configured_closing_month(company) % 12 + 1
	return calendar.month_name[month]


def calendar_year_for(fiscal_year, month):
	"""Calendar year in which ``month`` falls inside an existing ``fiscal_year``, or ``None``."""
	fy = frappe.db.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"], as_dict=True) if fiscal_year else None
	months = list(calendar.month_name)
	if not fy or month not in months[1:]:
		return None
	number = months.index(month)
	start, end = getdate(fy.year_start_date), getdate(fy.year_end_date)
	for year in (start.year, end.year):
		if (start.year, start.month) <= (year, number) <= (end.year, end.month):
			return year
	return None
