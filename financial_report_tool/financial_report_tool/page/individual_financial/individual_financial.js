// let selected_financial_report_id = null;

// frappe.pages['individual-financial'].on_page_load = function(wrapper) {
//     const page = frappe.ui.make_app_page({
//         parent: wrapper,
//         title: 'Financial Report',
//         single_column: true
//     });

//     // Filter to select Financial Report
//     page.add_field({
//         label: 'Financial Report ID',
//         fieldname: 'financial_report_id',
//         fieldtype: 'Link',
//         options: 'Financial Report',
//         change() {
//             selected_financial_report_id = this.get_value();
//             if (selected_financial_report_id) {
//                 try { localStorage.setItem('fr_selected_report', selected_financial_report_id); } catch (e) {}
//                 load_financial_report(selected_financial_report_id, page);
//             }
//         }
//     });

//     // Main layout: LEFT = 70% tables, RIGHT = 30% comment panel (hidden initially)
//     $(page.body).html(`
//         <div class="financial-report-wrapper" style="display:flex; gap:15px; margin-top:20px;">
//             <div class="financial-report-container" style="flex:0 0 70%; overflow-x:auto; padding-bottom:50px;">
//                 <h4>Please select a Financial Report from the filter above.</h4>
//             </div>
//             <div class="comment-panel-wrapper" style="flex:0 0 30%; position:relative; display:none;">
//                 <div class="comment-panel" style="
//                     position:fixed;
//                     right:15px;
//                     top:50%;
//                     transform:translateY(-50%);
//                     border:1px solid #ddd;
//                     border-radius:6px;
//                     padding:10px;
//                     background:#f9f9f9;
//                     width:28%;
//                     max-height:90vh;
//                     display:flex;
//                     flex-direction:column;
//                     box-shadow:0 2px 8px rgba(0,0,0,0.1);
//                 ">
//                     <h5 style="text-align:center;">Comments</h5>
//                     <div class="comment-add-section" style="margin-bottom:10px;">
//                         <textarea class="comment-input" placeholder="Add your comment..." style="width:100%; min-height:50px; margin-bottom:5px;"></textarea>
//                         <button class="btn btn-sm btn-primary add-comment-btn" style="width:100%;">Add Comment</button>
//                     </div>
//                     <div class="comment-list" style="flex:1; overflow-y:auto; border-top:1px solid #eee; padding-top:5px;">
//                         Select a row to see comments
//                     </div>
//                 </div>
//             </div>
//         </div>
//     `);

//     // Auto-load last report if available
//     try {
//         const last = localStorage.getItem('fr_selected_report');
//         if (last) {
//             selected_financial_report_id = last;
//             const fld = page.fields_dict && page.fields_dict.financial_report_id;
//             if (fld && fld.set_value) fld.set_value(last);
//             load_financial_report(last, page);
//         }
//     } catch (e) {}

//     // CSS
//     const style = document.createElement("style");
//     style.innerHTML = `
//         tr.has-comments { background-color: #fffbe6; border-left:4px solid #f0ad4e; }
//         tr.has-comments:hover { background-color: #fff3cd; }

//         .financial-report-container table { width:100%; margin-bottom:15px; border-collapse:collapse; table-layout:fixed; }
//         .financial-report-container th, .financial-report-container td { padding:6px; border:1px solid #ccc; font-size:13px; word-break:break-word; }

//         /* Comment button hidden by default */
//         .comment-button { 
//             cursor:pointer; 
//             font-size:14px; 
//             padding:2px 6px; 
//             border:none; 
//             border-radius:3px; 
//             background:#eee; 
//             display:none; 
//             margin-left:5px;
//         }

//         /* Show comment button on row hover */
//         tr:hover .comment-button { display:inline-block; }

//         .comment-button:hover { background:#ddd; }
//     `;
//     document.head.appendChild(style);

//     // Add general comment button handler
//     $(document).on('click', '.add-comment-btn', function() {
//         const textarea = document.querySelector('.comment-input');
//         const content = textarea.value.trim();
//         if (!content) return;
//         if (!selected_financial_report_id) return frappe.show_alert('Select a report first');

//         frappe.call({
//             method:'frappe.client.insert',
//             args:{ doc:{
//                 doctype:'Financial Report Comments',
//                 financial_report: selected_financial_report_id,
//                 comment_added_by: frappe.session.user,
//                 note_no: null,
//                 row_index: null,
//                 row_label: null,
//                 comment: content
//             }},
//             callback: ()=>{
//                 frappe.show_alert('Comment added');
//                 textarea.value = '';
//             }
//         });
//     });
// };

