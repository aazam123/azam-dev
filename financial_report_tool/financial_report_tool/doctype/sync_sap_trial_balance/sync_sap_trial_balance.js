frappe.ui.form.on("Sync SAP Trial Balance", {
    refresh(frm) {
        frappe.db.get_single_value("FR Financial Settings", "sap_threshold_amount").then(setting_amount => {
            if ((frm.doc.total_amount || 0) <= setting_amount && frm.doc.tb_created == 0) {
                frm.add_custom_button(__('Create TB'), function () {
                    frappe.call({
                        method: "create_trail_balance",
                        doc: frm.doc,
                        callback: function (r) {
                            if (!r.exc) {
                                frappe.msgprint("Trial Balance created successfully!");
                                frm.reload_doc(); // Optional: reload document to reflect changes from server
                            }
                        }
                    });
                });
            }
        });
    },


    setup(frm) {
        // Set query for child table field "account"
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
