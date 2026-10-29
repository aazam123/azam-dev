# Copyright (c) 2025, Hybrowlabs Pvt Ltd
# For license information, please see license.txt

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

from financial_report_tool.financial_report_tool.doctype.fr_sync_sap_trial_balance.parent_account_model import (
	ParentAccountModel,
)
from financial_report_tool.financial_report_tool.fiscal_cycle import calendar_year_for, get_start_month


# Minimum share of sibling accounts that must agree on a parent for it to be taken
# as a *confident* existing-group match (see ``_suggest_parent``).
SIBLING_PURITY = 0.6

# SAP GL codes are series-coded: the leading digit fixes the account's financial
# nature (root type) and therefore which statement it lands on. When a GL code is
# present we use this to pin the root type and only ever suggest parents of the
# matching nature — a much stronger signal than prefix/name similarity alone.
#
#   GL Series   Root Type   Report Type
#   1xxxxxxx    Liability    Balance Sheet
#   2xxxxxxx    Asset        Balance Sheet
#   3xxxxxxx    Income       Profit and Loss
#   4xxxxxxx    Expense      Profit and Loss
#   5xxxxxxx    Expense      Profit and Loss
#   6xxxxxxx    Expense      Profit and Loss (not used)
#   7xxxxxxx    Equity       Balance Sheet
GL_SERIES_ROOT_TYPE = {
	"1": "Liability",
	"2": "Asset",
	"3": "Income",
	"4": "Expense",
	"5": "Expense",
	"6": "Expense",
	"7": "Equity",
}


def _gl_series_root_type(gl_code):
	"""Root type implied by a GL code's leading digit, or ``None`` if unknown.

	GL codes are stored with leading zeros stripped (see ``apply_trial_balance_rows``),
	so the first character is the series digit. Description-only rows (no code) and
	codes outside the known series return ``None``, leaving suggestion unconstrained.
	"""
	code = (gl_code or "").strip().lstrip("0")
	if not code:
		return None
	return GL_SERIES_ROOT_TYPE.get(code[0])


# Fully-qualified path of the inbound callback SAP pushes the generated report to.
_CALLBACK_METHOD = (
	"financial_report_tool.financial_report_tool.doctype."
	"fr_sync_sap_trial_balance.fr_sync_sap_trial_balance.receive_sap_trial_balance"
)

# RFBILA offers three mutually-exclusive output modes; SAP's ``z_f01_extract``
# takes them as a flag triplet where exactly one carries "X". Maps the doc's
# ``output_format`` choice to the flag that gets set.
OUTPUT_FLAG_FIELD = {
	"Classic List": "s_billst",  # Bilanz List  (classic ABAP list)
	"ALV Grid": "s_bilgrd",      # Bilanz Grid  (ALV grid)
	"ALV Tree": "s_biltre",      # Bilanz Tree  (ALV tree)
}


def _period_range(low, high):
	"""SAP select-option range table for a fiscal-period span.

	Returns ``[{sign, option, low, high}]`` as ``z_f01_extract`` expects for
	``s_rfper``/``s_cmpfmn``. Periods are zero-padded to two digits (SAP posting
	periods run 01–16: 12 regular + 4 special). A single-period span collapses to
	an ``EQ`` on ``low`` rather than a degenerate ``BT``.
	"""
	lo = str(low or "").strip().zfill(2)
	hi = str(high or "").strip().zfill(2)
	if lo == hi:
		return [{"sign": "I", "option": "EQ", "low": lo, "high": ""}]
	return [{"sign": "I", "option": "BT", "low": lo, "high": hi}]


def _callback_url():
	"""Absolute URL SAP posts the generated trial balance back to.

	Uses the explicit override in FR Financial Settings when set, otherwise
	derives it from the site URL so it works across environments without config.
	"""
	override = frappe.db.get_value("FR Financial Settings", None, "callback_url")
	if override:
		return override.strip()
	return frappe.utils.get_url(f"/api/method/{_CALLBACK_METHOD}")


def _callback_token():
	"""The ``p_token`` SAP requires to authenticate its callback to us.

	SAP's ``z_f01_extract`` treats ``p_token`` as a mandatory selection-screen
	field: without it the scheduled batch step cancels with *"Fill in all required
	entry fields"* (Msg 055) even though the request itself is acknowledged. We send
	the Frappe ``api_key:api_secret`` from FR Financial Settings' ``callback_token``,
	formatted as the ``Authorization: token <key>:<secret>`` header value SAP replays
	when POSTing back to :func:`receive_sap_trial_balance`.
	"""
	token = (frappe.db.get_value("FR Financial Settings", None, "callback_token") or "").strip()
	if not token:
		frappe.throw(
			_("Please configure <b>Callback Token</b> in FR Financial Settings — "
			  "SAP needs it (as p_token) to push the trial balance back."),
			title=_("Callback Token missing"),
		)
	# Already prefixed (e.g. "token key:secret") → send as-is, else add the scheme.
	return token if token.lower().startswith("token ") else f"token {token}"


