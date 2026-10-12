/* =====================================================================
   commented_legend.js
   The N rows have comments line: counts, reveal a hidden row, open the next commented row.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

/* ---------------------------------------------------------------------
   COMMENTED-ROWS LEGEND  ("N rows have comments" -> click to jump)
   The number is counted from the rows on screen, so it always matches
   what the user can actually open. Each click opens the next commented
   row, in table order, and wraps around after the last one.
--------------------------------------------------------------------- */
// Every row of the open report that has at least one comment, in table order.
function commentedRows() {
    return [...FR.dom.sheet.querySelectorAll('tr[data-key].has-comments')];
}

// Updates the legend line: "N rows have comments" with the total, coloured by the roles that commented; hidden when nothing is commented.
function updateCommentedLegend() {
    const btn = FR.dom.sheet.querySelector('.fr-legend-comments');
    if (!btn) return;
    const rows = commentedRows();
    const total = rows.reduce((n, tr) => n + (FR.counts[tr.dataset.key] || 0), 0);

    btn.hidden = !rows.length;
    setRoleVars(btn.querySelector('i'), unionRoles(rows));
    btn.querySelector('i').textContent = rows.length > 99 ? '99+' : rows.length;
    btn.querySelector('span').textContent =
        `${rows.length === 1 ? 'Row has' : 'Rows have'} ${FR.cmtOf !== 'current' ? FR.cmtLabel + ' ' : ''}comments` +
        (total !== rows.length ? ` · ${total} total` : '');
    btn.title = `Open ${rows.length === 1 ? 'the commented row' : 'next commented row'}`;
}

// Makes a row reachable: undoes the search / "Commented only" filters that hide it and opens its section.
function revealRow(tr) {
    if (tr.classList.contains('is-hidden')) {
        FR.filter = { q: '', only: false };
        const input = FR.dom.sheet.querySelector('.fr-search input');
        const toggle = FR.dom.sheet.querySelector('.fr-toggle');
        if (input) input.value = '';
        if (toggle) toggle.setAttribute('aria-pressed', 'false');
        applyFilters();
    }
    const note = tr.closest('.fr-note');
    if (note) note.classList.remove('is-collapsed');
}

// Legend click: open the next commented row after the open one (the first when none is open), wrapping at the end.
function openNextCommented() {
    const rows = commentedRows();
    if (!rows.length) return;

    // continue after the row that is open now; otherwise start from the first one
    const at = FR.active ? rows.indexOf(FR.active.rowEl) : -1;
    const next = rows[(at + 1) % rows.length];

    revealRow(next);
    openDrawer(ctxFromRow(next));
}
