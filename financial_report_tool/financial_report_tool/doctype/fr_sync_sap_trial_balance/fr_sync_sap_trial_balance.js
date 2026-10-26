function load_missing_accounts(frm) {
    frappe.call({
        method: "load_missing_accounts",
        doc: frm.doc,
        freeze: true,
        freeze_message: __("Loading missing accounts…"),
        callback: function (r) {
            if (!r.exc) {
                frm.reload_doc();
                frm.scroll_to_field && frm.scroll_to_field("missing_accounts");
            }
        }
    });
}

function create_missing_accounts(frm) {
    frappe.call({
        method: "create_missing_accounts",
        doc: frm.doc,
        freeze: true,
        freeze_message: __("Creating missing accounts…"),
        callback: function (r) {
            if (!r.exc) {
                const m = r.message || {};
                const created = (m.created_accounts || []).length;
                const skipped = (m.skipped || []).length;
                let msg = __("Created {0} account(s) and {1} GL group mapping(s).", [created, m.created_mappings || 0]);
                if (skipped) {
                    msg += " " + __("{0} row(s) skipped.", [skipped]);
                }
                frappe.show_alert({ message: msg, indicator: "blue" }, 7);
                frm.reload_doc();
            }
        }
    });
}

// Calendar-ordered, matching the Month select and the server MONTHS list.
const SAP_MONTHS = ["January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"];

// Pull the company-fixed SAP params from SAP Company Mapping onto the form.
// Runs on explicit company change, so it overwrites (the chosen company wins).
function apply_company_template(frm) {
    if (!frm.doc.company) return;
    frappe.db.get_value("FR SAP Company Mapping", { company: frm.doc.company },
        ["company_code", "chartofacc", "sversion", "layout", "sap_client"]
    ).then(r => {
        const d = (r && r.message) || {};
        if (!Object.keys(d).length) {
            frappe.show_alert({
                message: __("No SAP Company Mapping for {0} — fill the SAP params manually or create a mapping.", [frm.doc.company]),
                indicator: "orange"
            }, 7);
            return;
        }
        ["company_code", "chartofacc", "sversion", "layout", "sap_client"].forEach(f => {
            if (d[f]) frm.set_value(f, d[f]);
        });
    });
}

// April, the standard Indian fiscal-year start — used when a Fiscal Year has no
// stored start date to read (mirrors DEFAULT_FY_START_MONTH on the server).
const DEFAULT_FY_START_MONTH = 4;

// A Jan-Dec company is requested in calendar periods whichever existing Fiscal
// Year labels the snapshot, so its year and periods come from the month's own
// calendar date (mirrors calendar_year_for on the server).
async function apply_calendar_periods(frm) {
    const cycle = await frappe.db.get_value("FR SAP Company Mapping", { company: frm.doc.company }, "fiscal_cycle");
    if (cycle.message?.fiscal_cycle !== "Jan-Dec") return false;
    const fy = await frappe.db.get_value("Fiscal Year", frm.doc.fiscal_year, ["year_start_date", "year_end_date"]);
    const i = SAP_MONTHS.indexOf(frm.doc.month);
    if (!fy.message?.year_start_date || i < 0) return false;
    const [sy, sm] = fy.message.year_start_date.split("-").map(Number);
    const [ey, em] = fy.message.year_end_date.split("-").map(Number);
    const year = [sy, ey].find(y => (sy * 12 + sm) <= (y * 12 + i + 1) && (y * 12 + i + 1) <= (ey * 12 + em));
    if (!year) return false;
    const mm = String(i + 1).padStart(2, "0");
    frm.set_value("repyear", String(year));
    frm.set_value("compyear", String(year - 1));
    frm.set_value("srepmonth", "01");
    frm.set_value("trepmonth", mm);
    frm.set_value("scompmonth", "01");
    frm.set_value("tcompmonth", mm);
    return true;
}

// Reporting year = fiscal year start; comparison year = one before.
async function apply_period_years(frm) {
    if (!frm.doc.fiscal_year) return;
    if (frm.doc.company && frm.doc.month && await apply_calendar_periods(frm)) return;
    const y = parseInt(String(frm.doc.fiscal_year).split("-")[0], 10);
    if (isNaN(y)) return;
    frm.set_value("repyear", String(y));
    frm.set_value("compyear", String(y - 1));
}

// SAP counts posting periods from the fiscal-year start, not the calendar year:
// with an April fiscal year August is period 05, not 08. Resolve the fiscal
// year's start month, then map the selected month onto the period.
async function apply_period_months(frm) {
    const i = SAP_MONTHS.indexOf(frm.doc.month);
    if (i < 0) return;
    if (frm.doc.company && frm.doc.fiscal_year && await apply_calendar_periods(frm)) return;
    const cal = i + 1; // 1..12 calendar month

    const set_span = (startMonth) => {
        const period = (((cal - startMonth) % 12) + 12) % 12 + 1;
        const mm = String(period).padStart(2, "0");
        frm.set_value("srepmonth", "01");
        frm.set_value("trepmonth", mm);
        frm.set_value("scompmonth", "01");
        frm.set_value("tcompmonth", mm);
    };

    if (!frm.doc.fiscal_year) {
        set_span(DEFAULT_FY_START_MONTH);
        return;
    }
    frappe.db.get_value("Fiscal Year", frm.doc.fiscal_year, "year_start_date").then(r => {
        const start = r && r.message && r.message.year_start_date;
        // JS months are 0-based; year_start_date is "YYYY-MM-DD".
        const startMonth = start ? parseInt(String(start).slice(5, 7), 10) : DEFAULT_FY_START_MONTH;
        set_span(startMonth || DEFAULT_FY_START_MONTH);
    });
}

