// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

frappe.pages['missing-gl-group-mapping'].on_page_load = function(wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Missing GL Group Mapping',
        single_column: true
    });

    // Store page reference
    wrapper.page = page;

    // Add filters
    page.add_field({
        label: 'Company',
        fieldname: 'company',
        fieldtype: 'Link',
        options: 'Company',
        default: frappe.defaults.get_user_default("Company"),
        reqd: 1,
        change() {
            // Don't auto-refresh, wait for report type
        }
    });

    page.add_field({
        label: 'Report Type',
        fieldname: 'report_type',
        fieldtype: 'Select',
        options: '\nMonthly\nYearly\nMIS',
        reqd: 1,
        change() {
            const company = page.fields_dict.company.get_value();
            const report_type = this.get_value();
            if (company && report_type) {
                load_missing_gl_data(page);
            }
        }
    });

    // Add Refresh button
    page.set_primary_action(__('Refresh'), function() {
        const company = page.fields_dict.company.get_value();
        const report_type = page.fields_dict.report_type.get_value();
        if (company && report_type) {
            load_missing_gl_data(page);
        } else {
            frappe.msgprint(__('Please select Company and Report Type'));
        }
    }, 'octicon octicon-sync');

    // Create main container
    page.main_container = $('<div class="missing-gl-container"></div>').appendTo(page.body);

    // Add styles
    add_page_styles();

    // Initial message
    page.main_container.html(`
        <div class="empty-state">
            <div class="empty-state-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
            </div>
            <h4>Select Filters to Begin</h4>
            <p>Please select Company and Report Type, then click Refresh to load missing GL accounts.</p>
        </div>
    `);
};

function add_page_styles() {
    if (document.getElementById('missing-gl-page-styles')) return;

    const style = document.createElement('style');
    style.id = 'missing-gl-page-styles';

    style.innerHTML = `

        /* =========================
           Layout Fix (IMPORTANT)
        ==========================*/

        .table-card,
        .missing-gl-table-wrapper,
        .missing-gl-table,
        .missing-gl-table tbody,
        .missing-gl-table tr,
        .missing-gl-table td,
        .link-field-cell,
        .form-group,
        .control-input-wrapper,
        .layout-main-section,
        .layout-main,
        .page-body,
        .page-container {
            overflow: visible !important;
        }

        .missing-gl-container {
            padding: 20px;
            max-width: 100%;
        }

        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
        }

        .empty-state-icon {
            margin-bottom: 20px;
            color: var(--gray-400);
        }

        .empty-state h4 {
            color: var(--text-color);
            margin-bottom: 10px;
            font-weight: 600;
        }

        .empty-state p {
            color: var(--text-muted);
            max-width: 400px;
            margin: 0 auto;
        }

        .loading-state {
            text-align: center;
            padding: 60px 20px;
        }

        .loading-spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--gray-200);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .table-card {
            background: var(--card-bg);
            border-radius: 10px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
            border: 1px solid var(--border-color);
        }

        .table-header {
            padding: 15px 20px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: var(--subtle-fg);
        }

        .table-header h5 {
            margin: 0;
            font-weight: 600;
            color: var(--text-color);
        }

        .table-header .count-badge {
            background: var(--primary);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }

        .missing-gl-table-wrapper {
            overflow-x: auto;
        }

        .missing-gl-table {
            width: 100%;
            border-collapse: collapse;
        }

        .missing-gl-table th {
            background: var(--subtle-fg);
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            border-bottom: 2px solid var(--border-color);
            white-space: nowrap;
        }

        .missing-gl-table td {
            padding: 12px 15px;
            border-bottom: 1px solid var(--border-color);
            font-size: 13px;
        }

        .missing-gl-table tbody tr:hover {
            background: var(--subtle-fg);
        }

        .missing-gl-table tbody tr.mapping-created {
            background: rgba(34, 197, 94, 0.1);
        }

        .link-field-cell {
            min-width: 200px;
            padding: 8px 10px !important;
            position: relative;
        }


        .link-field-cell .frappe-control,
        .link-field-cell .form-group {
            margin-bottom: 0;
        }


        .link-field-cell .control-label {
            display: none;
        }


        .link-field-cell input.input-with-feedback {
            height: 32px;
            font-size: 13px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
            padding: 4px 10px;
            width: 100%;
        }


        .link-field-cell input.input-with-feedback:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
        }


        .link-field-cell .link-btn {
            display: none;
        }


        .link-field-cell .awesomplete {
            width: 100%;
            display: block;
        }


        /* Dropdown Fix */
        .link-field-cell .awesomplete > ul {
            z-index: 100000 !important;
            max-height: 250px;
        }


        .link-field-cell .help-box {
            display: none;
        }

        /* MultiSelect field styles */
        .link-field-cell .frappe-control[data-fieldtype="MultiSelect"] {
            width: 100%;
        }

        .link-field-cell .frappe-control[data-fieldtype="MultiSelect"] .form-group {
            margin-bottom: 0;
        }

        .link-field-cell .frappe-control[data-fieldtype="MultiSelect"] .control-label {
            display: none;
        }

        .link-field-cell .frappe-control[data-fieldtype="MultiSelect"] .control-input-wrapper {
            position: relative;
        }

        .link-field-cell .frappe-control[data-fieldtype="MultiSelect"] input {
            height: 32px;
            font-size: 13px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
            padding: 4px 10px;
        }

        .link-field-cell .frappe-control[data-fieldtype="MultiSelect"] input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
        }

        .link-field-cell .frappe-control[data-fieldtype="MultiSelect"] .awesomplete > ul {
            z-index: 100000 !important;
            max-height: 250px;
        }

        .link-field-cell .tb-selected-value {
            background: var(--primary);
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            margin: 2px;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .link-field-cell .tb-selected-value .btn-remove {
            cursor: pointer;
            opacity: 0.8;
        }

        .link-field-cell .tb-selected-value .btn-remove:hover {
            opacity: 1;
        }

        .status-cell {
            text-align: center;
            width: 60px;
        }


        .status-pending {
            color: var(--orange-500);
            font-size: 18px;
            font-weight: bold;
        }


        .status-created {
            color: var(--green-600);
            font-size: 18px;
            font-weight: bold;
        }

        .action-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }

        .btn-create-grouping {
            display: inline-flex;
            align-items: center;
            padding: 10px 20px;
            font-weight: 600;
            border-radius: 8px;
            font-size: 14px;
        }

        .btn-create-grouping:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(37,99,235,0.3);
        }

        .filled-count {
            color: var(--text-muted);
            font-size: 13px;
        }

        @media (max-width: 768px) {

            .table-header {
                flex-direction: column;
                gap: 10px;
                text-align: center;
            }

            .action-bar {
                flex-direction: column;
                align-items: flex-start;
            }
        }

    `;

    document.head.appendChild(style);
}

