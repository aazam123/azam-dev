/* =====================================================================
   api.js
   How the page talks to the server: method paths and the multipart POST used for comments with files and for the Excel export.
   Part of the Individual Financial page. All files share one scope; the order they are loaded in is in
   individual_financial.js (see README.md in this folder).
   ===================================================================== */

const COMMENTS_API = 'financial_report_tool.financial_report_tool.doctype.financial_report_comments.financial_report_comments.';

// POST a FormData to a whitelisted method with Frappe's CSRF token. Returns the method's `message`, or, with asFile, the downloaded
// file as {blob, filename}. A failed call rejects with the server's own text.
function postForm(method, body, asFile) {
    return fetch('/api/method/' + method, {
        method: 'POST',
        body,
        credentials: 'same-origin',
        headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token, 'Accept': asFile ? '*/*' : 'application/json' }
    }).then(res => {
        if (res.ok && asFile) {
            const m = /filename\*?=(?:UTF-8'')?"?([^";]+)/i.exec(res.headers.get('Content-Disposition') || '');
            return res.blob().then(blob => ({ blob, filename: m ? decodeURIComponent(m[1]) : '' }));
        }
        return res.json().catch(() => ({})).then(data => {
            if (res.ok) return data.message;
            let msg = '';
            try { msg = JSON.parse(data._server_messages || '[]').map(m => JSON.parse(m).message).join(' '); } catch (e) { /* not JSON */ }
            const err = new Error((msg || data.exception || `Request failed (${res.status})`).replace(/<[^>]+>/g, ''));
            err.status = res.status;
            throw err;
        });
    });
}

/* ---------------------------------------------------------------------
   EXPORT  (the whole open report to one Excel file)
   The tables are read from the screen, because the FTM / Previous Month / Previous FTM columns exist only there. The server adds the
   report's details, every comment (with its files' names, deleted ones marked) and the review state, and builds the .xlsx
   (page/individual_financial/individual_financial.py). It always exports the open report itself, whatever "Comments of" shows.
--------------------------------------------------------------------- */
const PAGE_API = 'financial_report_tool.financial_report_tool.page.individual_financial.individual_financial.';
