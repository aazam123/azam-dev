// Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Company Hierarchy", {
	fetch_all_companies(frm) {
		frm.call({
			method: 'fetch_all_companies',
			doc: frm.doc,
			freeze: true,
			freeze_message: __("Fetching companies..."),
			callback: function() {
				frm.refresh_field("company_hierarchy_relation");
				frm.dirty();
				let count = (frm.doc.company_hierarchy_relation || []).length;
				frappe.msgprint(__("{0} companies classified.", [count]));
			}
		});
	},
});