function load_missing_gl_data(page) {
    const company = page.fields_dict.company.get_value();
    const report_type = page.fields_dict.report_type.get_value();

    page.main_container.html(`
        <div class="loading-state">
            <div class="loading-spinner"></div>
            <p>Loading GL accounts...</p>
        </div>
    `);

    frappe.call({
        method: 'financial_report_tool.financial_report_tool.page.missing_gl_group_mapping.missing_gl_group_mapping.get_missing_gl_accounts',
        args: {
            company: company,
            report_type: report_type
        },
        callback: function(r) {
            if (r.message) {
                render_table(page, r.message.data);
            }
        }
    });
}

function render_table(page, data) {
    if (!data || data.length === 0) {
        page.main_container.html(`
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                    </svg>
                </div>
                <h4>All GL Accounts Mapped</h4>
                <p>No missing GL account mappings found for the selected filters.</p>
            </div>
        `);
        return;
    }

    // Store data on page for later use
    page.gl_data = data;

    let html = `
        <div class="action-bar">
            <div class="action-bar-left">
                <button class="btn btn-default btn-sm btn-download-template">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 5px;">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                    </svg>
                    Download Template
                </button>
                <button class="btn btn-default btn-sm btn-upload-excel">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 5px;">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="17 8 12 3 7 8"></polyline>
                        <line x1="12" y1="3" x2="12" y2="15"></line>
                    </svg>
                    Upload Excel
                </button>
            </div>
            <div class="action-bar-right">
                <span class="filled-count" id="filled-count">0 ready to create</span>
                <button class="btn btn-primary btn-create-grouping">Create Grouping</button>
            </div>
        </div>
        <div class="table-card">
            <div class="table-header">
                <h5>GL Accounts Missing Mapping</h5>
                <span class="count-badge">${data.length} accounts</span>
            </div>
            <div class="missing-gl-table-wrapper">
                <table class="missing-gl-table">
                    <thead>
                        <tr>
                            <th style="width: 50px;">#</th>
                            <th style="width: 120px;">Account No.</th>
                            <th>GL Account</th>
                            <th><span style="display:inline-flex;align-items:center;gap:2px;">Primary Group<span class="text-danger">*</span></span></th>
                            <th><span style="display:inline-flex;align-items:center;gap:2px;">Secondary Group<span class="text-danger">*</span></span></th>
                            <th>Higher Secondary</th>
                            <th class="status-cell">Status</th>
                        </tr>
                    </thead>
                    <tbody>
    `;

    data.forEach((row, idx) => {
        const accountNumber = frappe.utils.escape_html(row.account_number || '');
        html += `
            <tr data-idx="${idx}" data-gl-account="${frappe.utils.escape_html(row.gl_account)}" id="row-${idx}">
                <td style="color: var(--text-muted); font-size: 12px;">${idx + 1}</td>
                <td class="account-number-cell">
                    ${accountNumber ? accountNumber : '-'}
                </td>
                <td>
                    <a href="/app/account/${encodeURIComponent(row.gl_account)}" target="_blank" class="gl-account-link">
                        ${frappe.utils.escape_html(row.gl_account)}
                    </a>
                </td>
                <td class="link-field-cell" id="primary-group-${idx}"></td>
                <td class="link-field-cell" id="secondary-group-${idx}"></td>
                <td class="link-field-cell" id="higher-secondary-group-${idx}"></td>
                <td class="status-cell" id="status-${idx}">
                    <span class="status-pending" title="Pending">●</span>
                </td>
            </tr>
        `;
    });

    html += `
                    </tbody>
                </table>
            </div>
        </div>
    `;

    page.main_container.html(html);

    // Initialize Link fields for each row
    data.forEach((_, idx) => {
        init_link_fields(page, idx);
    });

    // Create Grouping button click handler
    page.main_container.find('.btn-create-grouping').on('click', function() {
        create_all_filled_mappings(page);
    });

    // Download Template button click handler
    page.main_container.find('.btn-download-template').on('click', function() {
        const company = page.fields_dict.company.get_value();
        const report_type = page.fields_dict.report_type.get_value();
        window.open(`/api/method/financial_report_tool.financial_report_tool.page.missing_gl_group_mapping.missing_gl_group_mapping.download_template?company=${encodeURIComponent(company)}&report_type=${encodeURIComponent(report_type)}`);
    });

    // Upload Excel button click handler
    page.main_container.find('.btn-upload-excel').on('click', function() {
        upload_excel_dialog(page);
    });

    // Copy button click handler
    page.main_container.find('.copy-btn').on('click', function(e) {
        e.preventDefault();
        const text = $(this).data('copy');
        const btn = $(this);

        navigator.clipboard.writeText(text).then(function() {
            btn.addClass('copied');
            btn.html(`
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            `);
            setTimeout(function() {
                btn.removeClass('copied');
                btn.html(`
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                `);
            }, 1500);
        });
    });
}

