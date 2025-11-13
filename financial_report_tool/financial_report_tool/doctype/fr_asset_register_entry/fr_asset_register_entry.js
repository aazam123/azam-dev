// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("FR Asset Register Entry", {
	fiscal_year(frm) {
        calculate_days_in_current_year(frm);
	},
    ordinary_depreciation_start_date(frm){
        calculate_days_in_current_year(frm);
    },
    sales_date(frm){
        calculate_days_in_current_year(frm);
    }
});

function calculate_days_in_current_year(frm){
    if (!frm.doc.fiscal_year || !frm.doc.ordinary_depreciation_start_date) {
        frm.set_value("days_in_current_year", 0);
        return;
    }

    frm.call({
        method: "calculate_days_in_current_year",
        doc: frm.doc,
        callback: function(resp){
            if (resp.message) {
                frm.set_value("days_in_current_year", resp.message);
            }
        }
    });
}