// // Load report
// function load_financial_report(report_id, page) {
//     frappe.call({
//         method:"frappe.client.get",
//         args:{ doctype:"Financial Report", name:report_id },
//         callback:function(r){
//             if(r.message) render_financial_report(r.message,page);
//             else $(page.body).find(".financial-report-container").html(`<p style="color:red;">No data found for report ${report_id}</p>`);
//         }
//     });
// }

// // Render report
// function render_financial_report(doc,page){
//     let html=`<h3>${doc.company||"Company Name"}</h3>`;
//     html+=`<h4 style="text-align:center; margin-bottom:15px;">INDEPENDENT AUDITOR'S REPORT</h4>`;

//     if(doc.financial_report_details && doc.financial_report_details.length){
//         doc.financial_report_details.forEach(row=>{
//             html+=`
//                 <div class="note-block" id="note-${row.note_no}" data-note="${row.note_no}" style="margin-bottom:20px;">
//                     <div style="margin-bottom:10px; font-weight:bold;">Note ${row.note_no}. ${row.section}</div>
//                     <div class="note-description">${row.section_description||""}</div>
//                 </div>
//             `;
//         });
//     } else html+=`<p>No financial details available in this report.</p>`;

//     $(page.body).find(".financial-report-container").html(html);
//     enhanceTablesForRowComments();
//     loadExistingComments();
// }

// // Add comment buttons to table rows (hover only)
// function enhanceTablesForRowComments(){
//     const canAddComment = frappe.user_roles.includes('Finance Manager');

//     document.querySelectorAll('.note-block').forEach(noteBlock=>{
//         noteBlock.querySelectorAll('table').forEach(table=>{
//             const tbody = table.querySelector('tbody')||table;
//             [...tbody.querySelectorAll('tr')].forEach((tr,idx)=>{
//                 if(tr.querySelector('th')) return; // skip header

//                 tr.dataset.rowIndex = idx;

//                 const td = document.createElement('td');
//                 const btn = document.createElement('button');
//                 btn.className = 'comment-button';
//                 btn.innerText = '💬';

//                 td.appendChild(btn);
//                 tr.appendChild(td);

//                 btn.addEventListener('click', ()=>{
//                     showCommentsRightPanel(noteBlock.id, idx, canAddComment, tr);
//                 });
//             });
//         });
//     });
// }

// // Show row-specific comments in right panel
// function showCommentsRightPanel(noteId, rowIndex, canAddComment, rowEl){
//     const panelWrapper = document.querySelector('.comment-panel-wrapper');
//     panelWrapper.style.display = 'flex'; // show the panel

//     const panel = document.querySelector('.comment-panel .comment-list');
//     panel.innerHTML = "<p>Loading...</p>";

//     const textarea = document.querySelector('.comment-input'); 
//     const addBtn = document.querySelector('.add-comment-btn');
//     textarea.value = ''; 

//     // Remove previous click handler to avoid duplicates
//     const newAddBtn = addBtn.cloneNode(true);
//     addBtn.parentNode.replaceChild(newAddBtn, addBtn);

//     newAddBtn.addEventListener('click', ()=>{
//         const content = textarea.value.trim();
//         if(!content) return frappe.show_alert('Enter comment');

//         frappe.call({
//             method:'frappe.client.insert',
//             args:{ doc:{
//                 doctype:'Financial Report Comments',
//                 financial_report:selected_financial_report_id,
//                 comment_added_by:frappe.session.user,
//                 note_no:noteId,
//                 row_index:rowIndex,
//                 row_label:rowEl.querySelector('td')?.innerText||'',
//                 comment:content
//             }},
//             callback:()=>{
//                 const item=document.createElement('div');
//                 item.style.borderLeft='3px solid #6f42c1';
//                 item.style.background='#f5f5f5';
//                 item.style.padding='6px';
//                 item.style.marginBottom='6px';
//                 item.innerHTML=`<b>${frappe.session.user}</b><br><small>${frappe.datetime.now_datetime()}</small><div>${frappe.utils.escape_html(content)}</div>`;
//                 panel.appendChild(item);
//                 textarea.value='';
//                 rowEl.classList.add('has-comments');
//             }
//         });
//     });

