/* =====================================================================
   send_comment.js
   Send: saves the text and its files in one request, then updates the thread, marker, pills, legend and cards.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

// Send button / Enter: saves the comment on the report whose chat is on screen, then updates the open thread, the row marker,
// the section pill, the legend and the report cards without reloading. Two sends at once are blocked (FR.sending).
// Only a Financial Report Manager can write; the server checks this again.
function submitComment() {
    if (!FR.active || !FR.canComment || FR.sending) return;
    const cid = commentReportId(FR.report);
    if (!cid) return frappe.show_alert({ message: 'No report found for that month', indicator: 'orange' });

    const text = FR.dom.input.value.trim();
    const files = FR.pendingFiles.slice();
    if (!text && !files.length) {
        return frappe.show_alert({ message: 'Write a comment or attach a file', indicator: 'orange' });
    }

    const ctx = FR.active;
    const btn = FR.dom.send;
    FR.sending = true;
    btn.disabled = true;
    btn.classList.add('is-busy');

    // one multipart request: the comment and its files are saved together, or not at all
    const body = new FormData();
    body.append('report', cid);                                    // the report whose chat is on screen (the open one, or the chosen month's report)
    body.append('note_no', ctx.noteId || '');
    body.append('section_type', ctx.sectionType || '');
    body.append('row_index', ctx.rowIndex);
    body.append('row_label', ctx.rowEl.querySelector('td')?.innerText || '');
    body.append('comment', text);
    files.forEach(f => body.append('files', f, f.name));

    postForm(COMMENTS_API + 'add_comment', body).then(saved => {
        const box = FR.dom.thread;
        if (box.querySelector('.fr-thread-empty')) {
            box.innerHTML = '';
            FR.thread = { lastAuthor: null, lastTs: 0, lastDay: null };
        }

        appendMessage({
            name: saved && saved.name,
            comment: text,
            files: (saved && saved.files) || [],
            comment_added_by: frappe.session.user,
            creation: (saved && saved.creation) || frappe.datetime.convert_to_system_tz(frappe.datetime.now_datetime())      // stored times are in the system time zone
        });
        const last = box.lastElementChild;
        if (last) last.classList.add('is-new');
        box.scrollTop = box.scrollHeight;

        FR.counts[ctx.key] = (FR.counts[ctx.key] || 0) + 1;
        FR.reportComments[cid] = (FR.reportComments[cid] || 0) + 1;
        renderReportCards();
        FR.rowRoles[ctx.key] = bumpRole(FR.rowRoles[ctx.key], roleOf(frappe.session.user));
        paintMarker(ctx.rowEl, FR.counts[ctx.key]);
        refreshNoteMeta(ctx.rowEl.closest('.fr-note'));
        updateCommentedLegend();
        if (FR.filter.only) applyFilters();
        if (FR.cmtOf !== 'current') refreshCmtList();            // the chat column of that month follows the chat

        // refresh the people strip
        const users = uniq([...FR.dom.stack.querySelectorAll('i[data-u]')].map(i => i.dataset.u).concat(frappe.session.user));
        FR.dom.stack.innerHTML = users.slice(0, 4).map(personChip).join('');
        const n = FR.counts[ctx.key];
        FR.dom.count.textContent = `${n} comment${n > 1 ? 's' : ''} · ${users.length} ${users.length === 1 ? 'person' : 'people'}`;

        FR.dom.input.value = '';
        clearPendingFiles();
        autoGrow();
        frappe.show_alert({ message: files.length ? `Comment sent with ${files.length} ${files.length === 1 ? 'file' : 'files'}` : 'Comment sent', indicator: 'green' });
    }).catch(err => {
        frappe.show_alert({ message: err.message || 'Could not send the comment', indicator: 'red' });      // what was typed and attached stays, so nothing is lost
    }).finally(() => {
        FR.sending = false;
        btn.disabled = false;
        btn.classList.remove('is-busy');
        FR.dom.input.focus({ preventScroll: true });
    });
}
