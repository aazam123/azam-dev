// Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("FR Corporate Social Responsibliity Master", {
	refresh(frm) {
		if (frm.doc.calculation_details_data) {
			frm.fields_dict.calculation_details.$wrapper.html(frm.doc.calculation_details_data);
		}
	},
});
