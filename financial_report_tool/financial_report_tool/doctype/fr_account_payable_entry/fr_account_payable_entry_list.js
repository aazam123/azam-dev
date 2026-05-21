frappe.listview_settings["FR Account Payable Entry"] = {

    onload(listview) {

        listview.page.add_inner_button(
            "Import From Sync SAP",

            function () {

                const dialog = new frappe.ui.Dialog({

                    title: "Import AP Entries",

                    fields: [

                        {
                            label: "Sync SAP Document",
                            fieldname: "sync_sap_doc",
                            fieldtype: "Link",
                            options: "Sync SAP",
                            reqd: 1,

                            get_query() {

                                return {
                                    filters: {
                                        document_type:
                                            "Account Payable Entry"
                                    }
                                };
                            }
                        },

                        {
                            label: "Fiscal Year",
                            fieldname: "fiscal_year",
                            fieldtype: "Link",
                            options: "Fiscal Year",
                            reqd: 1
                        }
                    ],

                    primary_action_label: "Import",

                    primary_action(values) {

                        frappe.call({

                            method:
                                "financial_report_tool.financial_report_tool.doctype.fr_account_payable_entry.fr_account_payable_entry.import_from_sync_sap",

                            args: {
                                sync_sap_doc:
                                    values.sync_sap_doc,

                                fiscal_year:
                                    values.fiscal_year
                            },

                            freeze: true,

                            freeze_message:
                                "Importing AP Entries...",

                            callback(r) {

                                if (r.message) {

                                    frappe.msgprint(
                                        r.message
                                    );

                                    listview.refresh();
                                }

                                dialog.hide();
                            }
                        });
                    }
                });

                dialog.show();
            }
        );
    }
};