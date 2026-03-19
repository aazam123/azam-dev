// Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("FR RPT Entry", {
	fetch_companies_for_related_parties(frm) {
		if (!frm.doc.company) {
			frappe.msgprint(__("Please select a Company first."));
			return;
		}
		frappe.call({
			method: "financial_report_tool.financial_report_tool.doctype.fr_rpt_entry.fr_rpt_entry.fetch_companies_for_table",
			args: {
				company: frm.doc.company,
				table_type: "related_parties"
			},
			freeze: true,
			freeze_message: __("Fetching related parties..."),
			callback(r) {
				if (r.message && r.message.length) {
					frm.clear_table("names_of_replated");
					r.message.forEach(row => {
						let child = frm.add_child("names_of_replated");
						child.company = row.company;
						child.relation = row.relation;
					});
					frm.refresh_field("names_of_replated");
					frm.dirty();
					frappe.msgprint(__("{0} related parties fetched.", [r.message.length]));
				} else {
					frappe.msgprint(__("No related parties found for {0}.", [frm.doc.company]));
				}
			}
		});
	},

	calculate_transactions(frm) {
		if (!frm.doc.company || !frm.doc.fiscal_year) {
			frappe.msgprint(__("Please select Company and Fiscal Year first."));
			return;
		}
		if (!frm.doc.names_of_replated || !frm.doc.names_of_replated.length) {
			frappe.msgprint(__("Please fetch related parties first."));
			return;
		}
		frappe.call({
			method: "financial_report_tool.financial_report_tool.doctype.fr_rpt_entry.fr_rpt_entry.calculate_rpt_transactions",
			args: {
				company: frm.doc.company,
				fiscal_year: frm.doc.fiscal_year,
				fr_rpt_entry_name: frm.doc.name
			},
			freeze: true,
			freeze_message: __("Calculating RPT transactions..."),
			callback(r) {
				if (r.message && r.message.length) {
					frm.clear_table("rpt_transactions");
					r.message.forEach(row => {
						let child = frm.add_child("rpt_transactions");
						child.relation_type = row.relation_type;
						child.entry_type = row.entry_type;
						child.transaction_category = row.transaction_category;
						child.description = row.description;
						child.company_name = row.company_name;
						child.current_year_amount = row.current_year_amount;
						child.previous_year_amount = row.previous_year_amount;
					});
					frm.refresh_field("rpt_transactions");
					frm.dirty();
					frappe.msgprint(__("{0} transaction rows calculated.", [r.message.length]));
				} else {
					frappe.msgprint(__("No RPT transactions found for the selected period."));
				}
			}
		});
	}
});

frappe.ui.form.on("FR RPT Transaction", {
	transaction_category(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.transaction_category && row.transaction_category !== "Other") {
			frappe.model.set_value(cdt, cdn, "description", row.transaction_category);
		}
	}
});
