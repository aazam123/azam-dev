let selected_financial_report_id = null; // store selected report

frappe.pages['individual-financial'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Financial Report',
        single_column: true
    });

    // Add filter to select Financial Report
    page.add_field({
        label: 'Financial Report ID',
        fieldname: 'financial_report_id',
        fieldtype: 'Link',
        options: 'Financial Report',
        change() {
            selected_financial_report_id = this.get_value(); // store selected report
            if (selected_financial_report_id) {
                load_financial_report(selected_financial_report_id, page);
            }
        }
    });

    // Container
    $(`
        <div class="financial-report-container" style="margin-top:20px;">
            <h4>Please select a Financial Report from the filter above.</h4>
        </div>
    `).appendTo(page.body);
};

// Fetch & render report
function load_financial_report(report_id, page) {
    frappe.call({
        method: "frappe.client.get",
        args: { doctype: "Financial Report", name: report_id },
        callback: function(r) {
            if (r.message) {
                render_financial_report(r.message, page);
            } else {
                $(page.body).find(".financial-report-container").html(
                    `<p style="color:red;">No data found for report ${report_id}</p>`
                );
            }
        }
    });
}

// Render report
function render_financial_report(doc, page) {
    let html = `
        <div class="company-header">
            <h3 style="margin-bottom:10px;">${doc.company || "Company Name"}</h3>
        </div>
        <div class="auditor-section" style="margin-bottom:20px;">
            <h3 style="text-align: center;">INDEPENDENT AUDITOR'S REPORT</h3>
        </div>
    `;

    if (doc.financial_report_details && doc.financial_report_details.length) {
        doc.financial_report_details.forEach(row => {
            html += `
                <div class="note-block" id="note-${row.note_no}" 
                     style="border:1px solid #ddd; padding:10px; margin-bottom:15px; border-radius:6px; box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                    
                    <div class="note-title" style="font-weight:bold; margin-bottom:10px; font-size:14px;">
                        Note ${row.note_no}. ${row.section}
                    </div>

                    <div class="note-content-wrapper" style="display:flex; gap:15px; align-items:flex-start;">
                        <!-- Section Description -->
                        <div class="note-description" style="flex:2;">
                            ${row.section_description ? `<p style="margin:0; font-size:13px; line-height:1.4;">${row.section_description}</p>` : ""}
                        </div>

                        <!-- Comment box -->
                        <div class="note-comment" style="flex:1; min-width:150px;">
                            <label style="font-size:12px; font-weight:600; display:block; margin-bottom:5px;">Add Comment:</label>
                            <textarea class="comment-input" data-note="${row.note_no}" 
                                      style="width:100%; padding:6px; font-size:12px; min-height:50px; border-radius:4px; border:1px solid #ccc; resize:none;"></textarea>
                            <button class="btn btn-sm btn-primary add-comment-btn" data-note="${row.note_no}" 
                                    style="margin-top:5px;">Add Comment</button>
                        </div>
                    </div>
                </div>
            `;
        });
    } else {
        html += `<p>No financial details available in this report.</p>`;
    }

    $(page.body).find(".financial-report-container").html(html);

    initializeAddCommentButtons();
}

