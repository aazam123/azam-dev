/* =====================================================================
   filter_bar.js
   Company / month / year dropdowns and the report cards under them.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

// Does report `r` pass the filters? `skip` leaves one filter out (used to list the options of that same dropdown).
function matchReport(r, skip) {
    const F = FR.F;
    return (skip === 'company' || !F.company || r.company === F.company) &&
           (skip === 'month' || !F.month || String(r.month) === String(F.month)) &&
           (skip === 'year' || !F.year || String(r.year) === String(F.year));
}

const uniq = arr => [...new Set(arr)];

// Redraws the three dropdowns from the reports that still match the OTHER filters, so an empty combination can never be picked.
function refreshFilters() {
    const R = FR.reports, F = FR.F, S = FR.schema;

    const companies = uniq(R.filter(r => matchReport(r, 'company')).map(r => r.company).filter(Boolean)).sort();
    const months = uniq(R.filter(r => matchReport(r, 'month')).map(r => r.month).filter(Boolean)).sort((a, b) => a - b);
    const years = uniq(R.filter(r => matchReport(r, 'year')).map(r => r.year).filter(Boolean)).sort((a, b) => b - a);

    // drop a selection that no longer exists in the other filters' results
    if (F.company && !companies.includes(F.company)) F.company = '';
    if (F.month && !months.map(String).includes(String(F.month))) F.month = '';
    if (F.year && !years.map(String).includes(String(F.year))) F.year = '';

    const d = FR.dom;
    fillSelect(d.selCompany, companies.map(c => ({ value: c, label: c })), 'All companies', F.company);
    fillSelect(d.selMonth, months.map(m => ({ value: m, label: MONTHS[m - 1] })), 'All months', F.month);
    fillSelect(d.selYear, years.map(y => ({ value: y, label: String(y) })), 'All years', F.year);

    // Hide what the doctype cannot provide, instead of showing a dead filter
    d.fieldCompany.hidden = !S.company;
    d.fieldMonth.hidden = !S.hasPeriod;
    d.fieldYear.hidden = !S.hasPeriod;

    const anyFilter = !!(F.company || F.month || F.year);
    d.reset.hidden = !anyFilter;

    renderReportCards();
}

// Fills a <select> with a placeholder option plus `items` ({value, label}); `value` is the selected one.
function fillSelect(sel, items, placeholder, value) {
    sel.innerHTML =
        `<option value="">${esc(placeholder)}</option>` +
        items.map(i => `<option value="${esc(i.value)}"${String(i.value) === String(value) ? ' selected' : ''}>${esc(i.label)}</option>`).join('');
    sel.classList.toggle('has-value', !!value);
}

// Reports that pass the company / month / year filters.
function currentMatches() {
    return FR.reports.filter(r => matchReport(r));
}

// how many comments the chat of "Comments of" holds for one report: its own, or those of the chosen month's report of the same company
function chatCount(r) {
    if (r.name === FR.report && Array.isArray(FR.cmtList)) return FR.cmtList.length;     // live, includes what was just written / deleted
    if (FR.cmtOf === 'current') return FR.reportComments[r.name] || 0;
    const target = monthReport(r.company, FR.cmtOf);
    return target ? (FR.reportComments[target.name] || 0) : 0;
}

// Draws the report cards under the filters (one card per matching report, with its comment count) and the "N reports found" line.
function renderReportCards() {
    const matches = currentMatches();
    const d = FR.dom;
    const other = FR.cmtOf !== 'current';
    const label = FR.cmtLabel || (FR.reports.find(r => monthKey(r) === FR.cmtOf) ? periodLabel(FR.reports.find(r => monthKey(r) === FR.cmtOf)) : '');
    const counts = new Map(matches.map(r => [r.name, chatCount(r)]));
    const totalComments = [...counts.values()].reduce((a, b) => a + b, 0);
    const ofMonth = other ? ` (${label})` : '';
    d.resultCount.textContent = matches.length === 0
        ? 'No reports match these filters'
        : `${matches.length} ${matches.length === 1 ? 'report' : 'reports'} found · ` +
          `${totalComments} ${totalComments === 1 ? 'comment' : 'comments'} in this selection${ofMonth}`;

    d.reportList.innerHTML = matches.map(r => `
        <button type="button" class="fr-report-card ${r.name === FR.report ? 'is-open' : ''}${other ? ' is-otherchat' : ''}" data-id="${esc(r.name)}"${other ? ` title="Badge = comments of ${esc(label)}"` : ''}>
            <strong>${esc(r.name)}</strong>
            <span>${esc([r.company, periodLabel(r)].filter(Boolean).join(' · ') || 'Financial Report')}</span>
            ${counts.get(r.name) ? `<em class="fr-card-count">${counts.get(r.name)}</em>` : ''}
        </button>`).join('');

    d.reportList.querySelectorAll('.fr-report-card').forEach(btn =>
        btn.addEventListener('click', () => selectReport(btn.dataset.id)));
}

// Any filter changed: remember it, redraw the dropdowns, and open the report if only one is left.
// If the open report no longer fits the filters, clear the sheet and ask the user to pick again.
function onFilterChange() {
    saveFilters();
    refreshFilters();

    const matches = currentMatches();

    if (matches.length === 1) {
        if (matches[0].name !== FR.report) selectReport(matches[0].name);
        return;
    }

    // the open report no longer fits the filters -> ask the user to choose again
    if (FR.report && !matches.some(r => r.name === FR.report)) {
        FR.report = null;
        FR.doc = null;
        closeDrawer();
        refreshCommentSelect();
        FR.dom.sheet.innerHTML = matches.length
            ? emptyMarkup('Choose a report', 'Several reports match. Pick one from the list above.')
            : emptyMarkup('No reports found', 'Change the company, month or year to see other reports.');
    }
}

// With exactly one matching report there is nothing to choose, so it opens by itself.
function autoOpenIfSingle() {
    const matches = currentMatches();
    if (matches.length === 1) selectReport(matches[0].name);
}
