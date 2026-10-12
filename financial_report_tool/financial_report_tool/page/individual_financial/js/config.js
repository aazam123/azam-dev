/* =====================================================================
   config.js
   Names and limits that can be changed in one place: doctype names, field names, the manager role, polling time, quick notes.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

const FR_CONFIG = {
    DOCTYPE: 'Financial Report',
    COMMENT_DOCTYPE: 'Financial Report Comments',
    COMPANY_FIELD: 'company',
    MONTH_FIELD: 'month',          // Select / Int / Data holding the month
    YEAR_FIELD: 'year',            // Select / Int / Data holding the year
    // Used only when month/year fields do not exist: the first one found wins
    DATE_FIELDS: ['to_date', 'report_date', 'reporting_date', 'posting_date', 'period_end_date', 'end_date', 'from_date'],
    MANAGER_ROLE: 'Financial Report Manager',
    POLL_MS: 20000,                // live refresh of the open comment channel
    QUICK_NOTES: ['Please clarify', 'Verified', 'Supporting document needed', 'Amount mismatch']
};

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'];