# The Sync SAP Trial Balance ``month`` Select is calendar-ordered, so a month's
# index (+1) is its *calendar* number. That is NOT the SAP posting period: SAP
# counts periods from the fiscal-year start, so for an April-starting fiscal year
# August is period 05, not 08 (see ``_month_period``).
MONTHS = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]

# Fallback fiscal-year start month when a Fiscal Year has no stored start date —
# April, the standard Indian fiscal year these companies run on.
DEFAULT_FY_START_MONTH = 4


def _fiscal_start_year(fiscal_year):
	"""Start year (int) of a Fiscal Year, or ``None``.

	Reads the Fiscal Year's ``year_start_date`` (authoritative regardless of
	naming), falling back to the leading ``YYYY`` of a ``YYYY-YYYY`` name.
	"""
	start = frappe.db.get_value("Fiscal Year", fiscal_year, "year_start_date")
	if start:
		return start.year
	token = (fiscal_year or "").split("-")[0].strip()
	return int(token) if token.isdigit() else None


def _fiscal_start_month(fiscal_year):
	"""Calendar month (1-12) the Fiscal Year begins in, from ``year_start_date``.

	This is what turns a calendar month into a SAP posting period. Defaults to
	:data:`DEFAULT_FY_START_MONTH` (April) when the Fiscal Year is missing or has
	no stored start date, so an unconfigured record still lands on the usual
	Indian fiscal calendar rather than the (wrong) calendar-year one.
	"""
	start = frappe.db.get_value("Fiscal Year", fiscal_year, "year_start_date")
	return start.month if start else DEFAULT_FY_START_MONTH


def _month_period(month, fy_start_month=DEFAULT_FY_START_MONTH):
	"""Two-digit SAP posting period for a month name, or ``None``.

	SAP numbers periods from the fiscal-year start, not the calendar year: with
	an April-starting fiscal year (``fy_start_month=4``) April is period 01,
	August is 05, and January is 10. ``fy_start_month=1`` (a calendar-year fiscal
	year) reproduces the plain month number (August -> 08).
	"""
	try:
		cal = MONTHS.index(month) + 1
	except ValueError:
		return None
	period = ((cal - fy_start_month) % 12) + 1
	return f"{period:02d}"


