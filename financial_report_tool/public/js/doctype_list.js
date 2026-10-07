// The DocType list prints each record's raw name. Run it through the
// translation map (translations/en.csv) so "FR Financial Report" shows as
// "Financial Report". Backend names are unchanged.
frappe.listview_settings["DocType"] = Object.assign(frappe.listview_settings["DocType"] || {}, {
	formatters: Object.assign((frappe.listview_settings["DocType"] || {}).formatters || {}, {
		name: (value) => __(value),
	}),
});
