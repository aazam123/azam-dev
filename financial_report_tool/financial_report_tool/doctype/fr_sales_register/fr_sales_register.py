# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FRSalesRegister(Document):
	def validate(self):
		if self.ship_to_country == "IN":
			self.nature = "Domestic"
		else:
			self.nature = "Foreign"

		settings = frappe.db.exists("FR RPT Master", self.company)
		if not settings:
			frappe.throw("Please set the Related and Internal Customer List in FR RPT Master")

		settings = frappe.get_doc("FR RPT Master", self.company)
		related_customers = {row.customer_code for row in settings.related_customer_list}
		internal_customers = {row.customer_code for row in settings.internal_customer_list}

		if self.ship_to_party in related_customers:
			self.party_type = "Related Party"
		elif self.ship_to_party in internal_customers:
			self.party_type = "Branch Transfer"
		else:
			self.party_type = "Unrelated Party"


import frappe
import json

from frappe.utils import flt, getdate


@frappe.whitelist()
def import_from_sync_sap(sync_sap_doc, fiscal_year):

    # ---------------------------------------------------
    # GET SYNC SAP DOC
    # ---------------------------------------------------

    sync_doc = frappe.get_doc(
        "Sync SAP",
        sync_sap_doc
    )

    # ---------------------------------------------------
    # VALIDATIONS
    # ---------------------------------------------------

    if not sync_doc.json_data:
        frappe.throw("JSON Data not found in Sync SAP")

    # Prevent duplicate import
    already_imported = frappe.db.exists(
        "FR Sales Register",
        {
            "sync_sap_id": sync_doc.name
        }
    )

    if already_imported:

        frappe.throw(
            f"Entries already imported from "
            f"Sync SAP: {sync_doc.name}"
        )

    # ---------------------------------------------------
    # LOAD JSON
    # ---------------------------------------------------

    try:

        data = json.loads(sync_doc.json_data)

    except Exception:

        frappe.throw("Invalid JSON Data")

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
        "Plant": "plant",
        "PlantRegion": "plant_region",
        "BillingDoc_vak": "sosto",
        "SOSTOType": "sosto_type",
        "SalesOrg": "sales_organization",
        "BillingType_tx": "bill_type_description",
        "BillingType": "billing_type",
        "BillingDoc": "billing_document",

        # Bill To
        "Payer": "bill_to",
        "PayerName": "bill_to_name",
        "PayerCity": "bill_to_city",
        "PayerGSTNNo": "bill_to_gstn_no",
        "Payercountry": "bill_to_country",
        "PayerRegion": "bill_to_region",

        # Ship To
        "ShiptoParty": "ship_to_party",
        "ShiptoPartyname": "ship_to_name",
        "ShiptoPartycity": "ship_to_city",
        "ShiptoPartygstn": "ship_to_gstn_no",
        "ShiptoPartycntry": "ship_to_country",
        "ShiptoPartyregn": "ship_to_region",

        # Item
        "Division": "division",
        "MaterialGroup": "material_group",
        "MaterialType": "material_type",
        "HSNSACCode": "hsnsac_code",
        "Batch": "batch",
        "Material": "material",
        "Description": "description",
        "DoCSTatus": "document_status",

        # Account
        "AccntDoc": "account_document",
        "ExciseInv": "excise_invoice",

        # Currency
        "DocCurrency": "document_currency",

        # GL
        "RevenueGL": "revenue_gl",
        "RevenueGLDesc": "revenue_gl_description",

        # Extra
        "ExportType": "export_type",
        "AAGMaterial": "aag_material",
        "AAGCustomer": "aag_customer",
        "FIStatus": "fi_status",
        "SOReference": "so_reference",
        "Returns": "returns",
        "Cancelled": "cancelled"
    }

    # ---------------------------------------------------
    # FLOAT FIELD MAP
    # ---------------------------------------------------

    float_fields = {

        "Rate": "rate",
        "Discount": "discount",
        "LuxCess": "luxury_cess",
        "Cess": "cess",
        "Billedqty": "billed_qty",
        "BaseAmt": "base_amount",
        "VolumeDisc": "volume_discount",
        "Freight": "freight",
        "RoundOff": "roundoff",
        "GrossAmt": "gross_amount",
        "NetAmt": "net_amount",
        "IGST": "igst",
        "CGST": "cgst",
        "SGST": "sgst",
        "UGST": "ugst",
        "TaxableAmt": "taxable_amount",
        "InvoiceValue": "invoice_value",
        "InvoiceValueinLC": "invoice_value_in_lc",
        "Revenue": "revenue",
        "CustomBED": "custom_bed",
        "CustomBaseamount": "custom_base_amount",
        "ExchRateaCustomerClassText":
            "exchange_rate_account"
    }

    # ---------------------------------------------------
    # DATE FIELD MAP
    # ---------------------------------------------------

    date_fields = {

        "SOSTODt": "sosto_date",
        "BillingDate": "billing_date",
        "Excdocdate": "excise_document_date",
        "DeliveryDt": "delivery_date"
    }

    # ---------------------------------------------------
    # COUNTERS
    # ---------------------------------------------------

    created = 0

    # ---------------------------------------------------
    # LOOP THROUGH JSON
    # ---------------------------------------------------

    for index, row in enumerate(data, start=1):

        try:

            # ---------------------------------------------------
            # COMPANY
            # ---------------------------------------------------

            custom_company_code = str(
                row.get("CompanyCode") or ""
            ).strip()

            company = company_map.get(
                custom_company_code
            )

            if not company:

                frappe.throw(
                    f"""
                    Company not found

                    Row:
                    {index}

                    Company Code:
                    {custom_company_code}
                    """
                )

            # ---------------------------------------------------
            # CREATE DOC
            # ---------------------------------------------------

            doc = frappe.new_doc(
                "FR Sales Register"
            )

            # ---------------------------------------------------
            # REQUIRED FIELDS
            # ---------------------------------------------------

            doc.company = company

            doc.company_code = (
                custom_company_code
            )

            doc.fiscal_year = fiscal_year

            doc.sync_sap_id = sync_doc.name

            doc.gst_no = (
                row.get("PayerGSTNNo")
                or "0"
            )

            doc.item = str(
                row.get("Item") or ""
            )

            doc.nature = "Foreign"

            doc.party_type = (
                "Unrelated Party"
            )

            # ---------------------------------------------------
            # NORMAL FIELDS
            # ---------------------------------------------------

            for json_key, fieldname in (
                field_map.items()
            ):

                setattr(
                    doc,
                    fieldname,
                    row.get(json_key)
                )

            # ---------------------------------------------------
            # FLOAT FIELDS
            # ---------------------------------------------------

            for json_key, fieldname in (
                float_fields.items()
            ):

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

            for json_key, fieldname in (
                date_fields.items()
            ):

                setattr(
                    doc,
                    fieldname,
                    get_valid_date(
                        row.get(json_key)
                    )
                )

            # ---------------------------------------------------
            # CALCULATED FIELDS
            # ---------------------------------------------------

            doc.tax_amount = (

                flt(doc.igst)
                + flt(doc.cgst)
                + flt(doc.sgst)
                + flt(doc.ugst)
                + flt(doc.cess)

            )

            doc.total_tax = (
                doc.tax_amount
            )

            doc.total = flt(
                doc.gross_amount
            )

            # ---------------------------------------------------
            # IGNORE LINK VALIDATION
            # ---------------------------------------------------

            doc.flags.ignore_links = True

            # ---------------------------------------------------
            # INSERT
            # ---------------------------------------------------

            doc.insert(
                ignore_permissions=True
            )

            created += 1

        except Exception:

            frappe.throw(
                f"""
                ERROR IN ROW:
                {index}

                TRACEBACK:

                {frappe.get_traceback()}
                """
            )

    # ---------------------------------------------------
    # COMMIT
    # ---------------------------------------------------

    frappe.db.commit()

    # ---------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------

    return (
        f"{created} entries created successfully"
    )


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