class FRSyncSAPTrialBalance(Document):
	def before_save(self):
		"""Fill SAP params from the company/period, auto-map accounts, total up.

		The fixed SAP parameters are never retyped per run: the company code /
		chart of accounts / version / layout / client come from the company's
		:doctype:`FR SAP Company Mapping`, the reporting & comparison years derive from
		``fiscal_year``, and the period spans derive from ``month``. All of these
		are *fill-if-empty* so a manual override on a given document is preserved
		(the form's own onchange handlers refresh them when you switch company /
		fiscal year / month).
		"""
		self._apply_company_template()
		# Jan-Dec SAP companies are requested in calendar periods whichever
		# existing Fiscal Year is selected (see ``_apply_period_defaults``).
		self._apply_period_defaults()

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

	def _apply_company_template(self):
		"""Fill the company-fixed SAP params from :doctype:`FR SAP Company Mapping`.

		Only blank fields are filled, so a per-document override sticks. Missing
		mapping (or missing values on it) simply leaves the fields as-is, and the
		usual ``validate_required_fields`` guard still catches anything unset at
		sync time.
		"""
		if not self.company:
			return
		tpl = frappe.db.get_value(
			"FR SAP Company Mapping",
			{"company": self.company},
			["company_code", "chartofacc", "sversion", "layout", "sap_client"],
			as_dict=True,
		)
		if not tpl:
			return
		for field in ("company_code", "chartofacc", "sversion", "layout", "sap_client"):
			if tpl.get(field) and not self.get(field):
				self.set(field, tpl.get(field))

	def _apply_period_defaults(self):
		"""Derive the year + period params from ``fiscal_year`` and ``month``.

		``repyear`` is the fiscal year's start year and ``compyear`` the year
		before it. The period spans are year-to-date: ``01`` through the selected
		``month``'s SAP posting period (counted from the fiscal-year start, so for
		an April fiscal year August -> 01..05), applied to both the reporting and
		comparison ranges. Fill-if-empty, like the company template — so a manual
		override of any period field on the document is preserved.
		"""
		if self.company and self.fiscal_year and self.month and get_start_month(self.company) == "January":
			# Calendar-year company: the report year and periods follow the
			# calendar month's own date, so an existing Apr-Mar Fiscal Year can
			# label the snapshot without any Jan-Dec Fiscal Year being created.
			year = calendar_year_for(self.fiscal_year, self.month)
			if year:
				period = _month_period(self.month, 1)
				for field, value in (("repyear", str(year)), ("compyear", str(year - 1)),
									 ("srepmonth", "01"), ("trepmonth", period),
									 ("scompmonth", "01"), ("tcompmonth", period)):
					if not self.get(field):
						self.set(field, value)
				return
		if self.fiscal_year:
			year = _fiscal_start_year(self.fiscal_year)
			if year:
				if not self.repyear:
					self.repyear = str(year)
				if not self.compyear:
					self.compyear = str(year - 1)

		if self.month:
			mm = _month_period(self.month, _fiscal_start_month(self.fiscal_year))
			if mm:
				if not self.srepmonth:
					self.srepmonth = "01"
				if not self.trepmonth:
					self.trepmonth = mm
				if not self.scompmonth:
					self.scompmonth = "01"
				if not self.tcompmonth:
					self.tcompmonth = mm

	def validate_sap_settings(self):
		"""Ensure SAP API settings exist and are complete"""
		fs = frappe.db.get_value(
			"FR Financial Settings",
			None,
			["user_name", "password", "api_end_point", "timeout"],
			as_dict=True,
		)
		if not fs or not fs.user_name or not fs.password or not fs.api_end_point or not fs.timeout:
			frappe.throw("Please configure User Name, Password, API URL, Timeout and Client in <b>Financial Settings</b>")
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
			"financial_report_tool.financial_report_tool.doctype.fr_sync_sap_trial_balance.fr_sync_sap_trial_balance.do_sync_sap_data",
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
		"""Request half: ask SAP's ``z_f01_extract`` to generate the Trial Balance.

		SAP responds with an acknowledgement only. We send our own document name
		as ``reference_id`` and the absolute ``callback_url`` so SAP can push the
		generated report back to :func:`receive_sap_trial_balance` and we can match
		it to this exact record.

		The request is a JSON ``POST`` (``sap-client`` stays on the query string).
		Fiscal-period spans are sent as SAP select-option range tables, and the
		RFBILA output mode is expressed via the ``s_billst``/``s_bilgrd``/``s_biltre``
		flag triplet.

		Runs inside the background job. Raising here marks the job Failed and the
		error is surfaced on the form via ``sync_error`` (see ``do_sync_sap_data``).
		"""
		self.details.clear()
		self.responce = None

		fs = self.validate_sap_settings()
		self.validate_required_fields()

		chosen = self.output_format or "ALV Grid"
		flags = {
			field: ("X" if field == OUTPUT_FLAG_FIELD[chosen] else "")
			for field in ("s_billst", "s_bilgrd", "s_biltre")
		}

		body = {
			# So SAP can correlate its later callback with this document.
			"reference_id": self.name,
			"s_ktopl": self.chartofacc,
			"p_bukrs": self.company_code,
			"s_rldnr": self.ledger or "0L",
			"s_versn": self.sversion,
			"s_rpyear": self.repyear,
			"s_rfper": _period_range(self.srepmonth, self.trepmonth),
			"s_cmpyr": self.compyear,
			"s_cmpfmn": _period_range(self.scompmonth, self.tcompmonth),
			**flags,
			"s_layout": self.layout,
			"callback_url": _callback_url(),
			# Mandatory on SAP's side: the token SAP replays to authenticate its callback.
			"p_token": _callback_token(),
		}

		response = requests.post(
			fs.api_end_point,
			params={"sap-client": self.sap_client},
			json=body,
			auth=HTTPBasicAuth(fs.user_name, fs.password),
			verify=False,
			timeout=int(fs.timeout),
		)

		# On failure, surface SAP's *own* response body — a bare "403 Forbidden"
		# from raise_for_status() hides the real reason (missing authorization,
		# CSRF token required, wrong client, service inactive, ...). SAP usually
		# spells it out in the body, so put that in the error the user sees.
		if not response.ok:
			detail = (response.text or "").strip()
			frappe.throw(
				_("SAP rejected the request ({0} {1}) at {2}: {3}").format(
					response.status_code,
					response.reason,
					response.url,
					(detail[:1800] + " …") if len(detail) > 1800 else (detail or "(empty response body)"),
				),
				title=_("SAP Request Failed"),
			)

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
		# A Jan-Dec company's calendar snapshot labelled with an Apr-Mar Fiscal
		# Year is cumulative from 1 January, so it must never become that year's
		# trial balance entries; Derive Apr-Mar TB reads the accepted sync instead.
		calendar_snapshot = get_start_month(self.company) == "January" and _fiscal_start_month(self.fiscal_year) != 1
		none_account = [d for d in self.details if not d.account]
		if none_account:
			first = none_account[0]
			frappe.throw(
				f"<b>Row: {first.idx}</b>, "
				f"GL: {first.gl_code}, "
				f"GL Desc: {first.gl_description}, "
				f"Amount: {first.amount} → <b>GL Account is missing</b>"
			)

		if calendar_snapshot:
			frappe.db.set_value("FR Sync SAP Trial Balance", self.name, "tb_created", 1)
			frappe.msgprint(_("Calendar-year snapshot accepted. Use Derive Apr-Mar TB to create the Apr-Mar trial balance."))
			return
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

		frappe.db.set_value("FR Sync SAP Trial Balance", self.name, "tb_created", 1)
		frappe.msgprint("Trial Balance Entries created successfully!")

	@frappe.whitelist()
	def load_missing_accounts(self):
		"""(Re)populate the Missing Accounts tab from unmapped detail rows.

		A detail row is "unmapped" when it has no linked Account but carries a GL
		code *or* just a GL description (description-only rows are matched to an
		Account by name). Any grouping already entered is preserved across reloads,
		so a reload never discards in-progress selections; rows whose Account got
		mapped since the last load simply drop off.

		Empty fields are auto-suggested and only ever *filled*, never overwritten:

		* Parent Account — an existing group inferred from sibling accounts and a
		  local ML classifier trained on this company's Chart of Accounts
		  (:class:`ParentAccountModel`). When nothing existing fits, the row is left
		  without a parent for you to pick one manually.
		* Standalone Groups — borrowed from sibling accounts via the heuristic
		  :func:`_suggest_grouping`.
		"""
		existing_cfg = {_missing_key(r.gl_code, r.gl_description): r for r in self.missing_accounts}

		model = ParentAccountModel(self.company)
		group_cache = {}
		suggested = 0

		self.missing_accounts = []
		for row in self.details:
			if row.account:
				continue
			gl = (row.gl_code or "").strip()
			desc = (row.gl_description or "").strip()
			if not gl and not desc:
				continue

			prev = existing_cfg.get(_missing_key(gl, desc))
			values = {
				"parent_account": prev.parent_account if prev else None,
				"primary_group": prev.primary_group if prev else None,
				"secondary_group": prev.secondary_group if prev else None,
				"higher_secondary_group": prev.higher_secondary_group if prev else None,
				"suggested_parent": None,
				"confidence": None,
			}

			# Re-suggest a parent whenever none has been *chosen* (a set
			# ``parent_account`` is a decision we keep). This recomputes stale
			# auto-suggestions on reload.
			if not values["parent_account"]:
				parent_fields = _suggest_parent(model, self.company, gl, desc)
				values.update(parent_fields)
				if parent_fields.get("parent_account"):
					suggested += 1

			# Borrow Standalone Groups from sibling accounts (blanks only).
			key = _missing_key(gl, desc)
			if key not in group_cache:
				group_cache[key] = _suggest_grouping(self.company, gl, desc)
			for field in ("primary_group", "secondary_group", "higher_secondary_group"):
				if group_cache[key].get(field) and not values.get(field):
					values[field] = group_cache[key][field]

			self.append("missing_accounts", dict(values, gl_code=gl, gl_description=row.gl_description, amount=row.amount))

		self.save()
		message = _("Loaded {0} missing account(s).").format(len(self.missing_accounts))
		if suggested:
			message += " " + _("Suggested an existing parent for {0}.").format(suggested)
		if not model.ok:
			message += " " + _("(ML model unavailable — used the prefix heuristic.)")
		frappe.msgprint(message, indicator="blue")
		return {"count": len(self.missing_accounts), "suggested": suggested}

	@frappe.whitelist()
	def create_missing_accounts(self):
		"""Create ERPNext Accounts + GL Group Mappings from the Missing Accounts tab.

		Each row of ``missing_accounts`` resolves to its chosen ``parent_account``
		(an existing group); rows without one are skipped. The Account is created
		there; a :doctype:`FR GL Group Mapping` is created too when the row has
		Standalone Groups (blank groups just skip the mapping — the account is still
		created).

		``report_scope`` (``"Monthly"`` / ``"Yearly"`` / ``"Both"``) selects which GL
		Group Mapping report types get created. The method is idempotent: existing
		Accounts / mappings / groups are reused, never duplicated.
		"""
		config_by_key = {}
		for r in self.missing_accounts:
			config_by_key[_missing_key(r.gl_code, r.gl_description)] = r

		if not config_by_key:
			frappe.throw(_("No rows in Missing Accounts. Click 'Load Missing Accounts' first."))

		report_types = {
			"Monthly": ["Monthly"],
			"Yearly": ["Yearly"],
			"Both": ["Monthly", "Yearly"],
		}.get(self.report_scope or "Both", ["Monthly", "Yearly"])

		validated_parents = set()
		created_accounts = []
		created_mappings = 0
		skipped = []

		for row in self.details:
			if row.account:
				continue

			gl = (row.gl_code or "").strip()
			desc = (row.gl_description or "").strip()
			if not gl and not desc:
				continue

			cfg = config_by_key.get(_missing_key(gl, desc))
			if not cfg:
				continue

			parent_account = _resolve_parent_account(cfg, self.company, validated_parents)
			if not parent_account:
				skipped.append(gl or desc)
				continue

			# GL code matches by account number; description-only rows match by name.
			if gl:
				existing = frappe.get_value(
					"Account",
					{"account_number": gl, "company": self.company, "is_group": 0},
					"name",
				)
			else:
				existing = frappe.get_value(
					"Account",
					{"account_name": desc, "company": self.company, "is_group": 0},
					"name",
				)

			if existing:
				row.account = existing
			else:
				row.account = _create_account(gl, row.gl_description, self.company, parent_account)
				created_accounts.append(row.account)

			# Groups are optional — only map when both primary and secondary are set.
			if cfg.primary_group and cfg.secondary_group:
				for report_type in report_types:
					if _ensure_gl_group_mapping(
						row.account, self.company, report_type,
						cfg.primary_group, cfg.secondary_group, cfg.higher_secondary_group,
					):
						created_mappings += 1

		# Saving recomputes account auto-mapping + total_amount via before_save.
		self.save()
		frappe.db.commit()

		return {
			"created_accounts": created_accounts,
			"created_mappings": created_mappings,
			"skipped": skipped,
		}


