/* =====================================================================
   chat_drawer.js
   The chat drawer: open the chat of one row, close it, step to the previous or next commented row.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

// Opens the chat of one row: shows the row title and a loading state, slides the drawer in, then loads its thread (loadThread).
// `ctx` says which row: {key, noteId, sectionType, sectionName, rowIndex, rowEl}.
function openDrawer(ctx) {
    if (FR.active && FR.active.rowEl) FR.active.rowEl.classList.remove('is-active');
    FR.active = ctx;
    ctx.rowEl.classList.add('is-active');

    const rowText = rowLabel(ctx.rowEl) || `Row ${ctx.rowIndex + 1}`;
    FR.dom.kicker.textContent = `${FR.cmtOf !== 'current' ? FR.cmtLabel + ' · ' : ''}Note ${ctx.noteId}${ctx.sectionName ? ' · ' + ctx.sectionName : ''}`;
    FR.dom.rowTitle.textContent = rowText;
    FR.dom.stack.innerHTML = '';
    FR.dom.count.textContent = FR.counts[ctx.key] ? 'Loading…' : 'No comments yet';

    FR.dom.shell.classList.add('drawer-open');
    FR.dom.drawer.setAttribute('aria-hidden', 'false');

    // The drawer is sticky; from the top of the page it sits lower than its pinned spot and its
    // composer would fall below the fold. Bring the page up to where it pins.
    const pin = parseFloat(getComputedStyle(FR.dom.root).getPropertyValue('--sticky-top')) || 92;
    const gap = FR.dom.shell.getBoundingClientRect().top - pin;
    if (gap > 4) window.scrollBy({ top: gap, behavior: 'smooth' });

    // the chat of the chosen month is a normal chat: writing goes to that month's report
    const canWrite = FR.canComment;
    FR.dom.composer.style.display = canWrite ? 'flex' : 'none';
    FR.dom.input.placeholder = FR.cmtOf !== 'current' ? `Write in the ${FR.cmtLabel} chat…` : 'Write a comment…';
    FR.dom.readonly.style.display = canWrite ? 'none' : 'block';
    FR.dom.input.value = '';
    clearPendingFiles();
    autoGrow();

    FR.dom.thread.innerHTML = `<div class="fr-skeleton is-thread"><i></i><i></i><i></i></div>`;
    loadThread(ctx);

    ctx.rowEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    if (canWrite) setTimeout(() => FR.dom.input.focus({ preventScroll: true }), 240);
}

// Closes the chat drawer and clears the active row.
function closeDrawer() {
    if (!FR.dom.shell) return;
    if (FR.active && FR.active.rowEl) FR.active.rowEl.classList.remove('is-active');
    FR.active = null;
    clearPendingFiles();
    FR.dom.shell.classList.remove('drawer-open');
    FR.dom.drawer.setAttribute('aria-hidden', 'true');
}

// Up / down arrows in the drawer: jump to the previous / next commented row that is not hidden by a filter.
function stepComment(dir) {
    if (!FR.active) return;
    const rows = [...FR.dom.sheet.querySelectorAll('tr[data-key]:not(.is-hidden)')];
    const i = rows.indexOf(FR.active.rowEl);
    for (let j = i + dir; j >= 0 && j < rows.length; j += dir) {
        if (rows[j].classList.contains('has-comments')) {
            const note = rows[j].closest('.fr-note');
            if (note) note.classList.remove('is-collapsed');
            openDrawer(ctxFromRow(rows[j]));
            return;
        }
    }
    frappe.show_alert({
        message: dir > 0 ? 'No more commented rows below' : 'No more commented rows above',
        indicator: 'orange'
    });
}
