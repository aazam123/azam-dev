// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sync SAP Trial Balance", {
    refresh(frm) {
        let total_amount = frm.doc.total_amount || 0;

        frappe.db.get_single_value("FR Financial Settings", "sap_threshold_amount").then(setting_amount => {
            if (total_amount <= setting_amount) {
                frm.add_custom_button(__('Create TB'), function () {
                    frappe.call({
                        method: "create_trail_balance",
                        doc: frm.doc,
                        callback: function (r) {
                            if (!r.exc) {
                                frappe.msgprint("Trial Balance created successfully!");
                                frm.reload_doc();
                            }
                        }
                    });
                });
            }
        });
    },
    setup(frm) {
        frm.fields_dict["details"].grid.get_field("account").get_query = function(doc, cdt, cdn) {
            return {
                filters: {
                    company: frm.doc.company,
                    is_group: 0,
                    disabled: 0
                }
            };
        };
    }
});

