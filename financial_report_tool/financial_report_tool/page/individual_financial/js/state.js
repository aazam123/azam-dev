/* =====================================================================
   state.js
   FR is the one object that holds everything on screen. rowKey and esc are used everywhere.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

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
    pendingFiles: [],    // File objects chosen in the composer and not sent yet (up to MAX_FILES)
    exporting: false,    // an Excel export is being built (blocks a second click)
    dom: {},             // page elements, filled once by buildShell
    observer: null,      // IntersectionObserver that marks the section chip in view
    collapseObs: null,   // MutationObserver that keeps the expand/collapse-all button in step
    poll: null,          // setInterval id of the 20 s live refresh (thread + review chips)
    KEYS: { report: 'fr_selected_report', filters: 'fr_filters', cmt: 'fr_comments_of' }   // localStorage keys
};

const rowKey = (note, type, idx) => `${note}|${type}|${idx}`;

const esc = v => frappe.utils.escape_html(v == null ? '' : String(v));