function init_link_fields(page, idx) {
    // Primary Group MultiSelect Link (Mandatory)
    const primary_field = frappe.ui.form.make_control({
        df: {
            fieldtype: 'MultiSelect',
            fieldname: `primary_group_${idx}`,
            options: 'Standalone Group',
            placeholder: 'Select Primary',
            reqd: 1,
            get_query: function() {
                return {
                    filters: {
                        'is_primary_group': 1,
                        'disable': 0
                    }
                };
            },
            change: function() {
                const val = this.get_value();
                page.gl_data[idx].primary_group = val;
                // Clear secondary when primary changes
                if (page.gl_data[idx]._secondary_field) {
                    page.gl_data[idx]._secondary_field.set_value([]);
                    page.gl_data[idx].secondary_group = [];
                }
                update_filled_count(page);
            }
        },
        parent: $(`#primary-group-${idx}`),
        render_input: true
    });
    primary_field.refresh();
    page.gl_data[idx]._primary_field = primary_field;

    // Secondary Group MultiSelect Link (Mandatory)
    const secondary_field = frappe.ui.form.make_control({
        df: {
            fieldtype: 'MultiSelect',
            fieldname: `secondary_group_${idx}`,
            options: 'Standalone Group',
            placeholder: 'Select Secondary',
            reqd: 1,
            get_query: function() {
                let filters = {
                    'disable': 0
                };
                return { filters: filters };
            },
            change: function() {
                page.gl_data[idx].secondary_group = this.get_value();
                update_filled_count(page);
            }
        },
        parent: $(`#secondary-group-${idx}`),
        render_input: true
    });
    secondary_field.refresh();
    page.gl_data[idx]._secondary_field = secondary_field;

    // Higher Secondary Group MultiSelect Link (Optional)
    const higher_secondary_field = frappe.ui.form.make_control({
        df: {
            fieldtype: 'MultiSelect',
            fieldname: `higher_secondary_group_${idx}`,
            options: 'Standalone Group',
            placeholder: 'Optional',
            get_query: function() {
                return {
                    filters: {
                        'disable': 0
                    }
                };
            },
            change: function() {
                page.gl_data[idx].higher_secondary_group = this.get_value();
            }
        },
        parent: $(`#higher-secondary-group-${idx}`),
        render_input: true
    });
    higher_secondary_field.refresh();
    page.gl_data[idx]._higher_secondary_field = higher_secondary_field;
}

