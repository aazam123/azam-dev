// Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("FR Employee Benefit Obligation", {
	template(frm) {
        frm.call({
            method: 'fetch_templates',
            doc: frm.doc,
            callback: function(resp) {
                
            }
        })
	},
    refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button("Download Excel", () => {
				window.open(
					`/api/method/financial_report_tool.financial_report_tool.doctype.fr_employee_benefit_obligation.fr_employee_benefit_obligation.download_excel?docname=${frm.doc.name}`
				);
			});

			frm.add_custom_button("Upload Excel", () => {
				frappe.prompt(
					[
						{
							fieldtype: "Attach",
							label: "Upload Excel",
							fieldname: "excel",
							reqd: 1
						}
					],
					(data) => {
						frappe.call({
							method: "financial_report_tool.financial_report_tool.doctype.fr_employee_benefit_obligation.fr_employee_benefit_obligation.upload_excel",
							args: {
								docname: frm.doc.name,
								file_url: data.excel
							},
							callback() {
								frm.reload_doc();
							}
						});
					},
					"Upload Excel"
				);
			});
		}
	}
});