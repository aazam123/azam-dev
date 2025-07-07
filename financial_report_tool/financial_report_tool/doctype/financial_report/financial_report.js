// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Financial Report", {
	financial_report_template(frm) {
        frappe.call({
            method: 'get_financial_report_template',
            doc: frm.doc,
            callback: function(rsp){
                frm.refresh_field('financial_report_details')
            }
        })
	},
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button("Show Report", function () {
                const print_format = "Financial Report";

                const print_url = `/printview?doctype=Financial Report&name=${frm.doc.name}&format=${print_format}&no_letterhead=0`;

                window.open(print_url, '_blank');
            });
        }
    }
});

frappe.ui.form.on("Financial Report Details", {
	section_type(frm) {
        let row = locals[cdt][cdn];

		if(row.section_type == "Consolidation Note"){
			frappe.model.set_value(cdt, cdn, "doctype_name", "FR Section");
		} else if(row.section_type == "Profit & Loss"){
			frappe.model.set_value(cdt, cdn, "doctype_name", "Profit And Loss Template");
		} else if(row.section_type == "Balance Sheet"){
			frappe.model.set_value(cdt, cdn, "doctype_name", "Balance Sheet Template");
		} else if(row.section_type == "Cash Flow"){
			frappe.model.set_value(cdt, cdn, "doctype_name", "Cash Flow Template");
		} else if(row.section_type == "Equity"){
			frappe.model.set_value(cdt, cdn, "doctype_name", "Equity Template");
		}

		frm.refresh_field('financial_report_details');
	},
});