# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime
from frappe.model.document import Document


class FRForeignExchangeRate(Document):
	def before_insert(self):
		filters = {"date": self.date, "fiscal_year": self.fiscal_year, "from_currency": self.from_currency, "to_currency": self.to_currency,}
		exist = frappe.db.exists("FR Foreign Exchange Rate", filters)
		if exist:
			frappe.throw(f"Duplicate Foreign Exchange Rate already exists: {exist}")

	def before_save(self):
		if self.date:
			if isinstance(self.date, str):
				date_obj = datetime.strptime(self.date, "%Y-%m-%d")
			else:
				date_obj = self.date
			self.month = date_obj.strftime("%B")

		if self.rate:
			if self.discount_precentage:
				self.closing_rate = (self.rate - ((self.rate/100)*self.discount_precentage))
			else:
				self.closing_rate = self.rate

		closing_month = frappe.db.get_single_value("FR Financial Settings", "closing_month")
		previous_fiscal_year = frappe.get_value("FR Previous Fiscal Year", {'current_fiscal_year': self.fiscal_year}, 'previous_fiscal_year')
		if previous_fiscal_year and closing_month:
			prev_year_closing = frappe.get_value("FR Foreign Exchange Rate", {'month': closing_month, 'fiscal_year': previous_fiscal_year, 'from_currency': self.from_currency, 'to_currency': self.to_currency}, 'closing_rate')
			if not prev_year_closing:
				frappe.throw(f"Closing Rate Is Missing For Fiscal Year <b>{previous_fiscal_year}</b>, Month <b>{closing_month}</b>, From Currency <b>{self.from_currency}</b>, To Currency <b>{self.to_currency}</b>")
			self.average_rate = round((prev_year_closing + self.closing_rate)/2, 6)
		
		if not closing_month:
			frappe.throw("Update The Financial Settings.")

		if not previous_fiscal_year:
			frappe.msgprint("Opening Foreign Exchange Rate is saved.")
