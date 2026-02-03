// Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("FR Repayment", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button("Adjustment", () => {
				open_adjustment_dialog(frm);
			});
		}
	},
});

function open_adjustment_dialog(frm) {
	let d = new frappe.ui.Dialog({
		title: "Repayment Adjustment",
		fields: [
			{
				label: "Posting Date", fieldname: "posting_date", fieldtype: "Date", reqd: 0
			},
			{
				label: "Amount",fieldname: "amount",fieldtype: "Currency",reqd: 0
			}

		],
		primary_action_label: "Apply",
		primary_action(values) {

			d.hide();

			apply_adjustment(frm, values);
		}
	});

	d.show();
}

function apply_adjustment(frm, values) {
	frappe.call({
		method: "apply_adjustment",
        doc: frm.doc,
		args: {
			posting_date: values.posting_date,
			amount: values.amount
		},

		callback(r) {
			if (!r.exc) {
				frappe.msgprint("Adjustment Applied Successfully");
				frm.reload_doc();
			}
		}
	});
}

