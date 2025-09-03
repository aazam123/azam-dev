// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Vendor Ageing Report"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1
        },
		{
            "fieldname": "fiscal_year",
            "label": __("Fiscal Year"),
            "fieldtype": "Link",
            "options": "Fiscal Year",
            "reqd": 1
        },
        {
            "fieldname": "report_type",
            "label": __("Report Type"),
            "fieldtype": "Select",
            "options": ["Yearly", "Monthly"],
            "reqd": 1
        },
        {
            "fieldname": "supplier",
            "label": __("Supplier"),
            "fieldtype": "Link",
            "options": "Supplier"
        },
    ]
};
