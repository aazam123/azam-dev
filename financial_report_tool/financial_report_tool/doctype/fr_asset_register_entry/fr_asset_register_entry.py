# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import calendar
import json
from frappe.utils import (
    flt,
    cint,
    getdate,
    nowdate
)


class FRAssetRegisterEntry(Document):
	def before_insert(self):
		if not self.asset:
			asset = frappe.get_doc("FR Assets Master", {"assets_id": self.asset_id, 'company': self.company, 'subnumber': self.subnumber})
			if not asset:
				frappe.throw(f"No Assets Master found for Asset ID {self.asset_id} in Company {self.company} with Subnumber {self.subnumber}")
			self.asset = asset.name
			self.asset_value = asset.assets_value
			self.ordinary_depreciation_start_date = asset.capitalisation_date
			self.life_years = asset.life_years
			self.life_days = asset.life_days
			self.shift = asset.shift
			self.assets_end_date = asset.end_date
		
		self.calculate_days_in_current_year()
		self.set_starting_book_value()
		self.calculation()

	def before_save(self):
		if not (self.asset_value and self.life_days and self.days_in_current_year):
			return

		self.calculate_days_in_current_year()
		self.set_starting_book_value()
		self.calculation()
		
	# 1️⃣ Calculate total days used in current fiscal year
	@frappe.whitelist()
	def calculate_days_in_current_year(self):
		if not self.ordinary_depreciation_start_date or not self.fiscal_year:
			return 0

		fy = frappe.get_doc("Fiscal Year", self.fiscal_year)
		fy_start = getdate(fy.year_start_date)
		fy_end = getdate(fy.year_end_date)
		dep_start = getdate(self.ordinary_depreciation_start_date)

		effective_start = dep_start if dep_start > fy_start else fy_start
		effective_end = getdate(self.sales_date) if self.sales_date else fy_end

		diff_in_days = (effective_end - effective_start).days + 1
		is_leap = calendar.isleap(fy_start.year) or calendar.isleap(fy_end.year)
		max_days = 366 if is_leap else 365
		self.days_in_current_year = min(diff_in_days, max_days)

		return self.days_in_current_year

	# 2️⃣ Set starting book value from last depreciation year
	def set_starting_book_value(self):
		"""
		Pull last year's closing value from the latest FR Asset Register Entry of the same asset_id before this fiscal year.
		"""
		last_entry = frappe.db.get_value(
			"FR Asset Register Entry",{"asset_id": self.asset_id,
				"fiscal_year": ["!=", self.fiscal_year]
			},
			["name", "ending_book_value", "fiscal_year"],
			order_by="creation desc",
			as_dict=True
		)

		if last_entry:
			self.starting_book_value = last_entry.ending_book_value
		else:
			self.starting_book_value = self.asset_value

	# 3️⃣ Main depreciation calculation logic
	def calculation(self):
		if self.life_days == 0 and self.depreciation_key != "Z000":
			frappe.throw("Life Days cannot be zero while calculating depreciation.")

		# Get fiscal year range
		fy = frappe.get_doc("Fiscal Year", self.fiscal_year)
		fy_start = getdate(fy.year_start_date)
		fy_end = getdate(fy.year_end_date)

		# --- Basic self.depreciation ---
		self.depreciation = round((self.asset_value * self.days_in_current_year) / self.life_days, 3) if self.depreciation_key != "Z000" else 0

		# --- Shift-based Additional Depreciation ---
		if self.shift == "1":
			self.additional = 0
		elif self.shift == "2":
			self.additional = round(self.depreciation * 0.5, 3)
		elif self.shift == "3":
			self.additional = round(self.depreciation * 1, 3)
		else:
			self.additional = 0

		# --- Total Depreciation ---
		self.total_depreciation = round(self.depreciation + self.additional, 3)

		# --- Accumulated Depreciation ---
		self.open_accumulated_depreciation = self.total_depreciation

		# Planned Depreciation Logic:
		dep_start = getdate(self.ordinary_depreciation_start_date)
		if fy_start <= dep_start <= fy_end:
			self.planned_depreciation = 0
		else:
			self.planned_depreciation = self.total_depreciation

		# --- Gross Block and Book Value Calculations ---
		self.close_gross_block = (self.open_gross_block or 0) + (self.transaction_acquisition_value or 0)
		self.close_accumulated_depreciation = self.open_accumulated_depreciation + self.planned_depreciation
		self.ending_book_value = self.close_gross_block - self.close_accumulated_depreciation


# import frappe
# from frappe.model.document import Document
# from frappe.utils import getdate
# import calendar

# class FRAssetRegisterEntry(Document):
# 	def before_insert(self):
# 		self.calculate_days_in_current_year()
# 		self.set_starting_book_value()
# 		self.calculation()

# 	def before_save(self):
# 		if not (self.asset_value and self.life_days and self.days_in_current_year):
# 			return

# 		self.calculate_days_in_current_year()
# 		self.set_starting_book_value()
# 		self.calculation()
	
