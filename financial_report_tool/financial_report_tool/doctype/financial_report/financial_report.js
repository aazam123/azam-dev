// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Financial Report", {
    setup(frm){
        if (frm.grid) {
            const originalAddRow = frm.grid.add_row;
            const originalDeleteRow = frm.grid.delete_row;
            const originalMoveRow = frm.grid.move_row;
            
            frm.grid.add_row = function(...args) {
                const result = originalAddRow.apply(this, args);
                setTimeout(async () => await updateNoteNumbers(frm), 100);
                return result;
            };
            
            frm.grid.delete_row = function(...args) {
                const result = originalDeleteRow.apply(this, args);
                setTimeout(async () => await updateNoteNumbers(frm), 100);
                return result;
            };
            
            frm.grid.move_row = function(...args) {
                const result = originalMoveRow.apply(this, args);
                setTimeout(async () => await updateNoteNumbers(frm), 100);
                return result;
            };
        }
    },
    company: function(frm) {
        frappe.db.get_value('Company', frm.doc.company, 'default_currency')
        .then(r => {
            if (r.message && r.message.default_currency) {
                frm.set_value('currency', r.message.default_currency);
            }
        });
    },
	financial_report_template(frm) {
        frappe.call({
            method: 'get_financial_report_template',
            doc: frm.doc,
            callback: function(rsp){
                frm.refresh_field('financial_report_details')
                frm.refresh_field('foreign_exchange_rate')
                setTimeout(async () => await updateNoteNumbers(frm), 200);
            }
        })
	},
    refresh(frm) {
        // Status indicator
        if (frm.doc.report_status === "Under Generation") {
            frm.dashboard.set_headline_alert(
                '<span class="indicator-pill whitespace-nowrap blue">' +
                '<span class="indicator-dot"></span> Under Generation</span>'
            );
        } else if (frm.doc.report_status === "Failed") {
            frm.set_intro("Report generation failed. Check Error Details below.", "red");
            frm.dashboard.set_headline_alert(
                '<span class="indicator-pill whitespace-nowrap red">' +
                '<span class="indicator-dot"></span> Generation Failed</span>'
            );
        } else if (frm.doc.report_status === "Successful") {
            frm.dashboard.set_headline_alert(
                '<span class="indicator-pill whitespace-nowrap green">' +
                '<span class="indicator-dot"></span> Report Generated Successfully</span>'
            );
        }

        // Listen for realtime event to auto-reload when job finishes
        frappe.realtime.off("report_generation_complete");
        frappe.realtime.on("report_generation_complete", (data) => {
            if (data.docname === frm.doc.name) {
                frm.reload_doc();
                if (data.status === "Successful") {
                    frappe.show_alert({message: "Report generated successfully!", indicator: "green"});
                } else if (data.status === "Failed") {
                    frappe.show_alert({message: "Report generation failed. Check the form for details.", indicator: "red"});
                }
            }
        });

        if (!frm.is_new()) {
            frm.add_custom_button("Show Report", function () {
                const print_format = "Financial Report";
                const print_url = `/printview?doctype=Financial Report&name=${frm.doc.name}&format=${print_format}&no_letterhead=0`;
                window.open(print_url, '_blank');
            });

            frm.add_custom_button("Export Excel", function() {
                exportToExcel(frm);
            }, "Export");
            
            frm.add_custom_button("Export PDF (with Note Linking)", function() {
                exportToPDF(frm);
            }, "Export");
        }
        
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button("Generate Report", function() {
                generateFinancialReport(frm);
            }, "Generate");
            
            frm.add_custom_button("Update Note Numbers", async function() {
                await updateNoteNumbers(frm);
                frappe.msgprint("Note numbers updated successfully!");
            }, "Generate");
        }
        
        setTimeout(async () => await updateNoteNumbers(frm), 500);
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
            frappe.model.set_value(cdt, cdn, "section", "Equity");
			frappe.model.set_value(cdt, cdn, "doctype_name", "");
		}

		frm.refresh_field('financial_report_details');
		// Update note numbers after section type change
		setTimeout(async () => await updateNoteNumbers(frm), 100);  
	},
    section: async function(frm, cdt, cdn) {
        await section(frm, cdt, cdn);
        // Update note numbers after section change
        setTimeout(async () => await updateNoteNumbers(frm), 100);
    },
	subsection: async function(frm, cdt, cdn) {
        await subsection(frm, cdt, cdn);
    }
});


