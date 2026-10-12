/* =====================================================================
   page_load.js
   Page start: on_page_load builds the shell and starts init (schema, report list, restore the last session).
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

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
