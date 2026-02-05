// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["GL Account Group Report"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company"),
            "reqd": 1
        },
        {
            "fieldname": "fiscal_year",
            "label": __("Fiscal Year"),
            "fieldtype": "Link",
            "options": "Fiscal Year",
            "default": frappe.defaults.get_user_default("fiscal_year"),
            "reqd": 1
        },
        {
            "fieldname": "month",
            "label": __("Month"),
            "fieldtype": "Select",
            "options": "\nJanuary\nFebruary\nMarch\nApril\nMay\nJune\nJuly\nAugust\nSeptember\nOctober\nNovember\nDecember",
            "reqd": 1
        },
        {
            "fieldname": "report_type",
            "label": __("Report Type"),
            "fieldtype": "Select",
            "options": "\nMonthly\nYearly\nMIS",
            "reqd": 1
        },
        {
            fieldname: "primary_group",
            label: __("Primary Group"),
            fieldtype: "MultiSelectList",
            options: "Standalone Group",
            get_data: function(txt) {
                return frappe.db.get_link_options("Standalone Group", txt, {
                    disable: 0
                });
            }
        },
        {
            fieldname: "secondary_group",
            label: __("Secondary Group"),
            fieldtype: "MultiSelectList",
            options: "Standalone Group",
            get_data: function(txt) {
                return frappe.db.get_link_options("Standalone Group", txt, {
                    disable: 0
                });
            }
        },
        {
            "fieldname": "higher_secondary_group",
            "label": __("Higher Secondary Group"),
            "fieldtype": "MultiSelectList",
            "options": "Standalone Group",
            get_data: function(txt) {
                return frappe.db.get_link_options("Standalone Group", txt, {
                    disable: 0
                });
            }
        }
    ]
};
