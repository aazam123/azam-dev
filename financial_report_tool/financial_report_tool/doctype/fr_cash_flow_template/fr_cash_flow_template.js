// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("FR Cash Flow Template", {
	refresh(frm) {
        frm.set_query('account', 'cash_flow_template_details', function() {
            return {
                filters: {
                    "template_type": "Cash Flow",
                    'company': frm.doc.company
                }
            };
        });
	},
});