def _missing_key(gl_code, gl_description):
	"""Stable identity for a missing row — GL codes may be blank (description-only)."""
	return ((gl_code or "").strip(), (gl_description or "").strip())


def _suggest_parent(model, company, gl_code, gl_description):
	"""Suggest an existing Parent Account for one missing GL. Order of preference:

	1. Sibling accounts sharing the GL-code prefix (or a description keyword) with
	   a dominant parent — the strongest, most reliable signal that these accounts
	   belong together.
	2. The ML classifier's confident prediction.
	3. A weaker sibling / ML signal — still an existing group.
	4. Nothing to learn from (no siblings and no trained model) → return ``{}`` so
	   the row is left without a parent for the user to pick one manually.

	When the GL code carries a known series (see :data:`GL_SERIES_ROOT_TYPE`), both
	the sibling search and the ML prediction are restricted to parents of the matching
	root type, so a suggestion can never cross the Balance Sheet / Profit and Loss line
	the code has already fixed.
	"""
	root_type = _gl_series_root_type(gl_code)
	siblings = _find_sibling_accounts(company, gl_code, gl_description, root_type)
	sib_parent, purity = _dominant_parent(siblings)
	prediction = model.predict(gl_code, gl_description, root_type) if model and model.ok else None

	# 1) Confident existing group from (near-)unanimous siblings.
	if sib_parent and purity >= SIBLING_PURITY:
		return _existing(sib_parent, purity * 100)

	# 2) Confident ML prediction — also an existing group.
	if prediction and prediction["confident"]:
		return _existing(prediction["parent_account"], prediction["confidence"] * 100)

	# 3) Weaker signals still beat leaving it blank.
	if sib_parent:
		return _existing(sib_parent, purity * 100)
	if prediction:
		return _existing(prediction["parent_account"], prediction["confidence"] * 100)

	# 4) Genuinely nothing fits → leave the parent blank for manual selection.
	return {}


