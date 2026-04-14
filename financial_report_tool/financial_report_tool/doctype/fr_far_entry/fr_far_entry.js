// Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("FR FAR Entry", {
	fiscal_year(frm) {
        frm.call({
            method: "get_previous_fiscal_year",
            doc: frm.doc,
            args: {
                fiscal_year: frm.doc.fiscal_year
            },
            callback: function(r) {
                if (r.message) {
                    frm.set_value("previous_fiscal_year", r.message);
                    frm.call({
                        method: "get_previous_fiscal_year",
                       doc: frm.doc,
                        args: {
                            fiscal_year: r.message
                        },
                        callback: function(r) {
                            if (r.message) {
                                frm.set_value("pre_previous_year", r.message);
                            }
                        } 
                    });
                }
            }
        });
	},
    process_calculation(frm) {
        if (!frm.doc.fiscal_year) {
            frappe.msgprint("Please select a fiscal year before processing the calculation.");
            return;
        }

        if (!frm.doc.company) {
            frappe.msgprint("Please select a company before processing the calculation.");
            return;
        }

        frappe.call({
            method: "process_calculation",
            doc: frm.doc,
            callback: function(r) {
                if (r.message) {
                    frm.refresh();
                    frappe.msgprint("Calculation processed successfully.");
                }
            }
        });
    }
});
