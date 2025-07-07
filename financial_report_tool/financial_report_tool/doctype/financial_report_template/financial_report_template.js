// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Financial Report Template", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on("Financial Report Template Details", {
	section_type(frm, cdt, cdn) {
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

		frm.refresh_field('financial_report_template_details');
	}
});


// frappe.ui.form.on("Financial Report Template Details", {
// 	section: function(frm, cdt, cdn) {
// 		let row = locals[cdt][cdn];
// 		if (row.doctype_name) {
// 			frappe.meta.get_docfield("Financial Report Template Details", "section", frm.doc.name).options = row.doctype_name;
// 		}
// 	}
// });