frappe.ui.form.on("FR Sync SAP Trial Balance", {
    company(frm) {
        apply_company_template(frm);
    },
    fiscal_year(frm) {
        apply_period_years(frm);
        // The fiscal-year start month drives the SAP period, so re-derive the
        // month spans whenever the fiscal year changes.
        apply_period_months(frm);
    },
    month(frm) {
        apply_period_months(frm);
    },
    refresh(frm) {
        // Collapse the sidebar by default on this form (mirrors clicking the
        // page-header "Toggle Sidebar"). Users can re-open it with that button.
        frm.page.sidebar.toggle(false);
        frm.page.update_sidebar_icon && frm.page.update_sidebar_icon();

        frappe.db.get_single_value("FR Financial Settings", "sap_threshold_amount").then(setting_amount => {
            if ((frm.doc.total_amount || 0) <= setting_amount && frm.doc.tb_created == 0) {
                frm.add_custom_button(__('Create TB'), function () {
                    frappe.call({
                        method: "create_trail_balance",
                        doc: frm.doc,
                        callback: function (r) {
                            if (!r.exc) {
                                frappe.msgprint("Trial Balance created successfully!");
                                frm.reload_doc();
                            }
                        }
                    });
                });
            }
        });

        if (frm.doc.tb_created && frm.doc.company) {
            frappe.db.get_value("FR SAP Company Mapping", { company: frm.doc.company }, "fiscal_cycle")
                .then(r => {
                    if (r.message?.fiscal_cycle !== "Jan-Dec") return;
                    frm.add_custom_button(__("Derive Apr-Mar TB"), () => {
                        const dialog = new frappe.ui.Dialog({
                            title: __("Derive Apr-Mar TB"),
                            fields: [
                                { fieldname: "fiscal_year", fieldtype: "Link", options: "Fiscal Year", label: __("Apr-Mar Fiscal Year"), reqd: 1 },
                                { fieldname: "month", fieldtype: "Select", options: SAP_MONTHS.join("\n"), label: __("Month"), default: frm.doc.month, reqd: 1 }
                            ],
                            primary_action_label: __("Derive"),
                            primary_action(values) {
                                frappe.call({
                                    method: "financial_report_tool.financial_report_tool.derive_trial_balance.derive_apr_mar_tb",
                                    args: { company: frm.doc.company, ...values },
                                    freeze: true,
                                    callback(result) {
                                        if (!result.exc) {
                                            dialog.hide();
                                            frappe.msgprint(__("Derived {0} accounts from SAP TBs {1}.", [result.message.accounts, result.message.source_sap_tbs]));
                                        }
                                    }
                                });
                            }
                        });
                        dialog.show();
                    });
                });
        }

        // Also expose the Missing Account actions in the top button menu.
        frm.add_custom_button(__('Load Missing Accounts'), () => load_missing_accounts(frm), __('Accounts'));
        if ((frm.doc.missing_accounts || []).length) {
            frm.add_custom_button(__('Create Accounts'), () => create_missing_accounts(frm), __('Accounts'));
        }

        frm.add_custom_button(__('Sync SAP Data'), function () {
            frappe.call({
                method: "sync_sap_data",
                doc: frm.doc,
                callback: function (r) {
                    if (!r.exc && r.message) {
                        frappe.show_alert({
                            message: r.message.message || __("SAP data sync started in background…"),
                            indicator: "blue"
                        });
                        // Reload so the "Queued"/"Syncing" status shows; the
                        // realtime handler below auto-reloads on completion.
                        frm.reload_doc();
                    }
                }
            });
        });

        // Auto-reload when the background SAP sync finishes (mirrors the
        // Financial Report realtime pattern).
        frappe.realtime.off("sap_tb_sync_complete");
        frappe.realtime.on("sap_tb_sync_complete", (data) => {
            if (data.docname === frm.doc.name) {
                frm.reload_doc();
                if (data.status === "Completed") {
                    frappe.show_alert({ message: __("SAP data synced successfully!"), indicator: "green" });
                } else if (data.status === "Awaiting SAP") {
                    frappe.show_alert({ message: __("Request accepted by SAP. Waiting for SAP to push the trial balance…"), indicator: "orange" });
                } else if (data.status === "Failed") {
                    frappe.show_alert({ message: __("SAP sync failed. See 'Sync Error' on the form."), indicator: "red" });
                }
            }
        });
    },
    load_missing_accounts_btn(frm) {
        load_missing_accounts(frm);
    },
    create_accounts_btn(frm) {
        create_missing_accounts(frm);
    },
    setup(frm) {
        frm.fields_dict["details"].grid.get_field("account").get_query = function (doc, cdt, cdn) {
            return {
                filters: {
                    company: frm.doc.company,
                    is_group: 0,
                    disabled: 0
                }
            };
        };

        // In the Missing Accounts tab, restrict Parent Account to group accounts
        // of this document's company.
        frm.fields_dict["missing_accounts"].grid.get_field("parent_account").get_query = function (doc, cdt, cdn) {
            return {
                filters: {
                    company: frm.doc.company,
                    is_group: 1
                }
            };
        };
    }
});
