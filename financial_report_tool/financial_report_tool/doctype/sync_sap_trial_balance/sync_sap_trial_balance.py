# Copyright (c) 2025, Hybrowlabs Pvt Ltd
# For license information, please see license.txt

import json
import frappe
import requests
from requests.auth import HTTPBasicAuth
from frappe.model.document import Document


class SyncSAPTrialBalance(Document):
	def before_save(self):
		"""Auto-map accounts + calculate total amount"""
		total = 0
		for i in self.details:
			if not i.account and i.gl_code:
				account = frappe.get_value(
					"Account",
					{"account_number": i.gl_code, "company": self.company, "is_group": 0},
					"name"
				)
				i.account = account or ""

			if not i.account and not i.gl_code and i.gl_description:
				account = frappe.get_value(
					"Account",
					{"account_name": i.gl_description, "company": self.company, "is_group": 0},
					"name"
				)
				i.account = account or ""

			total += float(i.amount or 0)

		self.total_amount = total

	def validate_sap_settings(self):
		"""Ensure SAP API settings exist and are complete"""
		fs = frappe.db.get_value(
			"FR Financial Settings",
			None,
			["user_name", "password", "api_end_point", "timeout"],
			as_dict=True,
		)
		if not fs or not fs.user_name or not fs.password or not fs.api_end_point or not fs.timeout:
			frappe.throw("Please configure User Name, Password, API URL, Timeout and Client in <b>FR Financial Settings</b>")
		return fs

	def validate_required_fields(self):
		"""Check all mandatory fields before making API request"""
		required = ["chartofacc", "company_code", "sversion", "repyear",
					"srepmonth", "trepmonth", "compyear", "scompmonth", "tcompmonth", "layout", "sap_client"]
		missing = [field for field in required if not self.get(field)]
		if missing:
			frappe.throw(f"Missing required fields: {', '.join(missing)}")

	@frappe.whitelist()
	def sync_sap_data(self):
		"""Fetch Trial Balance data from SAP"""
		self.details.clear()
		self.responce = None

		fs = self.validate_sap_settings()
		self.validate_required_fields()

		params = {
			"sap-client": self.sap_client,
			"CHARTOFACC": self.chartofacc,
			"COMPANY": self.company_code,
			"SVERSION": self.sversion,
			"REPYEAR": self.repyear,
			"SREPMONTH": self.srepmonth,
			"TREPMONTH": self.trepmonth,
			"COMPYEAR": self.compyear,
			"SCOMPMONTH": self.scompmonth,
			"TCOMPMONTH": self.tcompmonth,
			"LAYOUT": self.layout,
		}

		response = requests.get(fs.api_end_point, params=params, auth=HTTPBasicAuth(fs.user_name, fs.password), verify=False, timeout=int(fs.timeout))
		response.raise_for_status()
		resp_json = response.json()
		if not resp_json.get("items"):
			frappe.throw("No trial balance data returned from SAP")

		self.responce = json.dumps(resp_json, ensure_ascii=False)
		for d in resp_json.get("items"):
			self.append("details", {
				"gl_code": d.get("RACCT"),
				"gl_description": d.get("TEXT"),
				"amount": d.get("REPVAL") or 0
			})
		self.save()

	@frappe.whitelist()
	def create_trail_balance(self):
		"""Generate FR Trial Balance Entries from synced details"""
		none_account = [d for d in self.details if not d.account]
		if none_account:
			first = none_account[0]
			frappe.throw(
				f"<b>Row: {first.idx}</b>, "
				f"GL: {first.gl_code}, "
				f"GL Desc: {first.gl_description}, "
				f"Amount: {first.amount} → <b>GL Account is missing</b>"
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
					"company": self.company,
				})
				fr.insert(ignore_permissions=True)

		frappe.db.set_value("Sync SAP Trial Balance", self.name, "tb_created", 1)
		frappe.msgprint("Trial Balance Entries created successfully!")


# params = {
# 	"sap-client": fs.sap_client,
# 	"CHARTOFACC": "7000",
# 	"COMPANY": "7000",
# 	"SVERSION": "7000",
# 	"REPYEAR": "2025",
# 	"SREPMONTH": "01",
# 	"TREPMONTH": "16",
# 	"COMPYEAR": "2024",
# 	"SCOMPMONTH": "01",
# 	"TCOMPMONTH": "16",
# 	"LAYOUT": "TEST_API"
# }