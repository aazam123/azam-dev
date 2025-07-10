// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Financial Report", {
    // fiscal_year: async function(frm) {
    //     if (!frm.doc.fiscal_year) return;
    
    //     try {
    //         const fy = await frappe.db.get_doc('Fiscal Year', frm.doc.fiscal_year);
    //         const yearEndDate = new Date(fy.year_end_date);
    //         const prevYearEndDate = new Date(yearEndDate);
    //         prevYearEndDate.setFullYear(prevYearEndDate.getFullYear() - 1);
    
    //         await frm.set_value('previous_year_ending_date', frappe.datetime.obj_to_str(prevYearEndDate));
    //     } catch (error) {
    //         console.error("Error fetching fiscal year or setting date:", error);
    //     }
    // },    
	financial_report_template(frm) {
        frappe.call({
            method: 'get_financial_report_template',
            doc: frm.doc,
            callback: function(rsp){
                frm.refresh_field('financial_report_details')
            }
        })
	},
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button("Show Report", function () {
                const print_format = "Financial Report";

                const print_url = `/printview?doctype=Financial Report&name=${frm.doc.name}&format=${print_format}&no_letterhead=0`;

                window.open(print_url, '_blank');
            });
        }
    }
});

frappe.ui.form.on("Financial Report Details", {
	section_type(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

		if(row.section_type == "Consolidation Note"){
			frappe.model.set_value(cdt, cdn, "doctype_name", "FR Section");
		} else if(row.section_type == "Profit & Loss"){
			frappe.model.set_value(cdt, cdn, "doctype_name", "Profit And Loss Template");
		} else if(row.section_type == "Balance Sheet"){
			frappe.model.set_value(cdt, cdn, "doctype_name", "Balance Sheet Template");
		} else if(row.section_type == "Cash Flow"){
			frappe.model.set_value(cdt, cdn, "doctype_name", "Cash Flow Template");
		} else if(row.section_type == "Equity"){
			frappe.model.set_value(cdt, cdn, "doctype_name", "Equity Template");
		}

		frm.refresh_field('financial_report_details');
	},
    section: async function(frm, cdt, cdn) {
        await section(frm, cdt, cdn);
    },
	subsection: async function(frm, cdt, cdn) {
        await subsection(frm, cdt, cdn);
    }
});


async function section(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.section_type === "Consolidation Note" && row.section) {
        try {
            const response = await frappe.db.get_value(
                'FR Section',
                row.section,
                'section_type_description'
            );

            if (response && response.message && response.message.section_type_description) {
                frappe.model.set_value(cdt, cdn, 'section_description', response.message.section_type_description);
            }
        } catch (error) {
            console.error("Failed to fetch section description:", error);
        }
    }
}

async function subsection(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.section_type === "Consolidation Note" && row.subsection) {
        try {
            const response = await frappe.db.get_value(
                'FR Subsection',
                row.subsection,
                'subsection_type_description'
            );

            if (response && response.message && response.message.subsection_type_description) {
                frappe.model.set_value(cdt, cdn, 'subsection_description', response.message.subsection_type_description);
            }
        } catch (error) {
            console.error("Failed to fetch section description:", error);
        }
    }
}