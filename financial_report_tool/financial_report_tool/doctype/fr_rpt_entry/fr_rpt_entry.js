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
	}
});
