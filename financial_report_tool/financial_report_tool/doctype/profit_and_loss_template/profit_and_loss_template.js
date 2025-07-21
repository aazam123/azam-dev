// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt


frappe.ui.form.on('Profit And Loss Template Details', {
    account: function(frm, cdt, cdn) {
        update_note_numbers(frm);
    },
    profit_and_loss_template_details_add: function(frm, cdt, cdn) {
        update_note_numbers(frm);
    },
    profit_and_loss_template_details_remove: function(frm, cdt, cdn) {
        update_note_numbers(frm);
    },
    profit_and_loss_template_details_move: function(frm, cdt, cdn) {
        update_note_numbers(frm);
    },
    has_note_no: function(frm, cdt, cdn) {
        update_note_numbers(frm);
    }
});

function update_note_numbers(frm) {
    let details = frm.doc.profit_and_loss_template_details || [];
    let has_note = details.some(row => row.has_note_no);
    let start = has_note ? 4 : 1;
    let note_no = start;

    details.forEach((row) => {
        if (row.has_note_no) {
            frappe.model.set_value(row.doctype, row.name, 'note', note_no);
            note_no++;
        } else {
            frappe.model.set_value(row.doctype, row.name, 'note', null);
        }
    });
}