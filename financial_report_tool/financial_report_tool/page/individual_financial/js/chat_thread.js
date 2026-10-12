/* =====================================================================
   chat_thread.js
   One row's conversation: load it, draw people and messages, live refresh, delete.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

// Fetches every comment of one row (deleted ones too, so they can show as notes) from the report whose chat is on screen.
function fetchThread(ctx) {
    const cid = commentReportId(FR.report);
    if (!cid) return Promise.resolve([]);
    return frappe.xcall(COMMENTS_API + 'get_thread', {
        report: cid,
        note_no: ctx.noteId,
        section_type: ctx.sectionType,
        row_index: ctx.rowIndex
    }).then(list => list || []);
}

// Loads the open row's thread and shows it. Drops the answer if the user already opened another row.
function loadThread(ctx) {
    fetchThread(ctx).then(list => {
        if (!FR.active || FR.active.key !== ctx.key) return;      // drawer moved on
        applyThread(ctx, list);
    }).catch(() => {
        FR.dom.thread.innerHTML = `
            <div class="fr-thread-empty">
                <strong>Comments couldn't be loaded</strong>
                <span>Close the panel and open the row again.</span>
            </div>`;
    });
}

// deleted comments stay in the thread as a note, but never count as comments
const liveOf = list => list.filter(c => !c.is_deleted);

// Puts a freshly loaded thread on screen and brings everything that depends on it up to date: the row's count and role colours,
// the marker, the section pill, the legend, and the drawer header and messages. Used on open, on live refresh and after a delete.
function applyThread(ctx, list) {
    const live = liveOf(list);
    FR.counts[ctx.key] = live.length;
    FR.deletedN[ctx.key] = list.length - live.length;
    FR.rowRoles[ctx.key] = rolesOfList(live);
    paintMarker(ctx.rowEl, live.length);
    refreshNoteMeta(ctx.rowEl.closest('.fr-note'));
    updateCommentedLegend();
    renderPeople(list);
    renderThread(list);
}

// Live refresh: new / deleted comments from colleagues appear without reopening the row
function pollThread() {
    if (!FR.active || FR.sending || document.hidden) return;
    if (!FR.dom.root || !document.body.contains(FR.dom.root) || FR.dom.root.offsetParent === null) return;

    const ctx = FR.active;
    fetchThread(ctx).then(list => {
        if (!FR.active || FR.active.key !== ctx.key || FR.sending) return;
        const live = liveOf(list).length, dead = list.length - live;
        const before = FR.counts[ctx.key] || 0;
        if (live === before && dead === (FR.deletedN[ctx.key] || 0)) return;
        applyThread(ctx, list);
        if (live > before) frappe.show_alert({ message: 'New comment on this row', indicator: 'blue' }, 4);
    }).catch(() => {});
}

// One person's initials chip. Its colour is the role colour when the person has a role (see avatarCls).
function personChip(u) {
    const n = userName(u);
    return `<i${avatarCls(u) ? ` class="${avatarCls(u).trim()}"` : ''} data-u="${esc(u)}" style="--av:${colorFor(n)}" title="${esc(n)}">${esc(initials(n))}</i>`;
}

// Header of the drawer: up to 4 initials chips of the people who commented (+N for more) and the "N comments · N people" text.
function renderPeople(list) {
    const live = liveOf(list);
    const people = uniq(live.map(c => c.comment_added_by).filter(Boolean));
    FR.dom.stack.innerHTML = people.slice(0, 4).map(personChip).join('') + (people.length > 4 ? `<i class="more">+${people.length - 4}</i>` : '');

    const n = live.length, dead = list.length - n;
    FR.dom.count.textContent = (n
        ? `${n} comment${n > 1 ? 's' : ''} · ${people.length} ${people.length === 1 ? 'person' : 'people'}`
        : 'No comments yet') + (dead ? ` · ${dead} deleted` : '');
}

// Fills the thread box with all messages of the row, or an empty-state hint when there are none.
function renderThread(list) {
    const box = FR.dom.thread;
    box.innerHTML = '';
    FR.thread = { lastAuthor: null, lastTs: 0, lastDay: null };

    if (!list.length) {
        box.innerHTML = `
            <div class="fr-thread-empty">
                <div class="fr-empty-mark is-small"></div>
                <strong>No comments on this row${FR.cmtOf !== 'current' ? ' in ' + esc(FR.cmtLabel) : ' yet'}</strong>
                <span>${FR.canComment ? (FR.cmtOf !== 'current' ? `Start the conversation below. It is saved on the ${esc(FR.cmtLabel)} report.` : 'Start the conversation below. Use a quick note or write your own.') : 'Comments added by managers will appear here.'}</span>
            </div>`;
        return;
    }

    list.forEach(appendMessage);
    box.scrollTop = box.scrollHeight;
}

// Adds one message to the thread: a day divider when the day changes, and no repeated name/avatar for consecutive messages
// of the same person within 5 minutes.
function appendMessage(c) {
    const box = FR.dom.thread;
    const d = parseDate(c.creation);
    const day = dayKey(c.creation);

    if (day !== FR.thread.lastDay) {
        const div = document.createElement('div');
        div.className = 'fr-day';
        div.textContent = dayLabel(c.creation);
        box.appendChild(div);
        FR.thread.lastDay = day;
        FR.thread.lastAuthor = null;
    }

    const grouped = !c.is_deleted && FR.thread.lastAuthor === c.comment_added_by && (d - FR.thread.lastTs) < 5 * 60 * 1000;
    box.appendChild(messageNode(c, grouped));
    FR.thread.lastAuthor = c.is_deleted ? null : c.comment_added_by;
    FR.thread.lastTs = d;
}

// One message as an element. Own messages sit on the right without avatar; others on the left with the role-coloured initials chip.
// A deleted comment is only a short note ("Comment deleted by X, time"); its text is never shown.
function messageNode(c, grouped) {
    const el = document.createElement('article');
    if (c.name) el.dataset.name = c.name;

    // deleted: keep the place in the conversation, hide the text, say who deleted it and when
    if (c.is_deleted) {
        const who = userName(c.deleted_by) + (c.deleted_by === frappe.session.user ? ' (you)' : '');
        el.className = 'fr-deleted';
        el.innerHTML = `<span>${ICON.trash}Comment deleted by <b>${esc(who)}</b>${c.deleted_on ? `<time>${esc(timeLabel(c.deleted_on))}</time>` : ''}</span>`;
        return el;
    }

    const own = c.comment_added_by === frappe.session.user;
    const name = userName(c.comment_added_by);
    el.className = `fr-msg ${own ? 'is-own' : ''} ${grouped ? 'is-grouped' : ''}`;

    const canDelete = !!c.name && (own || FR.canComment);      // the server enforces the same rule
    const bubble = `
        <div class="fr-bubble">
            <p class="fr-msg-text">${esc(c.comment)}</p>
            ${(c.files && c.files.length) ? `<div class="fr-msg-files">${filesNode(c.files)}</div>` : ''}
            <div class="fr-bubble-foot">
                ${canDelete ? `<button type="button" class="fr-msg-del" title="Delete comment" aria-label="Delete comment">${ICON.trash}</button>` : ''}
                <time>${esc(timeLabel(c.creation))}</time>
            </div>
        </div>`;

    el.innerHTML = own
        ? `<div class="fr-msg-col">${grouped ? '' : '<span class="fr-author">You</span>'}${bubble}</div>`
        : `<div class="fr-avatar${avatarCls(c.comment_added_by)}" style="--av:${colorFor(name)}" aria-hidden="true">${esc(initials(name))}</div>
           <div class="fr-msg-col">${grouped ? '' : `<span class="fr-author" style="--av:${colorFor(name)}">${esc(name)}</span>`}${bubble}</div>`;
    return el;
}

// Delete button on a message: asks first, then the server soft-deletes it (the row stays as "deleted by X").
// Afterwards the counts, report cards and the open thread are refreshed from the server.
function deleteComment(name) {
    const ctx = FR.active;
    if (!ctx || !name) return;
    frappe.confirm('Delete this comment? It will stay in the thread as "deleted by you".', () => {
        frappe.xcall('financial_report_tool.financial_report_tool.doctype.fr_financial_report_comments.fr_financial_report_comments.delete_comment', { name })
            .then(() => {
                const cid = commentReportId(FR.report);
                if (cid) FR.reportComments[cid] = Math.max(0, (FR.reportComments[cid] || 1) - 1);
                if (FR.cmtOf !== 'current') refreshCmtList();
                renderReportCards();
                if (FR.active && FR.active.key === ctx.key) {
                    return fetchThread(ctx).then(list => {
                        if (FR.active && FR.active.key === ctx.key) applyThread(ctx, list);
                    });
                }
            })
            .then(() => {
                if (FR.filter.only) applyFilters();
                frappe.show_alert({ message: 'Comment deleted', indicator: 'green' });
            });
    });
}
