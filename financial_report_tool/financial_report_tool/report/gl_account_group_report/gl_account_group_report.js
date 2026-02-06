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
            "reqd": 1,
            "default": "Monthly"
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
    ],

    get_datatable_options(options) {
        return Object.assign(options, {
            checkboxColumn: true
        });
    },

    onload(report) {
        report.page.add_inner_button(__("Update Grouping"), function() {
            let checked_items = report.get_checked_items();
            if (!checked_items || checked_items.length === 0) {
                frappe.msgprint(__("Please select at least one row to update grouping."));
                return;
            }

            let filters = report.get_values();
            if (!filters.company || !filters.report_type) {
                frappe.msgprint(__("Company and Report Type filters are required."));
                return;
            }

            let d = new frappe.ui.Dialog({
                title: __("Update Grouping for {0} Account(s)", [checked_items.length]),
                fields: [
                    {
                        fieldname: "primary_group",
                        fieldtype: "Link",
                        label: __("Primary Group"),
                        options: "Standalone Group",
                        description: __("Leave blank to keep existing value")
                    },
                    {
                        fieldname: "secondary_group",
                        fieldtype: "Link",
                        label: __("Secondary Group"),
                        options: "Standalone Group",
                        description: __("Leave blank to keep existing value")
                    },
                    {
                        fieldname: "higher_secondary_group",
                        fieldtype: "Link",
                        label: __("Higher Secondary Group"),
                        options: "Standalone Group",
                        description: __("Leave blank to keep existing value")
                    }
                ],
                primary_action_label: __("Update"),
                primary_action(values) {
                    if (!values.primary_group && !values.secondary_group && !values.higher_secondary_group) {
                        frappe.msgprint(__("Please set at least one group field to update."));
                        return;
                    }

                    let gl_accounts = checked_items.map(row => row.gl_account);

                    frappe.call({
                        method: "financial_report_tool.api.bulk_update_gl_group_mappings",
                        args: {
                            gl_accounts: gl_accounts,
                            company: filters.company,
                            report_type: filters.report_type,
                            primary_group: values.primary_group || "",
                            secondary_group: values.secondary_group || "",
                            higher_secondary_group: values.higher_secondary_group || ""
                        },
                        freeze: true,
                        freeze_message: __("Updating grouping..."),
                        callback(r) {
                            if (r.message) {
                                let updated = r.message.updated || [];
                                let errors = r.message.errors || [];

                                if (updated.length > 0) {
                                    frappe.show_alert({
                                        message: __("{0} account(s) updated successfully", [updated.length]),
                                        indicator: "green"
                                    });
                                }
                                if (errors.length > 0) {
                                    frappe.msgprint({
                                        title: __("Errors"),
                                        message: errors.map(e => `${e.gl_account}: ${e.error}`).join("<br>"),
                                        indicator: "orange"
                                    });
                                }

                                d.hide();
                                report.refresh();
                            }
                        }
                    });
                }
            });
            d.show();
        });
    }
};
