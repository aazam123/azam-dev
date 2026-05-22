# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
from frappe.utils import (
    flt,
    cint,
    getdate
)



class FRAccountPayableEntry(Document):
	def set_employee_grouping(self):
		if self.currency != "INR" and self.ap == "Advance":
			self.grouping = "Employee Foreign Advance"
		elif self.currency == "INR" and self.ap == "Advance":
			self.grouping = "Employee Advance"
		elif self.currency == "INR" and self.ap == "Payable":
			self.grouping = "Employee Payable"
		elif self.currency != "INR" and self.ap == "Payable":
			self.grouping = "Employee Foreign Payable"
	
	def before_save(self):
		self.grouping_remark = ""
		if self.country == "IN":
			self.domesticimport = "Domestic"
		else:
			self.domesticimport = "Import"

		self.reconciliation_account = frappe.get_value("Account", {"account_number": self.account_no, "company": self.company, 'disabled': 0}, 'name')
		if not self.reconciliation_account:
			frappe.throw(f"Reconciliation account not found for account number {self.account_no} in company {self.company}")

		self.ap = "Payable" if self.amount_in_lc < 0 else "Advance"
		if self.ap == "Advance":
			if self.special_gl_ind:
				sp_gl_grouping = frappe.get_all("Special GL Indicator Grouping", {"parent": self.company, "special_gl_indicator": self.special_gl_ind}, ["nature", "e_ne", "currency", "grouping"])
				for sp_grouping in sp_gl_grouping:
					if sp_grouping:
						nature, e_ne, currency, grouping = sp_grouping.get("nature"), sp_grouping.get("e_ne"), sp_grouping.get("currency"), sp_grouping.get("grouping")
						if not nature:
							self.grouping = grouping
							self.grouping_remark = f"Advance + Special GL Ind '{self.special_gl_ind}' (no nature filter) → {grouping}"
						else:
							# frappe.throw(f"{self.ap}, {self.special_gl_ind}, {sp_grouping}")
							if currency:
								if e_ne == 'Not Equals' and self.currency != currency and self.ap == nature:
									self.grouping = grouping
									self.grouping_remark = f"Advance + Special GL Ind '{self.special_gl_ind}', nature='{nature}', currency!='{currency}' (actual: {self.currency}) → {grouping}"
								elif e_ne == 'Equals' and self.currency == currency and self.ap == nature:
									self.grouping = grouping
									self.grouping_remark = f"Advance + Special GL Ind '{self.special_gl_ind}', nature='{nature}', currency='{currency}' → {grouping}"
							else:
								if self.ap == nature:
									self.grouping = grouping
									self.grouping_remark = f"Advance + Special GL Ind '{self.special_gl_ind}', nature='{nature}' (no currency filter) → {grouping}"
			else:
				po_series = frappe.get_all("Purchase Order Series For Grouping", filters={"parent": self.company}, fields=["po_series_start_from", "grouping", "ap"])
				for po_s in po_series:
					if str(self.purchase_order).startswith(po_s.po_series_start_from) and self.ap == po_s.ap:
						self.grouping = po_s.grouping
						self.grouping_remark = f"Advance + PO '{self.purchase_order}' matched series '{po_s.po_series_start_from}' → {po_s.grouping}"
						break
		elif self.ap == "Payable":
			if self.purchase_order:
				po_series = frappe.get_all("Purchase Order Series For Grouping", filters={"parent": self.company}, fields=["po_series_start_from", "grouping", "ap"])
				for po_s in po_series:
					if str(self.purchase_order).startswith(po_s.po_series_start_from) and self.ap == po_s.ap:
						self.grouping = po_s.grouping
						self.grouping_remark = f"Payable + PO '{self.purchase_order}' matched series '{po_s.po_series_start_from}' → {po_s.grouping}"
						break
			else:
				sp_gl_grouping = frappe.get_all("Special GL Indicator Grouping", {"parent": self.company, "special_gl_indicator": self.special_gl_ind}, ["nature", "e_ne", "currency", "grouping"])
				for sp_grouping in sp_gl_grouping:
					if sp_grouping:
						nature, e_ne, currency, grouping = sp_grouping.get("nature"), sp_grouping.get("e_ne"), sp_grouping.get("currency"), sp_grouping.get("grouping")
						if not nature:
							self.grouping = grouping
							self.grouping_remark = f"Payable (no PO) + Special GL Ind '{self.special_gl_ind}' (no nature filter) → {grouping}"
						else:
							if currency:
								if e_ne == 'Not Equals' and self.currency != currency and self.ap == nature:
									self.grouping = grouping
									self.grouping_remark = f"Payable (no PO) + Special GL Ind '{self.special_gl_ind}', nature='{nature}', currency!='{currency}' (actual: {self.currency}) → {grouping}"
								elif e_ne == 'Equals' and self.currency == currency and self.ap == nature:
									self.grouping = grouping
									self.grouping_remark = f"Payable (no PO) + Special GL Ind '{self.special_gl_ind}', nature='{nature}', currency='{currency}' → {grouping}"
							else:
								if self.ap == nature:
									self.grouping = grouping
									self.grouping_remark = f"Payable (no PO) + Special GL Ind '{self.special_gl_ind}', nature='{nature}' (no currency filter) → {grouping}"

		voucher_series = frappe.get_all("Vendor Series For Nature", filters={"parent": self.company}, fields=["series_start_from", "nature"])
		for v_series in voucher_series:
			if str(self.supplier).startswith(v_series.series_start_from):
				self.nature = v_series.nature
				if self.nature == "Employee" and not self.grouping:
					self.set_employee_grouping()
					self.grouping_remark = f"Vendor series '{v_series.series_start_from}' → Employee, currency='{self.currency}', ap='{self.ap}' → {self.grouping}"
				break

		if self.document_type in ("AB", "SA"):
			self.nature = "Clearing Document"
		elif self.document_type == "EE":
			self.nature = "Employee"
			if not self.grouping:
				self.set_employee_grouping()
				self.grouping_remark = f"Document Type '{self.document_type}' → Employee, currency='{self.currency}', ap='{self.ap}' → {self.grouping}"
		elif self.document_type in ("KR", "RE", "MB"):
			self.nature = "Invoicing Document"
		elif self.document_type in ("KZ", "FP", "KG", "MP"):
			self.nature = "Payment"
		elif self.document_type == "AA":
			self.nature = "Asset Posting"
		elif self.document_type == "UE":
			self.nature = "Transfer Entry"
		elif self.document_type == "B1":
			self.nature = "Deposit"
		else:
			self.nature = "Payable" if self.amount_in_lc < 0 else "Advance"

		if self.due_days == 0:
			self.ageing = "Not Due"
		elif 0 < self.due_days <= 180:
			self.ageing = "0-6 Months"
		elif 180 < self.due_days <= 365:
			self.ageing = "6-12 Months"
		elif 365 < self.due_days <= 730:
			self.ageing = "1-2 Years"
		elif 730 < self.due_days <= 1095:
			self.ageing = "2-3 Years"
		elif self.due_days > 1095:
			self.ageing = "More Than 3 Years"
		else:
			self.ageing = "Not Due"

		if not self.closing_exchange_rate:
			closing_exchange_rate = frappe.get_value("FR Foreign Exchange Rate",{"from_currency": self.currency, "to_currency": "INR", "month": "April", "fiscal_year": self.fiscal_year}, 'closing_rate') or 0
			self.closing_exchange_rate = closing_exchange_rate if closing_exchange_rate else 1

		if self.closing_exchange_rate:
			self.restated_value = self.amount_in_dc * self.closing_exchange_rate
			self.gainloss = self.amount_in_lc - self.restated_value

		if not self.nature:
			self.nature = self.ap

		gl_account_grouping = frappe.get_value("GL Account For Grouping",{"parent": self.company, "gl_account": self.reconciliation_account},"grouping")
		if gl_account_grouping and not self.grouping:
			self.grouping = gl_account_grouping
			self.grouping_remark = f"Recon Account '{self.reconciliation_account}' → GL Account Grouping → {gl_account_grouping}"

		if self.special_gl_ind == "D":
			self.nature = "Deposit"
			self.grouping = "Deposit"
			self.grouping_remark = f"Special GL Ind = 'D' → Deposit (override)"

		if not self.grouping:
			if self.ap == "Advance":
				self.grouping = "Service Advance"
				self.grouping_remark = "No grouping match found → Default: Service Advance"
			elif self.ap == "Payable":
				self.grouping = "Service Payable"
				self.grouping_remark = "No grouping match found → Default: Service Payable"
			self.remark = "No Grouping Match"



