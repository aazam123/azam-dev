/* =====================================================================
   role_colours.js
   Yellow Prepare, green Level 1, red Level 2 on initials chips and on the row markers, bars and pills.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

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

const bumpRole = (arr, r) => (arr || []).filter(x => x !== r).concat(r);

// distinct roles, the latest commenter's last
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
