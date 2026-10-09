/* =====================================================================
   FINANCIAL REPORT  ·  Frappe page "individual-financial"
   ---------------------------------------------------------------------
   WHAT THE USER DOES
     1. Picks Company, Month and Year  ->  matching reports appear as cards
     2. Opens a report                 ->  every section is shown as a ledger table
     3. Clicks the marker on any row   ->  a comment channel opens beside it
     4. Review chips                   ->  Prepare / Level 1 / Level 2 sign off the whole report

   HOW THE CODE IS ORGANISED  (top to bottom, one banner per part)
     CONFIG / STATE     FR_CONFIG = names and limits, FR = the one object that holds everything on screen
     PAGE ENTRY         on_page_load -> init: schema, report list, restore last session
     FILTER BAR         company / month / year dropdowns and the report cards
     SHELL              the empty page skeleton, theme, keyboard
     OPEN A REPORT      selectReport -> loadReport (report + its comments) -> renderReport
     COMMENTS OF        month-wise chat switch (this month or any other month) and the chat column of that month
     REPORT REVIEW      the three role chips (sign-off of the whole report)
     PERIOD COLUMNS     FTM, Previous Month and Previous FTM columns (read from the previous month's report)
     TOOLBAR            section chips, search, "Commented only", expand/collapse all
     TABLES             amount alignment, row markers, schedule jump (row -> its note and back)
     TABLE DECORATION   tags the stored HTML table with classes; the CSS does the painting
     COMMENT CHANNEL    drawer: open a row, thread, people, send, delete
     HELPERS            names, initials, colours, dates in the user's time zone and format
     STYLES             all CSS, injected once, every rule scoped under .fr-root

   ONE IDEA TO KEEP IN MIND: a comment belongs to a row by its KEY  "note|sectionType|rowIndex".
   The same key is on the table row (tr.dataset.key) and on the saved comment, so counts, markers and colours
   are always looked up by that key (FR.counts[key], FR.rowRoles[key]).

   COLOURS BY ROLE (initials chip and the comment markers of a row)
     Comment finance Prepare = yellow · Reviewer Level 1 = green · Reviewer Level 2 = red · no role = brown.
     The server tells the page which user has which colour (get_role_users); no role name is shown anywhere.

   No external fonts / files are loaded, so the page can never trigger a static-file 404 on the server.

   Backend (all in financial_report_tool/doctype/):
     Financial Report            -> financial_report_details[]  (the sections, their HTML and figures)
     Financial Report Comments  -> financial_report, note_no, section_type, row_index, row_label, comment,
                                   comment_added_by, is_deleted / deleted_by / deleted_on (soft delete)
                                   server methods: delete_comment, get_role_users
     Financial Report Review    -> one record per (report, role): who reviewed and when
                                   server methods: get_review_state, set_review
     Role that may comment      -> Financial Report Manager
   ===================================================================== */

/* ---------------------------------------------------------------------
   CONFIG  – change field names here if your doctype uses different ones
--------------------------------------------------------------------- */
const FR_CONFIG = {
    DOCTYPE: 'Financial Report',
    COMMENT_DOCTYPE: 'Financial Report Comments',
    COMPANY_FIELD: 'company',
    MONTH_FIELD: 'month',          // Select / Int / Data holding the month
    YEAR_FIELD: 'year',            // Select / Int / Data holding the year
    // Used only when month/year fields do not exist: the first one found wins
    DATE_FIELDS: ['to_date', 'report_date', 'reporting_date', 'posting_date', 'period_end_date', 'end_date', 'from_date'],
    MANAGER_ROLE: 'Financial Report Manager',
    POLL_MS: 20000,                // live refresh of the open comment channel
    QUICK_NOTES: ['Please clarify', 'Verified', 'Supporting document needed', 'Amount mismatch']
};

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'];

/* ---------------------------------------------------------------------
   STATE
--------------------------------------------------------------------- */
const FR = {
    report: null,        // open Financial Report ID
    doc: null,           // its document
    reports: [],         // every report, normalised {name, company, month, year}
    fiscalYears: {},     // Fiscal Year name -> {year_start_date, year_end_date}
    backRow: null,       // statement row to return to after a schedule jump
    deletedN: {},        // "note|sectionType|row" -> number of deleted comments (kept in the thread as a note)
    schema: { company: false, month: null, year: null, date: null, hasPeriod: false },
    F: { company: '', month: '', year: '' },   // filter values
    cmtOf: 'current',    // whose chat is shown: 'current' = the open report, or a month key "fiscal_year|month" = the chat of that month's report of the same company
    cmtLabel: '',        // short label of that month ("Oct 2025"); empty while 'current'
    cmtList: null,       // comments of the report whose chat is on screen (used by the previous-month panel)
    roleUsers: {},       // user -> "prepare" | "review1" | "review2": colour of their initials chip and of the row indicators
    reportComments: {},  // report ID -> total comments (shown on the report cards)
    counts: {},          // "note|sectionType|row" -> number of comments
    rowRoles: {},        // "note|sectionType|row" -> roles of its commenters, latest last ("prepare" | "review1" | "review2" | "none")
    review: null,        // review cards of the open report: {report, cards: [{key, holders, can, reviewed_by, reviewed_on}]}
    reviewBusy: false,   // a Mark reviewed / Unreview request is running
    active: null,        // the row open in the comment drawer: {key, noteId, sectionType, sectionName, rowIndex, rowEl}
    canComment: false,   // the user holds the Financial Report Manager role (the server checks again)
    filter: { q: '', only: false },   // search text (lower case) and the "Commented only" switch
    thread: { lastAuthor: null, lastTs: 0, lastDay: null },   // grouping state while a thread is drawn
    sending: false,      // a comment is being saved (blocks a second send)
    dom: {},             // page elements, filled once by buildShell
    observer: null,      // IntersectionObserver that marks the section chip in view
    collapseObs: null,   // MutationObserver that keeps the expand/collapse-all button in step
    poll: null,          // setInterval id of the 20 s live refresh (thread + review chips)
    KEYS: { report: 'fr_selected_report', filters: 'fr_filters', cmt: 'fr_comments_of' }   // localStorage keys
};

const rowKey = (note, type, idx) => `${note}|${type}|${idx}`;
const esc = v => frappe.utils.escape_html(v == null ? '' : String(v));

/* ---------------------------------------------------------------------
   PAGE ENTRY
--------------------------------------------------------------------- */
frappe.pages['individual-financial'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Financial Report',
        single_column: true
    });

    FR.canComment = frappe.user_roles.includes(FR_CONFIG.MANAGER_ROLE);

    injectStyles();
    buildShell(page);
    bindGlobalKeys();

    page.set_secondary_action('Refresh', () => refreshAll(), 'refresh');

    // keep the live refresh running only while this page exists
    clearInterval(FR.poll);
    FR.poll = setInterval(() => { pollThread(); pollReview(); }, FR_CONFIG.POLL_MS);

    document.body.classList.add('fr-page-open');
    $(wrapper).off('show.fr').on('show.fr', () => document.body.classList.add('fr-page-open'));
    $(document).off('page-change.fr').on('page-change.fr', () => {
        if (!(FR.dom.root && document.body.contains(FR.dom.root) && FR.dom.root.offsetParent !== null)) {
            document.body.classList.remove('fr-page-open');
        }
    });

    init();
};

// Page start: read the doctype's fields, load all reports, then restore the last session. A failure shows one clear message.
function init() {
    resolveSchema()
        .then(loadReportList)
        .then(restoreSession)
        .catch(() => {
            FR.dom.sheet.innerHTML = emptyMarkup(
                "Couldn't load reports",
                'Please refresh the page. If this keeps happening, check your permissions on Financial Report.',
                true
            );
        });
}

// "Refresh" button: reload the list of reports and, if one is open, reload it too.
function refreshAll() {
    loadReportList().then(() => {
        refreshFilters();
        if (FR.report) loadReport(FR.report);
    });
}

/* ---------------------------------------------------------------------
   SCHEMA  – find out which fields the doctype really has
--------------------------------------------------------------------- */
function resolveSchema() {
    return new Promise(resolve => {
        frappe.model.with_doctype(FR_CONFIG.DOCTYPE, () => {
            const meta = frappe.get_meta(FR_CONFIG.DOCTYPE);
            const field = name => {
                const list = (meta && meta.fields) || [];
                return list.find(f => f.fieldname === name) || null;
            };

            const s = FR.schema;
            s.company = !!field(FR_CONFIG.COMPANY_FIELD);
            s.month = field(FR_CONFIG.MONTH_FIELD) ? FR_CONFIG.MONTH_FIELD : null;
            s.year = field(FR_CONFIG.YEAR_FIELD) ? FR_CONFIG.YEAR_FIELD : null;
            s.date = FR_CONFIG.DATE_FIELDS.find(f => {
                const df = field(f);
                return df && /^Date/.test(df.fieldtype);
            }) || 'creation';              // last resort: the date the report was created
            s.hasPeriod = true;                // Month and Year filters are always available
            resolve();
        });
    });
}

/* ---------------------------------------------------------------------
   REPORT LIST  (one request, then every filter works instantly)
--------------------------------------------------------------------- */
function loadReportList() {
    return Promise.all([
        frappe.xcall('frappe.client.get_list', {
            doctype: FR_CONFIG.DOCTYPE,
            fields: ['*'],
            order_by: 'modified desc',
            limit_page_length: 0
        }),
        // comment totals per report, so every filter result can show them
        frappe.xcall('frappe.client.get_list', {
            doctype: FR_CONFIG.COMMENT_DOCTYPE,
            filters: { is_deleted: 0 },
            fields: ['financial_report'],
            limit_page_length: 0
        }).catch(() => []),
        // fiscal years turn "August" + "2025-2026" into the real calendar year
        frappe.xcall('frappe.client.get_list', {
            doctype: 'Fiscal Year',
            fields: ['name', 'year_start_date', 'year_end_date'],
            limit_page_length: 0
        }).catch(() => []),
        // commenters whose initials chip is coloured by role (yellow / green)
        frappe.xcall('financial_report_tool.financial_report_tool.doctype.financial_report_comments.financial_report_comments.get_role_users').catch(() => ({}))
    ]).then(([rows, comments, years, roleUsers]) => {
        FR.roleUsers = roleUsers || {};
        FR.fiscalYears = {};
        (years || []).forEach(y => { FR.fiscalYears[y.name] = y; });
        detectFieldsFromData(rows || []);
        FR.reports = (rows || []).map(normaliseReport);
        FR.reportComments = {};
        (comments || []).forEach(c => {
            FR.reportComments[c.financial_report] = (FR.reportComments[c.financial_report] || 0) + 1;
        });
    });
}

// If the doctype meta could not be read, fall back to what the rows really contain
function detectFieldsFromData(rows) {
    if (!rows.length) return;
    const S = FR.schema, keys = Object.keys(rows[0]);
    if (!S.company && keys.includes(FR_CONFIG.COMPANY_FIELD)) S.company = true;
    if (!S.month && keys.includes(FR_CONFIG.MONTH_FIELD)) S.month = FR_CONFIG.MONTH_FIELD;
    if (!S.year && keys.includes(FR_CONFIG.YEAR_FIELD)) S.year = FR_CONFIG.YEAR_FIELD;
    if (!S.date || S.date === 'creation') {
        S.date = FR_CONFIG.DATE_FIELDS.find(f => keys.includes(f)) || 'creation';
    }
}

// The report's real period. `creation` is only the day the report was generated, so it is NOT used when
// the report states its own period: Monthly -> current_month inside its fiscal year; Yearly -> year end date.
function realPeriod(r) {
    const fy = FR.fiscalYears[r.fiscal_year];
    const end = parseDate(r.current_year_ending_date || (fy && fy.year_end_date));
    if (r.report_type === 'Yearly') {
        return isNaN(end) ? null : { month: end.getMonth() + 1, year: end.getFullYear() };
    }
    const month = toMonth(r.current_month);
    if (!month) return null;
    const start = fy ? parseDate(fy.year_start_date) : NaN;
    if (!isNaN(start)) {
        const fyEnd = parseDate(fy.year_end_date);
        return { month, year: month >= start.getMonth() + 1 ? start.getFullYear() : fyEnd.getFullYear() };
    }
    if (isNaN(end)) return null;
    return { month, year: month > end.getMonth() + 1 ? end.getFullYear() - 1 : end.getFullYear() };
}