function create_all_filled_mappings(page) {
    const company = page.fields_dict.company.get_value();
    const report_type = page.fields_dict.report_type.get_value();

    if (!company || !report_type) {
        frappe.msgprint(__('Please select Company and Report Type'));
        return;
    }

    // Collect all rows with complete mappings that haven't been created yet
    const mappings = [];

    page.gl_data.forEach((row, idx) => {
        const primary = row.primary_group;
        const secondary = row.secondary_group;
        const hasPrimary = primary && (Array.isArray(primary) ? primary.length > 0 : primary);
        const hasSecondary = secondary && (Array.isArray(secondary) ? secondary.length > 0 : secondary);

        if (hasPrimary && hasSecondary && !row._mapping_created) {
            // Convert to arrays if not already
            const primaryGroups = Array.isArray(primary) ? primary : [primary];
            const secondaryGroups = Array.isArray(secondary) ? secondary : [secondary];
            const higherSecondaryGroups = row.higher_secondary_group
                ? (Array.isArray(row.higher_secondary_group) ? row.higher_secondary_group : [row.higher_secondary_group])
                : [];

            mappings.push({
                idx: idx,
                gl_account: row.gl_account,
                primary_group: primaryGroups,
                secondary_group: secondaryGroups,
                higher_secondary_group: higherSecondaryGroups.length > 0 ? higherSecondaryGroups : null
            });
        }
    });

    if (mappings.length === 0) {
        frappe.msgprint(__('No complete mappings to create. Please fill Primary Group and Secondary Group for at least one row.'));
        return;
    }

    // Create the mappings
    frappe.call({
        method: 'financial_report_tool.financial_report_tool.page.missing_gl_group_mapping.missing_gl_group_mapping.create_bulk_gl_group_mappings',
        args: {
            mappings: mappings,
            company: company,
            report_type: report_type
        },
        freeze: true,
        freeze_message: __('Creating GL Group Mappings...'),
        callback: function(r) {
            if (r.message) {
                const created = r.message.created || [];
                const errors = r.message.errors || [];

                // Update UI for created mappings
                created.forEach(gl_account => {
                    const idx = page.gl_data.findIndex(row => row.gl_account === gl_account);
                    if (idx !== -1) {
                        const row = page.gl_data[idx];
                        row._mapping_created = true;

                        $(`#row-${idx}`).addClass('mapping-created');
                        $(`#status-${idx}`).html(`
                            <span class="status-created" title="Created">✓</span>
                        `);

                        // Disable the fields
                        if (row._primary_field) row._primary_field.$input.prop('disabled', true);
                        if (row._secondary_field) row._secondary_field.$input.prop('disabled', true);
                        if (row._higher_secondary_field) row._higher_secondary_field.$input.prop('disabled', true);
                    }
                });

                // Show result message
                let msg = '';
                if (created.length > 0) {
                    msg += __('Successfully created {0} GL Group Mapping(s).', [created.length]);
                }
                if (errors.length > 0) {
                    msg += '<br>' + __('Failed to create {0} mapping(s):', [errors.length]) + '<br>';
                    errors.forEach(err => {
                        msg += `- ${err.gl_account}: ${err.error}<br>`;
                    });
                }

                if (created.length > 0) {
                    frappe.show_alert({
                        message: __('Created {0} mapping(s)', [created.length]),
                        indicator: 'green'
                    }, 5);
                }

                if (errors.length > 0) {
                    frappe.msgprint(msg);
                }

                // Update filled count
                update_filled_count(page);
            }
        }
    });
}

function update_filled_count(page) {
    let filled = 0;
    page.gl_data.forEach(row => {
        const primary = row.primary_group;
        const secondary = row.secondary_group;
        const hasPrimary = primary && (Array.isArray(primary) ? primary.length > 0 : primary);
        const hasSecondary = secondary && (Array.isArray(secondary) ? secondary.length > 0 : secondary);
        if (hasPrimary && hasSecondary && !row._mapping_created) {
            filled++;
        }
    });
    page.main_container.find('#filled-count').text(filled + ' ready to create');
}