def _existing(parent, confidence):
	"""Child-row fields for mapping to an existing parent group."""
	return {
		"parent_account": parent,
		"suggested_parent": parent,
		"confidence": round(confidence, 1),
	}


def _dominant_parent(siblings):
	"""Return ``(most_common_parent, purity)`` for a list of sibling accounts."""
	parents = [s.parent_account for s in siblings if s.parent_account]
	if not parents:
		return None, 0.0
	from collections import Counter

	parent, count = Counter(parents).most_common(1)[0]
	return parent, count / len(parents)


def _resolve_parent_account(cfg, company, validated_parents):
	"""Return the chosen existing parent group for ``cfg``, or ``None`` if unset.

	Uses the chosen ``parent_account`` when set; rows without one are skipped by
	the caller. Existing parents are validated once (cached in ``validated_parents``).
	"""
	if cfg.parent_account:
		if cfg.parent_account not in validated_parents:
			_validate_parent_group(cfg.parent_account, company)
			validated_parents.add(cfg.parent_account)
		return cfg.parent_account

	return None


def _suggest_grouping(company, gl_code, gl_description):
	"""Best-effort grouping suggestion for a missing GL, learned from existing Accounts.

	SAP GL codes are hierarchical, so accounts sharing the longest numeric prefix
	almost always live under the same parent group. We take the majority parent of
	the closest-matching siblings and, if a sibling already has a GL Group Mapping,
	borrow its Standalone Groups too. Falls back to a description keyword when the
	code yields nothing. Returns a dict with any of ``parent_account`` /
	``primary_group`` / ``secondary_group`` / ``higher_secondary_group`` — or ``{}``.
	"""
	siblings = _find_sibling_accounts(
		company, gl_code, gl_description, _gl_series_root_type(gl_code)
	)
	if not siblings:
		return {}

	suggestion = {}
	parent = _majority([s.parent_account for s in siblings if s.parent_account])
	if parent:
		suggestion["parent_account"] = parent

	# Borrow grouping from the first sibling that already has a GL Group Mapping.
	for s in siblings:
		mapping = frappe.db.get_value(
			"FR GL Group Mapping",
			{"gl_account": s.name, "company": company},
			["primary_group", "secondary_group", "higher_secondary_group"],
			as_dict=True,
		)
		if mapping and mapping.primary_group and mapping.secondary_group:
			suggestion.setdefault("primary_group", mapping.primary_group)
			suggestion.setdefault("secondary_group", mapping.secondary_group)
			if mapping.higher_secondary_group:
				suggestion.setdefault("higher_secondary_group", mapping.higher_secondary_group)
			break

	return suggestion