# 	# 1️⃣ Calculate total days used in current fiscal year
# 	@frappe.whitelist()
# 	def calculate_days_in_current_year(self):
# 		if not self.ordinary_depreciation_start_date or not self.fiscal_year:
# 			return 0

# 		fy = frappe.get_doc("Fiscal Year", self.fiscal_year)
# 		fy_start = getdate(fy.year_start_date)
# 		fy_end = getdate(fy.year_end_date)
# 		dep_start = getdate(self.ordinary_depreciation_start_date)

# 		effective_start = dep_start if dep_start > fy_start else fy_start
# 		effective_end = getdate(self.sales_date) if self.sales_date else fy_end

# 		diff_in_days = (effective_end - effective_start).days + 1
# 		is_leap = calendar.isleap(fy_start.year) or calendar.isleap(fy_end.year)
# 		max_days = 366 if is_leap else 365
# 		self.days_in_current_year = min(diff_in_days, max_days)

# 		return self.days_in_current_year

# 	# 2️⃣ Set starting book value from last depreciation year
# 	def set_starting_book_value(self):
# 		"""
# 		Pull last year's closing value from the latest FR Asset Register Entry of the same asset_id before this fiscal year.
# 		"""
# 		last_entry = frappe.db.get_value(
# 			"FR Asset Register Entry",{"asset_id": self.asset_id,
# 				"fiscal_year": ["!=", self.fiscal_year]
# 			},
# 			["name", "ending_book_value", "fiscal_year"],
# 			order_by="creation desc",
# 			as_dict=True
# 		)

# 		if last_entry:
# 			self.starting_book_value = last_entry.ending_book_value
# 		else:
# 			self.starting_book_value = self.asset_value

# 	# 3️⃣ Main depreciation calculation logic
# 	def calculation(self):
# 		if self.life_days == 0:
# 			frappe.throw("Life Days cannot be zero while calculating depreciation.")

# 		# Get fiscal year range
# 		fy = frappe.get_doc("Fiscal Year", self.fiscal_year)
# 		fy_start = getdate(fy.year_start_date)
# 		fy_end = getdate(fy.year_end_date)

# 		# --- Basic Depreciation ---
# 		self.depreciation = round((self.asset_value * self.days_in_current_year) / self.life_days, 3)

# 		# --- Shift-based Additional Depreciation ---
# 		if self.shift == "1":
# 			self.additional = 0
# 		elif self.shift == "2":
# 			self.additional = round(self.depreciation * 0.5, 3)
# 		elif self.shift == "3":
# 			self.additional = round(self.depreciation * 1, 3)
# 		else:
# 			self.additional = 0

# 		# --- Total Depreciation ---
# 		self.total_depreciation = round(self.depreciation + self.additional, 3)

# 		# --- Accumulated Depreciation ---
# 		self.open_accumulated_depreciation = self.total_depreciation

# 		# Planned Depreciation Logic:
# 		dep_start = getdate(self.ordinary_depreciation_start_date)
# 		if fy_start <= dep_start <= fy_end:
# 			self.planned_depreciation = 0
# 		else:
# 			self.planned_depreciation = self.total_depreciation

# 		# --- Gross Block and Book Value Calculations ---
# 		self.close_gross_block = self.open_gross_block + (self.transaction_acquisition_value or 0)
# 		self.close_accumulated_depreciation = self.open_accumulated_depreciation + self.planned_depreciation
# 		self.ending_book_value = self.close_gross_block - self.close_accumulated_depreciation




