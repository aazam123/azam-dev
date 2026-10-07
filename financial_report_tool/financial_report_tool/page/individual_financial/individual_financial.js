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
        options: 'FR Financial Report',
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

        // RIGHT container - Chat style comment panel (Mint Green Theme)
        page.comment_wrapper = $(`
            <div class="comment-panel-wrapper" style="flex:0 0 30%; position:relative; display:none;">
                <div class="comment-panel" style="
                    position:fixed;
                    right:20px;
                    top:50%;
                    transform:translateY(-50%);
                    border:none;
                    border-radius:16px;
                    background:#ffffff;
                    width:26%;
                    min-width:320px;
                    max-height:80vh;
                    display:flex;
                    flex-direction:column;
                    box-shadow:0 10px 40px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.05);
                    overflow:hidden;
                ">
                    <div class="chat-header" style="
                        background:linear-gradient(135deg, #5a8c5dff 0%, #3a7e40ff 100%);
                        color:#fff;
                        padding:14px 16px;
                        display:flex;
                        align-items:center;
                        justify-content:space-between;
                    ">
                        <div style="display:flex; align-items:center; gap:12px; flex:1; min-width:0;">
                            <div style="
                                width:40px;
                                height:40px;
                                min-width:40px;
                                background:rgba(255,255,255,0.2);
                                border-radius:10px;
                                display:flex;
                                align-items:center;
                                justify-content:center;
                                font-size:18px;
                            ">💬</div>
                            <div style="flex:1; min-width:0;">
                                <div class="chat-header-title" style="font-weight:600; font-size:15px; letter-spacing:-0.3px;">Comments</div>
                                <div class="chat-row-label" style="font-size:11px; opacity:0.9; margin-top:3px; line-height:1.3;">
                                    <div>Select a row</div>
                                </div>
                            </div>
                        </div>
                        <button class="chat-close-btn" style="
                            background:rgba(255,255,255,0.15);
                            border:none;
                            color:#fff;
                            width:32px;
                            height:32px;
                            min-width:32px;
                            border-radius:8px;
                            cursor:pointer;
                            font-size:14px;
                            transition:all 0.2s;
                            margin-left:10px;
                        ">✕</button>
                    </div>
                    <div class="comment-list" style="
                        flex:1;
                        overflow-y:auto;
                        padding:16px;
                        background:linear-gradient(180deg, #ffffffff 0%, #eaf3eaff 100%);
                        min-height:280px;
                    ">
                        <div class="chat-empty-state" style="
                            text-align:center;
                            padding:50px 20px;
                            color:#2E7D32;
                        ">
                            <div style="
                                width:70px;
                                height:70px;
                                background:linear-gradient(135deg, #C8E6C9 0%, #A5D6A7 100%);
                                border-radius:50%;
                                display:flex;
                                align-items:center;
                                justify-content:center;
                                margin:0 auto 16px;
                                font-size:28px;
                            ">💭</div>
                            <div style="font-size:15px; font-weight:500; color:#1B5E20;">Select a row to view comments</div>
                        </div>
                    </div>
                    <div class="chat-input-area" style="
                        padding:14px 16px;
                        background:#ffffff;
                        border-top:1px solid #C8E6C9;
                        display:none;
                    ">
                        <div style="display:flex; gap:12px; align-items:flex-end;">
                            <textarea class="chat-input" placeholder="Type your comment..." style="
                                flex:1;
                                border:2px solid #C8E6C9;
                                border-radius:12px;
                                padding:12px 16px;
                                resize:none;
                                font-size:14px;
                                max-height:100px;
                                min-height:44px;
                                outline:none;
                                font-family:inherit;
                                transition:border-color 0.2s, box-shadow 0.2s;
                                background:#F1F8E9;
                            "></textarea>
                            <button class="chat-send-btn" style="
                                background:linear-gradient(135deg, #4CAF50 0%, #388E3C 100%);
                                border:none;
                                color:#fff;
                                width:44px;
                                height:44px;
                                border-radius:12px;
                                cursor:pointer;
                                font-size:18px;
                                display:flex;
                                align-items:center;
                                justify-content:center;
                                transition:all 0.2s;
                                box-shadow:0 4px 12px rgba(76,175,80,0.3);
                            ">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                    <line x1="22" y1="2" x2="11" y2="13"></line>
                                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                                </svg>
                            </button>
                        </div>
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
        /* Row with comments indicator - Mint Green Theme */
        tr.has-comments {
            border-left:4px solid #319234ff;
            background:linear-gradient(90deg, rgba(232,245,232,0.8) 0%, transparent 100%);
        }
        tr.has-comments:hover {
            background:linear-gradient(90deg, rgba(200,230,201,0.6) 0%, rgba(232,245,232,0.3) 100%);
        }

        /* Comment button on rows */
        .comment-button {
            cursor:pointer;
            font-size:12px;
            padding:6px 10px;
            border:none;
            border-radius:8px;
            background:linear-gradient(135deg, #75c978ff 0%, #60b564ff 100%);
            color:#fff;
            display:inline-flex;
            align-items:center;
            gap:4px;
            margin-left:5px;
            transition:all 0.2s ease;
            box-shadow:0 2px 6px rgba(76,175,80,0.3);
        }
        .comment-button:hover {
            transform:translateY(-2px);
            box-shadow:0 4px 12px rgba(76,175,80,0.4);
        }
        .comment-button:active {
            transform:translateY(0);
        }

        .note-block { margin-bottom:20px; }
        .note-block div.note-description { margin-top:5px; font-size:13px; }

        /* Chat bubble styles - Mint Green Theme */
        .chat-bubble {
            max-width:82%;
            padding:12px 16px;
            border-radius:16px;
            margin-bottom:10px;
            position:relative;
            word-wrap:break-word;
            animation:bubbleIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        }

        @keyframes bubbleIn {
            from {
                opacity:0;
                transform:translateY(10px) scale(0.95);
            }
            to {
                opacity:1;
                transform:translateY(0) scale(1);
            }
        }

        /* Own messages - Green gradient */
        .chat-bubble.own {
            background:linear-gradient(135deg, #4CAF50 0%, #4CAF50 100%);
            color:#fff;
            margin-left:auto;
            border-bottom-right-radius:6px;
            box-shadow:0 2px 8px rgba(76,175,80,0.3);
        }

        /* Other's messages - Light mint */
        .chat-bubble.other {
            background:#ffffff;
            color:#1B5E20;
            margin-right:auto;
            border-bottom-left-radius:6px;
            box-shadow:0 2px 8px rgba(0,0,0,0.06);
            border:1px solid #C8E6C9;
        }

        /* Author name with avatar */
        .chat-bubble .chat-author-wrap {
            display:flex;
            align-items:center;
            gap:8px;
            margin-bottom:6px;
        }

        .chat-bubble .chat-avatar {
            width:24px;
            height:24px;
            border-radius:50%;
            display:flex;
            align-items:center;
            justify-content:center;
            font-size:11px;
            font-weight:600;
            text-transform:uppercase;
        }

        .chat-bubble.own .chat-avatar {
            background:rgba(255,255,255,0.25);
            color:#fff;
        }

        .chat-bubble.other .chat-avatar {
            background:linear-gradient(135deg, #81C784 0%, #66BB6A 100%);
            color:#fff;
        }

        .chat-bubble .chat-author {
            font-size:12px;
            font-weight:600;
        }

        .chat-bubble.own .chat-author {
            color:rgba(255,255,255,0.9);
        }

        .chat-bubble.other .chat-author {
            color:#2E7D32;
        }

        /* Message text */
        .chat-bubble .chat-text {
            font-size:14px;
            line-height:1.5;
            letter-spacing:-0.1px;
        }

        /* Timestamp */
        .chat-bubble .chat-time {
            font-size:11px;
            margin-top:6px;
            display:flex;
            align-items:center;
            gap:4px;
        }

        .chat-bubble.own .chat-time {
            color:rgba(255,255,255,0.75);
            justify-content:flex-end;
        }

        .chat-bubble.other .chat-time {
            color:#81C784;
        }

        /* Date divider */
        .chat-date-divider {
            text-align:center;
            margin:20px 0;
            position:relative;
        }

        .chat-date-divider::before {
            content:'';
            position:absolute;
            left:0;
            right:0;
            top:50%;
            height:1px;
            background:#A5D6A7;
        }

        .chat-date-divider span {
            background:linear-gradient(135deg, #E8F5E8 0%, #C8E6C9 100%);
            padding:6px 14px;
            border-radius:20px;
            font-size:11px;
            font-weight:500;
            color:#2E7D32;
            position:relative;
            z-index:1;
            border:1px solid #A5D6A7;
        }

        /* Input focus state */
        .chat-input:focus {
            border-color:#4CAF50;
            box-shadow:0 0 0 3px rgba(76,175,80,0.15);
            background:#fff;
        }

        /* Send button states */
        .chat-send-btn:hover {
            transform:translateY(-2px);
            box-shadow:0 6px 16px rgba(76,175,80,0.4);
        }

        .chat-send-btn:active {
            transform:translateY(0);
            box-shadow:0 2px 8px rgba(76,175,80,0.3);
        }

        /* Close button hover */
        .chat-close-btn:hover {
            background:rgba(255,255,255,0.25);
            transform:scale(1.05);
        }

        /* Loading indicator */
        .typing-indicator {
            display:flex;
            gap:5px;
            padding:12px 18px;
            background:#fff;
            border-radius:16px;
            width:fit-content;
            box-shadow:0 2px 8px rgba(0,0,0,0.06);
            border:1px solid #C8E6C9;
        }

        .typing-indicator span {
            width:8px;
            height:8px;
            background:linear-gradient(135deg, #4CAF50 0%, #388E3C 100%);
            border-radius:50%;
            animation:typingPulse 1.4s infinite;
        }

        .typing-indicator span:nth-child(2) { animation-delay:0.2s; }
        .typing-indicator span:nth-child(3) { animation-delay:0.4s; }

        @keyframes typingPulse {
            0%, 60%, 100% {
                transform:translateY(0);
                opacity:0.4;
            }
            30% {
                transform:translateY(-6px);
                opacity:1;
            }
        }

        /* Scrollbar styling for chat */
        .comment-list::-webkit-scrollbar {
            width:6px;
        }

        .comment-list::-webkit-scrollbar-track {
            background:#E8F5E8;
        }

        .comment-list::-webkit-scrollbar-thumb {
            background:#A5D6A7;
            border-radius:3px;
        }

        .comment-list::-webkit-scrollbar-thumb:hover {
            background:#81C784;
        }

        /* Empty state styling */
        .chat-empty-state {
            animation:fadeIn 0.4s ease;
        }

        @keyframes fadeIn {
            from { opacity:0; }
            to { opacity:1; }
        }

        @keyframes spin {
            from { transform:rotate(0deg); }
            to { transform:rotate(360deg); }
        }

        .note-block {
            border-radius:8px;
            padding:10px;
        }
    `;
    document.head.appendChild(style);
};


