// Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("FR Additional Information Schedule III", {
	refresh(frm) {
		frappe.dom.set_style(
			`.fr-addl-info-grid .grid-heading-row { height: auto !important; min-height: 96px; }
			.fr-addl-info-grid .grid-heading-row .grid-static-col,
			.fr-addl-info-grid .grid-heading-row .row-check,
			.fr-addl-info-grid .grid-heading-row .row-index { height: auto !important; min-height: 96px; display: flex; align-items: center; }
			.fr-addl-info-grid .grid-heading-row .grid-static-col .static-area,
			.fr-addl-info-grid .grid-heading-row .grid-static-col .ellipsis {
				font-weight: 700; white-space: normal !important; overflow: visible !important;
				text-overflow: clip !important; word-break: break-word; line-height: 1.3;
			}
			.fr-addl-info-grid .grid-row.fr-bold-row .grid-static-col,
			.fr-addl-info-grid .grid-row.fr-bold-row .static-area { font-weight: 700; }`,
			"fr-addl-info-grid-style"
		);
		frm.fields_dict.rows.grid.wrapper.addClass("fr-addl-info-grid");
	},
});

frappe.ui.form.on("FR Additional Information Row", {
	is_bold(frm, cdt, cdn) {
		const row = frm.fields_dict.rows.grid.grid_rows_by_docname[cdn];
		if (row) row.wrapper.toggleClass("fr-bold-row", !!locals[cdt][cdn].is_bold);
	},
});

$(document).on("grid-row-render", (e, grid_row) => {
	if (grid_row.doc && grid_row.doc.doctype === "FR Additional Information Row") {
		grid_row.wrapper.toggleClass("fr-bold-row", !!grid_row.doc.is_bold);
	}
});
