// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("FR Trial Balance Entry", {
    onload: function(frm) {
        set_gl_account_filter(frm);
    },
    company: function(frm) {
        set_gl_account_filter(frm);
    }
});

function set_gl_account_filter(frm) {
    frm.set_query("gl_account", function() {
        if (frm.doc.company) {
            return {
                filters: {
                    company: frm.doc.company
                }
            };
        }
    });
}