// Turns a raw Financial Report row into the small object the page works with.
// The month and year are the report's real period (see realPeriod), with the doctype's own fields as a fallback.
function normaliseReport(r) {
    const S = FR.schema;
    const real = realPeriod(r);
    let month = real ? real.month : (S.month ? toMonth(r[S.month]) : null);
    let year = real ? real.year : (S.year ? toYear(r[S.year]) : null);

    if ((month == null || year == null) && S.date && r[S.date]) {
        const d = parseDate(r[S.date]);
        if (!isNaN(d)) {
            if (month == null) month = d.getMonth() + 1;
            if (year == null) year = d.getFullYear();
        }
    }
    return {
        name: r.name,
        company: (S.company && r[FR_CONFIG.COMPANY_FIELD]) || '',
        type: r.report_type || '',
        fy: r.fiscal_year || '',
        cm: r.current_month || '',
        fiscal_year: r.fiscal_year || '',
        current_month: r.current_month || '',
        previous_month: r.previous_month || '',
        previous_fiscal_year: r.previous_fiscal_year || '',
        month, year
    };
}

// Month number 1-12 from a number or a name ("November", "Nov", 11); null when it is none of those.
function toMonth(v) {
    if (v == null || v === '') return null;
    const n = Number(v);
    if (Number.isInteger(n) && n >= 1 && n <= 12) return n;
    const s = String(v).trim().toLowerCase().slice(0, 3);
    const i = MONTHS.findIndex(m => m.toLowerCase().startsWith(s));
    return i >= 0 ? i + 1 : null;
}

// Four-digit year found in any value ("2025-2026" -> 2025), or null.
function toYear(v) {
    const m = String(v == null ? '' : v).match(/\d{4}/);
    return m ? Number(m[0]) : null;
}

// "Nov 2025" (or "Yearly · Mar 2025"), the short period text shown on cards and the "Comments of" menu.
const periodLabel = r => (r.type === 'Yearly' ? 'Yearly · ' : '') +
    [r.month ? MONTHS[r.month - 1].slice(0, 3) : '', r.year || ''].filter(Boolean).join(' ');

/* ---------------------------------------------------------------------
   SESSION RESTORE
--------------------------------------------------------------------- */
// First thing after the reports are loaded: reopen the last report (and the "Comments of" choice) from localStorage,
// otherwise reapply the saved filters and open the report if only one matches.
function restoreSession() {
    try { const m = localStorage.getItem(FR.KEYS.cmt); if (m && m.includes('|')) FR.cmtOf = m; } catch (e) { /* storage unavailable */ }
    let last = null, saved = null;
    try {
        last = localStorage.getItem(FR.KEYS.report);
        saved = JSON.parse(localStorage.getItem(FR.KEYS.filters) || 'null');
    } catch (e) { /* storage unavailable */ }

    const found = FR.reports.find(r => r.name === last);
    if (found) {
        FR.F = { company: found.company || '', month: found.month || '', year: found.year || '' };
        refreshFilters();
        selectReport(found.name);
        return;
    }

    if (saved) FR.F = Object.assign({ company: '', month: '', year: '' }, saved);
    refreshFilters();
    autoOpenIfSingle();
}

// Keeps the chosen company / month / year in localStorage so they come back on the next visit.
function saveFilters() {
    try { localStorage.setItem(FR.KEYS.filters, JSON.stringify(FR.F)); } catch (e) {}
}

/* ---------------------------------------------------------------------
   FILTER BAR
--------------------------------------------------------------------- */
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

/* ---------------------------------------------------------------------
   SHELL
--------------------------------------------------------------------- */
const ICON = {
    close: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    up: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 15l6-6 6 6"/></svg>',
    down: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>',
    chevron: '<svg class="fr-chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>',
    plus: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>',
    search: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>',
    send: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg>',
    reset: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>',
    rows: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h10"/></svg>',
    comment: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16v11H9l-5 4z"/></svg>',
    moon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
    trash: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
    expandAll: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 15l5 5 5-5"/><path d="M7 9l5-5 5 5"/></svg>',
    collapseAll: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 20l5-5 5 5"/><path d="M7 4l5 5 5-5"/></svg>',
    sun: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
};

// Builds the empty page skeleton once (filter bar, report cards, the sheet area, the comment drawer) and stores the elements in FR.dom.
// Everything after this only fills these elements; nothing re-creates the shell.
function buildShell(page) {
    const $root = $(`
        <div class="fr-root">

            <section class="fr-filters" aria-label="Report filters">
                <div class="fr-filter-grid">
                    <label class="fr-field" data-field="company">
                        <span>Company</span>
                        <select data-f="company"></select>
                    </label>
                    <label class="fr-field" data-field="month">
                        <span>Month</span>
                        <select data-f="month"></select>
                    </label>
                    <label class="fr-field" data-field="year">
                        <span>Year</span>
                        <select data-f="year"></select>
                    </label>
                    <label class="fr-field" data-field="cmt" title="See the chat of this month, or of the month before it">
                        <span>Comments of</span>
                        <select data-f="cmt"></select>
                    </label>
                </div>

                <div class="fr-results">
                    <div class="fr-results-bar">
                        <div class="fr-results-count"></div>
                        <button type="button" class="fr-reset" hidden>${ICON.reset}<span>Clear filters</span></button>
                        <button type="button" class="fr-theme" aria-pressed="false"></button>
                    </div>
                    <div class="fr-report-list" role="list"></div>
                </div>
            </section>

            <div class="fr-shell">
                <main class="fr-sheet">
                    ${emptyMarkup('Choose a report', 'Pick a company, month and year above, then open a report to start reviewing.')}
                </main>

                <aside class="fr-drawer" aria-label="Row comments" aria-hidden="true">
                    <header class="fr-drawer-head">
                        <div class="fr-drawer-ctx">
                            <span class="fr-drawer-kicker"></span>
                            <h5 class="fr-drawer-row"></h5>
                            <div class="fr-drawer-people">
                                <span class="fr-stack"></span>
                                <span class="fr-drawer-count"></span>
                            </div>
                        </div>
                        <div class="fr-drawer-actions">
                            <button class="fr-icon-btn fr-prev" title="Previous commented row" aria-label="Previous commented row">${ICON.up}</button>
                            <button class="fr-icon-btn fr-next" title="Next commented row" aria-label="Next commented row">${ICON.down}</button>
                            <button class="fr-icon-btn fr-close" title="Close (Esc)" aria-label="Close comments">${ICON.close}</button>
                        </div>
                    </header>

                    <div class="fr-thread" role="log" aria-live="polite"></div>

                    <footer class="fr-composer">
                        <div class="fr-quick" aria-label="Quick notes"></div>
                        <textarea class="fr-input" rows="1" placeholder="Write a comment…" aria-label="Write a comment"></textarea>
                        <div class="fr-composer-row">
                            <span class="fr-hint">Enter to send · Shift+Enter for a new line</span>
                            <button class="fr-send" type="button">${ICON.send}<span>Send</span></button>
                        </div>
                    </footer>
                    <p class="fr-readonly">You can read comments here. Only Financial Report Managers can write them.</p>
                </aside>
            </div>
        </div>
    `).appendTo(page.body);

    const q = sel => $root.find(sel)[0];
    FR.dom = {
        root: $root[0],
        shell: q('.fr-shell'),
        sheet: q('.fr-sheet'),
        drawer: q('.fr-drawer'),
        kicker: q('.fr-drawer-kicker'),
        rowTitle: q('.fr-drawer-row'),
        stack: q('.fr-stack'),
        count: q('.fr-drawer-count'),
        thread: q('.fr-thread'),
        composer: q('.fr-composer'),
        quick: q('.fr-quick'),
        readonly: q('.fr-readonly'),
        input: q('.fr-input'),
        send: q('.fr-send'),
        prev: q('.fr-prev'),
        next: q('.fr-next'),
        selCompany: q('select[data-f="company"]'),
        selMonth: q('select[data-f="month"]'),
        selYear: q('select[data-f="year"]'),
        selCmt: q('select[data-f="cmt"]'),
        fieldCompany: q('[data-field="company"]'),
        fieldMonth: q('[data-field="month"]'),
        fieldYear: q('[data-field="year"]'),
        reset: q('.fr-reset'),
        resultCount: q('.fr-results-count'),
        reportList: q('.fr-report-list')
    };

    // Filters
    ['company', 'month', 'year'].forEach(name => {
        const sel = FR.dom['sel' + name[0].toUpperCase() + name.slice(1)];
        sel.addEventListener('change', () => { FR.F[name] = sel.value; onFilterChange(); });
    });
    FR.dom.reset.addEventListener('click', () => {
        FR.F = { company: '', month: '', year: '' };
        onFilterChange();
    });
    FR.dom.selCmt.addEventListener('change', () => setCommentMonth(FR.dom.selCmt.value));
    refreshCommentSelect();

    // Drawer
    $root.find('.fr-close').on('click', closeDrawer);
    FR.dom.prev.addEventListener('click', () => stepComment(-1));
    FR.dom.next.addEventListener('click', () => stepComment(1));
    FR.dom.send.addEventListener('click', submitComment);

    FR.dom.input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitComment(); }
    });
    FR.dom.input.addEventListener('input', autoGrow);

    // delete button inside a message bubble
    FR.dom.thread.addEventListener('click', e => {
        const b = e.target.closest('.fr-msg-del');
        if (b) deleteComment(b.closest('.fr-msg').dataset.name);
    });

    // Quick notes: one tap fills the box
    FR.dom.quick.innerHTML = FR_CONFIG.QUICK_NOTES
        .map(t => `<button type="button" class="fr-quick-chip">${esc(t)}</button>`).join('');
    FR.dom.quick.querySelectorAll('.fr-quick-chip').forEach(btn =>
        btn.addEventListener('click', () => {
            const el = FR.dom.input;
            el.value = el.value ? `${el.value.trim()} ${btn.textContent}` : btn.textContent;
            autoGrow();
            el.focus();
        }));

    // Theme
    FR.dom.themeBtn = $root.find('.fr-theme')[0];
    FR.dom.themeBtn.addEventListener('click', toggleTheme);
    paintThemeButton();

    // "Back to statement" buttons live inside the rendered notes
    FR.dom.sheet.addEventListener('click', e => {
        const b = e.target.closest('.fr-note-back');
        if (b) backFromSchedule(b);
        const cc = e.target.closest('td.fr-chatcol.has-chat');
        if (cc && cc.parentElement.dataset.key) openCommentRow(cc.parentElement.dataset.key);
    });
}

/* ---------------------------------------------------------------------
   THEME  (Light / Dark)
   Uses Frappe's own theme switch, so the whole desk changes and the choice
   is saved on the user's profile exactly like Settings > Switch Theme.
   Every colour on this page already follows html[data-theme].
--------------------------------------------------------------------- */
const currentTheme = () => document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';

// Shows the sun in dark mode and the moon in light mode.
function paintThemeButton() {
    const btn = FR.dom.themeBtn;
    if (!btn) return;
    const dark = currentTheme() === 'dark';
    btn.innerHTML = dark ? ICON.sun : ICON.moon;
    btn.title = dark ? 'Switch to light theme' : 'Switch to dark theme';
    btn.setAttribute('aria-label', btn.title);
    btn.setAttribute('aria-pressed', String(dark));
}

// Light / dark: switches the whole Frappe desk and saves the choice on the user's profile, like Settings > Switch Theme.
function toggleTheme() {
    const next = currentTheme() === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme-mode', next);
    document.documentElement.setAttribute('data-theme', next);
    paintThemeButton();
    frappe.xcall('frappe.core.doctype.user.user.switch_theme', { theme: next === 'dark' ? 'Dark' : 'Light' }).catch(() => {});
}

// Keyboard: Esc closes the open chat, "/" jumps to the search box. Ignored when this page is not the one on screen.
function bindGlobalKeys() {
    $(document).off('keydown.fr').on('keydown.fr', e => {
        // ignore when this page is not the visible one
        if (!FR.dom.root || !document.body.contains(FR.dom.root) || FR.dom.root.offsetParent === null) return;

        const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;

        if (e.key === 'Escape' && FR.active) { closeDrawer(); return; }
        if (e.key === '/' && !typing) {
            const s = FR.dom.sheet.querySelector('.fr-search input');
            if (s) { e.preventDefault(); s.focus(); }
        }
    });
}

