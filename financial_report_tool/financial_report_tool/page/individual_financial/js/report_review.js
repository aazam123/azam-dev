/* =====================================================================
   report_review.js
   Review chips: Prepare, Level 1 and Level 2 sign off the whole report (the server decides who may press which chip).
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

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