// Save comment in Financial Report Comments and show saved comments
function initializeAddCommentButtons() {
    document.querySelectorAll('.add-comment-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const note_no = this.dataset.note;
            const textarea = this.previousElementSibling;
            const comment = textarea.value;

            if (!selected_financial_report_id) {
                frappe.show_alert('Please select a Financial Report first.');
                return;
            }

            if (!comment) {
                frappe.show_alert('Please enter a comment before adding.');
                return;
            }

            // Optional: get standalone_group value from somewhere on page
            // For example, you could have a hidden input or select with id 'standalone_group'
            let standalone_group = document.getElementById('standalone_group') ? document.getElementById('standalone_group').value : '';

            frappe.call({
                method: "frappe.client.insert",
                args: {
                    doc: {
                        doctype: "Financial Report Comments",
                        financial_report: selected_financial_report_id,
                        comment_added_by: frappe.session.user,
                        standalone_group: standalone_group,
                        comment: comment,
                        note_no: note_no // store the note number as well
                    }
                },
                callback: function(r) {
                    frappe.show_alert(`Comment added for Note ${note_no}`);
                    textarea.value = ""; // Clear textarea

                    // Append saved comment below the textarea
                    const commentListDiv = btn.parentElement.querySelector('.comment-list');
                    if (commentListDiv) {
                        const user = frappe.session.user;
                        const date = frappe.datetime.now_datetime();
                        const commentHtml = `<div style="font-size:12px; margin-top:5px; padding:3px 5px; border-radius:3px; background:#f5f5f5;">
                            <strong>${user}</strong> (${date}): ${comment}
                        </div>`;
                        commentListDiv.innerHTML += commentHtml;
                    }
                }
            });
        });
    });

    // Add a container under each comment textarea to show saved comments
    document.querySelectorAll('.note-comment').forEach(div => {
        if (!div.querySelector('.comment-list')) {
            const commentListDiv = document.createElement('div');
            commentListDiv.className = 'comment-list';
            commentListDiv.style.marginTop = '5px';
            div.appendChild(commentListDiv);
        }
    });

    // Load existing comments for each note
    if (selected_financial_report_id) {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Financial Report Comments",
                filters: { financial_report: selected_financial_report_id },
                fields: ["comment", "comment_added_by", "note_no", "creation"],
                order_by: "creation asc"
            },
            callback: function(r) {
                if (r.message && r.message.length) {
                    r.message.forEach(c => {
                        const noteDiv = document.querySelector(`#note-${c.note_no} .comment-list`);
                        if (noteDiv) {
                            const commentHtml = `<div style="font-size:12px; margin-top:5px; padding:3px 5px; border-radius:3px; background:#f5f5f5;">
                                <strong>${c.comment_added_by}</strong> (${c.creation}): ${c.comment}
                            </div>`;
                            noteDiv.innerHTML += commentHtml;
                        }
                    });
                }
            }
        });
    }
}
// Save comment in Financial Report Comments and show saved comments
function initializeAddCommentButtons() {
    const currentUserRoles = frappe.user_roles; // Get current user's roles
    const canAddComment = currentUserRoles.includes("Finance Manager"); // Only Finance Manager can add

    document.querySelectorAll('.note-comment').forEach(div => {
        // Add a container under each comment textarea to show saved comments
        if (!div.querySelector('.comment-list')) {
            const commentListDiv = document.createElement('div');
            commentListDiv.className = 'comment-list';
            commentListDiv.style.marginTop = '5px';
            div.appendChild(commentListDiv);
        }

        // Disable textarea & button for non-Finance Manager users
        const textarea = div.querySelector('.comment-input');
        const btn = div.querySelector('.add-comment-btn');

        if (!canAddComment) {
            if (textarea) textarea.disabled = true;
            if (btn) {
                btn.disabled = true;
                btn.innerText = "No Access";
                btn.classList.remove('btn-primary');
                btn.classList.add('btn-secondary');
            }
        }
    });

    // Add click event only if user has access
    if (canAddComment) {
        document.querySelectorAll('.add-comment-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const note_no = this.dataset.note;
                const textarea = this.previousElementSibling;
                const comment = textarea.value;

                if (!selected_financial_report_id) {
                    frappe.show_alert('Please select a Financial Report first.');
                    return;
                }

                if (!comment) {
                    frappe.show_alert('Please enter a comment before adding.');
                    return;
                }

                let standalone_group = document.getElementById('standalone_group') 
                    ? document.getElementById('standalone_group').value 
                    : '';

                frappe.call({
                    method: "frappe.client.insert",
                    args: {
                        doc: {
                            doctype: "Financial Report Comments",
                            financial_report: selected_financial_report_id,
                            comment_added_by: frappe.session.user,
                            standalone_group: standalone_group,
                            comment: comment,
                            note_no: note_no
                        }
                    },
                    callback: function(r) {
                        frappe.show_alert(`Comment added for Note ${note_no}`);
                        textarea.value = ""; // Clear textarea

                        // Append saved comment below the textarea
                        const commentListDiv = btn.parentElement.querySelector('.comment-list');
                        if (commentListDiv) {
                            const user = frappe.session.user;
                            const date = frappe.datetime.now_datetime();
                            const commentHtml = `<div style="font-size:12px; margin-top:5px; padding:3px 5px; border-radius:3px; background:#f5f5f5;">
                                <strong>${user}</strong> (${date}): ${comment}
                            </div>`;
                            commentListDiv.innerHTML += commentHtml;
                        }
                    }
                });
            });
        });
    }

    // Load existing comments for each note
    if (selected_financial_report_id) {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Financial Report Comments",
                filters: { financial_report: selected_financial_report_id },
                fields: ["comment", "comment_added_by", "note_no", "creation"],
                order_by: "creation asc"
            },
            callback: function(r) {
                if (r.message && r.message.length) {
                    r.message.forEach(c => {
                        const noteDiv = document.querySelector(`#note-${c.note_no} .comment-list`);
                        if (noteDiv) {
                            const commentHtml = `<div style="font-size:12px; margin-top:5px; padding:3px 5px; border-radius:3px; background:#f5f5f5;">
                                <strong>${c.comment_added_by}</strong> (${c.creation}): ${c.comment}
                            </div>`;
                            noteDiv.innerHTML += commentHtml;
                        }
                    });
                }
            }
        });
    }
}
