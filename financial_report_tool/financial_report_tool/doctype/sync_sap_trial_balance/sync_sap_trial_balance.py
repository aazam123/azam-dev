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
			gl_code = (i.gl_code or "").strip()
			gl_desc = (i.gl_description or "").strip()

			if not i.account and gl_code and gl_desc:
				account = frappe.get_value(
					"Account", {"account_number": gl_code, "company": self.company, "is_group": 0}, "name"
				)
				i.account = account or ""

			elif not i.account and not gl_code and gl_desc:
				account = frappe.get_value(
					"Account", {"account_name": gl_desc, "company": self.company, "is_group": 0}, "name"
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
		"""Kick off the SAP Trial Balance sync in the background.

		The SAP API call plus the account-mapping save can take well over the
		120s Nginx/gateway limit for a large trial balance, so the heavy work is
		offloaded to a background job (see ``do_sync_sap_data``). This method only
		does the quick, synchronous validations — so the user still gets instant
		feedback on misconfiguration — then queues the job and returns immediately.
		"""
		# Fast, synchronous checks so config errors surface right away.
		self.validate_sap_settings()
		self.validate_required_fields()

		# Persist any pending field edits (SAP params) + mark queued, so the
		# background worker reads the current values from the DB.
		self.sync_status = "Queued"
		self.sync_error = ""
		self.save()
		frappe.db.commit()

		frappe.enqueue(
			"financial_report_tool.financial_report_tool.doctype.sync_sap_trial_balance.sync_sap_trial_balance.do_sync_sap_data",
			docname=self.name,
			queue="long",
			job_name=f"Sync SAP Trial Balance - {self.name}",
			timeout=1500,
		)

		return {
			"success": True,
			"message": (
				f"SAP data sync started in background for {self.name}. "
				"You will be notified once it completes."
			),
		}

	def _sync_sap_data_internal(self):
		"""Fetch Trial Balance data from SAP and store it (heavy work).

		Runs inside the background job. Raising here marks the job Failed and the
		error is surfaced on the form via ``sync_error`` (see ``do_sync_sap_data``).
		"""
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
			if d.get("RACCT") and d.get("REPVAL") != 0:
				racct = d.get("RACCT")
				racct = racct.lstrip('0') if racct else ''
				self.append("details", {
					"gl_code": racct,
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


def do_sync_sap_data(docname):
	"""Background worker: fetch + store SAP Trial Balance data for ``docname``.

	Enqueued by ``SyncSAPTrialBalance.sync_sap_data``. Updates ``sync_status`` as
	it progresses and publishes ``sap_tb_sync_complete`` so the form can auto
	reload. Any failure is recorded on ``sync_error`` and logged.
	"""
	doc = frappe.get_doc("Sync SAP Trial Balance", docname)
	try:
		doc.db_set("sync_status", "Syncing", commit=True)
		doc._sync_sap_data_internal()
		doc.db_set({"sync_status": "Completed", "sync_error": ""}, commit=True)
		frappe.publish_realtime(
			"sap_tb_sync_complete", {"docname": docname, "status": "Completed"}
		)
	except Exception:
		frappe.db.rollback()
		error_message = frappe.get_traceback(with_context=True)
		frappe.db.set_value(
			"Sync SAP Trial Balance",
			docname,
			{"sync_status": "Failed", "sync_error": error_message},
		)
		frappe.db.commit()
		frappe.publish_realtime(
			"sap_tb_sync_complete", {"docname": docname, "status": "Failed"}
		)
		frappe.log_error(title=f"SAP Trial Balance Sync Failed - {docname}")
		raise


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