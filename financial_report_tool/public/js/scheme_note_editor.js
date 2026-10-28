(function () {
// Note 62 (Scheme of Arrangement) coloured, inline-editable tables. Shared by the FR Financial Report row
// editor and the FR Scheme of Arrangement master.
const SCHEME_TABLE_FIELDS = [
    "sch_ac_asat", "sch_ac_col_shares", "sch_ac_col_amount", "sch_ac_tee_head",
    "sch_ac_tee_eq_label", "sch_ac_tee_eq_amt", "sch_ac_tee_pref_label", "sch_ac_tee_pref_amt",
    "sch_ac_tor_head", "sch_ac_tor_eq_label", "sch_ac_tor_eq_amt", "sch_ac_tor_pref1_label",
    "sch_ac_tor_pref1_amt", "sch_ac_tor_pref2_label", "sch_ac_tor_pref2_amt", "sch_text_pre_h", "sch_text_h",
    "sch_m1_caption", "sch_m1_particulars", "sch_m1_asat", "sch_m1_col_shares", "sch_m1_col_amount",
    "sch_m1_issued", "sch_m1_equity_label", "sch_m1_shares", "sch_m1_amount", "sch_m2_caption",
    "sch_m2_particulars", "sch_m2_asat", "sch_m2_col_shares", "sch_m2_col_amount", "sch_m2_issued",
    "sch_m2_equity_label", "sch_m2_shares", "sch_m2_amount",
    "sch_s_title", "sch_s_calc", "sch_t1_h0", "sch_t1_h1", "sch_t1_h2", "sch_t1_h3",
    "sch_t1_r1_0", "sch_t1_r1_1", "sch_t1_r1_2", "sch_t1_r1_3",
    "sch_t1_r2_0", "sch_t1_r2_1", "sch_t1_r2_2", "sch_t1_r2_3",
    "sch_t1_r3_0", "sch_t1_r3_1", "sch_t1_r3_2", "sch_t1_r3_3",
    "sch_t2_fy1", "sch_t2_amt", "sch_t2_a_l", "sch_t2_a_v", "sch_t2_b_l", "sch_t2_b_v", "sch_t2_ba_l", "sch_t2_ba_v",
    "sch_t2_fy2", "sch_t2_c_l", "sch_t2_c_v", "sch_t2_d_l", "sch_t2_d_v", "sch_t2_dc_l", "sch_t2_dc_v",
    "sch_t2_tot_l", "sch_t2_tot_v", "sch_n_head", "sch_n_text", "sch_n_iv", "sch_n_v",
];

function escapeSchemeValue(value) {
    return frappe.utils.escape_html(value || "");
}

function schemeInput(fieldname, value, className = "") {
    return `<input class="form-control scheme-note-input ${className}" data-fieldname="${fieldname}" value="${escapeSchemeValue(value)}">`;
}

function schemeTextarea(fieldname, value) {
    return `<textarea class="form-control scheme-note-input" rows="3" data-fieldname="${fieldname}">${escapeSchemeValue(value)}</textarea>`;
}

function renderSchemeNoteTables(opts) {
    // opts: {wrapper: jQuery element, get(fieldname), set(fieldname, value)}
    const htmlField = { $wrapper: opts.wrapper };
    const row = new Proxy({}, { get: (_t, fieldname) => opts.get(fieldname) });
    const r = (fieldname, cls = "") => schemeInput(fieldname, row[fieldname], cls);
    const authorisedRow = (label, amount) => `<tr><td>${r(label)}</td><td>${r(amount, "text-right")}</td></tr>`;
    const companyTable = (prefix) => `
        <p class="scheme-note-caption">${r(prefix + "caption")}</p>
        <table class="table table-bordered scheme-note-table">
            <tbody>
                <tr><th rowspan="2">${r(prefix + "particulars")}</th><th colspan="2">${r(prefix + "asat")}</th></tr>
                <tr><th>${r(prefix + "col_shares")}</th><th>${r(prefix + "col_amount")}</th></tr>
                <tr><td colspan="3">${r(prefix + "issued")}</td></tr>
                <tr><td>${r(prefix + "equity_label")}</td><td>${r(prefix + "shares", "text-right")}</td><td>${r(prefix + "amount", "text-right")}</td></tr>
            </tbody>
        </table>`;
    const t1Row = (n) => `<tr><td>${r(`sch_t1_r${n}_0`)}</td>${[1, 2, 3].map((c) => `<td>${r(`sch_t1_r${n}_${c}`, "text-right")}</td>`).join("")}</tr>`;
    const t2Row = (k) => `<tr><td>${r(`sch_t2_${k}_l`)}</td><td>${r(`sch_t2_${k}_v`, "text-right")}</td></tr>`;
    const summaryBlock = `
        <p class="scheme-note-caption">${r("sch_s_title")}</p>
        <p class="scheme-note-caption">${r("sch_s_calc")}</p>
        <table class="table table-bordered scheme-note-table">
            <tbody>
                <tr><th>${r("sch_t1_h0")}</th><th>${r("sch_t1_h1")}</th><th>${r("sch_t1_h2")}</th><th>${r("sch_t1_h3")}</th></tr>
                ${t1Row(1)}${t1Row(2)}${t1Row(3)}
            </tbody>
        </table>
        <table class="table table-bordered scheme-note-table scheme-authorised-table">
            <tbody>
                <tr><th>${r("sch_t2_fy1")}</th><th>${r("sch_t2_amt")}</th></tr>
                ${t2Row("a")}${t2Row("b")}${t2Row("ba")}
                <tr><th colspan="2">${r("sch_t2_fy2")}</th></tr>
                ${t2Row("c")}${t2Row("d")}${t2Row("dc")}${t2Row("tot")}
            </tbody>
        </table>
        <p class="scheme-note-caption">${r("sch_n_head")}</p>
        ${schemeTextarea("sch_n_text", row.sch_n_text)}
        ${schemeTextarea("sch_n_iv", row.sch_n_iv)}
        ${schemeTextarea("sch_n_v", row.sch_n_v)}`;

    htmlField.$wrapper.html(`
        <div class="scheme-note-editor">
            <div class="scheme-note-help">Edit directly inside the cells. Then click the main <strong>Save</strong> button for the Financial Report.</div>
            <table class="table table-bordered scheme-note-table scheme-authorised-table">
                <tbody>
                    <tr><th colspan="2">${r("sch_ac_asat")}</th></tr>
                    <tr><th colspan="2">${r("sch_ac_tee_head")}</th></tr>
                    <tr><th>${r("sch_ac_col_shares")}</th><th>${r("sch_ac_col_amount")}</th></tr>
                    ${authorisedRow("sch_ac_tee_eq_label", "sch_ac_tee_eq_amt")}
                    ${authorisedRow("sch_ac_tee_pref_label", "sch_ac_tee_pref_amt")}
                    <tr><th colspan="2">${r("sch_ac_tor_head")}</th></tr>
                    ${authorisedRow("sch_ac_tor_eq_label", "sch_ac_tor_eq_amt")}
                    ${authorisedRow("sch_ac_tor_pref1_label", "sch_ac_tor_pref1_amt")}
                    ${authorisedRow("sch_ac_tor_pref2_label", "sch_ac_tor_pref2_amt")}
                </tbody>
            </table>
            <div class="scheme-note-pre-h">${r("sch_text_pre_h")}</div>
            <div class="scheme-note-h">${r("sch_text_h")}</div>
            ${companyTable("sch_m1_")}
            ${companyTable("sch_m2_")}
            ${summaryBlock}
        </div>
    `);
    htmlField.$wrapper.find(".scheme-note-help").css({ margin: "8px 0", color: "#555" });
    htmlField.$wrapper.find(".scheme-note-caption").css({ margin: "14px 0 5px", fontWeight: "bold" });
    htmlField.$wrapper.find(".scheme-note-table").css({ width: "100%", borderCollapse: "collapse", margin: "6px 0 12px" });
    htmlField.$wrapper.find(".scheme-authorised-table").css("width", "70%");
    htmlField.$wrapper.find(".scheme-note-table th").css({ backgroundColor: "#EEEEEE", color: "#3498DB", fontWeight: "bold", textAlign: "center", border: "1px solid #000", padding: "4px" });
    htmlField.$wrapper.find(".scheme-note-table td").css({ border: "1px solid #000", padding: "4px" });
    htmlField.$wrapper.find(".scheme-note-input").css({ width: "100%", minHeight: "30px", border: "0", boxShadow: "none", backgroundColor: "transparent", padding: "2px" });
    htmlField.$wrapper.find(".scheme-note-table td .text-right").css({ textAlign: "right", backgroundColor: "#E8F5E8" });
    htmlField.$wrapper.find(".scheme-note-pre-h .scheme-note-input").css({ minHeight: "48px" });
    htmlField.$wrapper.find(".scheme-note-h .scheme-note-input").css({ minHeight: "48px" });
    htmlField.$wrapper.find(".scheme-note-input").on("change", function () {
        opts.set(this.dataset.fieldname, this.value);
    });
}

frappe.fr_scheme_editor = { fields: SCHEME_TABLE_FIELDS, render: renderSchemeNoteTables };
})();
