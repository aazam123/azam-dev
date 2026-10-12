/* =====================================================================
   export.js
   Export: reads every table from the screen and downloads one Excel file with the comments and review.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

// One table of the screen as plain rows: [{kind, cells: [{t, th, cs, rs}]}]. The comment-marker column and the chat column are left out.
// kind is "head" for a header row, or group / total / result for the rows styled that way, so the Excel file can style them too.
function collectTable(table) {
    return [...table.querySelectorAll('tr')].filter(tr => tr.closest('table') === table).map(tr => {
        const cells = [...tr.children].filter(c => /^(TD|TH)$/.test(c.tagName) && !c.classList.contains('fr-gutter') && !c.classList.contains('fr-chatcol'));
        const role = ['fr-group', 'fr-result', 'fr-total'].find(k => tr.classList.contains(k));
        return {
            kind: tr.querySelector('th') ? 'head' : (role ? role.slice(3) : ''),
            cells: cells.map(c => ({ t: c.textContent.replace(/\s+/g, ' ').trim(), th: c.tagName === 'TH' ? 1 : 0, cs: c.colSpan > 1 ? c.colSpan : 0, rs: c.rowSpan > 1 ? c.rowSpan : 0 }))
        };
    });
}

// Every section on screen (hidden by a search or folded closed too, so the file always holds everything): its title, note number and
// its tables and text in order.
function collectSections() {
    return [...FR.dom.sheet.querySelectorAll('.fr-note')].map(note => {
        const blocks = [];
        const walk = el => {
            if (el.tagName === 'TABLE') { blocks.push({ type: 'table', rows: collectTable(el) }); return; }
            if (el.querySelector('table')) { [...el.children].forEach(walk); return; }
            const t = el.textContent.replace(/\s+/g, ' ').trim();
            if (t) blocks.push({ type: 'text', text: t });
        };
        const desc = note.querySelector('.fr-note-desc');
        if (desc) {
            [...desc.children].forEach(walk);
            const plain = desc.textContent.replace(/\s+/g, ' ').trim();
            if (!blocks.length && plain) blocks.push({ type: 'text', text: plain });
        }
        const title = note.querySelector('.fr-note-toggle span');
        const kicker = note.querySelector('.fr-note-kicker');
        return { kicker: kicker ? kicker.textContent.trim() : '', title: title ? title.textContent.trim() : '', note: note.dataset.note || '', blocks };
    });
}

// Export button: sends the screen's tables to the server, which answers with the .xlsx; the browser then saves it. One export at a time.
function exportReport() {
    if (!FR.report || !FR.doc || FR.exporting) return;
    const id = FR.report;
    const meta = FR.reports.find(r => r.name === id);
    const button = () => FR.dom.sheet.querySelector('.fr-export');
    FR.exporting = true;
    if (button()) { button().disabled = true; button().classList.add('is-busy'); }

    const sections = collectSections();
    const body = new FormData();
    body.append('report', id);
    body.append('period', meta ? periodLabel(meta) : '');
    body.append('sections', JSON.stringify(sections));
    frappe.show_alert({ message: 'Preparing the Excel file…', indicator: 'blue' }, 3);

    postForm(PAGE_API + 'export_report', body, true).then(file => {
        const url = URL.createObjectURL(file.blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.filename || `${id}.xlsx`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
        frappe.show_alert({ message: `Exported ${sections.length} ${sections.length === 1 ? 'section' : 'sections'} with comments and review`, indicator: 'green' });
    }).catch(err => {
        frappe.show_alert({ message: err.message || 'Could not export the report', indicator: 'red' });
    }).finally(() => {
        FR.exporting = false;
        if (button()) { button().disabled = false; button().classList.remove('is-busy'); }
    });
}