def _find_sibling_accounts(company, gl_code, gl_description, root_type=None):
	"""Existing non-group Accounts most likely to share ``gl_code``'s group.

	Tries the account-number prefix from most to least specific (min 2 digits),
	then falls back to the longest description keyword (min 4 chars). When
	``root_type`` is given (from the GL series), only accounts of that root type are
	returned — this keeps a loose 2-digit prefix or a common keyword from dragging in
	siblings that sit on the other financial statement.
	"""
	base = {"company": company, "is_group": 0}
	if root_type:
		base["root_type"] = root_type

	code = (gl_code or "").strip().lstrip("0")
	for length in range(len(code) - 1, 1, -1):
		rows = frappe.get_all(
			"Account",
			filters=dict(base, account_number=["like", f"{code[:length]}%"]),
			fields=["name", "parent_account"],
			limit=50,
		)
		if rows:
			return rows

	desc = (gl_description or "").strip()
	if desc:
		token = max(desc.split(), key=len, default="")
		if len(token) >= 4:
			rows = frappe.get_all(
				"Account",
				filters=dict(base, account_name=["like", f"%{token}%"]),
				fields=["name", "parent_account"],
				limit=50,
			)
			if rows:
				return rows

	return []


def _majority(values):
	"""Most common value in ``values`` (``None`` if empty)."""
	if not values:
		return None
	from collections import Counter

	return Counter(values).most_common(1)[0][0]


def _validate_parent_group(parent_account, company):
	"""Ensure ``parent_account`` is a group account belonging to ``company``."""
	parent = frappe.db.get_value(
		"Account", parent_account, ["is_group", "company"], as_dict=True
	)
	if not parent:
		frappe.throw(_("Parent Account {0} not found.").format(parent_account))
	if not parent.is_group:
		frappe.throw(_("Parent Account {0} must be a Group.").format(parent_account))
	if parent.company != company:
		frappe.throw(
			_("Parent Account {0} belongs to {1}, not {2}.").format(
				parent_account, parent.company, company
			)
		)


def _create_account(gl_code, gl_description, company, parent_account):
	"""Create and return an Account for ``gl_code`` under ``parent_account``.

	``root_type`` is inherited from the parent group by ERPNext, so it isn't set
	here. ERPNext prefixes the record name with the account number, keeping
	accounts unique even when two GL codes share a description.
	"""
	account = frappe.new_doc("Account")
	account.account_name = (gl_description or gl_code).strip()
	if (gl_code or "").strip():
		account.account_number = gl_code
	account.company = company
	account.parent_account = parent_account
	account.insert(ignore_permissions=True)
	return account.name