// Grows the comment box with the text, up to 120px.
function autoGrow() {
    const el = FR.dom.input;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

/* ---------------------------------------------------------------------
   OPEN A REPORT
--------------------------------------------------------------------- */
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

/* ---------------------------------------------------------------------
   RENDER: REPORT
--------------------------------------------------------------------- */
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

/* ---------------------------------------------------------------------
   REPORT REVIEW  (whole report, one small chip per role)
   Sign-off for the whole open report: one round chip per role (Comment finance Prepare, Reviewer Level 1, Reviewer Level 2).
   The server (financial_report_review.py) decides who may press which chip, and checks it again on every click;
   the page only shows the state it is given. A reviewed chip is filled with the role colour; who / when is in the hover tooltip.
   Names are shown, never role names.
--------------------------------------------------------------------- */
const REVIEW_API = 'financial_report_tool.financial_report_tool.doctype.financial_report_review.financial_report_review.';

// Asks the server for the review state of the open report and draws it. Skipped while one of our own requests is running.
function loadReview() {
    const id = FR.report;
    if (!id) return Promise.resolve();
    return frappe.xcall(REVIEW_API + 'get_review_state', { report: id }).then(state => {
        if (id !== FR.report || FR.reviewBusy) return;
        FR.review = state;
        paintReview();
    }).catch(() => {});
}

// Called every 20 seconds: refresh the chips so another user's review shows up without reloading the page.
function pollReview() {
    if (!FR.report || FR.reviewBusy || document.hidden || !FR.dom || !FR.dom.root || !document.body.contains(FR.dom.root) || FR.dom.root.offsetParent === null) return;
    loadReview();
}

// Draws the three chips. A reviewed chip is filled with the role colour; the tooltip says who and when.
// A chip is a button only for the user who holds that role, everyone else sees a plain, hover-only chip.
function paintReview() {
    const box = FR.dom.sheet.querySelector('.fr-review');
    const s = FR.review;
    if (!box || !s || s.report !== FR.report) return;
    const tick = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
    box.innerHTML = '<span class="fr-review-l">Review</span>' + s.cards.map(c => {
        const done = !!c.reviewed_by;
        const holders = (c.holders || []).map(userName);
        const who = done ? userName(c.reviewed_by) : (holders[0] ? holders[0] + (holders.length > 1 ? ` +${holders.length - 1}` : '') : 'Nobody assigned');
        const st = ROLE_STYLE[c.key];
        const tip = !holders.length && !done ? 'Nobody is assigned to this review'
            : `${who} · ${done ? 'Reviewed ' + fullTimeLabel(c.reviewed_on) : 'Not reviewed yet'}` + (c.can ? ` · click to ${done ? 'unreview' : 'mark reviewed'}` : '');
        const attrs = `class="fr-rv${done ? ' is-done' : ''}" data-key="${esc(c.key)}" data-tip="${esc(tip)}" aria-label="${esc(tip)}" style="--c:${st.c};--fg:${st.fg}"`;
        const inner = `${esc(initials(who))}<i class="fr-rv-ok">${tick}</i>`;
        return c.can
            ? `<button type="button" ${attrs} data-act="${done ? 0 : 1}">${inner}</button>`
            : `<span ${attrs} tabindex="0" role="img">${inner}</span>`;
    }).join('');
    box.querySelectorAll('button.fr-rv').forEach(b => b.addEventListener('click', () => toggleReview(b)));
}

// Click on a chip: asks the server to mark / take back this role's review, then repaints from the answer.
// Only one request at a time (reviewBusy), so a double click cannot send two.
function toggleReview(btn) {
    const id = FR.report;
    if (!id || FR.reviewBusy) return;
    FR.reviewBusy = true;
    btn.disabled = true;
    frappe.xcall(REVIEW_API + 'set_review', { report: id, key: btn.dataset.key, reviewed: btn.dataset.act })
        .then(state => {
            FR.reviewBusy = false;
            if (id !== FR.report) return;
            FR.review = state;
            paintReview();
            frappe.show_alert({ message: btn.dataset.act === '1' ? 'Marked as reviewed' : 'Review taken back', indicator: 'green' });
        })
        .catch(() => { FR.reviewBusy = false; btn.disabled = false; loadReview(); });
}

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
    if (!head) return null;
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

/* ---------------------------------------------------------------------
   TOOLBAR  (chips · search · commented-only)
--------------------------------------------------------------------- */
// Wires the navigator bar under the legend: section chips (scroll to a section), per-section fold buttons,
// the expand/collapse-all button, the search box (120ms debounce, Esc clears) and the "Commented only" switch.
function bindToolbar() {
    const sheet = FR.dom.sheet;

    sheet.querySelectorAll('.fr-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const target = document.getElementById(chip.dataset.target);
            if (!target) return;
            target.classList.remove('is-collapsed');
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            target.classList.remove('is-flash'); void target.offsetWidth;
            target.classList.add('is-flash');
        });
    });

    sheet.querySelectorAll('.fr-note-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            const note = btn.closest('.fr-note');
            const collapsed = note.classList.toggle('is-collapsed');
            btn.setAttribute('aria-expanded', String(!collapsed));
        });
    });

    // One button for every section: collapse all when everything is open, otherwise expand all
    const allBtn = sheet.querySelector('.fr-expandall');
    const notes = () => [...sheet.querySelectorAll('.fr-note')];
    const syncExpandAll = () => {
        const list = notes();
        const open = list.length > 0 && list.every(n => !n.classList.contains('is-collapsed'));
        list.forEach(n => {
            const t = n.querySelector('.fr-note-toggle');
            if (t) t.setAttribute('aria-expanded', String(!n.classList.contains('is-collapsed')));
        });
        if (!allBtn) return;
        allBtn.innerHTML = open ? ICON.collapseAll : ICON.expandAll;
        allBtn.title = open ? 'Collapse all sections' : 'Expand all sections';
        allBtn.setAttribute('aria-label', allBtn.title);
    };
    if (allBtn) allBtn.addEventListener('click', () => {
        const list = notes();
        const collapse = list.every(n => !n.classList.contains('is-collapsed'));
        list.forEach(n => n.classList.toggle('is-collapsed', collapse));
    });
    // every way of opening/closing a section (title, chips, search, schedule jump...) changes the class, so watch it
    if (FR.collapseObs) FR.collapseObs.disconnect();
    FR.collapseObs = new MutationObserver(syncExpandAll);
    FR.collapseObs.observe(sheet, { subtree: true, attributes: true, attributeFilter: ['class'] });
    syncExpandAll();

    const input = sheet.querySelector('.fr-search input');
    let timer = null;
    input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => { FR.filter.q = input.value.trim().toLowerCase(); applyFilters(); }, 120);
    });
    input.addEventListener('keydown', e => {
        if (e.key === 'Escape') { input.value = ''; FR.filter.q = ''; applyFilters(); input.blur(); }
    });

    const toggle = sheet.querySelector('.fr-toggle');
    toggle.setAttribute('aria-pressed', String(FR.filter.only));      // "Commented only" survives a report switch
    toggle.addEventListener('click', () => {
        FR.filter.only = !FR.filter.only;
        toggle.setAttribute('aria-pressed', String(FR.filter.only));
        applyFilters();
    });
}

// Applies the search box and "Commented only" to the rows: hides rows that do not match, hides sections left empty,
// and shows "no results" when nothing is left.
function applyFilters() {
    const { q, only } = FR.filter;
    const filtering = !!(q || only);
    let visibleTotal = 0;

    FR.dom.sheet.querySelectorAll('.fr-note').forEach(note => {
        let visible = 0;
        note.querySelectorAll('tr[data-key]').forEach(tr => {
            const match = (!q || (tr.dataset.search || '').includes(q)) &&
                          (!only || tr.classList.contains('has-comments'));
            tr.classList.toggle('is-hidden', !match);
            if (match) visible++;
        });
        note.classList.toggle('is-filtered-out', filtering && visible === 0);
        if (filtering && visible) note.classList.remove('is-collapsed');
        visibleTotal += visible;
    });

    const none = FR.dom.sheet.querySelector('.fr-no-results');
    if (none) none.hidden = !(filtering && visibleTotal === 0);
}

// Marks the navigator chip of the section currently on screen as active (follows scrolling).
function observeNotes() {
    if (FR.observer) FR.observer.disconnect();
    if (!('IntersectionObserver' in window)) return;

    FR.observer = new IntersectionObserver(entries => {
        entries.forEach(en => {
            if (!en.isIntersecting) return;
            FR.dom.sheet.querySelectorAll('.fr-chip').forEach(c =>
                c.classList.toggle('is-current', c.dataset.target === en.target.id));
        });
    }, { rootMargin: '-160px 0px -65% 0px', threshold: 0 });

    FR.dom.sheet.querySelectorAll('.fr-note').forEach(n => FR.observer.observe(n));
}

// Redraws one section's "N rows / N commented" pill and its navigator chip dot, coloured by who commented (see setRoleVars).
function refreshNoteMeta(note) {
    if (!note) return;
    const rows = note.querySelectorAll('tr[data-key]').length;
    const commented = note.querySelectorAll('tr.has-comments').length;
    const meta = note.querySelector('.fr-note-meta');
    const roles = unionRoles([...note.querySelectorAll('tr.has-comments')]);
    if (meta) {
        meta.innerHTML =
            `<span class="fr-rowcount">${ICON.rows}${rows} ${rows === 1 ? 'row' : 'rows'}</span>` +
            (commented ? `<b class="fr-commented">${ICON.comment}${commented} commented</b>` : '');
        setRoleVars(meta.querySelector('.fr-commented'), roles);
    }
    const chip = FR.dom.sheet.querySelector(`.fr-chip[data-target="${note.id}"]`);
    if (chip) {
        chip.classList.toggle('has-comments', commented > 0);
        setRoleVars(chip, roles);
    }
}

// Repaints the "N rows / N commented" pill of every section.
function refreshAllNoteMeta() {
    FR.dom.sheet.querySelectorAll('.fr-note').forEach(refreshNoteMeta);
}

/* ---------------------------------------------------------------------
   TABLES  (column alignment + row markers)
--------------------------------------------------------------------- */

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

/* ---------------------------------------------------------------------
   SCHEDULE JUMP  (Revenue from operations -> Note 30, and back)
   A statement row stores data-schedule="30". Clicking the row scrolls to
   that note; the note shows a "Back to statement" button that returns to
   the exact row.
--------------------------------------------------------------------- */
// The section whose note number equals this row's data-schedule, or null (also null when it would be the row's own section).
function scheduleNote(tr) {
    const no = tr.dataset.schedule;
    if (!no) return null;
    return [...FR.dom.sheet.querySelectorAll('.fr-note')].find(n => n.dataset.note === no && n !== tr.closest('.fr-note')) || null;
}

// Briefly highlights a row so the eye finds it after a jump.
function flashRow(tr) {
    tr.classList.remove('is-flash-row'); void tr.offsetWidth;
    tr.classList.add('is-flash-row');
    setTimeout(() => tr.classList.remove('is-flash-row'), 2000);
}

// Click on a statement row that has a note number: opens that note, scrolls to it and shows its "Back to statement" button.
function jumpToSchedule(tr) {
    const note = scheduleNote(tr);
    if (!note) return;
    FR.dom.sheet.querySelectorAll('.fr-note-back').forEach(b => { b.hidden = true; });
    FR.backRow = tr;
    note.classList.remove('is-collapsed');
    const back = note.querySelector('.fr-note-back');
    if (back) back.hidden = false;
    note.scrollIntoView({ behavior: 'smooth', block: 'start' });
    note.classList.remove('is-flash'); void note.offsetWidth;
    note.classList.add('is-flash');
}