@frappe.whitelist()
def import_from_sync_sap(
    sync_sap_doc,
    fiscal_year
):

    # ---------------------------------------------------
    # GET SYNC DOC
    # ---------------------------------------------------

    sync_doc = frappe.get_doc(
        "Sync SAP",
        sync_sap_doc
    )

    # ---------------------------------------------------
    # VALIDATIONS
    # ---------------------------------------------------

    if not sync_doc.json_data:

        frappe.throw(
            "JSON Data not found"
        )

    # ---------------------------------------------------
    # PREVENT DUPLICATE IMPORT
    # ---------------------------------------------------

    already_imported = frappe.db.exists(
        "FR Account Payable Entry",
        {
            "sync_sap_id":
                sync_doc.name
        }
    )

    if already_imported:

        frappe.throw(
            f"Sync SAP already imported: "
            f"{sync_doc.name}"
        )

    # ---------------------------------------------------
    # LOAD JSON
    # ---------------------------------------------------

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

        # Basic
        "DocumentNumber":
            "document_number",

        "Vendor":
            "supplier",

        "VendorName":
            "supplier_name",

        "PurchaseOrder":
            "purchase_order",

        "ReconAC":
            "account_no",

        "Assignment":
            "assignment",

        "Reference":
            "reference",

        "Country":
            "country",

        "City":
            "city",

        "Region":
            "state",

        "DocumentType":
            "document_type",

        "DebitCredit":
            "debitcredit",

        "SpecialGLind":
            "special_gl_ind",

        "InvoiceNo":
            "invoice_no",

        "DocCurrency":
            "currency",

        "PaytTerms":
            "paymet_terms",

        "PaymentDays":
            "payment_days",

        "Text":
            "text"
    }

    # ---------------------------------------------------
    # FLOAT FIELD MAP
    # ---------------------------------------------------

    float_fields = {

        "ExchangeRate":
            "exchange_rate",

        "AmountinLC":
            "amount_in_lc",

        "AmountinDC":
            "amount_in_dc",

        "DueAmt":
            "due_amount",

        "NondueAmt":
            "non_due_amount"
    }

    # ---------------------------------------------------
    # DATE FIELD MAP
    # ---------------------------------------------------

    date_fields = {

        "DocumentDate":
            "document_date",

        "PostingDate":
            "posting_date",

        "BaselineDate":
            "baseline_date",

        "DueDate":
            "due_date"
    }

    # ---------------------------------------------------
    # COUNTERS
    # ---------------------------------------------------

    created = 0
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

            # ---------------------------------------------------
            # CREATE DOC
            # ---------------------------------------------------

            doc = frappe.new_doc(
                "FR Account Payable Entry"
            )

            # ---------------------------------------------------
            # REQUIRED
            # ---------------------------------------------------

            doc.company = company

            doc.fiscal_year = (
                fiscal_year
            )

            doc.sync_sap_id = (
                sync_doc.name
            )

            doc.account_no = (
                row.get("ReconAC")
            )

            doc.currency = (
                row.get("DocCurrency")
                or "INR"
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
            # CALCULATED
            # ---------------------------------------------------

            doc.due_days = cint(
                row.get("DueDays")
            )

            # Nature
            if (
                doc.document_type
                in ["KZ", "AA"]
            ):

                doc.nature = (
                    "Payment"
                )

            else:

                doc.nature = (
                    "Payable"
                )

            # AP
            if doc.special_gl_ind:

                doc.ap = "Advance"

            else:

                doc.ap = "Payable"

            # Domestic / Import
            if (
                row.get("Country")
                == "IN"
            ):

                doc.domesticimport = (
                    "Domestic"
                )

            else:

                doc.domesticimport = (
                    "Import"
                )

            # Ageing
            due_days = cint(
                row.get("DueDays")
            )

            if due_days <= 0:

                doc.ageing = (
                    "Not Due"
                )

            elif due_days <= 180:

                doc.ageing = (
                    "0-6 Months"
                )

            elif due_days <= 365:

                doc.ageing = (
                    "6-12 Months"
                )

            elif due_days <= 730:

                doc.ageing = (
                    "1-2 Years"
                )

            elif due_days <= 1095:

                doc.ageing = (
                    "2-3 Years"
                )

            else:

                doc.ageing = (
                    "More Than 3 Years"
                )

            # ---------------------------------------------------
            # INSERT
            # ---------------------------------------------------

            doc.insert(
                ignore_permissions=True
            )

            created += 1

        except Exception:

            failed += 1

            errors.append(
                f"""
                Row: {index}

                Document Number:
                {row.get('DocumentNumber')}

                Error:
                {frappe.get_traceback()}
                """
            )

    frappe.db.commit()

    return {
    "created": created,
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