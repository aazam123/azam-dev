/* =====================================================================
   shell.js
   The empty page skeleton (filters, cards, sheet area, chat drawer) and the icons. Built once, filled later.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

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
    sun: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    attach: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5l-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6l7.9-7.9"/></svg>',
    file: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg>',
    download: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11"/><path d="M7 11l5 5 5-5"/><path d="M5 20h14"/></svg>'
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
                        <div class="fr-pending" aria-label="Files to send"></div>
                        <div class="fr-composer-row">
                            <span class="fr-hint">Enter to send · Shift+Enter for a new line</span>
                            <div class="fr-composer-actions">
                                <input type="file" class="fr-file-input" multiple hidden>
                                <button class="fr-attach" type="button" title="Attach files (up to 5)" aria-label="Attach files">${ICON.attach}</button>
                                <button class="fr-send" type="button">${ICON.send}<span>Send</span></button>
                            </div>
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
        attach: q('.fr-attach'),
        fileInput: q('.fr-file-input'),
        pending: q('.fr-pending'),
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

    // attachments: paperclip, drag and drop onto the panel, paste a copied file or screenshot into the box
    FR.dom.attach.addEventListener('click', () => FR.dom.fileInput.click());
    FR.dom.fileInput.addEventListener('change', () => { addPendingFiles(FR.dom.fileInput.files); FR.dom.fileInput.value = ''; });
    FR.dom.pending.addEventListener('click', e => {
        const b = e.target.closest('button[data-i]');
        if (b) { FR.pendingFiles.splice(Number(b.dataset.i), 1); paintPendingFiles(); }
    });
    FR.dom.input.addEventListener('paste', e => {
        const files = [...(e.clipboardData && e.clipboardData.files || [])];
        if (files.length && FR.canComment) { e.preventDefault(); addPendingFiles(files); }
    });
    ['dragenter', 'dragover'].forEach(ev => FR.dom.drawer.addEventListener(ev, e => {
        if (!FR.canComment || !FR.active || !(e.dataTransfer && [...e.dataTransfer.types].includes('Files'))) return;
        e.preventDefault();
        FR.dom.drawer.classList.add('is-drop');
    }));
    ['dragleave', 'drop'].forEach(ev => FR.dom.drawer.addEventListener(ev, e => {
        if (ev === 'dragleave' && FR.dom.drawer.contains(e.relatedTarget)) return;
        FR.dom.drawer.classList.remove('is-drop');
        if (ev === 'drop' && FR.canComment && FR.active && e.dataTransfer && e.dataTransfer.files.length) {
            e.preventDefault();
            addPendingFiles(e.dataTransfer.files);
        }
    }));

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
