/* =====================================================================
   open_report.js
   Opening a report: fetch it with its comments, then draw legend, navigator and one card per section.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

function selectReport(id) {
    FR.report = id;
    closeDrawer();
    FR.filter = { q: '', only: FR.filter.only };               // the "Commented only" choice stays when you move to another report
    FR.cmtList = null;
    refreshCommentSelect();
    try { localStorage.setItem(FR.KEYS.report, id); } catch (e) {}
    renderReportCards();
    loadReport(id);
}

// Opens report `id`: fetches the report and its comments together, remembers the comment counts, then draws it (renderReport).
// The `id !== FR.report` checks drop a late answer when the user has already switched to another report.
function loadReport(id) {
    FR.dom.sheet.innerHTML = loadingMarkup();

    const cid = commentReportId(id);
    Promise.all([
        frappe.xcall('frappe.client.get', { doctype: FR_CONFIG.DOCTYPE, name: id }),
        fetchCommentRows(cid)
    ]).then(([doc, comments]) => {
        if (id !== FR.report) return;            // user switched report meanwhile
        applyCommentCounts(comments);
        FR.dom.sheet.classList.toggle('fr-othermonth', FR.cmtOf !== 'current');
        FR.doc = doc;
        FR.reportComments[cid || id] = comments.length;
        if (cid && FR.cmtOf === 'current') FR.reportComments[id] = comments.length;
        renderReportCards();
        if (!doc) return renderError(id);
        // the previous month's report supplies "Previous FTM"; a missing one only means that column is left out
        loadComparison(doc).catch(() => null).then(cmp => {
            if (id === FR.report) renderReport(doc, cmp);
        });
    }).catch(() => renderError(id));
}

// Draws the whole open report from its stored document `doc`: legend, navigator bar, then one card per section (P&L, Balance Sheet, notes...).
// `cmp` is the previous month's report (or null) used for the "Previous FTM" column.
// Order matters here: tables are decorated and get their extra columns first, then the row markers and the comment colours are painted on them.
function renderReport(doc, cmp) {
    const rows = doc.financial_report_details || [];

    // note_no is empty for P&L / Balance Sheet / Cash Flow / Equity, so chips and ids are keyed by position
    const chipLabel = r => r.note_no ? `Note ${esc(r.note_no)}`
        : esc(r.section_type === 'Consolidation Note' ? (r.section || 'Note') : (r.section_type || r.section || 'Section'));
    const chips = rows.map((r, i) => `
        <button class="fr-chip" type="button" data-target="sec-${i}" title="${esc(r.section || '')}">
            <i class="fr-dot"></i><span class="fr-chip-t">${chipLabel(r)}</span>
        </button>`).join('');

    let html = `
        <div class="fr-legend" aria-label="How to read this page">
            <button type="button" class="fr-legend-comments" hidden><i class="lg-badge">0</i><span>Rows have comments</span></button>
            <div class="fr-review" aria-label="Report review"></div>
        </div>

        <nav class="fr-toolbar" aria-label="Report navigator">
            <div class="fr-chips">${chips}</div>
            <div class="fr-tools">
                <button class="fr-expandall" type="button"></button>
                <button class="fr-export" type="button" title="Export the whole report to Excel" aria-label="Export the whole report to Excel">${ICON.download}</button>
                <label class="fr-search">
                    ${ICON.search}
                    <input type="search" placeholder="Search rows  ( / )" aria-label="Search rows">
                </label>
                <button class="fr-toggle" type="button" aria-pressed="false">
                    <i></i><span>Commented only</span>
                </button>
            </div>
        </nav>
    `;

    if (!rows.length) html += `<p class="fr-none">This report has no financial details yet.</p>`;

    rows.forEach((row, i) => {

        html += `
            <section class="fr-note"
                     id="sec-${i}"
                     data-note="${esc(row.note_no)}"
                     data-section="${esc(row.section || '')}"
                     data-section-type="${esc(row.section_type || '')}">
                <div class="fr-note-spine"><span class="${row.note_no ? '' : 'is-glyph'}">${esc(row.note_no || SECTION_GLYPH[row.section_type] || '§')}</span></div>
                <div class="fr-note-body">
                    <header class="fr-note-head">
                        <div class="fr-note-titlewrap">
                            <span class="fr-note-kicker">${esc(row.section_type || 'Note')}${row.note_no ? ' · Note ' + esc(row.note_no) : ''}</span>
                            <h4 class="fr-note-title">
                                <button type="button" class="fr-note-toggle" aria-expanded="true">
                                    <span>${esc(row.section || '')}</span>${ICON.chevron}
                                </button>
                            </h4>
                        </div>
                        <span class="fr-note-meta"></span>
                        <button type="button" class="fr-note-back" hidden>&larr; Back to statement</button>
                    </header>
                    <div class="fr-note-content">
                        <div class="fr-note-desc">${row.section_description || ''}</div>
                    </div>
                </div>
            </section>
        `;
    });

    html += `
        <div class="fr-no-results" hidden>
            ${emptyMarkup('No rows match', 'Try a different search, or turn off “Commented only”.')}
        </div>`;

    FR.dom.sheet.innerHTML = html;

    rows.forEach((row, i) => {
        if (['Balance Sheet', 'Profit & Loss', 'Cash Flow', 'Consolidation Note'].includes(row.section_type)) {
            addPeriodColumns(FR.dom.sheet.querySelector('#sec-' + i), row, doc, cmp);
        }
    });

    attachRowMarkers();
    bindToolbar();
    observeNotes();
    refreshAllNoteMeta();

    const legendBtn = FR.dom.sheet.querySelector('.fr-legend-comments');
    if (legendBtn) legendBtn.addEventListener('click', openNextCommented);
    updateCommentedLegend();
    paintChatColumn();
    paintReview();                                              // shows the last known state at once, then asks the server
    loadReview();
    if (FR.filter.only || FR.filter.q) applyFilters();          // a "Commented only" kept from the previous report applies to this one too
}

// Message shown when a report could not be loaded.
function renderError(id) {
    FR.dom.sheet.innerHTML = emptyMarkup(
        "Couldn't load this report",
        `No data was returned for <b>${esc(id)}</b>. Check the report and try again.`,
        true
    );
}

// Centered message block used for "Choose a report", "No reports found" and errors.
function emptyMarkup(title, text, isError) {
    return `
        <div class="fr-empty ${isError ? 'is-error' : ''}">
            <div class="fr-empty-mark"></div>
            <h4>${title}</h4>
            <p>${text}</p>
        </div>`;
}

// Grey skeleton shown while a report loads.
function loadingMarkup() {
    return `<div class="fr-skeleton"><b></b><i></i><i></i><i></i><i></i><i></i></div>`;
}
