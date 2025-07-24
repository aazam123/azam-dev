// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("FR Particular", {
	setup(frm) {
		frm.set_query('schedule', function() {
			return {
				filters: {
                    'is_schedule': 1,
                    'company': frm.doc.company
                }
			};
		});
	}
});

