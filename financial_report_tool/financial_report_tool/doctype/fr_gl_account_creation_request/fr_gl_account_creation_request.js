// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on('FR GL Account Creation Request', {
	refresh(frm) {
		if (frm.is_new()) return;

		const me = frappe.session.user;
		const can_act =
			me === frm.doc.assigned_to ||
			me === 'Administrator' ||
			frappe.user.has_role('System Manager');

		if (frm.doc.status === 'Requested' && can_act) {
			frm
				.add_custom_button(__('Create Account & Grouping'), () => {
					if (!frm.doc.primary_group || !frm.doc.secondary_group) {
						frappe.msgprint(__('Please set Primary Group and Secondary Group first.'));
						return;
					}
					frappe.confirm(
						__('Create ledger account <b>{0}</b> for {1} and map it to {2} / {3}?', [
							frappe.utils.escape_html(frm.doc.account_name),
							frm.doc.company,
							frm.doc.primary_group,
							frm.doc.secondary_group,
						]),
						() => {
							frm
								.call({ doc: frm.doc, method: 'create_account_and_grouping', freeze: true })
								.then(() => frm.reload_doc());
						}
					);
				})
				.addClass('btn-primary');

			frm.add_custom_button(__('Reject'), () => {
				frappe.prompt(
					[{ fieldtype: 'Small Text', label: __('Reason'), fieldname: 'reason', reqd: 1 }],
					(v) => {
						frm
							.call({ doc: frm.doc, method: 'reject', args: { reason: v.reason }, freeze: true })
							.then(() => frm.reload_doc());
					},
					__('Reject Request'),
					__('Reject')
				);
			});
		}

		if (frm.doc.created_account) {
			frm.add_custom_button(__('View Account'), () =>
				frappe.set_route('Form', 'Account', frm.doc.created_account)
			);
		}
		if (frm.doc.gl_group_mapping) {
			frm.add_custom_button(__('View GL Group Mapping'), () =>
				frappe.set_route('Form', 'FR GL Group Mapping', frm.doc.gl_group_mapping)
			);
		}

		// Only the assignee / managers should edit the grouping fields.
		['primary_group', 'secondary_group'].forEach((f) =>
			frm.set_df_property(f, 'read_only', frm.doc.status !== 'Requested' || !can_act ? 1 : 0)
		);
	},

	company(frm) {
		// Restrict grouping pickers to the request's company + report type.
		frm.set_query('parent_account', () => ({ filters: { company: frm.doc.company } }));

		// Fetch and assign the Receiver's Mail ID configured for this company.
		if (!frm.doc.company) {
			frm.set_value('assigned_to', '');
			frm.set_value('receiver_email', '');
			return;
		}
		frappe.call({
			method: 'financial_report_tool.financial_report_tool.financial_report_tool.doctype.fr_gl_account_creation_request.fr_gl_account_creation_request.get_receiver_for_company',
			args: { company: frm.doc.company },
		}).then((r) => {
			frm.set_value('assigned_to', (r.message && r.message.assigned_to) || '');
			frm.set_value('receiver_email', (r.message && r.message.receiver_email) || '');
			if (!r.message || !r.message.receiver_email) {
				frappe.msgprint(
					__('No assignee is configured for {0}. Set one in GL Account Request Settings.', [frm.doc.company]),
					__('No Assignee')
				);
			}
		});
	},
});
