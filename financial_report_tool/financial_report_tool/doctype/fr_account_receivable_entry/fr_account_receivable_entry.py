# Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
from frappe.utils import (
    flt,
    cint,
    getdate,
    today
)



class FRAccountReceivableEntry(Document):

    def before_insert(self):
        if self.report_type == "Yearly":
            customer_sum = frappe.db.sql("""
                SELECT COALESCE(SUM(amount_in_lc), 0)
                FROM `tabFR Account Receivable Entry`
                WHERE customer = %s
            """, (self.customer,))[0][0] or 0

            customer_sum += flt(self.amount_in_lc)

            self.nature = "Advance" if customer_sum < 0 else "Receivable"

    def before_save(self):

        # ✅ TB Nature Logic
        if self.gl_account:
            if str(self.gl_account).startswith("1"):
                self.tb_nature = "Advance"
            elif str(self.gl_account).startswith("2"):
                self.tb_nature = "Receivable"

        # ✅ Forex & Restatement
        if self.nature == "Receivable":
            if not self.closing_ex_rate:
                self.closing_ex_rate = frappe.get_value(
                    "FR Foreign Exchange Rate",
                    {
                        "from_currency": self.currency,
                        "to_currency": "INR",
                        "month": "March",
                        "fiscal_year": self.fiscal_year
                    },
                    "closing_rate"
                ) or 1

            self.restated_value = flt(self.amount_in_dc) * flt(self.closing_ex_rate)
            self.gainloss = flt(self.amount_in_lc) - flt(self.restated_value)

        # ✅ FIX: Proper Date Handling
        if self.due_date:
            due_date = getdate(self.due_date)
            if self.posting_date:
                today_date = getdate(self.posting_date)
            else:
                year = str(self.fiscal_year).split("-")[-1]
                today_date = getdate(f"{year}-03-31")

            self.due_days = (today_date - due_date).days + 1
        else:
            self.due_days = 0

        # ✅ Ageing Bucket Logic
        if self.due_days <= 0:
            self.ageing = "Not Due"
        elif 0 < self.due_days <= 180:
            self.ageing = "0-6 Months"
        elif 180 < self.due_days <= 365:
            self.ageing = "6-12 Months"
        elif 365 < self.due_days <= 730:
            self.ageing = "1-2 Years"
        elif 730 < self.due_days <= 1095:
            self.ageing = "2-3 Years"
        else:
            self.ageing = "More Than 3 Years"

        # ✅ Provision Calculation (safe)
        self.provision_amount = (
            flt(self.restated_value) * flt(self.provision_percentage)
        ) / 100 if self.restated_value else 0

    def on_update(self):

        if self.report_type == "Yearly":
            customer_sum = frappe.db.sql("""
                SELECT COALESCE(SUM(amount_in_lc), 0)
                FROM `tabFR Account Receivable Entry`
                WHERE customer = %s
            """, (self.customer,))[0][0] or 0

            self.nature = "Advance" if customer_sum < 0 else "Receivable"

        elif self.report_type == "Monthly":
            if self.special_gl_ind in ["A", "B"]:
                self.nature = "Advance"
            else:
                self.nature = "Receivable"

        # ✅ Recalculate provision safely
        self.provision_amount = (
            flt(self.restated_value) * flt(self.provision_percentage)
        ) / 100 if self.restated_value else 0




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
        "FR Account Receivable Entry",
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

        # Customer
        "Customer":
            "customer",

        "CustomerName":
            "customer_name",

        # Sales
        "SalesOffice":
            "sales_office",

        "SalesOfficeDesc":
            "sales_office_desc",

        "SalesGroup":
            "sales_group",

        "SalesOfficeDesc1":
            "sales_group_desc",

        # Location
        "Country":
            "country",

        "City":
            "city",

        "Region":
            "region",

        # Document
        "DocumentNumber":
            "document_number",

        "Lineitem":
            "line_item",

        "BillingDoc":
            "billing_doc",

        "DebitCredit":
            "debitcredit",

        "DocumentType":
            "document_type",

        "SpecialGLind":
            "special_gl_ind",

        # Payment
        "PaytTerms":
            "payment_terms",

        "PaymentDays":
            "payment_days",

        "Reference":
            "reference",

        "Assignment":
            "assignment",

        # Currency
        "DocCurrency":
            "currency",

        # Text
        "Text":
            "text",

        # GL
        "ReconAC":
            "reconac"
    }

    # ---------------------------------------------------
    # FLOAT FIELD MAP
    # ---------------------------------------------------

    float_fields = {

        "AmountinLC":
            "amount_in_lc",

        "AmountinDC":
            "amount_in_dc",

        "ExchangeRate":
            "exchange_rate",

        "DueAmt":
            "due_amt",

        "NondueAmt":
            "non_due_amt"
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
                "FR Account Receivable Entry"
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

            doc.currency = (
                row.get("DocCurrency")
                or "INR"
            )

            doc.report_type = (
                "Yearly"
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
            if doc.special_gl_ind:

                doc.nature = (
                    "Advance"
                )

                doc.tb_nature = (
                    "Advance"
                )

            else:

                doc.nature = (
                    "Receivable"
                )

                doc.tb_nature = (
                    "Receivable"
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