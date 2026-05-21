frappe.listview_settings['FR Sales Register'] = {

    onload(listview) {

        listview.page.add_inner_button(
            'Import From Sync SAP',
            function () {

                let d = new frappe.ui.Dialog({

                    title: 'Import Sales Register',

                    fields: [

                        {
                            label: 'Sync SAP Document',
                            fieldname: 'sync_sap',
                            fieldtype: 'Link',
                            options: 'Sync SAP',
                            reqd: 1,

                            get_query() {
                                return {
                                    filters: {
                                        document_type: 'Sales Register'
                                    }
                                };
                            }
                        },

                        {
                            label: 'Fiscal Year',
                            fieldname: 'fiscal_year',
                            fieldtype: 'Link',
                            options: 'Fiscal Year',
                            reqd: 1
                        }
                    ],

                    primary_action_label: 'Import',

                    primary_action(values) {

                        frappe.call({

                            method: 'financial_report_tool.financial_report_tool.doctype.fr_sales_register.fr_sales_register.import_from_sync_sap',

                            args: {
                                sync_sap_doc: values.sync_sap,
                                fiscal_year: values.fiscal_year
                            },

                            freeze: true,
                            freeze_message:
                                'Importing Sales Register...',

                            callback(r) {

                                if (r.message) {

                                    frappe.msgprint({
                                        title: 'Success',
                                        indicator: 'green',
                                        message: r.message
                                    });

                                    d.hide();
                                    listview.refresh();
                                }
                            }
                        });
                    }
                });

                d.show();
            }
        );
    }
};