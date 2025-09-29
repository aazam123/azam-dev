let selected_financial_report_id = null;

frappe.pages['individual-financial'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Financial Report',
        single_column: true
    });

    page.add_field({
        label: 'Financial Report ID',
        fieldname: 'financial_report_id',
        fieldtype: 'Link',
        options: 'Financial Report',
        change() {
            selected_financial_report_id = this.get_value();
            if (selected_financial_report_id) {
                load_financial_report(selected_financial_report_id, page);
            }
        }
    });

    $(`
        <div class="financial-report-container" style="margin-top:20px;">
            <h4>Please select a Financial Report from the filter above.</h4>
        </div>
    `).appendTo(page.body);
};

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
                     style="border:1px solid #ddd; margin-bottom:15px; border-radius:6px; 
                            box-shadow:0 2px 5px rgba(0,0,0,0.05); position:relative; transition:all 0.3s ease; display:flex;">
                    
                    <!-- Main Content Area -->
                    <div class="note-main-content" style="flex:2; padding:10px; border-right:1px solid #eee;">
                        <div class="note-title" style="font-weight:bold; margin-bottom:10px; font-size:14px;">
                            Note ${row.note_no}. ${row.section}
                            <span class="comment-indicator" style="float:right; color:#888; font-size:12px; cursor:pointer;">
                                💬 Hover to comment
                            </span>
                        </div>

                        <div class="note-description" style="margin-bottom:10px;">
                            ${row.section_description ? `<p style="margin:0; font-size:13px; line-height:1.4;">${row.section_description}</p>` : ""}
                        </div>
                    </div>

                    <!-- Comment Section (Initially Hidden) - Right Side -->
                    <div class="comment-section" data-note="${row.note_no}" 
                         style="display:none; flex:1; padding:15px; background:#f9f9f9; border-radius:0 6px 6px 0;">
                        
                        <div style="display:flex; flex-direction:column; height:100%; gap:15px;">
                            <!-- Add Comment Section -->
                            <div style="flex-shrink:0;">
                                <label style="font-size:12px; font-weight:600; display:block; margin-bottom:5px;">Add Comment:</label>
                                <textarea class="comment-input" data-note="${row.note_no}" 
                                          style="width:100%; padding:8px; font-size:12px; min-height:60px; 
                                                 border-radius:4px; border:1px solid #ccc; resize:vertical; box-sizing:border-box;"
                                          placeholder="Enter your comment here..."></textarea>
                                <button class="btn btn-sm btn-primary add-comment-btn" data-note="${row.note_no}" 
                                        style="margin-top:8px; width:100%;">Add Comment</button>
                            </div>
                            
                            <!-- Recent Comments Section -->
                            <div style="flex:1; min-height:0;">
                                <label style="font-size:12px; font-weight:600; display:block; margin-bottom:5px;">Recent Comments:</label>
                                <div class="comment-list" style="height:150px; overflow-y:auto; border:1px solid #ddd; 
                                                                   border-radius:4px; padding:5px; background:white;"></div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
    } else {
        html += `<p>No financial details available in this report.</p>`;
    }

    $(page.body).find(".financial-report-container").html(html);
    
    initializeHoverComments();
    initializeAddCommentButtons();
}

// New function to handle hover functionality
function initializeHoverComments() {
    document.querySelectorAll('.note-block').forEach(noteBlock => {
        const commentSection = noteBlock.querySelector('.comment-section');
        const mainContent = noteBlock.querySelector('.note-main-content');
        let hoverTimeout;
        
        // Show comment section on hover
        noteBlock.addEventListener('mouseenter', function() {
            clearTimeout(hoverTimeout);
            if (commentSection) {
                commentSection.style.display = 'flex';
                noteBlock.style.backgroundColor = '#fafafa';
                noteBlock.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
                
                // Add visual indicator to main content
                if (mainContent) {
                    mainContent.style.backgroundColor = '#f8f9fa';
                }
            }
        });
        
        // Hide comment section when leaving (with small delay)
        noteBlock.addEventListener('mouseleave', function() {
            hoverTimeout = setTimeout(() => {
                if (commentSection) {
                    // Only hide if user is not actively typing in textarea
                    const textarea = commentSection.querySelector('.comment-input');
                    if (!textarea || textarea !== document.activeElement) {
                        commentSection.style.display = 'none';
                        noteBlock.style.backgroundColor = '';
                        noteBlock.style.boxShadow = '0 2px 5px rgba(0,0,0,0.05)';
                        
                        if (mainContent) {
                            mainContent.style.backgroundColor = '';
                        }
                    }
                }
            }, 500); // 500ms delay before hiding
        });
        
        // Keep comment section visible when user is typing
        const textarea = commentSection?.querySelector('.comment-input');
        if (textarea) {
            textarea.addEventListener('focus', function() {
                clearTimeout(hoverTimeout);
                commentSection.style.display = 'flex';
            });
            
            textarea.addEventListener('blur', function() {
                // Hide after a longer delay when textarea loses focus
                hoverTimeout = setTimeout(() => {
                    if (!noteBlock.matches(':hover')) {
                        commentSection.style.display = 'none';
                        noteBlock.style.backgroundColor = '';
                        noteBlock.style.boxShadow = '0 2px 5px rgba(0,0,0,0.05)';
                        
                        if (mainContent) {
                            mainContent.style.backgroundColor = '';
                        }
                    }
                }, 1000);
            });
        }
    });
}

