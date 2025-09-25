// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sync SAP Trial Balance", {
    refresh(frm) {
        let total_amount = frm.doc.total_amount || 0;
    
        frappe.db.get_single_value("FR Financial Settings", "sap_threshold_amount").then(setting_amount => {
            if (frm.doc.total_amount <= setting_amount && frm.doc.tb_created == 0) {
                frm.add_custom_button(__('Create TB'), function () {
                    frappe.call({
                        method: "your_app.your_module.doctype.sync_sap_trial_balance.sync_sap_trial_balance.create_trail_balance",
                        doc: frm.doc,
                        callback: function (r) {
                            if (!r.exc) {
                                frappe.msgprint("Trial Balance created successfully!");
                                frm.set_value('tb_created', 1);
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

