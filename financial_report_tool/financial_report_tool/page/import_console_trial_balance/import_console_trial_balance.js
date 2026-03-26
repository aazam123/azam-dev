// Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.pages['import-console-trial-balance'].on_page_load = function(wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Import Console Trial Balance',
        single_column: true
    });

    wrapper.page = page;

    // --- Filters ---
    page.add_field({
        label: 'Fiscal Year',
        fieldname: 'fiscal_year',
        fieldtype: 'Link',
        options: 'Fiscal Year',
        reqd: 1,
        change() {
            clear_results(page);
        }
    });

    page.add_field({
        label: 'Month',
        fieldname: 'month',
        fieldtype: 'Select',
        options: '\nJanuary\nFebruary\nMarch\nApril\nMay\nJune\nJuly\nAugust\nSeptember\nOctober\nNovember\nDecember',
        reqd: 1,
        change() {
            clear_results(page);
        }
    });

    // --- Actions ---
    page.set_primary_action(__('Fetch Companies'), function() {
        fetch_companies(page);
    }, 'octicon octicon-search');

    page.set_secondary_action(__('Import'), function() {
        import_selected(page);
    });

    // --- Main Container ---
    page.main_container = $('<div class="import-ctb-container"></div>').appendTo(page.body);

    add_page_styles();

    // Initial state
    page.main_container.html(`
        <div class="empty-state">
            <div class="empty-state-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none"
                     stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
            </div>
            <h4>Import Console Trial Balance</h4>
            <p>Select Fiscal Year and Month, then click <b>Fetch Companies</b> to see available companies.</p>
        </div>
    `);
};

function get_filter_values(page) {
    return {
        fiscal_year: page.fields_dict.fiscal_year.get_value(),
        month: page.fields_dict.month.get_value()
    };
}

function clear_results(page) {
    page.main_container.find('.companies-section').remove();
    page.main_container.find('.preview-section').remove();
}

function fetch_companies(page) {
    const { fiscal_year, month } = get_filter_values(page);

    if (!fiscal_year || !month) {
        frappe.msgprint(__('Please select Fiscal Year and Month.'));
        return;
    }

    page.main_container.html('<div class="text-center p-5"><div class="spinner-border text-primary"></div></div>');

    frappe.call({
        method: 'financial_report_tool.financial_report_tool.page.import_console_trial_balance.import_console_trial_balance.get_companies_with_tb',
        args: { fiscal_year, month },
        callback: function(r) {
            if (!r.message || r.message.length === 0) {
                page.main_container.html(`
                    <div class="empty-state">
                        <h4>No Trial Balance Entries Found</h4>
                        <p>No FR Trial Balance Entry exists for <b>${fiscal_year}</b> - <b>${month}</b>.</p>
                    </div>
                `);
                return;
            }
            render_company_list(page, r.message, fiscal_year, month);
        }
    });
}

function render_company_list(page, companies, fiscal_year, month) {
    let html = `
        <div class="companies-section">
            <div class="section-header">
            <label class="select-all-label">
                <input type="checkbox" id="select-all-companies" checked> Select All
            </label>
            <h5>Companies with Trial Balance Entries (${fiscal_year} - ${month})</h5>
            <div class="action-bar">
                <button class="btn btn-primary btn-sm btn-validate">Validate</button>
            </div>
            </div>
            <table class="table table-bordered company-table">
                <thead>
                    <tr>
                        <th width="40"></th>
                        <th>Company</th>
                        <th>Currency</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>`;

    companies.forEach(function(c) {
        html += `
                    <tr>
                        <td class="text-center">
                            <input type="checkbox" class="company-check" data-company="${c.company}" checked>
                        </td>
                        <td>${c.company}</td>
                        <td>${c.default_currency || '-'}</td>
                        <td class="status-cell" data-company="${c.company}">
                            <span class="text-muted">Pending validation</span>
                        </td>
                    </tr>`;
    });

    html += `
                </tbody>
            </table>
        </div>`;

    page.main_container.html(html);

    // Select All toggle
    page.main_container.find('#select-all-companies').on('change', function() {
        const checked = $(this).prop('checked');
        page.main_container.find('.company-check').prop('checked', checked);
    });

    // Validate button
    page.main_container.find('.btn-validate').on('click', function() {
        validate_companies(page);
    });
}

function get_selected_companies(page) {
    const companies = [];
    page.main_container.find('.company-check:checked').each(function() {
        companies.push($(this).data('company'));
    });
    return companies;
}

