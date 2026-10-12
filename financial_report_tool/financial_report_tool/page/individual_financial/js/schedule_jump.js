/* =====================================================================
   schedule_jump.js
   A statement row with a note number jumps to that note; Back to statement returns to the row.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

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
