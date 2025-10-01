# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
import requests
from requests.auth import HTTPBasicAuth
from frappe.model.document import Document


class SyncSAPTrialBalance(Document):
	def before_save(self):
		total = 0
		for i in self.details:
			if not i.account and i.gl_code:
				account = frappe.get_value("Account", {'account_number': i.gl_code, 'company': self.company, 'is_group': 0}, 'name')
				i.account = account if account else ""
			if not i.account and not i.gl_code and i.gl_description:
				account = frappe.get_value("Account", {'account_name': i.gl_description, 'company': self.company, 'is_group': 0}, 'name')
				i.account = account if account else ""
			total += float(i.amount)
		self.total_amount = total

		fs = frappe.db.get_value("FR Financial Settings", None, ["user_name", "password", "api_end_point"], as_dict=True)
		if not fs:
			frappe.throw("Please configure User Name, Password and API URL in FR Financial Settings")

		username = fs.user_name
		password = fs.password
		api_url  = fs.api_end_point

		params = {
			"sap-client": "700",
			"CHARTOFACC": "7000",
			"COMPANY": "7000",
			"SVERSION": "7000",
			"REPYEAR": "2025",
			"SREPMONTH": "01",
			"TREPMONTH": "16",
			"COMPYEAR": "2024",
			"SCOMPMONTH": "01",
			"TCOMPMONTH": "16",
			"LAYOUT": "TEST_API"
		}
		response = requests.get(api_url, params=params, auth=HTTPBasicAuth(username, password), verify=False, timeout=60)
		response.raise_for_status()
		self.responce = response.json()

	@frappe.whitelist()
	def create_trail_balance(self):
		none_account = [d for idx, d in enumerate(self.get("details"), start=1) if not d.account]
		if none_account:
			frappe.throw(
				f"<b>Row: {none_account[0].idx}</b>, "
				f"GL: {none_account[0].gl_code}, "
				f"GL Desc: {none_account[0].gl_description}, "
				f"Amount: {none_account[0].amount} → <b>GL Account is missing</b>"
			)


		for i in self.details:
			if i.amount != 0:
				fr = frappe.get_doc({
					"doctype": "FR Trial Balance Entry",
					"fiscal_year": self.fiscal_year,
					"gl_account": i.account,
					"currency": self.currency,
					"uploaded_amount": i.amount,
					"month": self.month,
					"company": self.company
				})
				fr.save()
		frappe.db.set_value('Sync SAP Trial Balance', self.name, 'tb_created', 1)
		frappe.msgprint("Trial Balance Entries created successfully!")
