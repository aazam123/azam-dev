/* =====================================================================
   report_list.js
   Finds the doctype fields, loads every report once, works out each report's real month and year, restores the last session.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

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