//     // Load existing comments for this row
//     frappe.call({
//         method:"frappe.client.get_list",
//         args:{
//             doctype:"Financial Report Comments",
//             filters:{ financial_report:selected_financial_report_id, note_no:noteId, row_index:rowIndex },
//             fields:["name","comment","comment_added_by","creation","row_label"],
//             order_by:"creation desc"
//         },
//         callback:r=>{
//             panel.innerHTML=""; 
//             (r.message||[]).forEach(c=>{
//                 const item=document.createElement('div');
//                 item.style.borderLeft='3px solid #6f42c1';
//                 item.style.background='#f5f5f5';
//                 item.style.padding='6px';
//                 item.style.marginBottom='6px';
//                 item.innerHTML=`<b>${c.comment_added_by}</b><br><small>${c.creation}</small><div>${frappe.utils.escape_html(c.comment)}</div>`;
//                 panel.appendChild(item);
//             });
//         }
//     });
// }

// // Highlight rows with existing comments
// function loadExistingComments(){
//     if(!selected_financial_report_id) return;

//     frappe.call({
//         method:"frappe.client.get_list",
//         args:{
//             doctype:"Financial Report Comments",
//             filters:{ financial_report:selected_financial_report_id },
//             fields:["note_no","row_index"],
//         },
//         callback:r=>{
//             if(!r.message) return;
//             r.message.forEach(c=>{
//                 const noteEl=document.querySelector(`#note-${c.note_no}`);
//                 if(!noteEl) return;
//                 const rowEl=noteEl.querySelector(`tr[data-row-index="${c.row_index}"]`);
//                 if(rowEl) rowEl.classList.add("has-comments");
//             });
//         }
//     });
// }



let selected_financial_report_id = null;

frappe.pages['individual-financial'].on_page_load = function(wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Financial Report',
        single_column: true
    });

    // Filter to select Financial Report
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

    // Main layout: LEFT = 70% tables, RIGHT = 30% comment panel (hidden initially)
    $(page.body).html(`
        <div class="financial-report-wrapper" style="display:flex; gap:15px; margin-top:20px;">
            <div class="financial-report-container" style="flex:0 0 70%; overflow-x:auto; padding-bottom:50px;">
                <h4>Please select a Financial Report from the filter above.</h4>
            </div>
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
                    <div class="comment-add-section" style="margin-bottom:10px;">
                        <textarea class="comment-input" placeholder="Add your comment..." style="width:100%; min-height:50px; margin-bottom:5px;"></textarea>
                        <button class="btn btn-sm btn-primary add-comment-btn" style="width:100%;">Add Comment</button>
                    </div>
                    <div class="comment-list" style="flex:1; overflow-y:auto; border-top:1px solid #eee; padding-top:5px;">
                        Select a row to see comments
                    </div>
                </div>
            </div>
        </div>
    `);

    // Auto-load last report if available
    try {
        const last = localStorage.getItem('fr_selected_report');
        if (last) {
            selected_financial_report_id = last;
            const fld = page.fields_dict && page.fields_dict.financial_report_id;
            if (fld && fld.set_value) fld.set_value(last);
            load_financial_report(last, page);
        }
    } catch (e) {}

    // CSS for uniform tables and comments
    const style = document.createElement("style");
    style.innerHTML = `
        /* Tables uniform width like Print Format, no borders */
        .financial-report-container table {
            width: 100%;
            table-layout: fixed; /* Fixed column widths */
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        .financial-report-container th, 
        .financial-report-container td {
            padding: 6px;
            font-size: 13px;
            word-break: break-word;
            text-align: left;
            min-width: 80px; /* Ensures consistent column width */
            border: none; /* Removes horizontal & vertical lines */
        }

        /* Optional: subtle row separator */
        .financial-report-container tr + tr td {
            border-top: 1px solid #eee; /* light horizontal line between rows */
        }

        /* Highlight rows with comments */
        tr.has-comments { 
            border-left:4px solid #f0ad4e; 
        }
        tr.has-comments:hover { background-color: #fff3cd; }

        /* Comment button hidden by default */
        .comment-button { 
            cursor:pointer; 
            font-size:14px; 
            padding:2px 6px; 
            border:none; 
            border-radius:3px; 
            background:#eee; 
            display:none; 
            margin-left:5px;
        }
        tr:hover .comment-button { display:inline-block; }
        .comment-button:hover { background:#ddd; }

        /* Note block spacing */
        .note-block { margin-bottom:20px; }
        .note-block div.note-description { margin-top:5px; font-size:13px; }
    `;
    document.head.appendChild(style);

    // Add general comment button handler
    $(document).on('click', '.add-comment-btn', function() {
        const textarea = document.querySelector('.comment-input');
        const content = textarea.value.trim();
        if (!content) return;
        if (!selected_financial_report_id) return frappe.show_alert('Select a report first');

        frappe.call({
            method:'frappe.client.insert',
            args:{ doc:{
                doctype:'Financial Report Comments',
                financial_report: selected_financial_report_id,
                comment_added_by: frappe.session.user,
                note_no: null,
                row_index: null,
                row_label: null,
                comment: content
            }},
            callback: ()=>{
                frappe.show_alert('Comment added');
                textarea.value = '';
            }
        });
    });
};

