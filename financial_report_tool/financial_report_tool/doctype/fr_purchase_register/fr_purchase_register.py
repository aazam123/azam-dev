# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
from frappe.utils import (
    flt,
    cint,
    getdate
)



class FRPurchaseRegister(Document):
	def validate(self):
		if self.country == "India":
			self.nature = "Domestic"
		else:
			self.nature = "Foreign"

		settings = frappe.db.exists("FR RPT Master", self.company)
		if not settings:
			frappe.throw("Please set the Related and Internal Customer List in FR RPT Master")

		settings = frappe.get_doc("FR RPT Master", self.company)
		related_supplier = {row.supplier_code for row in settings.related_party_supplier}
		internal_supplier = {row.supplier_code for row in settings.internal_supplier}

		if self.invoicing_party in related_supplier:
			self.party_type = "Related Party"
		elif self.invoicing_party in internal_supplier:
			self.party_type = "Branch Transfer"
		else:
			self.party_type = "Unrelated Party"



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
        "FR Purchase Register",
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

        "InvDocNo":
            "invoice_document_no",

        "PurchaseOrder":
            "purchase_order",

        "PurchaseOrdItm":
            "purchase_order_item",

        "PurchaseOrdType":
            "purchase_order_type",

        "PurchaseOrdType_t":
            "purchase_order_type_description",

        "AccDoc":
            "accounting_document",

        "AccYear":
            "accounting_year",

        "DocumentType":
            "document_type",

        "TransactnType":
            "transaction_type",

        "Reference":
            "reference",

        "Currency":
            "currency",

        "InvoicingPty":
            "invoicing_party",

        "VendorName":
            "vendor_name",

        "City":
            "city",

        "Region":
            "region",

        "Country":
            "country",

        "CSTNo":
            "cst_no",

        "VATNo":
            "vat_no",

        "GSTNNo":
            "gstn_no",

        "VendorType":
            "vendor_type",

        "VendorClass":
            "vendor_class",

        "MIROStatus":
            "miro_status",

        "Reversedby":
            "reversed_by",

        "ReversedYear":
            "reversed_year",

        "Taxcode":
            "tax_code",

        "PaytTerms":
            "payment_terms",

        "PayTermDesc":
            "payment_term_description",

        "Incoterms":
            "incoterms",

        "Incoterms2":
            "incoterms_2",

        "Taxcode":
            "tax_code",

        "PurchasingOrg":
            "purchasing_organization",

        "Material":
            "material",

        "MaterialGroup":
            "material_group",

        "MaterialGroup_t":
            "material_group_description",

        "MaterialGroup_l":
            "material_group_description_2",

        "MaterialType":
            "material_type",

        "Mattypedescr":
            "material_type_description",

        "Division":
            "division",

        "Division_t":
            "division_text",

        "PurchasingGroup":
            "purchasing_group",

        "PurGroupDesc":
            "purchasing_group_description",

        "ItemText":
            "item_text",

        "Plant":
            "plant",

        "PlantRegion":
            "plant_region",

        "GLAccount":
            "gl_account_no",

        "GLLongName":
            "gl_long_name",

        "OrderUnit":
            "order_unit",

        "BaseUnit":
            "base_unit",

        "HSNSACCode":
            "hsnsac_code",

        "ReferenceDoc":
            "reference_document",

        "Yearcurperiod":
            "year_current_period",

        "RefDocItem":
            "reference_document_item",

        "Text":
            "text",

        "CreatedBy":
            "created_by",

        "PRNo":
            "pr_no",

        "PRItem":
            "pr_item",

        "RequesterNamePR":
            "requester_name_pr",

        "CostCenter":
            "cost_center",

        "CCName":
            "cc_name",

        "CCLongName":
            "cc_long_name",

        "PersonResp":
            "person_responsible",

        "Department":
            "department"
    }

    # ---------------------------------------------------
    # FLOAT FIELD MAP
    # ---------------------------------------------------

    float_fields = {

        "Item":
            "item",

        "Exchangerate":
            "exchange_rate",

        "QtyPOUom":
            "qty_pouom",

        "BaseAmount":
            "base_amount",

        "AddCustmDuty":
            "additional_customs_duty",

        "LandingChrg":
            "landing_charge",

        "Insurance":
            "insurance",

        "F&FAirSea":
            "fandf_air_sea",

        "LocalFreight":
            "local_freight",

        "AgencyChrg":
            "agency_charge",

        "CHAMiscellaneous":
            "cha_miscellaneous",

        "VendMiscellaneous":
            "vendor_miscellaneous",

        "Pack&Handl":
            "packing_and_handling_charges",

        "ServcChrgCHA":
            "service_chargecha",

        "ServcChrgDest":
            "service_chargedest",

        "Surcharge":
            "surcharge",

        "DevChrg":
            "development_charges",

        "ErecInstTrain":
            "erecinsttrain",

        "Miscellaneous":
            "miscellaneous",

        "Octroi":
            "octroi",

        "TotalExpenses":
            "total_expenses",

        "CustmDuty":
            "custom_duty",

        "CESSBCD+CVD":
            "cessbcdcvd",

        "HealthCessBCD+CVD":
            "hcessbcdcvd",

        "gst_BaseAmount":
            "taxable_amount",

        "CGST":
            "cgst",

        "CGSTNCr":
            "cgstncr",

        "CGSTay":
            "cgstpay",

        "SGST":
            "sgst",

        "SGSTNCr":
            "sgstncr",

        "SGSTay":
            "sgstpay",

        "IGST":
            "igst",

        "IGSTNCr":
            "igstncr",

        "IGSTay":
            "igstpay",

        "UGST":
            "ugst",

        "UGSTNCr":
            "ugstncr",

        "SocialWelfareSC":
            "social_welfare_sc",

        "SocialWelfareSC_per":
            "social_welfare_per",

        "HealthCess":
            "health_cess",

        "HealtHealthCessPer":
            "health_cess_per",

        "GrossAmount":
            "gross_amount",

        "Assessablevalue":
            "assessable_value",

        "Assessablevalue1":
            "assessable_value_boe",

        "Assessablevalue2":
            "valueigst",

        "PurchaseAmount":
            "purchase_amount",

        "Check":
            "check"
    }

    # ---------------------------------------------------
    # DATE FIELD MAP
    # ---------------------------------------------------

    date_fields = {

        "DocumentDate":
            "document_date",

        "PostingDate":
            "posting_date",

        "PostingDate_mkpf":
            "migo_date",

        "PODate":
            "po_date",

        "PRDate":
            "pr_date"
    }

    # ---------------------------------------------------
    # COUNTERS
    # ---------------------------------------------------

    created = 0
    skipped = 0
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
                "FR Purchase Register"
            )

            # ---------------------------------------------------
            # REQUIRED
            # ---------------------------------------------------

            doc.company = company

            doc.company_code = (
                company_code
            )

            doc.fiscal_year = (
                fiscal_year
            )

            doc.sync_sap_id = (
                sync_doc.name
            )

            doc.currency = (
                row.get("Currency")
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

            if (
                str(row.get("Country"))
                .lower()
                in ["india", "in"]
            ):

                doc.nature = (
                    "Domestic"
                )

            else:

                doc.nature = (
                    "Foreign"
                )

            doc.party_type = (
                "Unrelated Party"
            )

            doc.rpt = "No"

            # ---------------------------------------------------
            # INSERT
            # ---------------------------------------------------

            doc.insert(
                ignore_permissions=True
            )

            created += 1

        except Exception:

            skipped += 1

            errors.append(
                f"""
                Row: {index}

                Invoice Document:
                {row.get('InvDocNo')}

                Error:
                {frappe.get_traceback()}
                """
            )

    # ---------------------------------------------------
    # COMMIT
    # ---------------------------------------------------

    frappe.db.commit()

    # ---------------------------------------------------
    # LOG ERRORS
    # ---------------------------------------------------

    if errors:

        error_log = "\n\n".join(
            errors
        )

        frappe.log_error(
            title=
                "FR Purchase Register Import Errors",

            message=error_log
        )

    # ---------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------

    message = (
        f"{created} entries created "
        f"successfully and "
        f"{skipped} skipped"
    )

    if errors:

        message += (
            "<br><br>"
            "Check Error Log "
            "for skipped reasons."
        )

    return message


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