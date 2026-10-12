/* =====================================================================
   table_decoration.js
   Tags the stored HTML tables with classes (group, total, result, note pill...); the CSS does the painting.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

// Right-align the columns that hold amounts so digits line up like a ledger (a column counts as amounts when 70% of its cells look like numbers).
function alignNumericColumns(table) {
    const rows = [...table.querySelectorAll('tr')].filter(r => r.closest('table') === table);
    if (!rows.length) return;
    if (rows.some(r => !r.querySelector('th') && r.querySelector('[colspan]:not([colspan="1"])'))) return;   // merged BODY cells: leave alone

    const NUM = /^[\s(+-]*[^\d\s]{0,3}\s*[\d.,]+\s*%?\)?\s*[A-Za-z]{0,3}$|^[-–—]$/;
    const cols = Math.max(...rows.map(r => r.children.length));

    for (let c = 1; c < cols; c++) {            // column 0 = row label, stays left
        let total = 0, numeric = 0;
        rows.forEach(r => {
            const cell = r.children[c];
            if (!cell || cell.tagName === 'TH') return;
            const t = cell.textContent.trim();
            if (!t) return;
            total++;
            if (NUM.test(t)) numeric++;
        });
        if (total && numeric / total >= 0.7) {
            rows.forEach(r => r.children[c] && r.children[c].classList.add('fr-num'));
        }
    }
}

/* ---------------------------------------------------------------------
   TABLE DECORATION
   The stored HTML carries its look in inline styles (black borders, white
   and green cell fills). Here we only TAG what each row/column means; the
   stylesheet then restyles it (and overrides the inline styles).
     fr-cur     current-period column      fr-label   "Particulars" column
     fr-idx     (I) (II) index column      fr-noteno  "Note No." column
     fr-group   heading row, no figures    fr-total   bold row with figures
     fr-result  (III)-style key result     fr-neg/nil negative / empty value
--------------------------------------------------------------------- */
const STATEMENT_TYPES = ['Profit & Loss', 'Balance Sheet', 'Cash Flow'];

const ROMAN_IDX = /^\([ivxlcdm]+\)$/i;

const NEG_VALUE = /^(-\s*[\d.,]+|\([\d.,\s]+\))\s*%?$/;

const SECTION_GLYPH = { 'Profit & Loss': 'P&L', 'Balance Sheet': 'BS', 'Cash Flow': 'CF', 'Equity': 'EQ', 'Consolidation Note': 'CN' };

// Wraps the content of a cell in <span class="cls"> (used for the roman index and note number pills). Empty cells stay empty.
function wrapInPill(cell, cls) {
    if (!cell || !cell.textContent.trim()) return;
    const s = document.createElement('span');
    s.className = cls;
    while (cell.firstChild) s.appendChild(cell.firstChild);
    cell.appendChild(s);
}