// Load report
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

// Render report with uniform tables
function render_financial_report(doc,page){
    let html=`<h3>${doc.company||"Company Name"}</h3>`;
    html+=`<h4 style="text-align:center; margin-bottom:15px;">INDEPENDENT AUDITOR'S REPORT</h4>`;

    if(doc.financial_report_details && doc.financial_report_details.length){
        doc.financial_report_details.forEach(row=>{
            html+=`
                <div class="note-block" id="note-${row.note_no}" data-note="${row.note_no}">
                    <div style="margin-bottom:10px; font-weight:bold;">Note ${row.note_no}. ${row.section}</div>
                    <div class="note-description">${row.section_description||""}</div>
                    ${row.table_html || ''} <!-- Assuming table HTML comes from backend -->
                </div>
            `;
        });
    } else html+=`<p>No financial details available in this report.</p>`;

    $(page.body).find(".financial-report-container").html(html);
    enhanceTablesForRowComments();
    loadExistingComments();
}

// Add comment buttons to table rows (hover only)
function enhanceTablesForRowComments(){
    const canAddComment = frappe.user_roles.includes('Finance Manager');

    document.querySelectorAll('.note-block').forEach(noteBlock=>{
        noteBlock.querySelectorAll('table').forEach(table=>{
            const tbody = table.querySelector('tbody')||table;
            [...tbody.querySelectorAll('tr')].forEach((tr,idx)=>{
                if(tr.querySelector('th')) return; // skip header

                tr.dataset.rowIndex = idx;

                const td = document.createElement('td');
                const btn = document.createElement('button');
                btn.className = 'comment-button';
                btn.innerText = '💬';

                td.appendChild(btn);
                tr.appendChild(td);

                btn.addEventListener('click', ()=>{
                    showCommentsRightPanel(noteBlock.id, idx, canAddComment, tr);
                });
            });
        });
    });
}

// Show row-specific comments in right panel
function showCommentsRightPanel(noteId, rowIndex, canAddComment, rowEl){
    const panelWrapper = document.querySelector('.comment-panel-wrapper');
    panelWrapper.style.display = 'flex'; // show the panel

    const panel = document.querySelector('.comment-panel .comment-list');
    panel.innerHTML = "<p>Loading...</p>";

    const textarea = document.querySelector('.comment-input'); 
    const addBtn = document.querySelector('.add-comment-btn');
    textarea.value = ''; 

    const newAddBtn = addBtn.cloneNode(true);
    addBtn.parentNode.replaceChild(newAddBtn, addBtn);

    newAddBtn.addEventListener('click', ()=>{
        const content = textarea.value.trim();
        if(!content) return frappe.show_alert('Enter comment');

        frappe.call({
            method:'frappe.client.insert',
            args:{ doc:{
                doctype:'Financial Report Comments',
                financial_report:selected_financial_report_id,
                comment_added_by:frappe.session.user,
                note_no:noteId,
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
    frappe.call({
        method:"frappe.client.get_list",
        args:{
            doctype:"Financial Report Comments",
            filters:{ financial_report:selected_financial_report_id, note_no:noteId, row_index:rowIndex },
            fields:["name","comment","comment_added_by","creation","row_label"],
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
                item.innerHTML=`<b>${c.comment_added_by}</b><br><small>${c.creation}</small><div>${frappe.utils.escape_html(c.comment)}</div>`;
                panel.appendChild(item);
            });
        }
    });
}

// Highlight rows with existing comments
function loadExistingComments(){
    if(!selected_financial_report_id) return;

    frappe.call({
        method:"frappe.client.get_list",
        args:{
            doctype:"Financial Report Comments",
            filters:{ financial_report:selected_financial_report_id },
            fields:["note_no","row_index"],
        },
        callback:r=>{
            if(!r.message) return;
            r.message.forEach(c=>{
                const noteEl=document.querySelector(`#note-${c.note_no}`);
                if(!noteEl) return;
                const rowEl=noteEl.querySelector(`tr[data-row-index="${c.row_index}"]`);
                if(rowEl) rowEl.classList.add("has-comments");
            });
        }
    });
}