// --- Load report ---
function load_financial_report(report_id, page) {
    frappe.call({
        method:"frappe.client.get",
        args:{ doctype:"FR Financial Report", name:report_id },
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
                `<table style="width:${tableWidth}; margin-left:0;" data-section="${frappe.utils.escape_html(row.section || '')}"`
            );

            html += `
                <div class="note-block"
                     id="note-${row.note_no}"
                     data-note="${row.note_no}"
                     data-section="${frappe.utils.escape_html(row.section || '')}"
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
}

// --- Add comment buttons to rows and highlight rows with existing comments ---
function enhanceTablesForRowComments() {
    const canAddComment = frappe.user_roles.includes('Financial Report Manager');

    document.querySelectorAll('.note-block').forEach(noteBlock => {
        const noteId = noteBlock.dataset.note;
        const sectionType = noteBlock.dataset.sectionType;
        const sectionName = noteBlock.dataset.section || '';

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
                    showCommentsRightPanel(noteId, sectionType, sectionName, idx, canAddComment, tr);
                });

                // --- Highlight row if comments already exist for note, section_type, and row_index ---
                frappe.call({
                    method: "frappe.client.get_list",
                    args: {
                        doctype: "FR Financial Report Comments",
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

// --- Show row-specific comments (Chat style) ---
function showCommentsRightPanel(noteId, sectionType, sectionName, rowIndex, canAddComment, rowEl){
    const panelWrapper = document.querySelector('.comment-panel-wrapper');
    panelWrapper.style.display = 'flex';

    const panel = document.querySelector('.comment-panel .comment-list');
    const inputArea = document.querySelector('.chat-input-area');
    const textarea = document.querySelector('.chat-input');
    const sendBtn = document.querySelector('.chat-send-btn');
    const closeBtn = document.querySelector('.chat-close-btn');
    const rowLabel = document.querySelector('.chat-row-label');

    // Update header with section and row info
    const rowText = rowEl.querySelector('td')?.innerText || 'Row ' + (rowIndex + 1);
    const truncatedSection = sectionName.length > 25 ? sectionName.substring(0, 25) + '...' : sectionName;
    const truncatedRow = rowText.length > 30 ? rowText.substring(0, 30) + '...' : rowText;

    // Build header label with section info
    let labelHtml = `<div style="font-size:11px; opacity:0.8;">Note ${noteId} • ${truncatedSection}</div>`;
    labelHtml += `<div style="font-size:12px; margin-top:2px;">${truncatedRow}</div>`;
    rowLabel.innerHTML = labelHtml;

    // Show loading state
    panel.innerHTML = `
        <div style="display:flex; justify-content:center; padding:20px;">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;

    // Show input area only if user can add comments
    if (canAddComment) {
        inputArea.style.display = 'block';
        textarea.value = '';
    } else {
        inputArea.style.display = 'none';
    }

    // Close button handler
    closeBtn.onclick = () => {
        panelWrapper.style.display = 'none';
    };

    // Only setup send functionality if user can add comments
    if (!canAddComment) {
        loadExistingComments(noteId, sectionType, rowIndex, rowEl, panel);
        return;
    }

    // Remove old event listeners by cloning
    const newSendBtn = sendBtn.cloneNode(true);
    sendBtn.parentNode.replaceChild(newSendBtn, sendBtn);

    const newTextarea = textarea.cloneNode(true);
    textarea.parentNode.replaceChild(newTextarea, textarea);

    // Send message handler
    const handleSend = () => {
        const content = newTextarea.value.trim();
        if(!content) return frappe.show_alert({message: 'Please enter a comment', indicator: 'orange'});

        // Show sending state with spinner
        newSendBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="animation:spin 1s linear infinite;">
            <circle cx="12" cy="12" r="10" stroke-opacity="0.3"></circle>
            <path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"></path>
        </svg>`;
        newSendBtn.disabled = true;

        frappe.call({
            method:'frappe.client.insert',
            args:{ doc:{
                doctype:'FR Financial Report Comments',
                financial_report:selected_financial_report_id,
                comment_added_by:frappe.session.user,
                note_no:noteId,
                section_type:sectionType,
                row_index:rowIndex,
                row_label:rowEl.querySelector('td')?.innerText||'',
                comment:content
            }},
            callback:()=>{
                // Add new message bubble
                const bubble = createChatBubble({
                    comment: content,
                    comment_added_by: frappe.session.user,
                    creation: frappe.datetime.now_datetime()
                }, true);
                panel.appendChild(bubble);

                // Clear input and scroll to bottom
                newTextarea.value = '';
                panel.scrollTop = panel.scrollHeight;
                rowEl.classList.add('has-comments');

                // Reset button
                newSendBtn.innerHTML = getSendIcon();
                newSendBtn.disabled = false;

                frappe.show_alert({message: 'Comment added', indicator: 'green'});
            },
            error: () => {
                newSendBtn.innerHTML = getSendIcon();
                newSendBtn.disabled = false;
            }
        });
    };

    newSendBtn.addEventListener('click', handleSend);

    // Enter key to send (Shift+Enter for new line)
    newTextarea.addEventListener('keydown', (e) => {
        if(e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    // Auto-resize textarea
    newTextarea.addEventListener('input', () => {
        newTextarea.style.height = 'auto';
        newTextarea.style.height = Math.min(newTextarea.scrollHeight, 100) + 'px';
    });

    // Load existing comments for this row
    loadExistingComments(noteId, sectionType, rowIndex, rowEl, panel);
}

// --- Create chat bubble element ---
function createChatBubble(comment, isOwn) {
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${isOwn ? 'own' : 'other'}`;

    const authorName = comment.comment_added_by?.split('@')[0] || 'User';
    const initials = getInitials(authorName);
    const timeStr = formatChatTime(comment.creation);

    bubble.innerHTML = `
        <div class="chat-author-wrap">
            <div class="chat-avatar">${initials}</div>
            <div class="chat-author">${frappe.utils.escape_html(authorName)}</div>
        </div>
        <div class="chat-text">${frappe.utils.escape_html(comment.comment)}</div>
        <div class="chat-time">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            ${timeStr}
        </div>
    `;

    return bubble;
}

// --- Get initials from name ---
function getInitials(name) {
    if (!name) return '?';
    const parts = name.replace(/[._-]/g, ' ').split(' ').filter(p => p.length > 0);
    if (parts.length >= 2) {
        return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
}

// --- Get send button icon ---
function getSendIcon() {
    return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <line x1="22" y1="2" x2="11" y2="13"></line>
        <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
    </svg>`;
}

// --- Format time for chat ---
function formatChatTime(datetime) {
    if (!datetime) return '';
    const date = new Date(datetime);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();

    const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    if (isToday) {
        return timeStr;
    } else {
        const dateStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' });
        return `${dateStr}, ${timeStr}`;
    }
}

// --- Load and render existing comments (Chat style) ---
function loadExistingComments(noteId, sectionType, rowIndex, rowEl, panel) {
    if (!selected_financial_report_id) return;

    frappe.call({
        method:"frappe.client.get_list",
        args:{
            doctype:"FR Financial Report Comments",
            filters:{
                financial_report:selected_financial_report_id,
                note_no:noteId,
                row_index:rowIndex,
                section_type:sectionType
            },
            fields:["name","comment","comment_added_by","creation","row_label","section_type"],
            order_by:"creation asc"  // Oldest first like chat
        },
        callback:r=>{
            panel.innerHTML = "";

            const comments = r.message || [];

            if (comments.length === 0) {
                panel.innerHTML = `
                    <div class="chat-empty-state" style="
                        text-align:center;
                        padding:50px 20px;
                        color:#2E7D32;
                    ">
                        <div style="
                            width:80px;
                            height:80px;
                            background:linear-gradient(135deg, #C8E6C9 0%, #A5D6A7 100%);
                            border-radius:50%;
                            display:flex;
                            align-items:center;
                            justify-content:center;
                            margin:0 auto 20px;
                            border:2px dashed #81C784;
                        ">
                            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#2E7D32" stroke-width="1.5">
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                                <line x1="9" y1="10" x2="15" y2="10"></line>
                            </svg>
                        </div>
                        <div style="font-size:16px; font-weight:600; color:#1B5E20; margin-bottom:6px;">No comments yet</div>
                        <div style="font-size:13px; color:#4CAF50;">Be the first to start the conversation</div>
                    </div>
                `;
                return;
            }

            // Group comments by date
            let lastDate = null;

            comments.forEach(c => {
                const commentDate = new Date(c.creation).toDateString();

                // Add date divider if new date
                if (commentDate !== lastDate) {
                    const divider = document.createElement('div');
                    divider.className = 'chat-date-divider';
                    const dateLabel = formatDateDivider(c.creation);
                    divider.innerHTML = `<span>${dateLabel}</span>`;
                    panel.appendChild(divider);
                    lastDate = commentDate;
                }

                // Check if this is user's own message
                const isOwn = c.comment_added_by === frappe.session.user;
                const bubble = createChatBubble(c, isOwn);
                panel.appendChild(bubble);
            });

            // Scroll to bottom
            setTimeout(() => {
                panel.scrollTop = panel.scrollHeight;
            }, 100);

            if (comments.length > 0) {
                rowEl.classList.add("has-comments");
            }
        }
    });
}

// --- Format date for divider ---
function formatDateDivider(datetime) {
    const date = new Date(datetime);
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === now.toDateString()) {
        return 'Today';
    } else if (date.toDateString() === yesterday.toDateString()) {
        return 'Yesterday';
    } else {
        return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
    }
}
