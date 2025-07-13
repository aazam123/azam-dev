// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on('BalanceSheetTemplate', {
    refresh: function(frm) {
        update_note_numbers(frm);
    }
});

frappe.ui.form.on('Balance Sheet Template Details', {
    balance_sheet_template_details_add: function(frm, cdt, cdn) {
        update_note_numbers(frm);
    },
    balance_sheet_template_details_remove: function(frm, cdt, cdn) {
        update_note_numbers(frm);
    },
    balance_sheet_template_details_move: function(frm, cdt, cdn) {
        update_note_numbers(frm);
    },
    has_note_no: function(frm, cdt, cdn) {
        update_note_numbers(frm);
    }
});

function update_note_numbers(frm) {
    let start = 1;
    let details = frm.doc.balance_sheet_template_details || [];
    // Check if any row has has_note_no checked
    let has_note = details.some(row => row.has_note_no);
    if (has_note) {
        start = 4;
    }
    details.forEach((row, idx) => {
        frappe.model.set_value(row.doctype, row.name, 'note', start + idx);
    });
}
