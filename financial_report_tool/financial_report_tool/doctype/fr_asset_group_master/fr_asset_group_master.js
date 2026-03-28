// Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("FR Asset Group Master", {
	refresh(frm) {
		frm.add_custom_button(__("Update Asset Group"), function () {
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "FR Asset Register Entry",
					filters: {
						asset_group: frm.doc.asset_group,
						asset_class: ["like", "%" + frm.doc.asset_class + "%"]
					},
					fields: ["asset_class"],
					limit: 0
				},
				callback: function (r) {
					if (!r.message || !r.message.length) {
						frappe.msgprint(__("No entries found for this Asset Group."));
						return;
					}

					// Collect unique asset_class values
					const seen = new Set();
					const unique_classes = [];
					r.message.forEach(function (entry) {
						if (entry.asset_class && !seen.has(entry.asset_class)) {
							seen.add(entry.asset_class);
							unique_classes.push(entry.asset_class);
						}
					});

					// Clear existing child table rows
					frm.clear_table("child_asset_class");

					// Add each unique asset_class as a row
					unique_classes.forEach(function (asset_class) {
						let row = frm.add_child("child_asset_class");
						row.asset_class = asset_class;
					});

					frm.refresh_field("child_asset_class");
					frm.save();
					frappe.msgprint(__("Asset Group updated with {0} unique asset class(es).", [unique_classes.length]));
				}
			});
		});
	},
});