def _ensure_gl_group_mapping(
	gl_account, company, report_type, primary_group, secondary_group, higher_secondary_group=None
):
	"""Create the GL Group Mapping for ``gl_account``/``report_type`` if absent.

	Returns ``True`` when a mapping was created, ``False`` when one already exists.
	"""
	if frappe.db.exists(
		"FR GL Group Mapping",
		{"gl_account": gl_account, "company": company, "report_type": report_type},
	):
		return False

	mapping = frappe.new_doc("FR GL Group Mapping")
	mapping.gl_account = gl_account
	mapping.company = company
	mapping.report_type = report_type
	mapping.primary_group = primary_group
	mapping.secondary_group = secondary_group
	if higher_secondary_group:
		mapping.higher_secondary_group = higher_secondary_group
	mapping.insert(ignore_permissions=True)
	return True


def do_sync_sap_data(docname):
	"""Background worker: fire the generation request to SAP for ``docname``.

	Enqueued by ``FRSyncSAPTrialBalance.sync_sap_data``. It sends the request and
	marks the doc ``Awaiting SAP`` — the actual data arrives later through the
	``receive_sap_trial_balance`` callback. Any failure is recorded on
	``sync_error`` and logged.
	"""
	doc = frappe.get_doc("FR Sync SAP Trial Balance", docname)
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
			"FR Sync SAP Trial Balance",
			docname,
			{"sync_status": "Failed", "sync_error": error_message},
		)
		frappe.db.commit()
		frappe.publish_realtime(
			"sap_tb_sync_complete", {"docname": docname, "status": "Failed"}
		)
		frappe.log_error(title=f"SAP Trial Balance Sync Failed - {docname}")
		raise

@frappe.whitelist(allow_guest=True)
def receive_sap_trial_balance(reference_id=None, file_name=None, items=None):
	"""Inbound callback SAP calls once the Trial Balance has been generated.

	This is the ``callback_url`` handed to ``z_f01_extract``. SAP authenticates
	with a Frappe **api_key:api_secret** (``Authorization: token <key>:<secret>``)
	and pushes the generated report here.

	Endpoint::

	    POST /api/method/financial_report_tool.financial_report_tool.doctype.fr_sync_sap_trial_balance.fr_sync_sap_trial_balance.receive_sap_trial_balance

	SAP delivers the report one of two ways, both handled here:

	* **Inline JSON body** (what ``z_f01_extract`` actually posts) — a JSON object
	  ``{"reference_id": "...", "items": [{RACCT, TEXT, REPVAL}, ...]}``. The rows
	  arrive as the ``items`` argument.
	* **Multipart ``file`` upload** — a ``.csv`` or ``.json`` attachment
	  (``file_name`` optional; defaults to the upload's own name). Kept for manual
	  re-pushes and CSV output.

	``reference_id`` (the value we sent on the original request, i.e. the Sync SAP
	Trial Balance document name) is required either way so we can match the report
	to this exact record.

	The payload is stored against the document and the doc is marked ``Syncing``;
	the callback then returns immediately. A background job
	(:func:`process_sap_trial_balance_file`) normalizes the rows
	(RACCT/TEXT/REPVAL) into ``details`` and marks the doc ``Completed`` (or
	``Failed``). This keeps the callback fast even for large (~MB) payloads.
	"""
	if not reference_id:
		frappe.throw(_("reference_id is required"))

	if not frappe.db.exists("FR Sync SAP Trial Balance", reference_id):
		frappe.throw(_("No Sync SAP Trial Balance found for reference_id {0}").format(reference_id))

	# Persist the payload synchronously (fast), then hand parsing off to a
	# background worker so the callback returns immediately instead of blocking
	# SAP while thousands of detail rows are parsed and written.
	rows = _inline_items(items)
	if rows is not None:
		# Inline JSON push: materialize it as a .json payload so it flows through
		# the same store-then-parse pipeline as an uploaded file.
		raw_bytes = json.dumps({"items": rows}, ensure_ascii=False).encode("utf-8")
		file_name = file_name or f"{reference_id}.json"
		ext = ".json"
	else:
		raw_bytes, file_name = _read_inbound_file(file_name)
		ext = os.path.splitext(file_name)[1].lower()
		if ext not in (".csv", ".json"):
			frappe.throw(_("Only .csv and .json files are supported"))

	saved = save_file(
		fname=file_name,
		content=raw_bytes,
		dt="FR Sync SAP Trial Balance",
		dn=reference_id,
		decode=False,
		is_private=1,
	)

	frappe.db.set_value(
		"FR Sync SAP Trial Balance",
		reference_id,
		{"sync_status": "Syncing", "sync_error": ""},
	)
	frappe.db.commit()

	frappe.enqueue(
		"financial_report_tool.financial_report_tool.doctype.fr_sync_sap_trial_balance.fr_sync_sap_trial_balance.process_sap_trial_balance_file",
		queue="long",
		job_name=f"Parse SAP Trial Balance - {reference_id}",
		timeout=1500,
		reference_id=reference_id,
		file_url=saved.file_url,
		ext=ext,
	)

	return {
		"success": True,
		"reference_id": reference_id,
		"file": saved.file_url,
		"status": "Syncing",
		"message": f"File received for {reference_id}; parsing has been queued.",
	}


