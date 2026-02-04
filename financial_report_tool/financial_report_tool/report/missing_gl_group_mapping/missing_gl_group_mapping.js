// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["Missing GL Group Mapping"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1,
            "default": frappe.defaults.get_user_default("Company")
        },
        {
            "fieldname": "report_type",
            "label": __("Report Type"),
            "fieldtype": "Select",
            "options": "\nMonthly\nYearly\nMIS",
            "reqd": 1,
        }
    ],

    "get_datatable_options": function(options) {
        return Object.assign(options, {
            checkboxColumn: true,
            inlineFilters: true,
        });
    },

    onload: function(report) {
        // Add button to create mappings for selected rows
        report.page.add_inner_button(__("Create Mappings for Selected"), function() {
            create_mappings_for_selected(report);
        }, __("Actions"));

        // Add button to create all mappings
        report.page.add_inner_button(__("Create All Filled Mappings"), function() {
            create_all_filled_mappings(report);
        }, __("Actions"));

        // Add button to apply same grouping to selected rows
        report.page.add_inner_button(__("Apply Grouping to Selected"), function() {
            apply_grouping_to_selected(report);
        }, __("Actions"));
    }
};

function create_mappings_for_selected(report) {
    let checked_rows = report.datatable.rowmanager.getCheckedRows();
    let checked_row_indexes = checked_rows.map(i => parseInt(i));

    if (checked_row_indexes.length === 0) {
        frappe.msgprint(__("Please select at least one GL Account"));
        return;
    }

    let company = frappe.query_report.get_filter_value("company");
    let report_type = frappe.query_report.get_filter_value("report_type");

    if (!company || !report_type) {
        frappe.msgprint(__("Please select Company and Report Type"));
        return;
    }

    // Collect mappings to create
    let mappings = [];
    let incomplete = [];

    checked_row_indexes.forEach(function(idx) {
        let row_data = report.data[idx];
        if (row_data) {
            if (row_data.primary_group && row_data.secondary_group) {
                mappings.push({
                    gl_account: row_data.gl_account,
                    primary_group: row_data.primary_group,
                    secondary_group: row_data.secondary_group,
                    higher_secondary_group: row_data.higher_secondary_group || null
                });
            } else {
                incomplete.push(row_data.gl_account);
            }
        }
    });

    if (incomplete.length > 0) {
        frappe.msgprint(__(`The following GL Accounts have incomplete grouping: ${incomplete.join(", ")}`));
    }

    if (mappings.length === 0) {
        frappe.msgprint(__("No complete mappings to create. Please fill Primary Group and Secondary Group."));
        return;
    }

    frappe.confirm(
        __(`Create ${mappings.length} GL Group Mapping(s)?`),
        function() {
            create_bulk_mappings(mappings, company, report_type);
        }
    );
}

function create_all_filled_mappings(report) {
    let company = frappe.query_report.get_filter_value("company");
    let report_type = frappe.query_report.get_filter_value("report_type");

    if (!company || !report_type) {
        frappe.msgprint(__("Please select Company and Report Type"));
        return;
    }

    // Collect all rows with complete mappings
    let mappings = [];

    report.data.forEach(function(row_data) {
        if (row_data && row_data.primary_group && row_data.secondary_group) {
            mappings.push({
                gl_account: row_data.gl_account,
                primary_group: row_data.primary_group,
                secondary_group: row_data.secondary_group,
                higher_secondary_group: row_data.higher_secondary_group || null
            });
        }
    });

    if (mappings.length === 0) {
        frappe.msgprint(__("No complete mappings to create. Please fill Primary Group and Secondary Group for at least one row."));
        return;
    }

    frappe.confirm(
        __(`Create ${mappings.length} GL Group Mapping(s)?`),
        function() {
            create_bulk_mappings(mappings, company, report_type);
        }
    );
}

function create_bulk_mappings(mappings, company, report_type) {
    frappe.call({
        method: "financial_report_tool.financial_report_tool.report.missing_gl_group_mapping.missing_gl_group_mapping.create_bulk_gl_group_mappings",
        args: {
            mappings: mappings,
            company: company,
            report_type: report_type
        },
        freeze: true,
        freeze_message: __("Creating GL Group Mappings..."),
        callback: function(r) {
            if (r.message) {
                let created = r.message.created || [];
                let errors = r.message.errors || [];

                let msg = "";
                if (created.length > 0) {
                    msg += __(`Successfully created ${created.length} GL Group Mapping(s).`) + "<br>";
                }
                if (errors.length > 0) {
                    msg += __(`Failed to create ${errors.length} mapping(s):`) + "<br>";
                    errors.forEach(function(err) {
                        msg += `- ${err.gl_account}: ${err.error}<br>`;
                    });
                }

                frappe.msgprint(msg);
                frappe.query_report.refresh();
            }
        }
    });
}

function apply_grouping_to_selected(report) {
    let checked_rows = report.datatable.rowmanager.getCheckedRows();
    let checked_row_indexes = checked_rows.map(i => parseInt(i));

    if (checked_row_indexes.length === 0) {
        frappe.msgprint(__("Please select at least one GL Account"));
        return;
    }

    // Show dialog to select grouping
    let d = new frappe.ui.Dialog({
        title: __("Apply Grouping to Selected Rows"),
        fields: [
            {
                fieldname: "primary_group",
                label: __("Primary Group"),
                fieldtype: "Link",
                options: "Standalone Group",
                reqd: 1,
                get_query: function() {
                    return {
                        filters: {
                            "is_primary_group": 1,
                            "disable": 0
                        }
                    };
                }
            },
            {
                fieldname: "secondary_group",
                label: __("Secondary Group"),
                fieldtype: "Link",
                options: "Standalone Group",
                reqd: 1,
                get_query: function() {
                    let primary = d.get_value("primary_group");
                    return {
                        filters: {
                            "is_group": 0,
                            "is_primary_group": 0,
                            "disable": 0,
                            "parent_standalone_group": primary || undefined
                        }
                    };
                }
            },
            {
                fieldname: "higher_secondary_group",
                label: __("Higher Secondary Group"),
                fieldtype: "Link",
                options: "Standalone Group",
                get_query: function() {
                    return {
                        filters: {
                            "disable": 0
                        }
                    };
                }
            }
        ],
        primary_action_label: __("Apply"),
        primary_action: function(values) {
            // Apply values to selected rows
            checked_row_indexes.forEach(function(idx) {
                if (report.data[idx]) {
                    report.data[idx].primary_group = values.primary_group;
                    report.data[idx].secondary_group = values.secondary_group;
                    report.data[idx].higher_secondary_group = values.higher_secondary_group || '';
                }
            });

            // Refresh the datatable to show updated values
            frappe.query_report.refresh();
            d.hide();
            frappe.msgprint(__(`Applied grouping to ${checked_row_indexes.length} row(s). Click "Create Mappings for Selected" to save.`));
        }
    });

    d.show();
}
