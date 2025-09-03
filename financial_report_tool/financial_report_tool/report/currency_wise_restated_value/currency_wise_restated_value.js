// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Currency Wise Restated Value"] = {
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
            "options": "Yearly\nMonthly",
            "reqd": 1
        },
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer"
        }
	]
};
