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
                                frm.reload_doc();
                            }
                        }
                    });
                });
            }
        });

        frm.add_custom_button(__('Sync SAP Data'), function () {
            frappe.call({
                method: "sync_sap_data",
                doc: frm.doc,
                callback: function (r) {
                    if (!r.exc && r.message) {
                        frappe.show_alert({
                            message: r.message.message || __("SAP data sync started in background…"),
                            indicator: "blue"
                        });
                        // Reload so the "Queued"/"Syncing" status shows; the
                        // realtime handler below auto-reloads on completion.
                        frm.reload_doc();
                    }
                }
            });
        });

        // Auto-reload when the background SAP sync finishes (mirrors the
        // Financial Report realtime pattern).
        frappe.realtime.off("sap_tb_sync_complete");
        frappe.realtime.on("sap_tb_sync_complete", (data) => {
            if (data.docname === frm.doc.name) {
                frm.reload_doc();
                if (data.status === "Completed") {
                    frappe.show_alert({ message: __("SAP data synced successfully!"), indicator: "green" });
                } else if (data.status === "Awaiting SAP") {
                    frappe.show_alert({ message: __("Request accepted by SAP. Waiting for SAP to push the trial balance…"), indicator: "orange" });
                } else if (data.status === "Failed") {
                    frappe.show_alert({ message: __("SAP sync failed. See 'Sync Error' on the form."), indicator: "red" });
                }
            }
        });
    },
    setup(frm) {
        frm.fields_dict["details"].grid.get_field("account").get_query = function (doc, cdt, cdn) {
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
