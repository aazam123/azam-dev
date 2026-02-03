frappe.ui.form.on("Account", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.is_group === 0) {
			frm.add_custom_button(__("Create Grouping"), function() {
				open_grouping_dialog(frm);
			}, __("Actions"));
		}
	}
});

function open_grouping_dialog(frm) {
	let d = new frappe.ui.Dialog({
		title: __("Create GL Group Mapping"),
		fields: [
			{
				fieldname: "report_type",
				fieldtype: "Select",
				label: __("Report Type"),
				options: "Monthly\nYearly\nMIS",
				reqd: 1
			},
			{
				fieldname: "primary_group",
				fieldtype: "Link",
				label: __("Primary Group"),
				options: "Standalone Group",
				reqd: 1
			},
			{
				fieldname: "secondary_group",
				fieldtype: "Link",
				label: __("Secondary Group"),
				options: "Standalone Group",
				reqd: 1
			},
			{
				fieldname: "higher_secondary_group",
				fieldtype: "Link",
				label: __("Higher Secondary Group"),
				options: "Standalone Group"
			}
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			create_or_update_mapping(frm, values, d, 0);
		}
	});
	d.show();
}

function create_or_update_mapping(frm, values, dialog, update_existing) {
	frappe.call({
		method: "financial_report_tool.api.create_gl_group_mapping",
		args: {
			gl_account: frm.doc.name,
			company: frm.doc.company,
			report_type: values.report_type,
			primary_group: values.primary_group,
			secondary_group: values.secondary_group,
			higher_secondary_group: values.higher_secondary_group || "",
			update_existing: update_existing
		},
		freeze: true,
		freeze_message: update_existing ? __("Updating GL Group Mapping...") : __("Creating GL Group Mapping..."),
		callback(r) {
			if (r.message) {
				if (r.message.success && !r.message.exists) {
					// Created or updated successfully
					let msg = r.message.updated
						? __("GL Group Mapping updated successfully")
						: __("GL Group Mapping created successfully");
					frappe.show_alert({
						message: msg,
						indicator: "green"
					});
					dialog.hide();
				} else if (r.message.exists) {
					// Entry already exists, ask for update
					let existing = r.message.existing_data;
					let msg = `<p><strong>${__("GL Group Mapping already exists for this account and report type.")}</strong></p>
						<table class="table table-bordered" style="margin-top:10px;">
							<tr><th></th><th>${__("Existing")}</th><th>${__("New")}</th></tr>
							<tr><td>${__("Primary Group")}</td><td>${existing.primary_group}</td><td>${values.primary_group}</td></tr>
							<tr><td>${__("Secondary Group")}</td><td>${existing.secondary_group}</td><td>${values.secondary_group}</td></tr>
							<tr><td>${__("Higher Secondary Group")}</td><td>${existing.higher_secondary_group || "-"}</td><td>${values.higher_secondary_group || "-"}</td></tr>
						</table>
						<p>${__("Do you want to update it?")}</p>`;

					frappe.confirm(
						msg,
						function() {
							// User clicked Yes - update existing
							create_or_update_mapping(frm, values, dialog, 1);
						},
						function() {
							// User clicked No - do nothing
						}
					);
				}
			}
		}
	});
}