// Gives a stored statement table its look. The stored HTML carries inline styles, so this only TAGS things with classes
// (see the class list above) and the CSS does the painting. It also pads decimals so the points line up.
// Order inside: remove hash links, wrap the table in a scroll card, find the column positions from the header, tag each row
// (group / total / result / item), tag each number cell (negative / empty), then pad decimals.
function decorateTable(table, sectionType) {
    table.classList.add('fr-table');

    // The stored HTML wraps row names in links such as <a href="#note_31_other_income">. Frappe's body-level click handler turns every
    // "#..." link into a route, so a click ends on "Page #note_31_other_income not found". The row itself already jumps to the note,
    // so these links lose their href (the text stays) and are never followed.
    table.querySelectorAll('a[href^="#"]').forEach(a => {
        a.dataset.noteLink = a.getAttribute('href');
        a.removeAttribute('href');
    });
    if (STATEMENT_TYPES.includes(sectionType)) table.classList.add('fr-statement');

    // card with horizontal scroll (nested tables stay inside their parent cell)
    const host = table.parentElement;
    if (host && !host.closest('table') && !host.classList.contains('fr-table-wrap')) {
        const wrap = document.createElement('div');
        wrap.className = 'fr-table-wrap';
        table.replaceWith(wrap);
        wrap.appendChild(table);
    }

    table.querySelectorAll('[style*="#e8f5e8" i]').forEach(c => c.classList.add('fr-cur'));

    const own = tr => tr.closest('table') === table;
    const allRows = [...table.querySelectorAll('tr')].filter(own);
    const head = allRows.find(r => r.parentElement.tagName === 'THEAD') || allRows.find(r => r.querySelector('th'));
    // a header cell with colspan="2" stands for 2 columns; expand so header indexes line up with body cells
    const heads = head ? [...head.children].flatMap(c => Array(Math.max(1, parseInt(c.getAttribute('colspan'), 10) || 1)).fill(c.textContent.trim().toLowerCase())) : [];
    const noteCol = heads.findIndex(h => /^note\s*no/.test(h));
    let labelCol = heads.findIndex(h => /^particulars/.test(h));
    if (labelCol < 0) labelCol = 0;
    // newer reports use <th colspan="2">Particulars</th>: the first of those two columns is the (I)/(II) index, the last is the label
    let spanStart = labelCol;
    while (heads[labelCol + 1] !== undefined && heads[labelCol + 1] === heads[spanStart] && /^particulars/.test(heads[spanStart])) labelCol++;
    const idxCol = labelCol > spanStart ? spanStart : (labelCol > 0 && heads.slice(0, labelCol).every(h => h === '') ? 0 : -1);

    const body = allRows.filter(r => r !== head && !r.querySelector('th'));
    const merged = !table.querySelector('.fr-num');       // colspan tables are not column-aligned

    body.forEach(tr => {
        const cells = [...tr.children];
        const aligned = cells.length === heads.length;

        if (aligned) {
            if (noteCol >= 0) {
                cells[noteCol].classList.remove('fr-num');
                cells[noteCol].classList.add('fr-noteno');
                wrapInPill(cells[noteCol], 'fr-notepill');
            }
            cells[labelCol].classList.add('fr-label');
            if (idxCol >= 0) cells[idxCol].classList.add('fr-idx');

            // "&nbsp;" x4 per level  ->  real indentation
            const lab = cells[labelCol];
            const lead = lab.textContent.match(/^\u00a0+/);
            if (lead) {
                const node = document.createTreeWalker(lab, NodeFilter.SHOW_TEXT).nextNode();
                if (node) node.nodeValue = node.nodeValue.replace(/^\u00a0+/, '');
                lab.style.setProperty('--ind', Math.round(lead[0].length / 4));
            }
        }

        const roman = !!cells[0] && ROMAN_IDX.test(cells[0].textContent.trim());
        if (roman) {
            cells[0].classList.add('fr-roman');
            wrapInPill(cells[0], 'fr-romanpill');
        }

        let role = '';
        if (cells.some(c => /font-weight:\s*bold/i.test(c.getAttribute('style') || ''))) {
            const hasVals = merged
                ? cells.slice(1).some(c => /\d/.test(c.textContent))
                : cells.some(c => c.classList.contains('fr-num') && /\d/.test(c.textContent));
            role = !hasVals ? 'fr-group' : roman ? 'fr-result' : 'fr-total';
            if (!hasVals && !roman && aligned && /^total/i.test(cells[labelCol].textContent.trim())) role = 'fr-total';   // "Total x" with nothing to sum yet
            tr.classList.add(role);
        }

        // plain line items sit one level under their heading
        if (aligned && !role && table.classList.contains('fr-statement')) cells[labelCol].classList.add('fr-item');

        cells.forEach(c => {
            if (!c.classList.contains('fr-num')) return;
            const t = c.textContent.trim();
            if (NEG_VALUE.test(t)) c.classList.add('fr-neg');
            else if (/^[-–—]$/.test(t)) c.classList.add('fr-nil');
            else if (!t && role !== 'fr-group') c.classList.add('fr-blank');     // shown as a quiet dash
        });
    });

    // Pad decimals per column so the points line up (759.71 -> 759.710 next to 1046.778). Display only.
    const cols = {};
    body.forEach(tr => {
        const cells = [...tr.children];
        if (cells.length !== heads.length) return;
        cells.forEach((c, i) => {
            if (c.classList.contains('fr-num') && /^-?\d+(\.\d+)?$/.test(c.textContent.trim())) (cols[i] = cols[i] || []).push(c);
        });
    });
    Object.values(cols).forEach(list => {
        const dp = Math.max(...list.map(c => (c.textContent.trim().split('.')[1] || '').length));
        if (!dp || dp > 4) return;
        list.forEach(c => {
            const t = c.textContent.trim(), have = (t.split('.')[1] || '').length;
            if (have < dp) c.textContent = (have ? t : t + '.') + '0'.repeat(dp - have);
        });
    });
}