function upload_excel_dialog(page) {
    const dialog = new frappe.ui.Dialog({
        title: __('Upload GL Group Mappings'),
        fields: [
            {
                fieldtype: 'HTML',
                options: `
                    <div class="upload-instructions" style="margin-bottom: 15px; padding: 10px; background: var(--subtle-fg); border-radius: 6px;">
                        <p style="margin: 0 0 10px 0; font-weight: 500;">Instructions:</p>
                        <ol style="margin: 0; padding-left: 20px; font-size: 13px; color: var(--text-muted);">
                            <li>Download the template first using "Download Template" button</li>
                            <li>Fill in the Primary Group and Secondary Group columns (required)</li>
                            <li>Higher Secondary Group is optional</li>
                            <li>Upload the filled Excel file - data will be filled in the table</li>
                            <li>Review and adjust if needed, then click "Create Grouping"</li>
                        </ol>
                    </div>
                `
            },
            {
                fieldtype: 'Attach',
                fieldname: 'file',
                label: __('Excel File'),
                reqd: 1,
                options: {
                    restrictions: {
                        allowed_file_types: ['.xlsx', '.xls']
                    }
                }
            }
        ],
        primary_action_label: __('Fill Table'),
        primary_action: function(values) {
            if (!values.file) {
                frappe.msgprint(__('Please select a file'));
                return;
            }

            frappe.call({
                method: 'financial_report_tool.financial_report_tool.page.missing_gl_group_mapping.missing_gl_group_mapping.parse_excel_mappings',
                args: {
                    file_url: values.file
                },
                freeze: true,
                freeze_message: __('Reading Excel file...'),
                callback: function(r) {
                    dialog.hide();

                    if (r.message) {
                        const result = r.message;

                        if (!result.success && result.error) {
                            frappe.msgprint({
                                title: __('Error'),
                                indicator: 'red',
                                message: result.error
                            });
                            return;
                        }

                        const mappings = result.mappings || [];
                        const errors = result.errors || [];

                        // Fill the table with parsed data
                        let filled_count = 0;
                        mappings.forEach(mapping => {
                            // Find the row by GL Account
                            const idx = page.gl_data.findIndex(row => row.gl_account === mapping.gl_account);
                            if (idx !== -1 && !page.gl_data[idx]._mapping_created) {
                                const row = page.gl_data[idx];

                                // Fill Primary Group (convert to array for multi-select)
                                if (mapping.primary_group && row._primary_field) {
                                    const primaryValues = Array.isArray(mapping.primary_group)
                                        ? mapping.primary_group
                                        : [mapping.primary_group];
                                    row._primary_field.set_value(primaryValues);
                                    row.primary_group = primaryValues;
                                }

                                // Fill Secondary Group (convert to array for multi-select)
                                if (mapping.secondary_group && row._secondary_field) {
                                    const secondaryValues = Array.isArray(mapping.secondary_group)
                                        ? mapping.secondary_group
                                        : [mapping.secondary_group];
                                    row._secondary_field.set_value(secondaryValues);
                                    row.secondary_group = secondaryValues;
                                }

                                // Fill Higher Secondary Group (convert to array for multi-select)
                                if (mapping.higher_secondary_group && row._higher_secondary_field) {
                                    const higherSecValues = Array.isArray(mapping.higher_secondary_group)
                                        ? mapping.higher_secondary_group
                                        : [mapping.higher_secondary_group];
                                    row._higher_secondary_field.set_value(higherSecValues);
                                    row.higher_secondary_group = higherSecValues;
                                }

                                if (mapping.primary_group && mapping.secondary_group) {
                                    filled_count++;
                                }
                            }
                        });

                        // Update filled count
                        update_filled_count(page);

                        // Show result message
                        let msg = `<p style="color: var(--green-600);"><strong>${filled_count}</strong> row(s) filled from Excel.</p>`;
                        msg += `<p style="color: var(--text-muted);">Review the data and click <strong>Create Grouping</strong> to save.</p>`;

                        if (errors.length > 0) {
                            msg += `<p style="color: var(--orange-500); margin-top: 10px;"><strong>${errors.length}</strong> row(s) with issues:</p><ul style="font-size: 12px;">`;
                            errors.slice(0, 5).forEach(e => {
                                msg += `<li>Row ${e.row}: ${e.gl_account || 'Unknown'} - ${e.error}</li>`;
                            });
                            if (errors.length > 5) {
                                msg += `<li>... and ${errors.length - 5} more</li>`;
                            }
                            msg += '</ul>';
                        }

                        frappe.show_alert({
                            message: __('Filled {0} row(s) from Excel', [filled_count]),
                            indicator: 'green'
                        }, 5);
                    }
                }
            });
        }
    });

    dialog.show();
}
