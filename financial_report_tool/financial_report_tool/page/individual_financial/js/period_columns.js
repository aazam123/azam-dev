/* =====================================================================
   period_columns.js
   FTM, Previous Month and Previous FTM columns, read from the previous month's own report.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

// ---------------------------------------------------------------------
// PERIOD COLUMNS  (FTM and Previous FTM on Balance Sheet, P&L and Cash Flow)
//   P&L / Cash Flow already store: Month Ended | FTM | Previous Month Ended | Year Ended.
//   Balance Sheet only stores:     Month Ended | Year Ended.
//   Added here:  Balance Sheet -> FTM, Previous Month, Previous FTM     P&L / Cash Flow -> Previous FTM
//   "Previous FTM" is the movement of the previous month. It is not stored in this report, so it is taken from
//   the previous month's own report (its FTM column, or for the Balance Sheet its closing figure minus the
//   closing figure of the month before it). Rows are matched by their label, not by position.
// ---------------------------------------------------------------------
// Cache of loaded reports, so switching reports does not fetch the same previous month again.
const frDocs = {};

const getReportDoc = name => frDocs[name] || (frDocs[name] = frappe.xcall('frappe.client.get', { doctype: FR_CONFIG.DOCTYPE, name }).catch(e => { delete frDocs[name]; throw e; }));

// the monthly report of the same company for the month before `d` (April's previous month is March of the last fiscal year)
function findPrevMonthReport(d) {
    if (!d || !d.previous_month) return null;
    const fy = FR.fiscalYears[d.fiscal_year];
    const startMonth = fy ? parseDate(fy.year_start_date).getMonth() + 1 : 4;
    const year = toMonth(d.current_month) === startMonth ? d.previous_fiscal_year : d.fiscal_year;
    return FR.reports.find(r => r.name !== d.name && r.type === 'Monthly' && r.company === d.company && r.fy === year && r.cm === d.previous_month) || null;
}

// Newer reports keep the figures as JSON in table_data; older ones keep HTML there.
const hasJsonData = sec => (sec && sec.table_data || '').trim().startsWith('[');

// Loads what "Previous FTM" needs: the previous month's report and, only if its Balance Sheet stores no JSON figures, the month before it.
// Returns null for yearly reports and when there is no previous month. A failed second load is ignored (the column is then left out).
function loadComparison(doc) {
    if (doc.report_type !== 'Monthly') return Promise.resolve(null);
    const prevMeta = findPrevMonthReport(doc);
    if (!prevMeta) return Promise.resolve(null);
    return getReportDoc(prevMeta.name).then(prev => {
        const out = { prev, prevMeta, prevPrev: null };
        const prevBS = (prev.financial_report_details || []).find(s => s.section_type === 'Balance Sheet');
        const ppMeta = prevBS && !hasJsonData(prevBS) ? findPrevMonthReport(prev) : null;      // Balance Sheet needs the month before it
        return ppMeta ? getReportDoc(ppMeta.name).then(pp => { out.prevPrev = pp; return out; }).catch(() => out) : out;
    });
}

// A row label compared the same way everywhere: no non-breaking spaces, single spaces, lower case.
const labelKey = t => String(t || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase();

// "1,234.5" -> 1234.5, "(12)" or "-12" -> -12, "-" or empty -> 0, text -> null (not a number).
function parseAmount(t) {
    t = String(t == null ? '' : t).replace(/\u00a0/g, ' ').trim();
    if (!t || /^[-–—]$/.test(t)) return 0;
    if (/[a-z]/i.test(t)) return null;
    const n = parseFloat(t.replace(/[(),\s-]/g, ''));
    return isNaN(n) ? null : (/^\(.*\)$/.test(t) || t.startsWith('-') ? -n : n);
}

// Finds which column is which in a statement table (Particulars, Month Ended, FTM, Year Ended...). Header cells are expanded by
// colspan, so a header index is also the body cell index. Returns null when the table is not a plain statement.
function statementLayout(table) {
    const trs = [...table.querySelectorAll('tr')].filter(tr => tr.closest('table') === table);
    const head = trs.find(tr => tr.querySelector('th'));
    if (!head || head.querySelector('[rowspan]') || table.dataset.fc) return null;     // two-row headers and FC | INR tables are left as they are
    const heads = [];
    [...head.children].forEach(th => {
        const span = Math.max(1, parseInt(th.getAttribute('colspan'), 10) || 1);
        for (let i = 0; i < span; i++) heads.push({ th, text: th.textContent.trim().replace(/\s+/g, ' ') });
    });
    const body = trs.filter(tr => tr !== head && !tr.querySelector('th'));
    const find = re => heads.findIndex(h => re.test(h.text));
    const months = heads.map((h, i) => /^month ended/i.test(h.text) ? i : -1).filter(i => i >= 0);
    const part = find(/^particulars/i);
    if (part < 0 || !months.length || !body.length || !body.every(tr => tr.children.length === heads.length)) return null;
    let labelIdx = part;
    while (heads[labelIdx + 1] && heads[labelIdx + 1].th === heads[part].th) labelIdx++;     // "Particulars" may span the index + label cells
    return { heads, body, labelIdx, cur: months[0], prev: months.length > 1 ? months[1] : -1, ftm: find(/^ftm$/i), year: find(/^year ended/i) };
}

// One unique key per body row from its label. Repeated labels get "#1", "#2"... so they still match row for row.
function rowKeys(lay) {
    const seen = {};
    return lay.body.map(tr => {
        const base = labelKey(tr.children[lay.labelIdx].textContent);
        seen[base] = (seen[base] || 0) + 1;
        return base + '#' + seen[base];
    });
}

// Reads one section of another report (the previous month's) into a map: row label -> {cur, ftm, prev, jsonPrev} figures.
// Returns null when that section is missing or its table does not have the expected columns.
function readStatement(doc, type, sectionName) {
    const sec = (doc && doc.financial_report_details || []).find(s => s.section_type === type && (type !== 'Consolidation Note' || s.section === sectionName));
    if (!sec || !sec.section_description) return null;
    const box = document.createElement('div');
    box.innerHTML = sec.section_description;
    const table = box.querySelector('table');
    const lay = table && statementLayout(table);
    if (!lay) return null;
    let json = null;
    try { const j = JSON.parse(sec.table_data || ''); if (Array.isArray(j) && j.length === lay.body.length) json = j; } catch (e) { /* older reports saved HTML here */ }
    const at = (tr, k) => k >= 0 ? parseAmount(tr.children[k].textContent) : null;
    const rows = new Map();
    rowKeys(lay).forEach((key, i) => {
        const tr = lay.body[i];
        const jp = json && json[i].previous_month_amount != null ? json[i].previous_month_amount : null;
        rows.set(key, { cur: at(tr, lay.cur), ftm: at(tr, lay.ftm), prev: at(tr, lay.prev), jsonPrev: jp });
    });
    return rows;
}