function validate_companies(page) {
    const { fiscal_year, month } = get_filter_values(page);
    const companies = get_selected_companies(page);

    if (companies.length === 0) {
        frappe.msgprint(__('Please select at least one company.'));
        return;
    }

    // Show loading in status cells
    companies.forEach(function(company) {
        page.main_container.find(`.status-cell[data-company="${company}"]`).html(
            '<span class="text-muted"><i class="fa fa-spinner fa-spin"></i> Validating...</span>'
        );
    });

    // Remove old preview
    page.main_container.find('.preview-section').remove();

    frappe.call({
        method: 'financial_report_tool.financial_report_tool.page.import_console_trial_balance.import_console_trial_balance.validate_before_import',
        args: { fiscal_year, month, companies: JSON.stringify(companies) },
        callback: function(r) {
            if (!r.message) return;

            const valid_companies = [];

            r.message.forEach(function(v) {
                const cell = page.main_container.find(`.status-cell[data-company="${v.company}"]`);
                const checkbox = page.main_container.find(`.company-check[data-company="${v.company}"]`);

                if (v.valid) {
                    valid_companies.push(v.company);
                    cell.html(`
                        <span class="text-success">
                            <i class="fa fa-check-circle"></i> Ready
                            (${v.tb_count} entries, Closing: ${v.closing_rate}, Avg: ${v.average_rate})
                        </span>
                    `);
                } else {
                    let error_html = v.errors.map(e => `<div class="text-danger"><i class="fa fa-times-circle"></i> ${e}</div>`).join('');
                    cell.html(error_html);
                    checkbox.prop('checked', false);
                    checkbox.prop('disabled', true);
                }
            });

            // Update action bar
            const action_bar = page.main_container.find('.action-bar');
            action_bar.html('');

            if (valid_companies.length > 0) {
                action_bar.html(`
                    <span class="validation-summary text-muted mr-3">
                        ${valid_companies.length} of ${r.message.length} companies ready for import
                    </span>
                    <button class="btn btn-success btn-sm btn-import">
                        <i class="fa fa-download"></i> Import Selected
                    </button>
                `);

                action_bar.find('.btn-import').on('click', function() {
                    import_selected(page);
                });

                // Fetch and show preview table for valid companies
                fetch_preview_data(page, fiscal_year, month, valid_companies);
            } else {
                action_bar.html('<span class="text-danger">No companies are eligible for import.</span>');
            }
        }
    });
}

function fetch_preview_data(page, fiscal_year, month, companies) {
    // Show loading for preview
    page.main_container.append(`
        <div class="preview-section">
            <div class="text-center p-4">
                <i class="fa fa-spinner fa-spin"></i> Loading preview data...
            </div>
        </div>
    `);

    frappe.call({
        method: 'financial_report_tool.financial_report_tool.page.import_console_trial_balance.import_console_trial_balance.get_preview_data',
        args: { fiscal_year, month, companies: JSON.stringify(companies) },
        callback: function(r) {
            const data = r.message || {};
            const rows = data.rows || [];
            const threshold = data.threshold || 0;

            if (rows.length === 0) {
                page.main_container.find('.preview-section').html(`
                    <div class="text-muted text-center p-4">No entries to preview.</div>
                `);
                return;
            }
            // Store all rows and threshold on the page for filtering
            page._preview_rows = rows;
            page._preview_companies = companies;
            page._threshold = threshold;
            render_preview_table(page, rows);
        }
    });
}