function initializeAddCommentButtons() {
    const currentUserRoles = frappe.user_roles;
    const canAddComment = currentUserRoles.includes("Finance Manager");

    document.querySelectorAll('.comment-section').forEach(section => {
        const textarea = section.querySelector('.comment-input');
        const btn = section.querySelector('.add-comment-btn');

        if (!canAddComment) {
            if (textarea) {
                textarea.disabled = true;
                textarea.placeholder = "Access restricted to Finance Managers";
            }
            if (btn) {
                btn.disabled = true;
                btn.innerText = "No Access";
                btn.classList.remove('btn-primary');
                btn.classList.add('btn-secondary');
            }
        }
    });

    if (canAddComment) {
        document.querySelectorAll('.add-comment-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const note_no = this.dataset.note;
                const textarea = this.closest('.comment-section').querySelector('.comment-input');
                const comment = textarea.value.trim();

                if (!selected_financial_report_id) {
                    frappe.show_alert('Please select a Financial Report first.');
                    return;
                }

                if (!comment) {
                    frappe.show_alert('Please enter a comment before adding.');
                    return;
                }

                // Show loading state
                const originalText = btn.innerText;
                btn.disabled = true;
                btn.innerText = 'Adding...';

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
                        textarea.value = "";
                        
                        // Reset button state
                        btn.disabled = false;
                        btn.innerText = originalText;

                        // Add comment to UI immediately
                        const commentListDiv = btn.closest('.comment-section').querySelector('.comment-list');
                        if (commentListDiv) {
                            const user = frappe.session.user;
                            const date = frappe.datetime.now_datetime();
                            const commentHtml = `<div class="comment-item" style="font-size:12px; margin-bottom:8px; padding:6px; 
                                                                                    border-radius:3px; background:#f5f5f5; border-left:3px solid #007bff;">
                                <div style="font-weight:600; margin-bottom:2px;">${user}</div>
                                <div style="color:#666; font-size:11px; margin-bottom:4px;">${date}</div>
                                <div>${comment}</div>
                            </div>`;
                            commentListDiv.insertAdjacentHTML('afterbegin', commentHtml);
                        }
                    },
                    error: function() {
                        btn.disabled = false;
                        btn.innerText = originalText;
                        frappe.show_alert('Error adding comment. Please try again.', 'red');
                    }
                });
            });
        });
    }

    // Load existing comments
    loadExistingComments();
}

function loadExistingComments() {
    if (!selected_financial_report_id) return;

    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Financial Report Comments",
            filters: { financial_report: selected_financial_report_id },
            fields: ["comment", "comment_added_by", "note_no", "creation"],
            order_by: "creation desc" // Show newest first
        },
        callback: function(r) {
            if (r.message && r.message.length) {
                r.message.forEach(c => {
                    const noteDiv = document.querySelector(`#note-${c.note_no} .comment-list`);
                    if (noteDiv) {
                        const commentHtml = `<div class="comment-item" style="font-size:12px; margin-bottom:8px; padding:6px; 
                                                                                border-radius:3px; background:#f5f5f5; border-left:3px solid #28a745;">
                            <div style="font-weight:600; margin-bottom:2px;">${c.comment_added_by}</div>
                            <div style="color:#666; font-size:11px; margin-bottom:4px;">${frappe.datetime.get_datetime_as_string(c.creation)}</div>
                            <div>${c.comment}</div>
                        </div>`;
                        noteDiv.insertAdjacentHTML('beforeend', commentHtml);
                    }
                });
            }
        }
    });
}