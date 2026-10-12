/* =====================================================================
   toolbar.js
   Section chips, search, Commented only, expand / collapse all, Export button and the N rows / N commented pill of each section.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

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
    const exportBtn = sheet.querySelector('.fr-export');
    if (exportBtn) exportBtn.addEventListener('click', exportReport);
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
