/* =====================================================================
   comments_of.js
   The Comments of month switch: which report's chat is on screen, the chat column of that month, counts per row.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

// ---------------------------------------------------------------------
// "COMMENTS OF" switch: any month that has a report of this company
//   Reports of different months are separate documents, and the table rows keep the same positions from
//   month to month. So on the November report the same row can show the chat written on the September report.
//   The chat of the chosen month is a normal chat: what is written or deleted is saved on that month's report.
//   FR.cmtOf is 'current' (the open report) or a month key like "2025-2026|October".
// ---------------------------------------------------------------------
// "2025-2026|October": the month of a monthly report (same key = same month, whatever the company), or null for other reports
function monthKey(r) {
    return r && r.type === 'Monthly' && r.fy && r.cm ? `${r.fy}|${r.cm}` : null;
}

// The monthly report of `company` for a month key, or null
function monthReport(company, key) {
    return FR.reports.find(r => r.company === company && monthKey(r) === key) || null;
}

// which report's comments are on screen for `reportId` (null = this company has no report for the chosen month)
function commentReportId(reportId) {
    if (FR.cmtOf === 'current') return reportId;
    const meta = FR.reports.find(r => r.name === reportId);
    const target = meta && monthReport(meta.company, FR.cmtOf);
    return target ? target.name : null;
}

// All live (not deleted) comments of one report, with just the fields the page needs. Empty list when there is no such report.
function fetchCommentRows(cid) {
    if (!cid) return Promise.resolve([]);
    return frappe.xcall('frappe.client.get_list', {
        doctype: FR_CONFIG.COMMENT_DOCTYPE,
        filters: { financial_report: cid, is_deleted: 0 },
        fields: ['name', 'note_no', 'section_type', 'row_index', 'row_label', 'comment', 'comment_added_by', 'creation'],
        limit_page_length: 0
    }).then(list => list || []);
}

// Remembers the comments of the month on screen: how many per row (FR.counts) and which roles wrote them (FR.rowRoles).
// Row keys are built from note number, section type and row position, the same way for the table rows.
function applyCommentCounts(list) {
    FR.counts = {};
    FR.rowRoles = {};
    FR.cmtList = list;
    FR.deletedN = {};
    const byRow = {};
    list.forEach(c => {
        const k = rowKey(c.note_no, c.section_type, c.row_index);
        FR.counts[k] = (FR.counts[k] || 0) + 1;
        (byRow[k] = byRow[k] || []).push(c);
    });
    Object.keys(byRow).forEach(k => { FR.rowRoles[k] = rolesOfList(byRow[k]); });
}

// Adds the "{Mon YYYY} chat" column after "Year Ended ...": for each row, up to 3 comments of the chosen month, grouped by person.
// Only plain one-row-header tables get it (the grid of a two-row header such as Investments would shift).
// It is shown only while another month is chosen in "Comments of" and is removed again when you switch back.
function paintChatColumn() {
    FR.dom.sheet.querySelectorAll('.fr-chatcol').forEach(c => c.remove());
    if (FR.cmtOf === 'current' || !Array.isArray(FR.cmtList) || !FR.doc) return;
    const by = new Map();
    FR.cmtList.slice().sort((a, b) => String(a.creation).localeCompare(String(b.creation))).forEach(c => {
        const k = rowKey(c.note_no, c.section_type, c.row_index);
        if (!by.has(k)) by.set(k, []);
        by.get(k).push(c);
    });
    const SHOW = 3;
    FR.dom.sheet.querySelectorAll('.fr-table').forEach(table => {
        const trs = [...table.querySelectorAll('tr')].filter(r => r.closest('table') === table);
        const heads = trs.filter(r => r.querySelector('th'));
        const body = trs.filter(r => r.dataset.key);
        if (heads.length !== 1 || !body.length) return;
        const hg = heads[0].querySelector('th.fr-gutter');
        if (!hg) return;
        const th = document.createElement('th');
        th.className = 'fr-chatcol';
        th.textContent = `${FR.cmtLabel} chat`;
        th.title = `Chat of ${FR.cmtLabel}, row by row`;
        hg.before(th);
        body.forEach(tr => {
            const g = tr.querySelector('td.fr-gutter');
            if (!g) return;
            const list = by.get(tr.dataset.key) || [];
            const td = document.createElement('td');
            td.className = 'fr-chatcol' + (list.length ? ' has-chat' : '');
            if (list.length) {
                const people = new Map();
                list.forEach(c => { const u = c.comment_added_by || ''; if (!people.has(u)) people.set(u, []); people.get(u).push(c); });
                let left = SHOW, html = '';
                people.forEach((items, u) => {
                    if (left <= 0) return;
                    const n = userName(u), take = items.slice(0, left);
                    left -= take.length;
                    html += `<div class="fr-cc-u"><span class="fr-cc-av${avatarCls(u)}" style="--av:${colorFor(n)}">${esc(initials(n))}</span><div class="fr-cc-b"><b>${esc(n)}${u === frappe.session.user ? ' (you)' : ''}</b>` +
                        take.map(c => `<span class="fr-cc-t">${esc(c.comment)}</span><time class="fr-cc-d">${esc(fullTimeLabel(c.creation))}</time>`).join('') + `</div></div>`;
                });
                if (list.length > SHOW) html += `<span class="fr-cc-more">+${list.length - SHOW} more · click to open</span>`;
                td.innerHTML = html;
                td.title = 'Open this row’s chat';
            }
            g.before(td);
        });
    });
}

// Opens the chat of a row from its key (clicked in the previous-month chat column), scrolling to the row and flashing it.
function openCommentRow(key) {
    const tr = [...FR.dom.sheet.querySelectorAll('tr[data-key]')].find(r => r.dataset.key === key);
    if (!tr) return frappe.show_alert({ message: 'This row is not in the open report', indicator: 'orange' });
    revealRow(tr);
    openDrawer(ctxFromRow(tr));
    flashRow(tr);
}

// Rebuilds the "Comments of" menu: "This month" (the open report) plus one entry for every other month that has a report of the same
// company. While no report is open it lists the months of the filtered company (or of all companies). A chosen month that this
// company has no report for falls back to "this month".
function refreshCommentSelect() {
    const sel = FR.dom.selCmt;
    if (!sel) return;
    const meta = FR.report ? FR.reports.find(r => r.name === FR.report) : null;
    const own = meta ? monthKey(meta) : null;
    const months = new Map();                       // month key -> one report of that month (gives the label and the sort order)
    FR.reports.forEach(r => {
        const k = monthKey(r);
        if (!k || k === own || months.has(k)) return;
        if (meta ? r.company === meta.company : (!FR.F.company || r.company === FR.F.company)) months.set(k, r);
    });

    if (FR.cmtOf !== 'current') {
        if (meta && FR.cmtOf === own) {
            FR.cmtOf = 'current';                   // the chosen month is the open report itself
        } else if (!months.has(FR.cmtOf)) {
            const any = meta ? null : FR.reports.find(r => monthKey(r) === FR.cmtOf);     // no report open: keep the choice if some report has that month
            if (any) {
                months.set(FR.cmtOf, any);
            } else {
                FR.cmtOf = 'current';
                if (meta) frappe.show_alert({ message: 'No report found for that month. Showing this month’s comments.', indicator: 'orange' });
            }
        }
    }
    FR.cmtLabel = FR.cmtOf === 'current' ? '' : periodLabel(months.get(FR.cmtOf));

    const list = [...months.entries()].sort((a, b) => (a[1].year - b[1].year) || (a[1].month - b[1].month));
    sel.innerHTML =
        `<option value="current">${esc(meta ? 'This month · ' + periodLabel(meta) : 'This month')}</option>` +
        list.map(([k, r]) => `<option value="${esc(k)}">${esc(periodLabel(r))}</option>`).join('');
    sel.value = FR.cmtOf;
    sel.classList.toggle('has-value', FR.cmtOf !== 'current');
}

// Reloads the comments of the month on screen after something was written or deleted in another month's chat,
// so the chat column, the report cards and the status line stay true.
function refreshCmtList() {
    const id = FR.report, cid = commentReportId(id);
    return fetchCommentRows(cid).then(list => {
        if (id !== FR.report || FR.cmtOf === 'current') return;
        FR.cmtList = list;
        paintChatColumn();
        renderReportCards();
    }).catch(() => {});
}

// "Comments of" menu changed (this month or any other month): reload the comments of that month and repaint
// the row markers, note pills, legend and the chat column. If a row is open, its chat reloads for the new month too.
function setCommentMonth(of) {
    if (of === FR.cmtOf) return;
    FR.cmtOf = of;
    try { localStorage.setItem(FR.KEYS.cmt, of); } catch (e) {}
    refreshCommentSelect();
    if (!FR.report || !FR.doc) return;
    const id = FR.report, want = FR.cmtOf;
    fetchCommentRows(commentReportId(id)).then(list => {
        if (id !== FR.report || want !== FR.cmtOf) return;
        applyCommentCounts(list);
        FR.dom.sheet.classList.toggle('fr-othermonth', want !== 'current');
        FR.dom.sheet.querySelectorAll('tr[data-key]').forEach(tr => paintMarker(tr, FR.counts[tr.dataset.key] || 0));
        refreshAllNoteMeta();
        updateCommentedLegend();
        paintChatColumn();
        renderReportCards();
        if (FR.filter.only || FR.filter.q) applyFilters();
        if (FR.active) openDrawer(FR.active);                   // reload the open row's chat for the chosen month
    }).catch(() => frappe.show_alert({ message: 'Couldn’t load the comments', indicator: 'red' }));
}