// Adds the missing period columns to one table so every statement and schedule reads:
//   Month Ended | FTM | Previous Month Ended | Previous FTM | Year Ended
function addPeriodColumns(note, section, doc, cmp) {
    if (doc.report_type !== 'Monthly' || !note) return;
    const table = note.querySelector('.fr-note-desc table');
    if (!table || table.dataset.frPeriods) return;
    // only plain one-row headers: tables with rowspan/colspan header groups (e.g. Investments) cannot take extra columns safely
    const headRows = [...table.querySelectorAll('tr')].filter(r => r.closest('table') === table && r.querySelector('th'));
    if (headRows.length !== 1 || headRows[0].querySelector('[rowspan]')) return;
    const lay = statementLayout(table);
    if (!lay) return;                                           // other layouts (Equity...) are left alone
    const type = section.section_type;
    const needFtm = lay.ftm < 0, needPrev = lay.prev < 0;
    const keys = rowKeys(lay);
    const cell = (tr, k) => parseAmount(tr.children[k].textContent);

    let json = null;
    try { const j = JSON.parse(section.table_data || ''); if (Array.isArray(j) && j.length === lay.body.length) json = j; } catch (e) { /* HTML in older reports */ }
    const P = cmp && readStatement(cmp.prev, type, section.section);
    const PP = cmp && cmp.prevPrev && readStatement(cmp.prevPrev, type, section.section);

    // per row: [ftm, previous month, previous ftm]
    const figures = lay.body.map((tr, i) => {
        const cur = cell(tr, lay.cur), p = P && P.get(keys[i]);
        const prevM = lay.prev >= 0 ? cell(tr, lay.prev) : (json && json[i].previous_month_amount != null ? json[i].previous_month_amount : (p ? p.cur : null));
        const ftm = lay.ftm >= 0 ? cell(tr, lay.ftm) : (json && json[i].ftm_amount != null ? json[i].ftm_amount : (cur != null && prevM != null ? cur - prevM : null));
        let prevFtm = null;
        if (p) {
            if (p.ftm != null) prevFtm = p.ftm;                 // the previous report's own FTM column
            else {                                              // otherwise: its closing minus the closing before it
                const pp = PP && PP.get(keys[i]);
                const before = p.prev != null ? p.prev : (p.jsonPrev != null ? p.jsonPrev : (pp ? pp.cur : null));
                prevFtm = p.cur != null && before != null ? p.cur - before : null;
            }
        }
        return [ftm, prevM, prevFtm];
    });

    // number style of the cells already in this table ("1,234", "1234.0", "4.704")
    const samples = lay.body.map(tr => tr.children[lay.cur].textContent.trim()).filter(t => /\d/.test(t));
    const dp = Math.max(0, ...samples.map(t => (t.split('.')[1] || '').replace(/\D/g, '').length));
    const grouped = samples.some(t => t.includes(','));
    // schedules print zeros ("0.0"); the P&L / Balance Sheet leave them empty. Follow whatever this table does.
    const showZero = lay.body.some(tr => /^-?0([.,]0+)?$/.test(tr.children[lay.cur].textContent.trim()));
    const fmt = v => {
        if (v == null) return '';
        const n = Number(Number(v).toFixed(dp));
        if (!n) return showZero ? (0).toFixed(dp) : '';
        return grouped ? n.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp }) : n.toFixed(dp);
    };

    const labels = [...FR.dom.sheet.querySelectorAll('.fr-note[data-section-type="Profit & Loss"] th, .fr-note[data-section-type="Cash Flow"] th')]
        .map(th => th.textContent.trim().replace(/\s+/g, ' ')).filter(t => /^month ended/i.test(t));
    const curLabel = lay.heads[lay.cur].text;
    const prevLabel = lay.prev >= 0 ? lay.heads[lay.prev].text : (labels.find(t => t !== curLabel) || 'Previous Month');
    const pfTitle = P ? 'FTM of the previous month' : 'Previous month report not found';

    // what goes after the current-month column and after the previous-month column: [header, tooltip, value index]
    const afterCur = [];
    if (needFtm) afterCur.push(['FTM', '', 0]);
    if (needPrev) afterCur.push([prevLabel, '', 1], ['Previous FTM', pfTitle, 2]);
    const afterPrev = needPrev ? [] : [['Previous FTM', pfTitle, 2]];

    const model = lay.year >= 0 ? lay.year : lay.cur;           // new cells copy the look of a plain figure column
    const mk = (src, text, title) => { const c = src.cloneNode(false); c.textContent = text; c.removeAttribute('colspan'); if (title) c.title = title; return c; };
    const modelTh = lay.heads[model].th;
    const curTh = lay.heads[lay.cur].th, prevTh = lay.prev >= 0 ? lay.heads[lay.prev].th : null;
    const handles = lay.body.map(tr => ({ cur: tr.children[lay.cur], prev: lay.prev >= 0 ? tr.children[lay.prev] : null, model: tr.children[model] }));

    if (afterCur.length) curTh.after(...afterCur.map(([h, t]) => mk(modelTh, h, t)));
    if (afterPrev.length && prevTh) prevTh.after(...afterPrev.map(([h, t]) => mk(modelTh, h, t)));
    handles.forEach((h, i) => {
        if (afterCur.length) h.cur.after(...afterCur.map(([, , k]) => mk(h.model, fmt(figures[i][k]))));
        if (afterPrev.length && h.prev) h.prev.after(...afterPrev.map(([, , k]) => mk(h.model, fmt(figures[i][k]))));
    });
    table.dataset.frPeriods = '1';
}
