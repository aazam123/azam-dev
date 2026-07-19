# Copyright (c) 2025, Hybrowlabs Pvt Ltd
# For license information, please see license.txt

import base64
import csv
import io
import json
import os

import frappe
import requests
from requests.auth import HTTPBasicAuth
from frappe import _
from frappe.model.document import Document
from frappe.utils.file_manager import save_file


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

		The flow is asynchronous (request + callback):

		1. We ask SAP to generate the trial balance for the given params. SAP
		   only *acknowledges* the request — it generates the report in its own
		   background job and does **not** return the data inline.
		2. When SAP finishes, it pushes the JSON/CSV result back to us via the
		   ``receive_sap_trial_balance`` callback (see below), which fills in the
		   ``details`` and marks the doc ``Completed``.

		This method does the quick, synchronous validations — so the user gets
		instant feedback on misconfiguration — then queues the request job
		(``do_sync_sap_data``) and returns immediately.
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
				f"SAP data generation requested for {self.name}. "
				"The trial balance will be populated automatically once SAP "
				"pushes it back."
			),
		}

	def _send_sap_request(self):
		"""Request half: ask SAP to generate the Trial Balance in *its* background.

		SAP responds with an acknowledgement only. We send our own document name
		as ``REFERENCE_ID`` so SAP can echo it back on the callback and we can
		match the pushed file to this exact record.

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
			# So SAP can correlate its later callback with this document.
			"REFERENCE_ID": self.name,
		}

		response = requests.get(fs.api_end_point, params=params, auth=HTTPBasicAuth(fs.user_name, fs.password), verify=False, timeout=int(fs.timeout))
		response.raise_for_status()

		# The request is now just a trigger; SAP acknowledges asynchronously.
		# Store whatever acknowledgement it returns for traceability.
		try:
			self.responce = json.dumps(response.json(), ensure_ascii=False)
		except ValueError:
			self.responce = response.text

		self.save()

	def apply_trial_balance_rows(self, rows):
		"""Fill ``details`` from a normalized list of SAP rows (RACCT/TEXT/REPVAL).

		Shared by the inbound callback. Saving triggers ``before_save`` which
		auto-maps accounts and recomputes ``total_amount``.
		"""
		self.details.clear()

		for d in rows:
			racct = (str(d.get("RACCT")) if d.get("RACCT") is not None else "").strip()
			try:
				repval = float(d.get("REPVAL") or 0)
			except (TypeError, ValueError):
				repval = 0

			if racct and repval != 0:
				self.append("details", {
					"gl_code": racct.lstrip("0"),
					"gl_description": d.get("TEXT"),
					"amount": repval,
				})

		self.save()

	@frappe.whitelist()
	def create_trail_balance(self):
		"""Generate FR Trial Balance Entries from synced details.

		Idempotent: any entries previously generated for this
		(company, fiscal_year, month) are removed first, so re-running does not
		append duplicates. Duplicates are dangerous here because
		``FRTrialBalanceEntry.before_save`` derives ``amount`` from the running
		sum of previous months' entries — leftover duplicates compound that sum
		on every run until it overflows the ``amount`` column.
		"""
		none_account = [d for d in self.details if not d.account]
		if none_account:
			first = none_account[0]
			frappe.throw(
				f"<b>Row: {first.idx}</b>, "
				f"GL: {first.gl_code}, "
				f"GL Desc: {first.gl_description}, "
				f"Amount: {first.amount} → <b>GL Account is missing</b>"
			)

		frappe.db.delete("FR Trial Balance Entry", {
			"company": self.company,
			"fiscal_year": self.fiscal_year,
			"month": self.month,
		})

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
	"""Background worker: fire the generation request to SAP for ``docname``.

	Enqueued by ``SyncSAPTrialBalance.sync_sap_data``. It sends the request and
	marks the doc ``Awaiting SAP`` — the actual data arrives later through the
	``receive_sap_trial_balance`` callback. Any failure is recorded on
	``sync_error`` and logged.
	"""
	doc = frappe.get_doc("Sync SAP Trial Balance", docname)
	try:
		doc.db_set("sync_status", "Syncing", commit=True)
		doc._send_sap_request()
		doc.db_set({"sync_status": "Awaiting SAP", "sync_error": ""}, commit=True)
		frappe.publish_realtime(
			"sap_tb_sync_complete", {"docname": docname, "status": "Awaiting SAP"}
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


@frappe.whitelist()
def receive_sap_trial_balance(reference_id=None, file_name=None, file_content=None):
	"""Inbound callback SAP calls once the Trial Balance has been generated.

	This is the configurable "API Detail" to hand to SAP. SAP authenticates with
	a Frappe **api_key:api_secret** (``Authorization: token <key>:<secret>``) and
	pushes the generated report here.

	Endpoint::

	    POST /api/method/financial_report_tool.financial_report_tool.doctype.sync_sap_trial_balance.sync_sap_trial_balance.receive_sap_trial_balance

	Payload:
	  * ``reference_id`` – the value we sent as ``REFERENCE_ID`` on the original
	    request (the Sync SAP Trial Balance document name). Required.
	  * The result file, either as a multipart ``file`` upload, or as base64
	    ``file_content`` together with ``file_name`` (``.json`` or ``.csv``).

	The pushed file is stored against the document, parsed, and its rows written
	to ``details``; the doc is then marked ``Completed``.
	"""
	if not reference_id:
		frappe.throw(_("reference_id is required"))

	if not frappe.db.exists("Sync SAP Trial Balance", reference_id):
		frappe.throw(_("No Sync SAP Trial Balance found for reference_id {0}").format(reference_id))

	raw_bytes, file_name = _read_inbound_file(file_name, file_content)
	ext = os.path.splitext(file_name)[1].lower()
	if ext not in (".csv", ".json"):
		frappe.throw(_("Only .csv and .json files are supported"))

	rows = _parse_sap_tb_file(raw_bytes, ext)

	doc = frappe.get_doc("Sync SAP Trial Balance", reference_id)
	try:
		saved = save_file(
			fname=file_name,
			content=raw_bytes,
			dt="Sync SAP Trial Balance",
			dn=doc.name,
			decode=False,
			is_private=1,
		)

		doc.sync_status = "Completed"
		doc.sync_error = ""
		try:
			doc.responce = raw_bytes.decode("utf-8-sig")
		except UnicodeDecodeError:
			doc.responce = raw_bytes.decode("latin-1")

		# apply_trial_balance_rows saves the doc (recomputes total_amount).
		doc.apply_trial_balance_rows(rows)
		frappe.db.commit()

		frappe.publish_realtime(
			"sap_tb_sync_complete", {"docname": doc.name, "status": "Completed"}
		)

		return {
			"success": True,
			"reference_id": doc.name,
			"file": saved.file_url,
			"rows_imported": len(doc.details),
			"message": f"Trial Balance received and populated for {doc.name}.",
		}
	except Exception:
		frappe.db.rollback()
		error_message = frappe.get_traceback(with_context=True)
		frappe.db.set_value(
			"Sync SAP Trial Balance",
			doc.name,
			{"sync_status": "Failed", "sync_error": error_message},
		)
		frappe.db.commit()
		frappe.publish_realtime(
			"sap_tb_sync_complete", {"docname": doc.name, "status": "Failed"}
		)
		frappe.log_error(title=f"SAP Trial Balance Callback Failed - {doc.name}")
		raise


def _read_inbound_file(file_name=None, file_content=None):
	"""Return ``(raw_bytes, file_name)`` from a multipart upload or base64 body."""
	uploaded = frappe.request.files.get("file") if frappe.request else None
	if uploaded is not None:
		file_name = file_name or uploaded.filename
		return uploaded.stream.read(), file_name

	if file_content:
		if not file_name:
			frappe.throw(_("file_name is required when sending file_content"))
		try:
			return base64.b64decode(file_content), file_name
		except (ValueError, TypeError) as e:
			frappe.throw(_("file_content must be valid base64: {0}").format(e))

	frappe.throw(_("Provide either a multipart 'file' or base64 'file_content'"))


def _parse_sap_tb_file(raw_bytes, ext):
	"""Normalize a pushed SAP file into a list of row dicts (RACCT/TEXT/REPVAL)."""
	try:
		content = raw_bytes.decode("utf-8-sig")
	except UnicodeDecodeError:
		content = raw_bytes.decode("latin-1")

	if ext == ".json":
		try:
			data = json.loads(content)
		except ValueError as e:
			frappe.throw(_("Invalid JSON file: {0}").format(e))

		# Accept either {"items": [...]} (SAP's inline shape) or a bare list.
		if isinstance(data, dict):
			rows = data.get("items")
		else:
			rows = data

		if not isinstance(rows, list):
			frappe.throw(_("Expected a list of rows or an object with an 'items' list"))
		return rows

	# CSV
	reader = csv.DictReader(io.StringIO(content))
	return [row for row in reader]