// "Back to statement": returns to the statement row the jump started from, opens its section and flashes the row.
function backFromSchedule(btn) {
    const tr = FR.backRow;
    btn.hidden = true;
    if (!tr || !document.body.contains(tr)) return;
    const owner = tr.closest('.fr-note');
    if (owner) owner.classList.remove('is-collapsed');
    tr.classList.remove('is-hidden');
    tr.scrollIntoView({ behavior: 'smooth', block: 'center' });
    flashRow(tr);
    FR.backRow = null;
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

/* ---------------------------------------------------------------------
   COMMENT CHANNEL (drawer)
--------------------------------------------------------------------- */
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

// Fetches every comment of one row (deleted ones too, so they can show as notes) from the report whose chat is on screen.
function fetchThread(ctx) {
    const cid = commentReportId(FR.report);
    if (!cid) return Promise.resolve([]);
    return frappe.xcall('frappe.client.get_list', {
        doctype: FR_CONFIG.COMMENT_DOCTYPE,
        filters: {
            financial_report: cid,
            note_no: ctx.noteId,
            row_index: ctx.rowIndex,
            section_type: ctx.sectionType
        },
        fields: ['name', 'comment', 'comment_added_by', 'creation', 'is_deleted', 'deleted_by', 'deleted_on'],
        order_by: 'creation asc',
        limit_page_length: 0
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

// The initials chip (SH, AD...) of a commenter is coloured by role: Comment finance Prepare = yellow, Reviewer Level 1 = green,
// Reviewer Level 2 = red. The same colours replace the brown of the row markers / "N commented" pill / left bar (see setRoleVars).
const avatarCls = u => {
    const r = FR.roleUsers[u];
    return r === 'prepare' ? ' is-prep' : r === 'review1' ? ' is-rev1' : r === 'review2' ? ' is-rev2' : '';
};

const ROLE_STYLE = {
    prepare: { c: '#f5c518', fg: '#3b2d00', tint: 'rgba(245,197,24,.14)' },
    review1: { c: '#3ddc84', fg: '#06361b', tint: 'rgba(61,220,132,.13)' },
    review2: { c: '#e5484d', fg: '#ffffff', tint: 'rgba(229,72,77,.11)' }
};
const ROLE_ORDER = ['prepare', 'review1', 'review2', 'none'];
const roleOf = u => FR.roleUsers[u] || 'none';
const bumpRole = (arr, r) => (arr || []).filter(x => x !== r).concat(r);       // distinct roles, the latest commenter's last
const rolesOfList = list => list.slice()
    .sort((a, b) => String(a.creation).localeCompare(String(b.creation)))
    .reduce((acc, c) => bumpRole(acc, roleOf(c.comment_added_by)), []);

// roles present on a set of rows, in a fixed order (used by the note pill, the note chip dot and the legend badge)
function unionRoles(rows) {
    const seen = new Set();
    rows.forEach(tr => (FR.rowRoles[tr.dataset.key] || []).forEach(r => seen.add(r)));
    return ROLE_ORDER.filter(r => seen.has(r));
}

// Colour the comment indicators of `el` by the roles of its commenters: one role = that colour; several roles = split badge
// (all of them), left bar and tint of the latest one. Nobody with a role on it -> variables are removed, brown (sage) stays.
function setRoleVars(el, roles) {
    if (!el) return;
    const names = ['--rc-badge', '--rc-pill', '--rc-fg', '--rc-shadow', '--rc-bar', '--rc-tint'];
    if (!roles || !roles.some(r => r !== 'none')) { names.forEach(n => el.style.removeProperty(n)); return; }
    const none = FR.cmtOf !== 'current' ? '#4a8570' : '#b0763a';
    const colors = roles.map(r => r === 'none' ? none : ROLE_STYLE[r].c);
    const n = colors.length, latest = roles[n - 1];
    const stops = colors.map((c, i) => `${c} ${i * 100 / n}% ${(i + 1) * 100 / n}%`).join(',');
    el.style.setProperty('--rc-badge', n === 1 ? colors[0] : `conic-gradient(${stops})`);
    el.style.setProperty('--rc-pill', n === 1 ? colors[0] : `linear-gradient(90deg,${stops})`);
    el.style.setProperty('--rc-fg', n === 1 ? ROLE_STYLE[latest].fg : '#fff');
    el.style.setProperty('--rc-shadow', n === 1 ? 'none' : '0 1px 1px rgba(0,0,0,.55)');
    el.style.setProperty('--rc-bar', colors[n - 1]);
    if (ROLE_STYLE[latest]) el.style.setProperty('--rc-tint', ROLE_STYLE[latest].tint);
    else el.style.removeProperty('--rc-tint');
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
        frappe.xcall('financial_report_tool.financial_report_tool.doctype.financial_report_comments.financial_report_comments.delete_comment', { name })
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

/* ---------------------------------------------------------------------
   ADD COMMENT
--------------------------------------------------------------------- */
// Send button / Enter: saves the comment on the report whose chat is on screen, then updates the open thread, the row marker,
// the section pill, the legend and the report cards without reloading. Two sends at once are blocked (FR.sending).
// Only a Financial Report Manager can write; the server checks this again.
function submitComment() {
    if (!FR.active || !FR.canComment || FR.sending) return;
    const cid = commentReportId(FR.report);
    if (!cid) return frappe.show_alert({ message: 'No report found for that month', indicator: 'orange' });

    const text = FR.dom.input.value.trim();
    if (!text) {
        return frappe.show_alert({ message: 'Write a comment first', indicator: 'orange' });
    }

    const ctx = FR.active;
    const btn = FR.dom.send;
    FR.sending = true;
    btn.disabled = true;
    btn.classList.add('is-busy');

    frappe.xcall('frappe.client.insert', {
        doc: {
            doctype: FR_CONFIG.COMMENT_DOCTYPE,
            financial_report: cid,                          // the report whose chat is on screen (the open one, or the chosen month's report)
            comment_added_by: frappe.session.user,
            note_no: ctx.noteId,
            section_type: ctx.sectionType,
            row_index: ctx.rowIndex,
            row_label: ctx.rowEl.querySelector('td')?.innerText || '',
            comment: text
        }
    }).then(saved => {
        const box = FR.dom.thread;
        if (box.querySelector('.fr-thread-empty')) {
            box.innerHTML = '';
            FR.thread = { lastAuthor: null, lastTs: 0, lastDay: null };
        }

        appendMessage({
            name: saved && saved.name,
            comment: text,
            comment_added_by: frappe.session.user,
            creation: (saved && saved.creation) || frappe.datetime.convert_to_system_tz(frappe.datetime.now_datetime())      // stored times are in the system time zone
        });
        const last = box.lastElementChild;
        if (last) last.classList.add('is-new');
        box.scrollTop = box.scrollHeight;

        FR.counts[ctx.key] = (FR.counts[ctx.key] || 0) + 1;
        FR.reportComments[cid] = (FR.reportComments[cid] || 0) + 1;
        renderReportCards();
        FR.rowRoles[ctx.key] = bumpRole(FR.rowRoles[ctx.key], roleOf(frappe.session.user));
        paintMarker(ctx.rowEl, FR.counts[ctx.key]);
        refreshNoteMeta(ctx.rowEl.closest('.fr-note'));
        updateCommentedLegend();
        if (FR.filter.only) applyFilters();
        if (FR.cmtOf !== 'current') refreshCmtList();            // the chat column of that month follows the chat

        // refresh the people strip
        const users = uniq([...FR.dom.stack.querySelectorAll('i[data-u]')].map(i => i.dataset.u).concat(frappe.session.user));
        FR.dom.stack.innerHTML = users.slice(0, 4).map(personChip).join('');
        const n = FR.counts[ctx.key];
        FR.dom.count.textContent = `${n} comment${n > 1 ? 's' : ''} · ${users.length} ${users.length === 1 ? 'person' : 'people'}`;

        FR.dom.input.value = '';
        autoGrow();
        frappe.show_alert({ message: 'Comment sent', indicator: 'green' });
    }).finally(() => {
        FR.sending = false;
        btn.disabled = false;
        btn.classList.remove('is-busy');
        FR.dom.input.focus({ preventScroll: true });
    });
}

/* ---------------------------------------------------------------------
   HELPERS
--------------------------------------------------------------------- */
// The part of a user id before the "@" ("indrajeet@mail.com" -> "indrajeet"); "User" when empty.
const userName = u => (u || 'User').split('@')[0];

// Initials of a user for avatars: "indrajeet" -> "IN", "shivam.shrivastava" -> "SS".
function initials(name) {
    const parts = (name || '').replace(/[._-]/g, ' ').split(' ').filter(Boolean);
    if (!parts.length) return '?';
    return parts.length > 1
        ? (parts[0][0] + parts[1][0]).toUpperCase()
        : name.substring(0, 2).toUpperCase();
}

// Every person gets one stable colour, so conversations are easy to follow
const PEOPLE_COLORS = ['#2f5d50', '#b0763a', '#5d7a8c', '#8c4f5e', '#7a7a3a', '#6b5b95'];
// A person's colour: the same name always gives the same one (a simple hash of the name picks from PEOPLE_COLORS).
function colorFor(name) {
    let h = 0;
    for (const ch of String(name)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    return PEOPLE_COLORS[h % PEOPLE_COLORS.length];
}

// Frappe returns "YYYY-MM-DD HH:mm:ss.ffffff" in the SYSTEM time zone; make it Safari-safe (used for dates without a clock too)
function parseDate(dt) {
    return new Date(String(dt || '').replace(' ', 'T'));
}

// ---- comment dates ------------------------------------------------------------------------------
// A stored time is converted from the system time zone to the user's own, and written in the date / time format
// chosen in System Settings (e.g. 15-01-2026 17:17), exactly like the rest of Desk. Nothing depends on the browser's locale.
const userTz = () => (frappe.boot && frappe.boot.time_zone && frappe.boot.time_zone.system && frappe.boot.time_zone.user && moment.tz) ? frappe.boot.time_zone : null;

// A stored time (system time zone) as a moment in the user's own time zone; null when empty or not a date.
function userMoment(dt) {
    const s = String(dt || '').trim();
    if (!s) return null;
    const tz = userTz();
    const m = tz ? moment.tz(s, 'YYYY-MM-DD HH:mm:ss', tz.system).tz(tz.user) : moment(s, 'YYYY-MM-DD HH:mm:ss');
    return m.isValid() ? m : null;
}

// Today in the user's time zone (or the browser's, when Frappe gives no zone).
const nowInUserTz = () => { const tz = userTz(); return tz ? moment().tz(tz.user) : moment(); };
const userDateFmt = () => frappe.datetime.get_user_date_fmt().toUpperCase();                         // DD-MM-YYYY
const userClockFmt = () => frappe.datetime.get_user_time_fmt().replace(/[:.]ss/, '');               // HH:mm (seconds are noise in a chat)

// the calendar day of a stored time, in the user's time zone ("2026-01-15"): used to group a chat by day
const dayKey = dt => { const m = userMoment(dt); return m ? m.format('YYYY-MM-DD') : ''; };

// "17:17" for today, otherwise "15-01-2026, 17:17"
function timeLabel(dt) {
    const m = userMoment(dt);
    if (!m) return '';
    return m.format('YYYY-MM-DD') === nowInUserTz().format('YYYY-MM-DD') ? m.format(userClockFmt()) : m.format(`${userDateFmt()}, ${userClockFmt()}`);
}

// always with the date and the year: for comments of an earlier month
function fullTimeLabel(dt) {
    const m = userMoment(dt);
    return m ? m.format(`${userDateFmt()}, ${userClockFmt()}`) : '';
}

// day divider inside a chat: "Today", "Yesterday", or "Mon, 13-10-2025"
function dayLabel(dt) {
    const m = userMoment(dt);
    if (!m) return '';
    const now = nowInUserTz();
    if (m.format('YYYY-MM-DD') === now.format('YYYY-MM-DD')) return 'Today';
    if (m.format('YYYY-MM-DD') === now.clone().subtract(1, 'day').format('YYYY-MM-DD')) return 'Yesterday';
    return m.format(`ddd, ${userDateFmt()}`);
}

/* ---------------------------------------------------------------------
   STYLES   (every rule is scoped under .fr-root; no external resources)
--------------------------------------------------------------------- */
function injectStyles() {
    if (document.getElementById('fr-styles')) return;

    const style = document.createElement('style');
    style.id = 'fr-styles';
    style.textContent = `

    /* ============================ TOKENS ============================
       "Sage & Bronze"
       Sage   = structure (headers, note numbers, your messages, links)
       Bronze = conversation (comment markers, counts, badges)
       Mist   = the row you are looking at
       Muted, low-saturation, compact: calm for long review sessions.     */
    .fr-root {
        --ink: #1f2d29;
        --ink-soft: #66756f;
        --paper: #ffffff;
        --paper-tint: #f5f7f4;
        --paper-glass: rgba(255,255,255,.92);
        --rule: #e4e9e4;
        --rule-strong: #c9d3cb;

        --brand: #2f5d50;
        --brand-deep: #1f4337;
        --brand-2: #4a8570;
        --brand-soft: #e6eee9;
        --brand-wash: rgba(47,93,80,.055);
        --brand-wash-2: rgba(47,93,80,.1);
        --accent: #b0763a;
        --sel: #dbe8e1;
        --sel-ink: #1b3a30;

        --grad-main: linear-gradient(120deg, #2a5348 0%, #4a8570 100%);
        --grad-talk: linear-gradient(135deg, #c48a4d 0%, #a2652b 100%);

        --tick: #b0763a;
        --tick-fg: #ffffff;
        --tick-bg: rgba(176,118,58,.08);
        --danger: #b3382f;
        --neg: #b3382f;

        --shadow: 0 1px 2px rgba(30,52,46,.05), 0 8px 24px -16px rgba(30,52,46,.28);
        --shadow-soft: 0 1px 2px rgba(30,52,46,.06);
        --radius: 12px;
        --font: 'Avenir Next', 'Segoe UI Variable Text', 'Segoe UI', Roboto, 'Helvetica Neue', system-ui, sans-serif;
        --display: 'Avenir Next', 'Segoe UI Variable Display', 'Segoe UI', Roboto, system-ui, sans-serif;
        --sticky-top: 92px;

        font-family: var(--font);
        color: var(--ink);
        margin-top: 0;
    }
    [data-theme="dark"] .fr-root {
        --ink: #e6eee9;
        --ink-soft: #9db0a6;
        --paper: #17211e;
        --paper-tint: #1d2a26;
        --paper-glass: rgba(23,33,30,.92);
        --rule: #29392f;
        --rule-strong: #405448;
        --brand: #7fbfa5;
        --brand-deep: #b6e0cf;
        --brand-2: #62a88b;
        --brand-soft: rgba(127,191,165,.14);
        --brand-wash: rgba(127,191,165,.07);
        --brand-wash-2: rgba(127,191,165,.13);
        --accent: #e0a766;
        --sel: #23463b;
        --sel-ink: #dcefe6;
        --tick: #e0a766;
        --tick-fg: #2b1b08;
        --tick-bg: rgba(224,167,102,.11);
        --neg: #f09a93;
        --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.8);
        --shadow-soft: 0 1px 2px rgba(0,0,0,.4);
    }
    .fr-root *, .fr-root *::before, .fr-root *::after { box-sizing: border-box; }
    .fr-root button, .fr-root select, .fr-root input, .fr-root textarea { font-family: inherit; }
    .fr-root [hidden] { display: none !important; }

    /* ============================ FILTER PANEL ============================ */
    .fr-filters {
        position: relative; overflow: hidden;
        margin-bottom: 10px; padding: 12px 16px 12px;
        background: var(--paper); border: 1px solid var(--rule); border-radius: var(--radius); box-shadow: var(--shadow);
    }
    .fr-filters::before { content: ''; position: absolute; left: 0; right: 0; top: 0; height: 3px; background: var(--grad-main); }
    .fr-reset {
        margin-left: auto;
        display: inline-flex; align-items: center; gap: 6px; flex: none; height: 24px; padding: 0 9px;
        border: 1px solid var(--rule-strong); border-radius: 8px; background: var(--paper); color: var(--ink-soft);
        font-size: 12px; font-weight: 700; cursor: pointer; transition: color .15s, border-color .15s;
    }
    .fr-reset:hover { color: var(--tick); border-color: var(--tick); }
    .fr-theme {
        display: inline-grid; place-items: center; flex: none; width: 28px; height: 24px; margin: 0 0 0 6px; padding: 0;
        border: 1px solid var(--rule-strong); border-radius: 8px; background: var(--paper); color: var(--ink-soft); cursor: pointer;
        transition: color .15s, border-color .15s, background .15s;
    }
    .fr-reset[hidden] + .fr-theme { margin-left: auto; }
    .fr-theme:hover { color: var(--brand); border-color: var(--brand); background: var(--brand-soft); }
    .fr-theme:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
    /* Frappe toasts sit over the page; let clicks pass through them so the Send button is never swallowed */
    body.fr-page-open #alert-container, body.fr-page-open .desk-alert { pointer-events: none; }

    .fr-filter-grid { display: grid; grid-template-columns: 2fr 1fr 1fr 1.3fr; gap: 10px; }
    /* "Comments of" switch: while another month than the open report's is chosen, markers and highlights turn sage so the two views are never confused.
       A commenter's role colour (--rc-*, set from JS) still wins; sage is only the colour of rows nobody with a role wrote on. */
    .fr-root .fr-sheet.fr-othermonth .fr-marker.is-filled, .fr-root .fr-sheet.fr-othermonth .fr-legend .lg-badge { background: var(--rc-badge, var(--grad-main)); }
    .fr-root .fr-sheet.fr-othermonth .fr-commented { background: var(--rc-pill, var(--grad-main)); }
    .fr-root .fr-sheet.fr-othermonth .fr-table tbody tr.has-comments:not(.is-active):not(:hover) td { background: var(--rc-tint, var(--brand-wash-2)) !important; }
    .fr-root .fr-sheet.fr-othermonth .fr-table tbody tr.has-comments:not(.is-active) td:first-child { box-shadow: inset 3px 0 0 var(--rc-bar, var(--brand)); }

    /* previous-month chat column, right after "Year Ended ...": who wrote what on that row last month */
    .fr-root .fr-table th.fr-chatcol { min-width: 230px; width: 250px; text-align: left !important; white-space: nowrap; color: var(--brand-deep) !important; background: var(--brand-soft) !important; }
    .fr-root .fr-table td.fr-chatcol { min-width: 230px; max-width: 300px; padding: 4px 10px !important; text-align: left !important; white-space: normal !important; font-size: 11.5px; font-weight: 500; line-height: 1.35; vertical-align: top; border-left: 1px solid var(--rule) !important; cursor: default; }
    /* with the comment panel open there is less room: the chat column gets narrower */
    .fr-root .fr-shell.drawer-open .fr-table th.fr-chatcol { min-width: 170px; width: 170px; }
    .fr-root .fr-shell.drawer-open .fr-table td.fr-chatcol { min-width: 170px; max-width: 200px; }
    .fr-root .fr-table td.fr-chatcol.has-chat { cursor: pointer; }
    .fr-root .fr-table td.fr-chatcol.has-chat:hover { background: var(--brand-wash-2) !important; }
    .fr-cc-u { display: flex; align-items: flex-start; gap: 6px; padding: 2px 0; }
    .fr-cc-u + .fr-cc-u { border-top: 1px dashed var(--rule); }
    .fr-cc-av { flex: none; display: grid; place-items: center; width: 18px; height: 18px; margin-top: 1px; border-radius: 6px; background: var(--av, #64748b); color: #fff; font-size: 8.5px; font-weight: 800; }
    .fr-cc-b { min-width: 0; }
    .fr-cc-b > b { display: block; font-weight: 800; font-size: 11px; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .fr-cc-t { display: block; word-break: break-word; color: var(--ink); }
    .fr-cc-d { display: block; font-size: 9.5px; font-weight: 600; color: var(--ink-soft); }
    .fr-cc-more { display: block; padding-top: 2px; font-size: 10.5px; font-weight: 800; color: var(--brand); }
    .fr-field { display: flex; flex-direction: column; gap: 4px; margin: 0; min-width: 0; }
    .fr-field > span { font-size: 10.5px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-soft); }
    .fr-field select {
        width: 100%; height: 36px; padding: 0 34px 0 12px; margin: 0; cursor: pointer;
        font-size: 13px; font-weight: 600; color: var(--ink);
        background-color: var(--paper-tint); border: 1px solid var(--rule); border-radius: 9px; outline: 0; box-shadow: none;
        -webkit-appearance: none; appearance: none;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%232f5d50' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
        background-repeat: no-repeat; background-position: right 12px center;
        transition: border-color .15s, background-color .15s, box-shadow .15s;
    }
    .fr-field select:hover { border-color: var(--rule-strong); }
    .fr-field select:focus { background-color: var(--paper); border-color: var(--brand); box-shadow: 0 0 0 3px rgba(47,93,80,.16); }
    .fr-field select.has-value { background-color: var(--brand-soft); border-color: var(--brand); color: var(--brand-deep); }
    .fr-field select option { color: #1f2d29; background: #fff; }

    .fr-results { margin-top: 8px; padding-top: 6px; border-top: 1px dashed var(--rule-strong); }
    .fr-results-bar { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 4px; }
    .fr-results-count { font-size: 12px; font-weight: 700; color: var(--ink-soft); }
    .fr-report-list { display: flex; flex-wrap: wrap; gap: 6px; max-height: 96px; overflow-y: auto; padding: 1px; scrollbar-width: thin; }
    .fr-report-card {
        position: relative; overflow: hidden;
        display: flex; flex-direction: row; align-items: center; gap: 8px; min-width: 0; max-width: 100%; padding: 5px 10px 5px 14px;
        text-align: left; cursor: pointer; border-radius: 8px;
        background: var(--paper); border: 1px solid var(--rule); color: var(--ink);
        transition: border-color .15s, box-shadow .15s;
    }
    .fr-report-card::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--grad-main); opacity: .5; transition: opacity .15s; }
    .fr-report-card strong { font-size: 12.5px; font-weight: 800; white-space: nowrap; }
    .fr-report-card span { font-size: 12px; color: var(--ink-soft); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
    .fr-card-count {
        flex: none; min-width: 20px; height: 18px; padding: 0 6px; border-radius: 99px;
        display: grid; place-items: center; font-style: normal; font-size: 11px; font-weight: 800;
        background: var(--grad-talk); color: #fff;
    }
    .fr-report-card:hover { border-color: var(--brand); box-shadow: var(--shadow-soft); }
    .fr-report-card:hover::before { opacity: 1; }
    .fr-report-card.is-open { background: var(--grad-main); border-color: transparent; color: #fff; }
    .fr-report-card.is-open::before { opacity: 0; }
    .fr-report-card.is-open span { color: rgba(255,255,255,.85); }
    .fr-report-card.is-open .fr-card-count { background: #fff; color: var(--accent); }
    /* report cards show the chosen month's chat count while "Comments of" is not "this month": sage badge, same colour as the panel */
    .fr-report-card.is-otherchat .fr-card-count { background: var(--grad-main); }
    .fr-report-card.is-otherchat.is-open .fr-card-count { background: #fff; color: var(--brand); }
    .fr-report-card:focus-visible, .fr-reset:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }

    /* ============================ LAYOUT ============================ */
    .fr-shell {
        display: grid; grid-template-columns: minmax(0, 1fr) 0px; align-items: start;
        transition: grid-template-columns .3s cubic-bezier(.2,.8,.2,1), column-gap .3s;
    }
    .fr-shell.drawer-open { grid-template-columns: minmax(0, 1fr) 380px; column-gap: 14px; }
    .fr-sheet { min-width: 0; padding-bottom: 60px; }

    /* ============================ REPORT REVIEW ============================ */
    /* one small round chip per review role (--c / --fg come from ROLE_STYLE). Not reviewed = white with a role-coloured ring,
       reviewed = filled with the role colour + a tick. Name, time and status show in a tooltip on hover / keyboard focus. */
    .fr-review { display: flex; align-items: center; gap: 6px; }
    .fr-review-l { margin-right: 2px; font-size: 11px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: var(--ink-soft); }
    .fr-rv {
        --c: #64748b; --fg: #fff;
        position: relative; display: inline-grid; place-items: center; flex: none; width: 26px; height: 26px; margin: 0; padding: 0; border-radius: 50%;
        border: 2px solid var(--c); background: var(--paper); color: var(--ink); font: 800 9.5px/1 var(--font); letter-spacing: -.2px;
        cursor: default; transition: background .15s, color .15s, transform .12s, box-shadow .12s;
    }
    button.fr-rv { cursor: pointer; }
    button.fr-rv:hover { transform: scale(1.1); box-shadow: 0 0 0 3px color-mix(in srgb, var(--c) 28%, transparent); }
    button.fr-rv:active { transform: scale(.96); }
    button.fr-rv:disabled { opacity: .6; cursor: progress; }
    .fr-rv:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
    .fr-rv.is-done { background: var(--c); color: var(--fg); }
    .fr-rv-ok {
        position: absolute; right: -5px; bottom: -5px; display: none; place-items: center; width: 13px; height: 13px; border-radius: 50%;
        background: #fff; color: var(--c); border: 1.5px solid var(--c);
    }
    .fr-rv-ok svg { width: 8px; height: 8px; }
    .fr-rv.is-done .fr-rv-ok { display: grid; }
    .fr-rv::after {
        content: attr(data-tip); position: absolute; z-index: 40; top: calc(100% + 8px); left: 0; padding: 5px 9px; border-radius: 7px;
        background: #14201c; color: #fff; border: 1px solid rgba(255,255,255,.14); box-shadow: 0 6px 18px rgba(0,0,0,.28);
        font: 600 11.5px/1.3 var(--font); letter-spacing: 0; white-space: nowrap; pointer-events: none;
        opacity: 0; visibility: hidden; transform: translateY(-3px); transition: opacity .12s, transform .12s, visibility 0s .12s;
    }
    .fr-rv:hover::after, .fr-rv:focus-visible::after { opacity: 1; visibility: visible; transform: none; transition: opacity .12s, transform .12s, visibility 0s; }
    /* the chips sit inside the legend line: the generic ".fr-legend span / i" rules must not restyle them */
    .fr-legend .fr-rv { display: inline-grid; gap: 0; width: 26px; height: 26px; }
    .fr-legend .fr-rv-ok { display: none; min-width: 0; width: 13px; height: 13px; padding: 0; font-size: 0; }
    .fr-legend .fr-rv.is-done .fr-rv-ok { display: grid; }
    .fr-legend .fr-review-l { display: inline; }

    /* ============================ LEGEND ============================ */
    .fr-legend { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 0 2px 8px; font-size: 12px; font-weight: 500; color: var(--ink-soft); }
    .fr-legend span { display: inline-flex; align-items: center; gap: 6px; }
    .fr-legend i { display: inline-grid; place-items: center; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 99px; font-style: normal; font-size: 10px; font-weight: 800; }
    .fr-legend-comments {
        display: inline-flex; align-items: center; gap: 6px; margin: 0; padding: 2px 9px 2px 3px; border: 1px solid transparent; border-radius: 99px;
        background: transparent; color: var(--ink-soft); font: inherit; font-size: 12px; font-weight: 600; cursor: pointer;
        transition: background .12s, border-color .12s, color .12s;
    }
    .fr-legend-comments:hover { background: var(--tick-bg); border-color: var(--tick); color: var(--ink); }
    .fr-legend-comments:active { transform: scale(.98); }
    .fr-legend-comments:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
    .fr-legend-comments span { text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 3px; }
    .fr-legend .lg-badge { background: var(--rc-badge, var(--grad-talk)); color: var(--rc-fg, #fff); text-shadow: var(--rc-shadow, none); }

    /* ============================ TOOLBAR ============================ */
    .fr-toolbar {
        position: sticky; top: var(--sticky-top); z-index: 6;
        display: flex; align-items: center; justify-content: space-between; gap: 12px;
        padding: 4px 6px; margin-bottom: 10px;
        background: var(--paper-glass); border: 1px solid var(--rule); border-radius: 12px;
        backdrop-filter: blur(12px) saturate(1.3); -webkit-backdrop-filter: blur(12px) saturate(1.3);
        box-shadow: var(--shadow);
    }
    .fr-chips { display: flex; gap: 4px; min-width: 0; padding: 1px; overflow-x: auto; scrollbar-width: none; }
    .fr-chips::-webkit-scrollbar { display: none; }
    .fr-chip {
        flex: none; display: inline-flex; align-items: center; gap: 6px; padding: 5px 11px; border-radius: 8px; cursor: pointer;
        border: 1px solid transparent; background: transparent; color: var(--ink-soft); font-size: 12px; font-weight: 700;
        transition: background .15s, color .15s;
    }
    .fr-chip:hover { color: var(--brand-deep); background: var(--brand-soft); }
    .fr-chip.is-current { background: var(--brand); color: #fff; }
    .fr-chip:focus-visible, .fr-toggle:focus-visible, .fr-note-toggle:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
    .fr-dot { width: 6px; height: 6px; border-radius: 50%; background: transparent; }
    .fr-chip.has-comments .fr-dot { background: var(--rc-badge, var(--tick)); box-shadow: 0 0 0 2px rgba(176,118,58,.24); }
    .fr-chip.is-current.has-comments .fr-dot { background: #fff; box-shadow: 0 0 0 2px rgba(255,255,255,.3); }

    .fr-tools { display: flex; align-items: center; gap: 6px; flex: none; }
    .fr-search {
        display: flex; align-items: center; gap: 6px; height: 30px; margin: 0; padding: 0 10px; border-radius: 8px;
        background: var(--paper-tint); color: var(--ink-soft); border: 1px solid transparent; transition: border-color .15s, background .15s;
    }
    .fr-search:focus-within { background: var(--paper); border-color: var(--brand); color: var(--brand); }
    .fr-search input { width: 150px; height: 100%; padding: 0; border: 0; outline: 0; background: transparent; box-shadow: none; font-size: 12.5px; color: var(--ink); }
    .fr-search input::placeholder { color: var(--ink-soft); }
    .fr-toggle {
        display: inline-flex; align-items: center; gap: 7px; height: 30px; padding: 0 11px 0 9px; border-radius: 8px; cursor: pointer; white-space: nowrap;
        background: var(--paper-tint); color: var(--ink-soft); border: 1px solid transparent; font-size: 12px; font-weight: 700;
        transition: border-color .15s, color .15s;
    }
    .fr-toggle i { position: relative; width: 26px; height: 15px; border-radius: 99px; background: var(--rule-strong); transition: background .2s; }
    .fr-toggle i::after { content: ''; position: absolute; top: 2px; left: 2px; width: 11px; height: 11px; border-radius: 50%; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,.25); transition: transform .2s; }
    .fr-toggle[aria-pressed="true"] { color: var(--tick); border-color: var(--tick); }
    .fr-toggle[aria-pressed="true"] i { background: var(--grad-talk); }
    .fr-toggle[aria-pressed="true"] i::after { transform: translateX(11px); }

    .fr-expandall {
        display: inline-grid; place-items: center; flex: none; width: 30px; height: 30px; margin: 0; padding: 0; border-radius: 8px; cursor: pointer;
        background: var(--paper-tint); color: var(--ink-soft); border: 1px solid transparent; transition: color .15s, border-color .15s, background .15s;
    }
    .fr-expandall:hover { color: var(--brand); border-color: var(--brand); background: var(--brand-soft); }
    .fr-expandall:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
    .fr-expandall svg { width: 16px; height: 16px; }

    /* ============================ NOTES ============================ */
    .fr-note { display: grid; grid-template-columns: 30px minmax(0, 1fr); column-gap: 12px; margin-bottom: 4px; scroll-margin-top: calc(var(--sticky-top) + 52px); }
    .fr-note.is-filtered-out { display: none; }
    .fr-note-spine { position: relative; display: flex; justify-content: center; }
    .fr-note-spine::before {                  /* thread linking the notes */
        content: ''; position: absolute; top: 32px; bottom: -4px; width: 2px; border-radius: 2px;
        background: linear-gradient(to bottom, var(--brand), transparent); opacity: .3;
    }
    .fr-note-spine span {
        position: relative; z-index: 1; display: grid; place-items: center; width: 28px; height: 28px; border-radius: 8px;
        background: var(--grad-main); color: #fff; font-family: var(--display); font-weight: 800; font-size: 12px;
    }
    .fr-note-spine span.is-glyph { font-size: 9px; letter-spacing: 0; }
    .fr-note-body { min-width: 0; padding-bottom: 6px; }
    .fr-note-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 28px; }
    .fr-note-titlewrap { display: flex; flex-direction: column; gap: 0; min-width: 0; }
    .fr-note-kicker { font-size: 10px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: var(--brand); line-height: 1.2; }
    .fr-note-title { margin: 0; font-family: var(--display); font-weight: 800; font-size: 16px; line-height: 1.2; letter-spacing: -.01em; }
    .fr-note-toggle {
        display: inline-flex; align-items: center; gap: 6px; margin: 0; padding: 0 8px 0 0; border: 0; border-radius: 8px; background: transparent;
        cursor: pointer; text-align: left; font: inherit; letter-spacing: inherit; color: var(--ink);
    }
    .fr-chev { flex: none; width: 14px; height: 14px; color: var(--brand); transition: transform .2s; }
    .fr-note.is-collapsed .fr-chev { transform: rotate(-90deg); }
    .fr-note-meta { flex: none; display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; font-weight: 700; color: var(--ink-soft); }
    .fr-rowcount, .fr-commented { display: inline-flex; align-items: center; gap: 5px; padding: 4px 9px; border-radius: 99px; line-height: 1; white-space: nowrap; }
    .fr-rowcount { background: var(--paper); border: 1px solid var(--rule); }
    .fr-rowcount svg { color: var(--brand); }
    .fr-commented { margin: 0; font-weight: 800; color: var(--rc-fg, #fff); background: var(--rc-pill, var(--grad-talk)); text-shadow: var(--rc-shadow, none); }
    .fr-note.is-collapsed .fr-note-content { display: none; }
    .fr-note-desc { max-width: none; margin-top: 0; font-size: 12.5px; line-height: 1.55; color: var(--ink-soft); }
    .fr-note-desc:not(:empty) { margin-bottom: 6px; }
    .fr-note-desc .ql-editor { padding: 0 !important; min-height: 0 !important; overflow: visible !important; }
    .fr-note-desc p { margin-bottom: 4px; }
    .fr-note-desc p:last-child { margin-bottom: 0; }
    .fr-note-desc p:empty { display: none; }
    /* stored HTML pulls headings over the table with negative margins; the table is a card now, so undo that */
    .fr-note-desc :is(h5, p, div, strong, span)[style*="margin-bottom: -"], .fr-note-desc :is(h5, p, div, strong, span)[style*="margin-bottom:-"] { margin-bottom: 6px !important; }
    .fr-note-desc :is(h5, p, div, strong, span)[style*="margin-top: -"], .fr-note-desc :is(h5, p, div, strong, span)[style*="margin-top:-"] { margin-top: 0 !important; }
    .fr-note-desc h5 {
        display: flex; align-items: center; gap: 8px; margin: 8px 0 6px; padding: 0 !important;
        font-family: var(--display); font-size: 13px !important; font-weight: 800 !important; color: var(--ink);
    }
    .fr-note-desc h5::before { content: ''; flex: none; width: 4px; height: 14px; border-radius: 3px; background: var(--grad-main); }
    .fr-note.is-flash .fr-note-title { animation: frFlash 1.4s ease-out; border-radius: 8px; }
    @keyframes frFlash { 0% { background: var(--sel); box-shadow: 0 0 0 6px var(--sel); } 100% { background: transparent; box-shadow: 0 0 0 6px transparent; } }

    /* schedule jump: a statement row that has a note opens that note */
    .fr-root .fr-table tbody tr.has-schedule { cursor: pointer; }
    .fr-root .fr-table tbody tr.has-schedule td.fr-label::after { content: '\\2197'; margin-left: 6px; font-size: 11px; font-weight: 800; color: var(--brand); opacity: 0; transition: opacity .12s; }
    .fr-root .fr-table tbody tr.has-schedule:hover td.fr-label::after { opacity: 1; }
    .fr-root .fr-table tbody tr.is-flash-row td { animation: frRowFlash 1.8s ease-out; }
    @keyframes frRowFlash { 0%, 35% { box-shadow: inset 0 0 0 999px var(--sel); } 100% { box-shadow: inset 0 0 0 999px transparent; } }
    .fr-note-back {
        flex: none; display: inline-flex; align-items: center; gap: 5px; height: 24px; margin: 0; padding: 0 10px; border: 1px solid var(--brand); border-radius: 8px;
        background: var(--brand-soft); color: var(--brand-deep); font-size: 12px; font-weight: 700; cursor: pointer; transition: background .12s, color .12s;
    }
    .fr-note-back:hover { background: var(--brand); color: #fff; }
    .fr-note-back:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }

    /* ============================ TABLES ============================
       The stored table HTML styles itself inline (black grid, white and
       green fills), so every visual rule here is !important on purpose.
       decorateTable() tags rows/columns; this block only paints them.     */
    .fr-table-wrap { margin: 4px 0 6px; overflow-x: auto; background: var(--paper); border: 1px solid var(--rule); border-radius: var(--radius); box-shadow: var(--shadow-soft); }
    .fr-root table.fr-table { width: 100% !important; margin: 0 !important; table-layout: auto; border-collapse: separate !important; border-spacing: 0; background: transparent !important; border: 0 !important; font-size: 12.5px; font-variant-numeric: tabular-nums; }
    .fr-root .fr-table caption { caption-side: top; padding: 6px 12px 2px; text-align: right; font-size: 11.5px; font-weight: 700; font-style: italic; color: var(--ink-soft) !important; }
    .fr-root .fr-table a { color: inherit !important; text-decoration: none; border: 0; transition: color .15s; }
    .fr-root .fr-table a:hover { color: var(--brand) !important; text-decoration: underline; text-underline-offset: 3px; }

    /* header: light teal tint with a teal rule; the current period is a shade deeper */
    .fr-root .fr-table th {
        padding: 7px 12px !important; border: 0 !important; border-left: 1px solid var(--rule) !important;
        background: var(--brand-soft) !important; color: var(--brand-deep) !important; vertical-align: middle;
        border-bottom: 2px solid var(--brand) !important;
        font-weight: 800 !important; font-size: 10.5px !important; letter-spacing: .07em; text-transform: uppercase; line-height: 1.3; word-break: break-word;
    }
    .fr-root .fr-table th:first-child { border-left: 0 !important; }
    /* a header word is never cut in the middle: when space is short the table scrolls sideways instead of squeezing a column to one letter per line */
    .fr-root .fr-table th:not(:empty):not(.fr-gutter) { word-break: normal !important; overflow-wrap: normal !important; min-width: 84px; }
    .fr-root .fr-table th.fr-noteno { min-width: 84px; }
    .fr-root .fr-table th.fr-cur { background: color-mix(in srgb, var(--brand) 24%, var(--paper)) !important; border-bottom-color: var(--brand-2) !important; }
    /* the stored header <tr> carries an inline light-grey fill (#f1f1f1); in dark mode the cell fills are translucent, so it must not show through */
    .fr-root .fr-table tr, .fr-root .fr-table thead { background: transparent !important; }
    .fr-root .fr-table th.fr-noteno { text-align: center !important; white-space: nowrap !important; width: 84px !important; min-width: 84px !important; padding-left: 8px !important; padding-right: 8px !important; }
    .fr-root .fr-table th.fr-gutter { border-left: 0 !important; }

    /* body cells */
    .fr-root .fr-table td {
        padding: 5px 12px !important; border: 0 !important; border-bottom: 1px solid var(--rule) !important;
        background: transparent !important; vertical-align: middle; line-height: 1.35; word-break: break-word; color: var(--ink);
        transition: background .12s;
    }
    .fr-root .fr-table tbody tr:last-child td { border-bottom: 0 !important; }
    .fr-root .fr-table tbody tr:nth-child(even) td { background: var(--brand-wash) !important; }
    .fr-root .fr-table:not(.fr-statement) td:first-child, .fr-root .fr-table:not(.fr-statement) th:first-child { min-width: 180px; padding-left: 14px !important; }
    .fr-root .fr-table:not(.fr-statement) tbody td:first-child { font-weight: 600; }
    .fr-root .fr-table th.fr-num, .fr-root .fr-table td.fr-num { min-width: 84px; padding-right: 14px !important; text-align: right !important; white-space: nowrap; }
    .fr-root .fr-table th.fr-num { white-space: normal; min-width: 96px; width: auto !important; word-break: normal !important; overflow-wrap: normal; }
    .fr-root .fr-table td.fr-num:not(.fr-noteno) { font-variant-numeric: tabular-nums lining-nums; }
    .fr-root .fr-table td.fr-num { font-weight: 600; }
    .fr-root .fr-table td.fr-nil { color: var(--ink-soft) !important; font-weight: 400; }
    .fr-root .fr-table td.fr-blank::after { content: '–'; color: var(--ink-soft); opacity: .45; font-weight: 400; }
    .fr-root .fr-table tr.fr-total td.fr-num:empty::after { content: '–'; color: var(--ink-soft); opacity: .45; font-weight: 400; }
    .fr-root .fr-table td.fr-neg { color: var(--neg) !important; font-weight: 700; }

    /* statement columns: (I) index · particulars · note no. */
    .fr-root .fr-table .fr-idx { width: 58px; min-width: 58px; padding-left: 8px !important; padding-right: 2px !important; text-align: center !important; white-space: nowrap; }
    .fr-root .fr-table .fr-label { min-width: 200px; padding-left: calc(10px + var(--ind, 0) * 16px) !important; text-align: left !important; line-height: 1.35; }
    .fr-root .fr-table td.fr-label.fr-item { padding-left: calc(10px + (var(--ind, 0) + 1) * 16px) !important; }
    .fr-root .fr-table td.fr-label.fr-item::before { content: ''; display: inline-block; width: 4px; height: 4px; margin-right: 8px; border-radius: 50%; background: var(--rule-strong); vertical-align: middle; transition: background .12s; }
    .fr-root .fr-table tr:hover td.fr-label.fr-item::before { background: var(--brand); }
    .fr-root .fr-table td.fr-noteno { width: 84px !important; min-width: 84px !important; text-align: center !important; white-space: nowrap; padding-left: 8px !important; padding-right: 8px !important; }
    .fr-root .fr-notepill {
        display: inline-grid; place-items: center; min-width: 24px; height: 18px; padding: 0 7px; border-radius: 99px;
        background: rgba(176,118,58,.13); color: #8a5522; font-size: 11px; font-weight: 800;
    }
    [data-theme="dark"] .fr-root .fr-notepill { color: #e8c28f; background: rgba(214,163,102,.16); }
    .fr-root .fr-romanpill {
        display: inline-flex; align-items: center; justify-content: center; min-width: 34px; height: 18px; padding: 0 7px; border-radius: 6px; white-space: nowrap;
        background: var(--brand-wash-2); color: var(--brand-deep); font-size: 11px; font-weight: 800; letter-spacing: .02em;
    }

    /* current-period column */
    .fr-root .fr-table tbody tr td.fr-cur { background: rgba(74,133,112,.09) !important; font-weight: 700; }

    /* row roles: group heading · total · key result */
    .fr-root .fr-table tbody tr.fr-group td { background: var(--brand-wash-2) !important; border-bottom-color: var(--rule-strong) !important; color: var(--brand-deep); }
    .fr-root .fr-table tbody tr.fr-group td.fr-label { font-size: 13px; font-weight: 800; }
    .fr-root .fr-table tbody tr.fr-total td { background: var(--brand-wash) !important; border-top: 1px solid var(--rule-strong) !important; font-weight: 800; }
    .fr-root .fr-table tbody tr.fr-total td.fr-cur { background: rgba(74,133,112,.14) !important; }
    .fr-root .fr-table tbody tr.fr-result td {
        background: var(--brand-wash-2) !important; border-top: 1.5px solid var(--brand) !important; border-bottom: 1.5px solid var(--brand) !important;
        font-size: 13px; font-weight: 800;
    }
    .fr-root .fr-table tbody tr.fr-result td.fr-cur { background: rgba(74,133,112,.2) !important; }
    .fr-root .fr-table tbody tr.fr-result .fr-romanpill { background: var(--brand); color: #fff; }

    /* interaction states (must stay AFTER the role rules) */
    .fr-root .fr-table tr.is-hidden { display: none; }
    .fr-root .fr-table tbody tr.has-comments td { background: var(--rc-tint, var(--tick-bg)) !important; }
    .fr-root .fr-table tbody tr.has-comments td:first-child { box-shadow: inset 3px 0 0 var(--rc-bar, var(--tick)); }
    .fr-root .fr-table tbody tr:hover td { background: var(--brand-wash-2) !important; }
    .fr-root .fr-table tbody tr.is-active td, .fr-root .fr-table tbody tr.is-active:hover td { background: var(--sel) !important; color: var(--sel-ink) !important; border-bottom-color: transparent !important; }
    .fr-root .fr-table tbody tr.is-active td:first-child { box-shadow: inset 3px 0 0 var(--brand); }
    .fr-root .fr-table tbody tr.is-active .fr-romanpill, .fr-root .fr-table tbody tr.is-active .fr-notepill { background: rgba(0,0,0,.09); color: var(--sel-ink); }
    .fr-root .fr-table tbody tr.is-active td.fr-neg { color: #a8122f !important; }

    /* ============================ MARGIN MARKER ============================ */
    .fr-root .fr-table th.fr-gutter, .fr-root .fr-table td.fr-gutter { width: 40px; min-width: 40px; max-width: 40px; padding: 0 8px 0 0 !important; text-align: center !important; }
    .fr-marker {
        display: inline-grid; place-items: center; width: 22px; height: 22px; padding: 0; border-radius: 50%; cursor: pointer; vertical-align: middle; opacity: 0;
        border: 1px dashed var(--rule-strong); background: var(--paper); color: var(--brand); font: 800 11px/1 var(--font);
        transition: opacity .12s, transform .15s, background .12s, border-color .12s, color .12s;
    }
    .fr-marker svg { width: 12px; height: 12px; }
    tr:hover .fr-marker, .fr-marker:focus-visible, .fr-marker.is-filled, tr.is-active .fr-marker { opacity: 1; }
    .fr-marker:hover { transform: scale(1.12); border-style: solid; border-color: var(--brand); background: var(--brand); color: #fff; }
    .fr-marker.is-filled, .fr-marker.is-filled:hover { border: 0; background: var(--rc-badge, var(--grad-talk)); color: var(--rc-fg, #fff); text-shadow: var(--rc-shadow, none); }
    .fr-marker:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
    @media (hover: none) { .fr-marker { opacity: 1; } }

    /* ============================ COMMENT CHANNEL ============================ */
    .fr-drawer {
        position: sticky; top: var(--sticky-top); height: calc(100vh - var(--sticky-top) - 16px); min-width: 0;
        display: flex; flex-direction: column; overflow: hidden;
        background: var(--paper); border: 1px solid var(--rule); border-radius: 14px;
        box-shadow: 0 18px 40px -22px rgba(30,52,46,.45), 0 1px 3px rgba(30,52,46,.08);
        opacity: 0; transform: translateX(20px); visibility: hidden; pointer-events: none;
        transition: opacity .2s, transform .3s cubic-bezier(.2,.8,.2,1), visibility 0s .3s;
    }
    .fr-shell.drawer-open .fr-drawer { opacity: 1; transform: none; visibility: visible; pointer-events: auto; transition: opacity .2s, transform .3s cubic-bezier(.2,.8,.2,1), visibility 0s; }

    .fr-drawer-head {
        position: relative;
        display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; padding: 10px 10px 10px 14px; color: #fff;
        background: linear-gradient(125deg, #2a5348 0%, #4a8570 100%);
    }
    .fr-drawer-ctx { min-width: 0; }
    .fr-drawer-kicker { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 10px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase; color: rgba(255,255,255,.82); }
    .fr-drawer-row {
        margin: 1px 0 0; font-family: var(--display); font-weight: 800; font-size: 15px; line-height: 1.25; color: #fff; word-break: break-word;
        display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    }
    .fr-drawer-people { display: flex; align-items: center; gap: 7px; margin-top: 5px; min-height: 20px; }
    .fr-stack { display: inline-flex; }
    .fr-stack i {
        display: grid; place-items: center; width: 22px; height: 22px; margin-left: -3px; border-radius: 50%; border: 2px solid rgba(255,255,255,.9);
        background: var(--av, #64748b); color: #fff; font-style: normal; font-size: 9px; font-weight: 800; letter-spacing: -.2px;
    }
    .fr-stack i:first-child { margin-left: 0; }
    .fr-stack i.more { background: rgba(255,255,255,.3); }
    .fr-drawer-count { font-size: 11.5px; font-weight: 600; color: rgba(255,255,255,.92); }
    .fr-drawer-actions { display: flex; flex: none; gap: 4px; }
    .fr-icon-btn { display: grid; place-items: center; width: 26px; height: 26px; border: 1px solid rgba(255,255,255,.3); border-radius: 8px; cursor: pointer; background: rgba(255,255,255,.16); color: #fff; transition: background .12s; }
    .fr-icon-btn:hover { background: rgba(255,255,255,.32); }
    .fr-icon-btn:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
    .fr-icon-btn svg { width: 13px; height: 13px; }

    /* thread */
    .fr-thread {
        flex: 1; overflow-y: auto; padding: 10px 12px 6px; scrollbar-width: thin;
        background-color: var(--paper-tint);
    }
    .fr-day { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; font-size: 10.5px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--ink-soft); }
    .fr-day::before, .fr-day::after { content: ''; flex: 1; height: 1px; background: var(--rule-strong); }

    .fr-msg { display: flex; align-items: flex-end; gap: 7px; margin-bottom: 9px; max-width: 100%; }
    .fr-msg.is-grouped { margin-top: -6px; }
    .fr-msg-col { display: flex; flex-direction: column; min-width: 0; max-width: 84%; }
    .fr-avatar {
        flex: none; display: grid; place-items: center; width: 26px; height: 26px; border-radius: 8px;
        background: var(--av, #64748b); color: #fff; font-size: 10px; font-weight: 800;
    }
    .fr-msg.is-grouped .fr-avatar { visibility: hidden; }
    .fr-author { margin: 0 0 2px 2px; font-size: 11.5px; font-weight: 800; color: var(--av, var(--ink-soft)); }
    [data-theme="dark"] .fr-author { filter: brightness(1.55); }

    .fr-bubble {
        position: relative; padding: 6px 11px 4px; border-radius: 4px 12px 12px 12px;
        background: var(--paper); border: 1px solid var(--rule); box-shadow: var(--shadow-soft);
    }
    .fr-msg.is-grouped .fr-bubble { border-top-left-radius: 12px; }
    .fr-msg-text { margin: 0; font-size: 13px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; color: var(--ink); }
    .fr-bubble time { display: block; margin-top: 2px; text-align: right; font-size: 10px; font-weight: 600; color: var(--ink-soft); }

    .fr-msg.is-own { justify-content: flex-end; }
    .fr-msg.is-own .fr-msg-col { align-items: flex-end; }
    .fr-msg.is-own .fr-author { margin: 0 2px 2px 0; color: var(--brand); filter: none; }
    .fr-msg.is-own .fr-bubble { border: 0; border-radius: 12px 4px 12px 12px; background: var(--grad-main); }
    .fr-msg.is-own.is-grouped .fr-bubble { border-top-right-radius: 12px; }
    .fr-msg.is-own .fr-msg-text { color: #fff; }
    .fr-msg.is-own .fr-bubble time { color: rgba(255,255,255,.85); }

    /* avatar colour by role: yellow = "Comment finance Prepare", green = "Reviewer Level 1". Only the little initials chip changes. */
    .fr-avatar.is-prep, .fr-cc-av.is-prep, .fr-stack i.is-prep { background: #f5c518; color: #3b2d00; }
    .fr-avatar.is-rev1, .fr-cc-av.is-rev1, .fr-stack i.is-rev1 { background: #3ddc84; color: #06361b; }
    .fr-avatar.is-rev2, .fr-cc-av.is-rev2, .fr-stack i.is-rev2 { background: #e5484d; color: #fff; }
    .fr-msg.is-new { animation: frIn .25s ease-out; }
    @keyframes frIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

    /* delete: a small bin in the bubble footer; the message becomes a one-line note saying who deleted it */
    .fr-bubble-foot { display: flex; align-items: center; justify-content: flex-end; gap: 6px; }
    .fr-bubble-foot time { margin-top: 0; }
    .fr-msg-del {
        display: inline-grid; place-items: center; width: 16px; height: 16px; margin: 0; padding: 0; border: 0; border-radius: 4px; cursor: pointer;
        background: transparent; color: var(--ink-soft); opacity: 0; transition: opacity .12s, color .12s, background .12s;
    }
    .fr-msg-del svg { width: 12px; height: 12px; }
    .fr-bubble:hover .fr-msg-del, .fr-msg-del:focus-visible { opacity: .85; }
    .fr-msg-del:hover { opacity: 1; color: var(--danger); background: rgba(179,56,47,.12); }
    .fr-msg-del:focus-visible { outline: 2px solid var(--brand); outline-offset: 1px; }
    .fr-msg.is-own .fr-msg-del { color: rgba(255,255,255,.9); }
    .fr-msg.is-own .fr-msg-del:hover { color: #fff; background: rgba(0,0,0,.22); }
    @media (hover: none) { .fr-msg-del { opacity: .85; } }
    .fr-deleted { display: flex; justify-content: center; margin: 0 0 9px; }
    .fr-deleted span {
        display: block; max-width: 100%; padding: 4px 12px; border: 1px dashed var(--rule-strong); border-radius: 12px; text-align: center; line-height: 1.4;
        font-size: 11.5px; font-style: italic; color: var(--ink-soft); background: var(--paper);
    }
    .fr-deleted svg { display: inline-block; width: 12px; height: 12px; margin: -2px 5px 0 0; vertical-align: middle; }
    .fr-deleted b { font-weight: 800; font-style: normal; color: var(--ink); }
    .fr-deleted time { display: block; font-size: 10.5px; font-style: normal; font-weight: 600; white-space: nowrap; opacity: .85; }

    .fr-thread-empty { display: flex; flex-direction: column; align-items: center; gap: 3px; padding: 20px 14px; text-align: center; font-size: 12.5px; color: var(--ink-soft); }
    .fr-thread-empty strong { margin-top: 6px; font-size: 13.5px; font-weight: 800; color: var(--ink); }

    /* composer */
    .fr-composer { display: none; flex-direction: column; gap: 6px; padding: 8px 12px 10px; background: var(--paper); border-top: 1px solid var(--rule); }
    .fr-quick { display: flex; gap: 5px; overflow-x: auto; scrollbar-width: none; }
    .fr-quick::-webkit-scrollbar { display: none; }
    .fr-quick-chip {
        flex: none; padding: 3px 9px; border-radius: 99px; cursor: pointer; white-space: nowrap;
        border: 1px solid var(--rule-strong); background: transparent; color: var(--ink-soft); font-size: 11.5px; font-weight: 700;
        transition: color .12s, border-color .12s, background .12s;
    }
    .fr-quick-chip:hover { color: #fff; border-color: transparent; background: var(--brand); }
    .fr-input {
        width: 100%; min-height: 38px; max-height: 110px; padding: 8px 12px; resize: none; outline: 0; box-shadow: none;
        font-size: 13px; line-height: 1.4; color: var(--ink); background: var(--paper-tint); border: 1px solid var(--rule); border-radius: 10px;
        transition: border-color .12s, background .12s, box-shadow .12s;
    }
    .fr-input:focus { background: var(--paper); border-color: var(--brand); box-shadow: 0 0 0 3px rgba(47,93,80,.15); }
    .fr-composer-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .fr-hint { font-size: 11px; color: var(--ink-soft); }
    .fr-send {
        display: inline-flex; align-items: center; gap: 6px; padding: 6px 13px; border: 0; border-radius: 8px; cursor: pointer;
        background: var(--grad-main); color: #fff; font-size: 12.5px; font-weight: 800;
        transition: transform .1s, filter .12s;
    }
    .fr-send:hover { filter: brightness(1.08); }
    .fr-send:active { transform: scale(.97); }
    .fr-send:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
    .fr-send:disabled { opacity: .65; cursor: progress; }
    .fr-send.is-busy svg { animation: frSpin .7s linear infinite; }
    @keyframes frSpin { to { transform: rotate(360deg); } }
    .fr-readonly { display: none; margin: 0; padding: 10px 14px; background: var(--paper); border-top: 1px solid var(--rule); font-size: 12px; color: var(--ink-soft); }

    /* ============================ EMPTY / LOADING ============================ */
    .fr-empty { padding: 44px 20px; text-align: center; color: var(--ink-soft); }
    .fr-empty h4 { margin: 14px 0 4px; font-family: var(--display); font-weight: 800; font-size: 18px; color: var(--ink); }
    .fr-empty p { margin: 0 auto; max-width: 44ch; font-size: 13px; line-height: 1.5; }
    .fr-no-results .fr-empty { padding: 30px 20px; }
    .fr-empty-mark {
        position: relative; width: 46px; height: 58px; margin: 0 auto; border-radius: 10px; border: 2px solid var(--brand);
        background:
            linear-gradient(var(--rule-strong) 0 0) 9px 14px / 26px 3px no-repeat,
            linear-gradient(var(--rule-strong) 0 0) 9px 23px / 26px 3px no-repeat,
            linear-gradient(var(--accent) 0 0) 9px 32px / 16px 3px no-repeat,
            var(--paper);
        box-shadow: 6px 8px 0 -2px var(--brand-wash-2);
    }
    .fr-empty-mark.is-small { width: 34px; height: 44px; border-radius: 8px; background-size: 20px 2px, 20px 2px, 12px 2px; background-position: 6px 10px, 6px 17px, 6px 24px; box-shadow: 4px 6px 0 -2px var(--brand-wash-2); }
    .fr-empty.is-error .fr-empty-mark { border-color: var(--danger); }
    .fr-none { font-size: 13px; color: var(--ink-soft); }

    .fr-skeleton { display: grid; gap: 10px; padding: 6px 0; }
    .fr-skeleton b { height: 70px; border-radius: 12px; }
    .fr-skeleton i { height: 14px; border-radius: 99px; }
    .fr-skeleton b, .fr-skeleton i { background: linear-gradient(90deg, var(--rule) 25%, var(--paper-tint) 50%, var(--rule) 75%) 0 0 / 200% 100%; animation: frShimmer 1.3s linear infinite; }
    .fr-skeleton i:nth-of-type(2) { width: 88%; }
    .fr-skeleton i:nth-of-type(3) { width: 72%; }
    .fr-skeleton i:nth-of-type(4) { width: 55%; }
    .fr-skeleton.is-thread { padding: 4px 0; }
    @keyframes frShimmer { to { background-position: -200% 0; } }

    /* ============================ RESPONSIVE ============================ */
    @media (max-width: 1100px) {
        .fr-search input { width: 110px; }
    }
    @media (max-width: 900px) {
        .fr-filter-grid { grid-template-columns: 1fr; }
        .fr-filters { padding: 12px; }
        .fr-shell, .fr-shell.drawer-open { grid-template-columns: minmax(0, 1fr); column-gap: 0; }
        .fr-drawer { position: fixed; left: 8px; right: 8px; bottom: 8px; top: auto; z-index: 1030; height: 78vh; transform: translateY(24px); }
        .fr-toolbar { position: static; flex-direction: column; align-items: stretch; }
        .fr-tools { justify-content: space-between; }
        .fr-search { flex: 1; }
        .fr-search input { width: 100%; }
        .fr-note { grid-template-columns: minmax(0, 1fr); }
        .fr-note-spine, .fr-note-meta { display: none; }
        .fr-report-card { min-width: 100%; max-width: 100%; }
    }

    /* ============================ ACCESSIBILITY ============================ */
    @media (prefers-reduced-motion: reduce) {
        .fr-root *, .fr-root *::before, .fr-root *::after { animation: none !important; transition: none !important; }
    }

    /* ============================ PRINT ============================ */
    @media print {
        .fr-filters, .fr-toolbar, .fr-legend, .fr-drawer, .fr-gutter, .fr-note-meta, .fr-chev { display: none !important; }
        .fr-shell { display: block !important; }
        .fr-note.is-collapsed .fr-note-content { display: block !important; }
        .fr-note { break-inside: avoid; }
        .fr-note-spine span { background: #000; }
        .fr-root .fr-table tr.has-comments td, .fr-root .fr-table tr.is-active td { background: transparent !important; }
    }

    /* keep the Frappe page header tidy */
    .page-head .page-actions { display: flex; align-items: center; }
    `;
    document.head.appendChild(style);
}