def process_sap_trial_balance_file(reference_id, file_url, ext):
	"""Background worker: parse a stored SAP file and populate the Trial Balance.

	Enqueued by :func:`receive_sap_trial_balance` so the inbound callback can
	store the file and return immediately. Marks the document ``Completed`` on
	success, or ``Failed`` (with the traceback in ``sync_error``) on any error.

	SAP posts the callback unauthenticated, so the enqueued job inherits the
	``Guest`` user and ``doc.save()`` would raise ``PermissionError``. This is a
	trusted server-side processor (the report was requested by us and SAP only
	pushes it back), so run it as ``Administrator``.
	"""
	frappe.set_user("Administrator")
	try:
		raw_bytes = _read_stored_file(file_url)
		rows = _parse_sap_tb_file(raw_bytes, ext)

		doc = frappe.get_doc("FR Sync SAP Trial Balance", reference_id)
		doc.sync_status = "Completed"
		doc.sync_error = ""
		# The uploaded file is kept as an attachment (file_url); store only a
		# compact pointer here so large (~MB) payloads don't overflow the column.
		doc.responce = f"Stored file: {file_url} ({len(rows)} rows)"

		# apply_trial_balance_rows saves the doc (recomputes total_amount).
		doc.apply_trial_balance_rows(rows)
		frappe.db.commit()

		frappe.publish_realtime(
			"sap_tb_sync_complete", {"docname": reference_id, "status": "Completed"}
		)
	except Exception:
		frappe.db.rollback()
		error_message = frappe.get_traceback(with_context=True)
		frappe.db.set_value(
			"FR Sync SAP Trial Balance",
			reference_id,
			{"sync_status": "Failed", "sync_error": error_message},
		)
		frappe.db.commit()
		frappe.publish_realtime(
			"sap_tb_sync_complete", {"docname": reference_id, "status": "Failed"}
		)
		frappe.log_error(title=f"SAP Trial Balance Parse Failed - {reference_id}")
		raise


def _read_stored_file(file_url):
	"""Read the raw bytes of a stored File attachment by its ``file_url``."""
	from frappe.utils.file_manager import get_file
	content = get_file(file_url)[1]
	if isinstance(content, str):
		content = content.encode("utf-8")
	return content


def _read_inbound_file(file_name=None):
	"""Return ``(raw_bytes, file_name)`` from SAP's multipart ``file`` upload."""
	uploaded = frappe.request.files.get("file") if frappe.request else None
	if uploaded is None:
		frappe.throw(_("A multipart 'file' upload (.csv or .json) is required"))

	file_name = file_name or uploaded.filename
	return uploaded.stream.read(), file_name


def _inline_items(items):
	"""Rows from an inline JSON callback body, or ``None`` if it isn't one.

	``z_f01_extract`` posts the report as ``{"reference_id": ..., "items": [...]}``.
	Frappe maps the JSON body's ``items`` key straight to the whitelisted kwarg, but
	we also peek at the raw request body so a stringified or otherwise-unbound payload
	still resolves. Returns the row list (possibly empty) for an inline push, or
	``None`` so the caller falls back to the multipart ``file`` upload path.
	"""
	if items is None and frappe.request is not None:
		try:
			body = frappe.request.get_json(silent=True)
		except Exception:
			body = None
		if isinstance(body, dict):
			items = body.get("items")

	if items is None:
		return None

	if isinstance(items, str):
		try:
			items = json.loads(items)
		except ValueError:
			frappe.throw(_("Invalid 'items' JSON in SAP callback body"))

	if not isinstance(items, list):
		frappe.throw(_("SAP callback 'items' must be a list of rows"))

	return items


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