@frappe.whitelist()
def import_from_sync_sap(sync_sap_doc):
    sync_doc = frappe.get_doc(
        "Sync SAP",
        sync_sap_doc
    )

    if not sync_doc.json_data:

        frappe.throw(
            "JSON Data not found"
        )

    try:

        data = json.loads(
            sync_doc.json_data
        )

    except Exception:

        frappe.throw(
            "Invalid JSON Data"
        )

    if not isinstance(data, list):

        frappe.throw(
            "JSON Data must be a list"
        )

    # ---------------------------------------------------
    # COMPANY CACHE
    # ---------------------------------------------------

    company_map = {}

    companies = frappe.get_all(
        "Company",
        fields=[
            "name",
            "custom_company_code"
        ]
    )

    for company in companies:

        if company.custom_company_code:

            company_map[
                str(
                    company.custom_company_code
                ).strip()
            ] = company.name

    # ---------------------------------------------------
    # FIELD MAP
    # ---------------------------------------------------

    field_map = {

        "Asset":
            "asset_id",

        "Subnumber":
            "subnumber",

        "BalshacctAPC":
            "balance_sheet_account_apc",

        "AssetClass":
            "asset_class",

        "Depreciationkey":
            "depreciation_key",

        "Plant":
            "plant",

        "CostCenter":
            "cost_center",

        "Vendor":
            "vendor"
    }

    # ---------------------------------------------------
    # FLOAT FIELD MAP
    # ---------------------------------------------------

    float_fields = {

        "Quantity":
            "quantity",

        "Cumacqvalue":
            "cumulative_acquisition_value",

        "Transacqval":
            "transaction_acquisition_value",

        "PlndODep":
            "planned_depreciation",

        "CumOdep1":
            "transferred_accumulated_depreciation",

        "CumOdep3":
            "transferred_acquisition_value",

        "Startbookval":
            "starting_book_value",

        "Cumacqvalue7":
            "ending_book_value",

        "Cumacqvalue":
            "sap_cav",

        "CumOdep":
            "sap_acc_dep",

        "Transacqval":
            "sap_transaction_acq_value",

        "PlndODep":
            "sap_plan_dep",

        "CumOdep1":
            "sap_tran_accu_dep",

        "CumOdep3":
            "sap_tran_acq_value",

        "Startbookval":
            "sap_sbv",

        "Cumacqvalue7":
            "sap_ebv"
    }

    # ---------------------------------------------------
    # DATE FIELD MAP
    # ---------------------------------------------------

    date_fields = {

        "Orddepstartdate":
            "ordinary_depreciation_start_date"
    }

    # ---------------------------------------------------
    # COUNTERS
    # ---------------------------------------------------

    created = 0
    updated = 0
    failed = 0
    errors = []

    # ---------------------------------------------------
    # LOOP
    # ---------------------------------------------------

    for index, row in enumerate(
        data,
        start=1
    ):

        try:

            # ---------------------------------------------------
            # COMPANY
            # ---------------------------------------------------

            company_code = str(
                row.get("CompanyCode")
                or ""
            ).strip()

            company = company_map.get(
                company_code
            )

            if not company:

                skipped += 1

                errors.append(
                    f"Row {index}: "
                    f"Company not found "
                    f"for code "
                    f"{company_code}"
                )

                continue

            existing_doc = None
            unique_id = f"{row.get('Asset')}-{row.get('Subnumber')}-{row.get('CompanyCode')}"
            existing_doc = frappe.db.exists(
                "FR Asset Register Entry",
                {
                    "sap_unique_id": unique_id
                }
            )
            if existing_doc:
                doc = frappe.get_doc(
                    "FR Asset Register Entry",
                    existing_doc
                )
            else:
                doc = frappe.new_doc(
                    "FR Asset Register Entry"
                )           
                doc.sap_unique_id = unique_id

            doc.company = company

            doc.fiscal_year = frappe.db.get_value(
                "Fiscal Year",
                {
                    "year_start_date":
                        ["<=", nowdate()],

                    "year_end_date":
                        [">=", nowdate()]
                }
            )

            doc.sync_sap_id = (
                sync_doc.name
            )

            doc.asset_group = (
                "Default"
            )

            # ---------------------------------------------------
            # NORMAL FIELDS
            # ---------------------------------------------------

            for (
                json_key,
                fieldname
            ) in field_map.items():

                setattr(
                    doc,
                    fieldname,
                    row.get(json_key)
                )

            # ---------------------------------------------------
            # FLOAT FIELDS
            # ---------------------------------------------------

            for (
                json_key,
                fieldname
            ) in float_fields.items():

                setattr(
                    doc,
                    fieldname,
                    flt(
                        row.get(json_key)
                    )
                )

            # ---------------------------------------------------
            # DATE FIELDS
            # ---------------------------------------------------

            for (
                json_key,
                fieldname
            ) in date_fields.items():

                setattr(
                    doc,
                    fieldname,
                    get_valid_date(
                        row.get(json_key)
                    )
                )

            # ---------------------------------------------------
            # LIFE
            # ---------------------------------------------------

            life = (
                row.get("Life")
                or ""
            )

            if "/" in life:

                parts = life.split("/")

                doc.life_years = cint(
                    parts[0]
                )

                doc.life_days = cint(
                    parts[1]
                )

            # ---------------------------------------------------
            # ERP VALUES
            # ---------------------------------------------------

            doc.accumulated_depreciation = flt(
                row.get("CumOdep")
            )

            doc.open_accumulated_depreciation = flt(
                row.get("CumOdep1")
            )

            doc.close_accumulated_depreciation = flt(
                row.get("CumOdep2")
            )

            doc.open_gross_block = flt(
                row.get("Cumacqvalue8")
            )

            doc.close_gross_block = flt(
                row.get("Cumacqvalue9")
            )

            doc.total_depreciation = (
                flt(doc.depreciation)
                + flt(doc.additional)
            )

            doc.flags.ignore_links = True
            if existing_doc:
                doc.save(
                    ignore_permissions=True
                )
                updated += 1
            else:
                doc.insert(
                    ignore_permissions=True
                )
            
                created += 1

        except Exception:

            failed += 1

            errors.append(
                f"""
                Row: {index}

                Asset:
                {row.get('Asset')}

                Error:
                {frappe.get_traceback()}
                """
            )

    frappe.db.commit()

    return {
        "created": created,
        "updated": updated,
        "failed": failed,
        "error_log": "\n\n".join(errors) if errors else ""
    }


def get_valid_date(date_value):

    if not date_value:

        return None

    if str(date_value) in [

        "0000-00-00",
        "0",
        ""

    ]:

        return None

    try:

        return getdate(date_value)

    except Exception:

        return None