function format_number(num) {
    if (num == null) return '0.00';
    return parseFloat(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function render_preview_table(page, rows) {
    // Build company filter options
    const all_companies = page._preview_companies || [];
    let company_options = '<option value="">All Companies</option>';
    all_companies.forEach(function(c) {
        company_options += `<option value="${c}">${c}</option>`;
    });

    // Filter rows if a company is selected
    const filter_el = page.main_container.find('.preview-company-filter');
    const selected_company = filter_el.length ? filter_el.val() : '';
    const filtered_rows = selected_company
        ? rows.filter(r => r.company === selected_company)
        : rows;

    let total_dc = 0;
    let total_inr = 0;

    let tbody = '';
    filtered_rows.forEach(function(row, idx) {
        total_dc += row.amount || 0;
        total_inr += row.amount_inr || 0;

        tbody += `
            <tr>
                <td class="text-right">${idx + 1}</td>
                <td>${row.company}</td>
                <td>${row.gl_account}</td>
                <td>${row.report_type}</td>
                <td class="text-right">${row.exchange_rate}</td>
                <td class="text-right">${format_number(row.amount)}</td>
                <td class="text-right">${format_number(row.amount_inr)}</td>
            </tr>`;
    });

    const html = `
        <div class="preview-section">
            <div class="section-header" style="margin-top: 20px;">
            <div class="preview-filter-bar">
                <label>Company:</label>
                <select class="form-control input-sm preview-company-filter">
                ${company_options}
                </select>
            </div>
            <h5>Preview (${filtered_rows.length} entries)</h5>
            </div>
            <div class="preview-table-wrapper">
                <table class="table table-bordered preview-table">
                    <thead>
                        <tr>
                            <th class="text-right" width="50">#</th>
                            <th>Company</th>
                            <th>GL Account</th>
                            <th>Report Type</th>
                            <th class="text-right">Exchange Rate</th>
                            <th class="text-right">Amount (DC)</th>
                            <th class="text-right">Amount (INR)</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${tbody}
                    </tbody>
                    <tfoot>
                        <tr class="total-row">
                            <td colspan="5" class="text-right"><b>Total</b></td>
                            <td class="text-right"><b>${format_number(total_dc)}</b></td>
                            <td class="text-right"><b>${format_number(total_inr)}</b></td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>
    `;

    page.main_container.find('.preview-section').replaceWith(html);

    // Restore selected value & bind change
    if (selected_company) {
        page.main_container.find('.preview-company-filter').val(selected_company);
    }
    page.main_container.find('.preview-company-filter').on('change', function() {
        render_preview_table(page, page._preview_rows);
    });
}

function import_selected(page) {
    const { fiscal_year, month } = get_filter_values(page);
    const companies = get_selected_companies(page);

    if (!fiscal_year || !month) {
        frappe.msgprint(__('Please select Fiscal Year and Month.'));
        return;
    }

    if (companies.length === 0) {
        frappe.msgprint(__('Please select at least one company.'));
        return;
    }

    frappe.confirm(
        __('Import Console Trial Balance for <b>{0}</b> companies?<br>Fiscal Year: <b>{1}</b>, Month: <b>{2}</b>', [companies.length, fiscal_year, month]),
        function() {
            frappe.call({
                method: 'financial_report_tool.financial_report_tool.page.import_console_trial_balance.import_console_trial_balance.import_console_trial_balance',
                args: { fiscal_year, month, companies: JSON.stringify(companies) },
                freeze: true,
                freeze_message: __('Importing Console Trial Balance...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint({
                            title: __('Import Successful'),
                            indicator: 'green',
                            message: r.message.message
                        });
                        // Refresh to show updated statuses
                        fetch_companies(page);
                    }
                }
            });
        }
    );
}

function add_page_styles() {
    if (document.getElementById('import-ctb-styles')) return;

    const style = document.createElement('style');
    style.id = 'import-ctb-styles';
    style.innerHTML = `
        .import-ctb-container {
            padding: 15px;
        }
        .import-ctb-container .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
        }
        .import-ctb-container .empty-state h4 {
            margin-top: 15px;
            color: var(--text-color);
        }
        .import-ctb-container .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .import-ctb-container .section-header h5 {
            margin: 0;
        }
        .import-ctb-container .select-all-label {
            cursor: pointer;
            font-weight: normal;
            margin: 0;
        }
        .import-ctb-container .select-all-label input {
            margin-right: 5px;
        }
        .import-ctb-container .company-table {
            background: var(--card-bg);
            margin-bottom: 15px;
        }
        .import-ctb-container .company-table thead th,
        .import-ctb-container .preview-table thead th {
            background: var(--subtle-fg);
            font-size: 12px;
            text-transform: uppercase;
            font-weight: 600;
        }
        .import-ctb-container .company-table td {
            vertical-align: middle;
        }
        .import-ctb-container .action-bar {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 10px;
            padding: 10px 0;
        }
        .import-ctb-container .validation-summary {
            font-size: 13px;
        }
        .import-ctb-container .preview-filter-bar {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .import-ctb-container .preview-filter-bar label {
            margin: 0;
            font-weight: normal;
            white-space: nowrap;
        }
        .import-ctb-container .preview-company-filter {
            width: 250px;
        }
        .import-ctb-container .preview-table-wrapper {
            max-height: 500px;
            overflow-y: auto;
            border: 1px solid var(--border-color);
            border-radius: 4px;
        }
        .import-ctb-container .preview-table {
            margin-bottom: 0;
            background: var(--card-bg);
        }
        .import-ctb-container .preview-table thead {
            position: sticky;
            top: 0;
            z-index: 1;
        }
        .import-ctb-container .preview-table td {
            font-size: 13px;
            padding: 6px 10px;
        }
        .import-ctb-container .preview-table .total-row td {
            background: var(--subtle-fg);
            font-size: 13px;
            position: sticky;
            bottom: 0;
        }
    `;
    document.head.appendChild(style);
}
