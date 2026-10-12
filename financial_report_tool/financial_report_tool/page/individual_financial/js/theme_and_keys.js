/* =====================================================================
   theme_and_keys.js
   Light / dark switch, keyboard shortcuts (Esc, /) and the growing comment box.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

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