// Function to update note numbers
async function updateNoteNumbers(frm) {
    if (!frm.doc.financial_report_details) return;
    
    let noteCounter = 4;
    
    for (let i = 0; i < frm.doc.financial_report_details.length; i++) {
        const row = frm.doc.financial_report_details[i];
        
        if (row.section_type === "Consolidation Note" && row.section) {
            try {
                const response = await frappe.db.get_value('FR Section', row.section, 'is_schedule');
                if (response && response.message && response.message.is_schedule) {
                    row.note_no = noteCounter.toString();
                    noteCounter++;
                } else {
                    row.note_no = "";
                }
            } catch (error) {
                row.note_no = "";
            }
        } else {
            row.note_no = "";
        }
    }
    
    frm.refresh_field('financial_report_details');
}


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

async function generateFinancialReport(frm) {
    if (!frm.doc.company) {
        frappe.msgprint("Please select a Company", "Error");
        return;
    }

    if (!frm.doc.fiscal_year) {
        frappe.msgprint("Please select a Fiscal Year", "Error");
        return;
    }

    if (frm.doc.workflow_state && frm.doc.workflow_state == "Approved") {
        frappe.msgprint("This report has already been approved. You cannot regenerate it.", "Warning");
        return;
    }

    try {
        const result = await frappe.call({
            method: 'generate_report',
            doc: frm.doc
        });

        if (result.exc) {
            frappe.msgprint("Error generating report: " + result.exc, "Error");
        } else {
            frappe.show_alert({message: "Report generation started in background.", indicator: "blue"});
            frm.reload_doc();
        }

    } catch (error) {
        frappe.msgprint("Error generating report: " + error.message, "Error");
        console.error("Generate Report Error:", error);
    }
}

function updateProgress(dialog, percentage, message) {
    const progress_fill = dialog.get_field('progress_html').$wrapper.find('.progress-fill');
    const progress_text = dialog.get_field('progress_html').$wrapper.find('.progress-text');
    
    progress_fill.css('width', percentage + '%');
    progress_text.text(message);
}

function exportToExcel(frm) {
    frappe.call({
        method: 'export_to_excel',
        doc: frm.doc,
        callback: function(r) {
            if (r.exc) {
                frappe.msgprint("Error exporting to Excel: " + r.exc, "Error");
            } else if (r.message) {
                const link = document.createElement('a');
                link.href = r.message.file_url;
                link.download = r.message.file_name;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                frappe.msgprint("Excel file exported successfully!", "Success");
            }
        }
    });
}

function exportToPDF(frm) {
    // Show loading message
    frappe.msgprint("Generating PDF with note linking...", "Info");
    
    frappe.call({
        method: 'export_to_pdf',
        doc: frm.doc,
        callback: function(r) {
            if (r && r.exc) {
                frappe.msgprint("Error exporting to PDF: " + r.exc, "Error");
            } else if (r && r.message) {
                // Create a link to download the file
                const link = document.createElement('a');
                link.href = r.message.file_url;
                link.download = r.message.file_name;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                frappe.msgprint("PDF exported successfully with note linking!", "Success");
            } else {
                frappe.msgprint("PDF exported successfully!", "Success");
            }
        },
        error: function(xhr, status, error) {
            frappe.msgprint("Error exporting PDF: " + error, "Error");
        }
    });
}

