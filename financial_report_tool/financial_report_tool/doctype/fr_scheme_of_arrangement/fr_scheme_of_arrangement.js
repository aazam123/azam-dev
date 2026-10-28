// Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
// For license information, see license.txt

// Same colours as the Note 62 tables of the report: grey/blue bold headings, green right-aligned amounts.
const SCHEME_HEADING_FIELDS = [
	"sch_ac_asat", "sch_ac_tee_head", "sch_ac_col_shares", "sch_ac_col_amount", "sch_ac_tor_head",
	"sch_m1_particulars", "sch_m1_asat", "sch_m1_col_shares", "sch_m1_col_amount",
	"sch_m2_particulars", "sch_m2_asat", "sch_m2_col_shares", "sch_m2_col_amount",
	"sch_t1_h0", "sch_t1_h1", "sch_t1_h2", "sch_t1_h3", "sch_t2_fy1", "sch_t2_amt", "sch_t2_fy2",
];
const SCHEME_AMOUNT_FIELDS = [
	"sch_ac_tee_eq_amt", "sch_ac_tee_pref_amt", "sch_ac_tor_eq_amt", "sch_ac_tor_pref1_amt", "sch_ac_tor_pref2_amt",
	"sch_m1_shares", "sch_m1_amount", "sch_m2_shares", "sch_m2_amount",
	...[1, 2, 3].flatMap((r) => [1, 2, 3].map((c) => `sch_t1_r${r}_${c}`)),
	...["a", "b", "ba", "c", "d", "dc", "tot"].map((k) => `sch_t2_${k}_v`),
];

frappe.ui.form.on("FR Scheme of Arrangement", {
	refresh(frm) {
		frm.set_intro(
			__("Saving here updates Note 62 in the Financial Reports of this Company and Fiscal Year. Edits made on a report's Note 62 row stay on that report."),
			"blue"
		);
		for (const fieldname of SCHEME_HEADING_FIELDS) {
			frm.fields_dict[fieldname]?.$wrapper.find("input").css({
				backgroundColor: "#EEEEEE", color: "#3498DB", fontWeight: "bold", textAlign: "center",
			});
		}
		for (const fieldname of SCHEME_AMOUNT_FIELDS) {
			frm.fields_dict[fieldname]?.$wrapper.find("input").css({ backgroundColor: "#E8F5E8", textAlign: "right" });
		}
	},
});
