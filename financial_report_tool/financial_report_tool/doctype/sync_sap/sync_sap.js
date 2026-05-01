// Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sync SAP", {
	refresh(frm) {
		show_naming_preview(frm);
	},
	document_type(frm) {
		show_naming_preview(frm);
	},
});

function show_naming_preview(frm) {
	if (frm.doc.__islocal && frm.doc.document_type) {
		frm.set_intro(
			__("Naming Series: <b>{0}-####</b> (e.g. {0}-0001)", [frm.doc.document_type]),
			"blue"
		);
	} else {
		frm.set_intro("");
	}
}
