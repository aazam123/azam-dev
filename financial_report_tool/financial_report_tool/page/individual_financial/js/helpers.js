/* =====================================================================
   helpers.js
   Small pure helpers: names, initials, colours, file sizes and dates in the user's own time zone and date format.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

// "12 KB", "1.4 MB"
const fileSize = n => n < 1024 ? `${n} B` : n < 1048576 ? `${Math.round(n / 1024)} KB` : `${(n / 1048576).toFixed(1)} MB`;

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

const userDateFmt = () => frappe.datetime.get_user_date_fmt().toUpperCase();

// DD-MM-YYYY
const userClockFmt = () => frappe.datetime.get_user_time_fmt().replace(/[:.]ss/, '');

// HH:mm (seconds are noise in a chat)

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
