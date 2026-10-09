// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

// Two screens on one doctype:
//   Requestor  -> New GL Description, Company Name, Reference GL (+ description / company),
//                 Receiver's Mail ID. No access to the Maker section.
//   Maker      -> everything the Requestor sees, plus New GL and the Primary / Secondary
//                 Grouping (permlevel 1, only the FR GL Maker role can read / write it).
// The split is enforced by role permissions (permlevel) on the server; this script only
// adds the action buttons and keeps the screen tidy.

const MAKER_ROLE = 'FR GL Maker';
const CONTROLLER =
	'financial_report_tool.financial_report_tool.doctype.fr_gl_account_creation_request.fr_gl_account_creation_request';

function is_maker(frm) {
	// The Maker section is permlevel 1: the form only exposes it to users who can read it.
	return !!frm.get_perm(1, 'read');
}

function can_action(frm) {
	const me = frappe.session.user;
	return (
		me === frm.doc.assigned_to ||
		me === 'Administrator' ||
		frappe.user.has_role('System Manager')
	);
}

frappe.ui.form.on('FR GL Account Creation Request', {
	setup(frm) {
		frm.set_query('reference_gl', () => ({ filters: { is_group: 0 } }));
		frm.set_query('pattern_account', () => ({ filters: { company: frm.doc.company, is_group: 1 } }));
	},

	refresh(frm) {
		// Maker section: visible to users with the FR GL Maker role, on saved requests only.
		frm.toggle_display('maker_section', !frm.is_new() && frappe.user.has_role(MAKER_ROLE));

		if (frm.is_new()) return;

		const maker = is_maker(frm);

		// Approve / Reject are workflow actions (Actions menu); each opens a popup first,
		// see before_workflow_action below.

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

		// Maker fields are editable only while the request is open and only by the assignee / admin.
		['new_gl', 'primary_group', 'secondary_group', 'pattern_account'].forEach((f) =>
			frm.set_df_property(f, 'read_only', frm.doc.status !== 'Requested' || !can_action(frm) ? 1 : 0)
		);

		// A Requestor can change the request details only while it is still open.
		if (!maker && frm.doc.status !== 'Requested') {
			frm.disable_save();
		}
	},

	company(frm) {
		frm.set_query('parent_account', () => ({ filters: { company: frm.doc.company } }));

		// Fetch and assign the Receiver's Mail ID configured for this company.
		if (!frm.doc.company) {
			frm.set_value('assigned_to', '');
			frm.set_value('receiver_email', '');
			return;
		}
		frappe
			.call({
				method: 'financial_report_tool.financial_report_tool.doctype.fr_gl_account_creation_request.fr_gl_account_creation_request.get_receiver_for_company',
				args: { company: frm.doc.company },
			})
			.then((r) => {
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

	// Approve / Reject popups. The Actions-menu item opens the dialog; submitting it calls
	// one server method that saves the entries AND runs the workflow action (account +
	// grouping creation, state change). The hook's promise is deliberately never resolved:
	// resolving it would make the stock workflow code run the action a second time.
	before_workflow_action(frm) {
		const action = frm.selected_workflow_action;
		if (action !== 'Approve' && action !== 'Reject') return;

		frappe.dom.unfreeze(); // the workflow menu froze the screen; the dialog needs input
		const run = (method, args) =>
			frappe
				.xcall(`${CONTROLLER}.${method}`, { name: frm.doc.name, ...args })
				.then(() => {
					dialog.hide();
					frm.selected_workflow_action = null;
					return frm.reload_doc();
				})
				.catch(() => {
					// server-side validation failed (shown to the user): keep the dialog open
				});

		const dialog = new frappe.ui.Dialog(
			action === 'Approve'
				? {
						title: __('Approve GL Account Creation'),
						fields: [
							{ fieldname: 'new_gl', fieldtype: 'Data', label: __('New GL Account'), reqd: 1, default: frm.doc.new_gl },
							{ fieldname: 'account_name', fieldtype: 'Data', label: __('New GL Description'), reqd: 1, default: frm.doc.account_name },
							{ fieldname: 'primary_group', fieldtype: 'Link', options: 'FR Standalone Group', label: __('Primary Group'), reqd: 1, default: frm.doc.primary_group },
							{ fieldname: 'secondary_group', fieldtype: 'Link', options: 'FR Standalone Group', label: __('Secondary Group'), reqd: 1, default: frm.doc.secondary_group },
							{
								fieldname: 'pattern_account',
								fieldtype: 'Link',
								options: 'Account',
								label: __('Pattern Account'),
								reqd: 1,
								default: frm.doc.pattern_account,
								get_query: () => ({ filters: { company: frm.doc.company, is_group: 1 } }),
							},
						],
						primary_action_label: __('Approve'),
						primary_action: (v) => run('approve_request', v),
				  }
				: {
						title: __('Reject Request'),
						fields: [{ fieldname: 'remark', fieldtype: 'Small Text', label: __('Remark'), reqd: 1 }],
						primary_action_label: __('Reject'),
						primary_action: (v) => run('reject_request', v),
				  }
		);
		dialog.onhide = () => {
			frm.selected_workflow_action = null;
		};
		dialog.show();
		return new Promise(() => {});
	},
});
