/* =====================================================================
   row_markers.js
   The comment marker at the end of every row: its key, its count badge and the row description used by the drawer.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

// For every table row of every section: sets the table up (aligned numbers, look, header gutter), gives each body row a key and a
// comment marker, and makes rows that have a note number clickable (see SCHEDULE JUMP below).
// A row's key is "note|sectionType|rowIndex"; the same key is stored on its comments, so the two always find each other.
function attachRowMarkers() {
    FR.dom.sheet.querySelectorAll('.fr-note').forEach(note => {
        const noteId = note.dataset.note;
        const sectionType = note.dataset.sectionType;

        note.querySelectorAll('table').forEach(table => {
            const tbody = table.querySelector('tbody') || table;
            alignNumericColumns(table);
            decorateTable(table, sectionType);
            table.querySelectorAll('thead tr').forEach(tr => {       // header band must span the marker column too
                if (tr.closest('table') !== table || tr.querySelector('.fr-gutter')) return;
                const th = document.createElement('th');
                th.className = 'fr-gutter';
                tr.appendChild(th);
            });

            [...tbody.querySelectorAll('tr')].forEach((tr, idx) => {
                if (tr.querySelector('th')) {              // header row (no <thead>): keep the grid aligned
                    if (!tr.querySelector('.fr-gutter')) {
                        const th = document.createElement('th');
                        th.className = 'fr-gutter';
                        tr.appendChild(th);
                    }
                    return;
                }

                tr.dataset.rowIndex = idx;
                tr.dataset.search = tr.textContent.toLowerCase();   // before the marker is added

                const td = document.createElement('td');
                td.className = 'fr-gutter';
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'fr-marker';
                td.appendChild(btn);
                tr.appendChild(td);

                const key = rowKey(noteId, sectionType, idx);
                tr.dataset.key = key;
                paintMarker(tr, FR.counts[key] || 0);

                btn.addEventListener('click', e => { e.stopPropagation(); openDrawer(ctxFromRow(tr)); });

                if (scheduleNote(tr)) {
                    tr.classList.add('has-schedule');
                    tr.title = `Open Note ${tr.dataset.schedule}`;
                    tr.addEventListener('click', e => {
                        if (e.target.closest('.fr-gutter, .fr-chatcol, button')) return;
                        jumpToSchedule(tr);
                    });
                }
            });
        });
    });
}

// The row's visible name: its "Particulars" cell (not the (I)/(II) index), or else the first cell with text.
function rowLabel(tr) {
    const c = tr.querySelector('td.fr-label') ||
        [...tr.querySelectorAll('td:not(.fr-gutter)')].find(td => td.textContent.trim());
    return (c ? c.textContent : '').trim();
}

// Shows the comment count on a row: the "+" becomes a number badge, the row gets "has-comments", and the role colours are set.
function paintMarker(tr, count) {
    const btn = tr.querySelector('.fr-marker');
    if (!btn) return;
    tr.classList.toggle('has-comments', count > 0);
    btn.classList.toggle('is-filled', count > 0);
    btn.setAttribute('aria-label', count
        ? `${count} comment${count > 1 ? 's' : ''} on this row`
        : 'Comment on this row');
    btn.innerHTML = count ? `<span>${count > 99 ? '99+' : count}</span>` : ICON.plus;
    setRoleVars(tr, count ? FR.rowRoles[tr.dataset.key] : null);
}

// Describes a table row for the drawer and for saving a comment: note, section, row position and the element itself.
function ctxFromRow(tr) {
    const note = tr.closest('.fr-note');
    return {
        key: tr.dataset.key,
        noteId: note.dataset.note,
        sectionType: note.dataset.sectionType,
        sectionName: note.dataset.section || '',
        rowIndex: Number(tr.dataset.rowIndex),
        rowEl: tr
    };
}
