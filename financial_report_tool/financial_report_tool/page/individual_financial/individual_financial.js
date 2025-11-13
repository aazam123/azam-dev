let selected_financial_report_id = null;

frappe.pages['individual-financial'].on_page_load = function(wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Financial Report',
        single_column: true
    });

    // --- Add Link field in page header ---
    page.add_field({
        label: 'Financial Report ID',
        fieldname: 'financial_report_id',
        fieldtype: 'Link',
        options: 'Financial Report',
        change() {
            selected_financial_report_id = this.get_value();
            if (selected_financial_report_id) {
                try { localStorage.setItem('fr_selected_report', selected_financial_report_id); } catch (e) {}
                load_financial_report(selected_financial_report_id, page);
            }
        }
    });

    if (!page.main_content) {
        page.main_content = $('<div class="financial-report-wrapper" style="display:flex; gap:15px; margin-top:20px;"></div>').appendTo(page.body);

        // LEFT container
        page.report_container = $('<div class="financial-report-container" style="flex:0 0 70%; overflow-x:auto; padding-bottom:50px;">')
            .html('<h4>Please select a Financial Report from the filter above.</h4>')
            .appendTo(page.main_content);

        // RIGHT container
        page.comment_wrapper = $(`
            <div class="comment-panel-wrapper" style="flex:0 0 30%; position:relative; display:none;">
                <div class="comment-panel" style="
                    position:fixed;
                    right:15px;
                    top:50%;
                    transform:translateY(-50%);
                    border:1px solid #ddd;
                    border-radius:6px;
                    padding:10px;
                    background:#f9f9f9;
                    width:28%;
                    max-height:90vh;
                    display:flex;
                    flex-direction:column;
                    box-shadow:0 2px 8px rgba(0,0,0,0.1);
                ">
                    <h5 style="text-align:center;">Comments</h5>
                    <div class="comment-list" style="flex:1; overflow-y:auto; border-top:1px solid #eee; padding-top:5px;">
                        Select a row to see comments
                    </div>
                </div>
            </div>
        `).appendTo(page.main_content);
    }


    // --- Auto-load last report ---
    try {
        const last = localStorage.getItem('fr_selected_report');
        if (last) {
            selected_financial_report_id = last;
            const fld = page.fields_dict && page.fields_dict.financial_report_id;
            if (fld && fld.set_value) fld.set_value(last);
            load_financial_report(last, page);
        }
    } catch (e) {}

    // --- CSS for tables and comments + keep filter visible ---
    const style = document.createElement("style");
    style.innerHTML = `
        /* Keep the Financial Report ID filter always visible in the page header */
        
        .page-head .page-actions {
            display: flex;
            align-items: center;
        }
        .page-head .frappe-control {
            margin-right: 10px;
        }

        /* Financial report tables */
        .financial-report-container table {
            width: 95% !important;
            min-width: 350px;
            margin-left: 0;
            table-layout: fixed;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        .financial-report-container th, 
        .financial-report-container td {
            padding: 6px;
            font-size: 13px;
            word-break: break-word;
            text-align: left;
            min-width: 80px;
            border: none;
        }
        .financial-report-container tr + tr td {
            border-top: 1px solid #eee;
        }
        tr.has-comments { border-left:4px solid #f0ad4e; }
        tr.has-comments:hover { background-color: #fff3cd; }
        .comment-button { 
            cursor:pointer; 
            font-size:14px; 
            padding:2px 6px; 
            border:none; 
            border-radius:3px; 
            background:#eee; 
            display:inline-block;
            margin-left:5px;
        }
        .comment-button:hover { background:#ddd; }
        .note-block { margin-bottom:20px; }
        .note-block div.note-description { margin-top:5px; font-size:13px; }
    `;
    document.head.appendChild(style);
};


// --- Load report ---
function load_financial_report(report_id, page) {
    frappe.call({
        method:"frappe.client.get",
        args:{ doctype:"Financial Report", name:report_id },
        callback:function(r){
            if(r.message) render_financial_report(r.message,page);
            else $(page.body).find(".financial-report-container").html(`<p style="color:red;">No data found for report ${report_id}</p>`);
        }
    });
}


function render_financial_report(doc, page){
    let html = `<h3>${doc.company||"Company Name"}</h3>`;
    if (doc.financial_report_details && doc.financial_report_details.length) {
        doc.financial_report_details.forEach(row => {
            // Set table width and margin for section type
            let tableWidth = (row.section_type === "Consolidation Note") ? "95%" : "90%";
            let marginBottom = (row.section_type === "Consolidation Note") ? "10px" : "35px";
            let tableHtml = (row.table_html || '').replace(
                /<table\b/i, 
                `<table style="width:${tableWidth}; margin-left:0;"`
            );

            html += `
                <div class="note-block" 
                     id="note-${row.note_no}" 
                     data-note="${row.note_no}" 
                     data-section-type="${row.section_type || ''}">
                    <div style="margin-bottom:${marginBottom}; font-weight:bold;">
                        Note ${row.note_no}: ${row.section}
                    </div>
                    <div class="note-description">${row.section_description || ""}</div>
                    ${tableHtml}
                </div>
            `;
        });
    } else {
        html += `<p>No financial details available in this report.</p>`;
    }

    $(page.body).find(".financial-report-container").html(html);
    enhanceTablesForRowComments();
    // do not call loadExistingComments here without args, it needs params
}

// --- Add comment buttons to rows and highlight rows with existing comments ---
function enhanceTablesForRowComments() {
    const canAddComment = frappe.user_roles.includes('Financial Report Manager');

    document.querySelectorAll('.note-block').forEach(noteBlock => {
        const noteId = noteBlock.dataset.note;
        const sectionType = noteBlock.dataset.sectionType;

        noteBlock.querySelectorAll('table').forEach(table => {
            const tbody = table.querySelector('tbody') || table;

            [...tbody.querySelectorAll('tr')].forEach((tr, idx) => {
                if (tr.querySelector('th')) return; // Skip header

                tr.dataset.rowIndex = idx;

                // Add comment button
                const td = document.createElement('td');
                const btn = document.createElement('button');
                btn.className = 'comment-button';
                btn.innerText = '💬';
                td.appendChild(btn);
                tr.appendChild(td);

                // --- Show comment panel on click ---
                btn.addEventListener('click', () => {
                    showCommentsRightPanel(noteId, sectionType, idx, canAddComment, tr);
                });

                // --- Highlight row if comments already exist for note, section_type, and row_index ---
                frappe.call({
                    method: "frappe.client.get_list",
                    args: {
                        doctype: "Financial Report Comments",
                        filters: {
                            financial_report: selected_financial_report_id,
                            note_no: noteId,
                            section_type: sectionType,
                            row_index: idx
                        },
                        fields: ["name"],
                        limit_page_length: 1
                    },
                    callback: r => {
                        if (r.message && r.message.length > 0) {
                            tr.classList.add('has-comments');
                        }
                    }
                });
            });
        });
    });
}


// --- Show row-specific comments ---
function showCommentsRightPanel(noteId, sectionType, rowIndex, canAddComment, rowEl){
    const panelWrapper = document.querySelector('.comment-panel-wrapper');
    panelWrapper.style.display = 'flex';

    const panel = document.querySelector('.comment-panel .comment-list');
    panel.innerHTML = "<p>Loading...</p>";

    // Create input section for new comment
    const textarea = document.createElement('textarea');
    textarea.placeholder = "Add your comment...";
    textarea.style.width = '100%';
    textarea.style.minHeight = '50px';
    textarea.style.marginBottom = '5px';

    const addBtn = document.createElement('button');
    addBtn.className = 'btn btn-sm btn-primary';
    addBtn.innerText = 'Add Comment';
    addBtn.style.width = '100%';

    // Replace old add-section
    const existingAddSection = panel.parentElement.querySelector('.comment-add-section');
    if(existingAddSection) existingAddSection.remove();

    const addSection = document.createElement('div');
    addSection.className = 'comment-add-section';
    addSection.style.marginBottom = '10px';
    addSection.appendChild(textarea);
    addSection.appendChild(addBtn);
    panel.parentElement.insertBefore(addSection, panel);

    addBtn.addEventListener('click', ()=>{
        const content = textarea.value.trim();
        if(!content) return frappe.show_alert('Enter comment');

        frappe.call({
            method:'frappe.client.insert',
            args:{ doc:{
                doctype:'Financial Report Comments',
                financial_report:selected_financial_report_id,
                comment_added_by:frappe.session.user,
                note_no:noteId,
                section_type:sectionType,
                row_index:rowIndex,
                row_label:rowEl.querySelector('td')?.innerText||'',
                comment:content
            }},
            callback:()=>{
                const item=document.createElement('div');
                item.style.borderLeft='3px solid #6f42c1';
                item.style.background='#f5f5f5';
                item.style.padding='6px';
                item.style.marginBottom='6px';
                item.innerHTML=`<b>${frappe.session.user}</b><br><small>${frappe.datetime.now_datetime()}</small><div>${frappe.utils.escape_html(content)}</div>`;
                panel.appendChild(item);
                textarea.value='';
                rowEl.classList.add('has-comments');
            }
        });
    });

    // Load existing comments for this row
    loadExistingComments(noteId, sectionType, rowIndex, rowEl, panel);
}

// --- Load and render existing comments ---
function loadExistingComments(noteId, sectionType, rowIndex, rowEl, panel) {
    if (!selected_financial_report_id) return;

    frappe.call({
        method:"frappe.client.get_list",
        args:{
            doctype:"Financial Report Comments",
            filters:{ 
                financial_report:selected_financial_report_id, 
                note_no:noteId, 
                row_index:rowIndex,
                section_type:sectionType
            },
            fields:["name","comment","comment_added_by","creation","row_label","section_type"],
            order_by:"creation desc"
        },
        callback:r=>{
            panel.innerHTML=""; 
            (r.message||[]).forEach(c=>{
                const item=document.createElement('div');
                item.style.borderLeft='3px solid #6f42c1';
                item.style.background='#f5f5f5';
                item.style.padding='6px';
                item.style.marginBottom='6px';
                item.innerHTML=`<b>${c.comment_added_by}</b> <small>(${c.section_type||''})</small><br><small>${c.creation}</small><div>${frappe.utils.escape_html(c.comment)}</div>`;
                panel.appendChild(item);
            });

            if((r.message||[]).length > 0) {
                rowEl.classList.add("has-comments");
            }
        }
    });
}
