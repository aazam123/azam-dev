// Consolidated Financial Statement — one columnar table per statement:
//   Particular | Consolidate | <Company 1> | <Company 2> | ...
// Consolidate = arithmetic total of the domestic (INR) companies shown.

frappe.pages['domestic-financials'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Consolidated Financial Statement',
		single_column: true,
	});

	const state = {
		report_type: 'Yearly',
		fiscal_year: null,
		month: null,
		show_kpi: false, // Gross Margin rows hidden until the user opts in
	};

	// ---- Body scaffold: in-body filter row + table ----------------------
	page.body.html(`
		<div class="cfs-wrap">
			<div class="cfs-filters" id="cfs-filters">
				<div class="cfs-field">
					<label>Report Type</label>
					<select class="form-control input-sm" id="cfs-report-type">
						<option value="Yearly">Yearly</option>
						<option value="Monthly">Monthly</option>
					</select>
				</div>
				<div class="cfs-field">
					<label>Fiscal Year</label>
					<select class="form-control input-sm" id="cfs-fiscal-year"></select>
				</div>
				<div class="cfs-field" id="cfs-month-field" style="display:none;">
					<label>Month</label>
					<select class="form-control input-sm" id="cfs-month"></select>
				</div>
				<button class="btn btn-sm cfs-kpi-toggle" id="cfs-kpi-toggle" type="button">
					<span class="cfs-kpi-dot"></span><span class="cfs-kpi-label">Show Gross Margin</span>
				</button>
				<button class="btn btn-sm btn-default cfs-refresh" id="cfs-refresh">Refresh</button>
			</div>
			<div class="cfs-table-wrap" id="cfs-table">
				<div class="cfs-loading">Loading…</div>
			</div>
		</div>
	`);

	inject_styles();
	page.cfs = { state };

	const $body = $(page.body);
	$body.find('#cfs-report-type').on('change', function () {
		state.report_type = this.value || 'Yearly';
		load_context(page, state); // fiscal years + months depend on report type
	});
	$body.find('#cfs-fiscal-year').on('change', function () {
		state.fiscal_year = this.value || null;
		load_context(page, state); // refresh months for the new year
	});
	$body.find('#cfs-month').on('change', function () {
		state.month = this.value || null;
		load_statement(page, state);
	});
	$body.find('#cfs-refresh').on('click', () => load_statement(page, state));
	$body.find('#cfs-kpi-toggle').on('click', function () {
		state.show_kpi = !state.show_kpi;
		apply_kpi_visibility(page, state);
	});

	load_context(page, state);
};

// --- Toggle the Gross Margin (derived KPI) rows on/off --------------------
function apply_kpi_visibility(page, state) {
	const $body = $(page.body);
	$body.find('#cfs-table').toggleClass('cfs-kpi-on', !!state.show_kpi);
	const $btn = $body.find('#cfs-kpi-toggle');
	$btn.toggleClass('active', !!state.show_kpi);
	$btn.find('.cfs-kpi-label').text(state.show_kpi ? 'Hide Gross Margin' : 'Show Gross Margin');
}

// --- Populate a native <select> with options -----------------------------
function set_select(sel, options, selected) {
	sel.empty();
	(options || []).forEach((o) => {
		const opt = $('<option>').val(o.value).text(o.label);
		if (o.value === selected) opt.attr('selected', 'selected');
		sel.append(opt);
	});
	if (selected != null) sel.val(selected);
}

// --- Load fiscal-year / month filter context -----------------------------
function load_context(page, state) {
	frappe.call({
		method:
			'financial_report_tool.financial_report_tool.page.domestic_financials.domestic_financials.get_context',
		args: { report_type: state.report_type, fiscal_year: state.fiscal_year },
		callback(r) {
			const ctx = r.message || {};
			const $body = $(page.body);

			// Server resolves the fiscal year so months always match it.
			const years = ctx.fiscal_years || [];
			const fy = ctx.resolved_fiscal_year || null;
			state.fiscal_year = fy;
			set_select(
				$body.find('#cfs-fiscal-year'),
				years.map((y) => ({ value: y, label: 'FY ' + y })),
				fy
			);

			// Month filter: only relevant for Monthly.
			const is_monthly = state.report_type === 'Monthly';
			$body.find('#cfs-month-field').toggle(is_monthly);
			let months = [];
			if (is_monthly) {
				months = ctx.months || [];
				let m = state.month;
				if (!m || !months.includes(m)) m = ctx.default_month || (months.length ? months[0] : null);
				state.month = m;
				set_select(
					$body.find('#cfs-month'),
					months.map((x) => ({ value: x, label: x })),
					m
				);
			} else {
				state.month = null;
			}

			if (!fy) {
				render_empty(page, 'No generated reports found for domestic companies.');
				return;
			}
			if (is_monthly && !months.length) {
				render_empty(page, `No monthly reports found for FY ${fy}.`);
				return;
			}
			load_statement(page, state);
		},
	});
}

// --- Load both statements: Profit & Loss first, then Balance Sheet -------
function load_statement(page, state) {
	if (!state.fiscal_year) return;
	if (state.report_type === 'Monthly' && !state.month) return;
	$('#cfs-table').html('<div class="cfs-loading">Loading…</div>');

	// Guard against a slower earlier request overwriting a newer one.
	const seq = (page.cfs.load_seq = (page.cfs.load_seq || 0) + 1);

	const fetch = (statement) =>
		frappe
			.call({
				method:
					'financial_report_tool.financial_report_tool.page.domestic_financials.domestic_financials.get_consolidated_statement',
				args: {
					fiscal_year: state.fiscal_year,
					report_type: state.report_type,
					statement: statement,
					month: state.month,
				},
			})
			.then((r) => r.message || {});

	// P&L first, Balance Sheet below.
	Promise.all([fetch('Profit & Loss'), fetch('Balance Sheet')])
		.then(([pl, bs]) => {
			if (seq !== page.cfs.load_seq) return; // a newer load superseded this one
			const html =
				build_statement_block('Profit & Loss', pl) + build_statement_block('Balance Sheet', bs);
			$('#cfs-table').html(html);
		})
		.catch(() => {
			if (seq !== page.cfs.load_seq) return;
			render_empty(page, 'Failed to load statements. Please try again.');
		});
}

// --- Number formatting (whole numbers, comma-separated; no decimals) ------
function fmt_num(v) {
	if (v === null || v === undefined) return ''; // not applicable for this company
	const n = Math.round(Number(v));
	if (n === 0) return '-'; // includes values that round to zero
	return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

// --- Percentage formatting (one decimal, % suffix) -----------------------
function fmt_pct(v) {
	if (v === null || v === undefined) return ''; // not applicable / undefined denominator
	const n = Number(v);
	if (!isFinite(n)) return '';
	return n.toFixed(1) + '%';
}

// --- Build one statement's block (title + columnar table) ----------------
function build_statement_block(title, data) {
	const heading = `<div class="cfs-block-title">${frappe.utils.escape_html(title)}</div>`;
	const companies = data.companies || [];
	const rows = data.rows || [];
	if (!companies.length || !rows.length) {
		return `<div class="cfs-block">${heading}<div class="cfs-empty">No data available for the selected filters.</div></div>`;
	}

	// Measures (sub-columns) come from the server: 2 for Yearly, 3 for Monthly.
	const cols = data.columns && data.columns.length ? data.columns : [{ key: 'cy', label: '' }];
	const ncol = cols.length;

	// Grouped two-row header: each company (and Consolidate) spans its measures.
	const group_head = (label, extra) =>
		`<th colspan="${ncol}" class="cfs-num cfs-group ${extra || ''}" title="${label}">${label}</th>`;
	const sub_head = (extra) =>
		cols
			.map((c, ci) => {
				const cls = (ci === 0 ? 'cfs-group-start' : 'cfs-py') + (extra ? ' ' + extra : '');
				return `<th class="cfs-num ${cls}">${frappe.utils.escape_html(c.label)}</th>`;
			})
			.join('');

	const thead = `
		<tr>
			<th rowspan="2" class="cfs-particular cfs-sticky">Particular</th>
			${group_head('Consolidate', 'cfs-consol-col')}
			${companies.map((c) => group_head(frappe.utils.escape_html(c), 'cfs-comp-head')).join('')}
		</tr>
		<tr class="cfs-subhead">
			${sub_head('cfs-consol-col')}
			${companies.map(() => sub_head()).join('')}
		</tr>`;

	const num_cells = (obj, extra, blank, fmt = fmt_num) =>
		cols
			.map((c, ci) => {
				const cls = (ci === 0 ? 'cfs-group-start' : 'cfs-py') + (extra ? ' ' + extra : '');
				const val = obj ? obj[c.key] : null;
				return `<td class="cfs-num ${cls}">${blank ? '' : fmt(val)}</td>`;
			})
			.join('');

	const tbody = rows
		.map((row) => {
			const indent = row.indent ? `padding-left:${12 + row.indent * 18}px;` : '';
			// A row is blank (pure section header) when the server sent no totals.
			const blank = !row.consolidate;
			// Derived KPI rows (e.g. Gross Margin %) carry their own formatter.
			const fmt = row.value_format === 'percent' ? fmt_pct : fmt_num;
			const cls = [];
			if (blank && row.is_header) cls.push('cfs-header-row'); // e.g. Income, Expenses
			else if (row.is_bold) cls.push('cfs-bold-row'); // subtotals / grouped totals
			if (row.kind === 'derived') cls.push('cfs-derived-row'); // computed KPI

			const consol = num_cells(row.consolidate, 'cfs-consol-col', blank, fmt);
			const cells = companies.map((c, i) => num_cells(row.values[i], '', blank, fmt)).join('');

			return `
				<tr class="${cls.join(' ')}">
					<td class="cfs-particular cfs-sticky" style="${indent}">${frappe.utils.escape_html(row.particular)}</td>
					${consol}
					${cells}
				</tr>`;
		})
		.join('');

	const missing = data.missing_companies || [];
	const miss_note = missing.length
		? ` • <span title="${frappe.utils.escape_html(missing.join(', '))}">${missing.length} company(ies) without a report excluded</span>`
		: '';
	const col_labels = cols.map((c) => frappe.utils.escape_html(c.label)).join(', ');

	return `
		<div class="cfs-block">
			${heading}
			<div class="cfs-scroll">
				<table class="cfs-table">
					<thead>${thead}</thead>
					<tbody>${tbody}</tbody>
				</table>
			</div>
			<div class="cfs-foot">
				Columns per company: ${col_labels} •
				<b>Consolidate</b> = arithmetic total of the companies shown (no intercompany eliminations)${miss_note}.
			</div>
		</div>`;
}

function render_empty(page, msg) {
	$('#cfs-table').html(`<div class="cfs-empty">${frappe.utils.escape_html(msg)}</div>`);
}

// --- Styles --------------------------------------------------------------
function inject_styles() {
	if (document.getElementById('cfs-styles')) return;
	const style = document.createElement('style');
	style.id = 'cfs-styles';
	style.innerHTML = `
		.cfs-wrap { padding: 4px 2px 60px; }

		/* Stacked statement blocks (P&L, then Balance Sheet) */
		.cfs-block { margin-bottom:28px; }
		.cfs-block-title {
			font-size:15px; font-weight:700; color:#14351b;
			margin:4px 2px 10px; padding-bottom:6px; border-bottom:2px solid #cdebd6;
		}

		/* In-body filter row — compact */
		.cfs-filters {
			display:flex; flex-wrap:wrap; gap:6px 12px; align-items:center;
			padding:7px 10px; margin-bottom:10px;
			background:#fafbfc; border:1px solid #eef1f5; border-radius:8px;
		}
		.cfs-field { display:flex; flex-direction:row; align-items:center; gap:6px; }
		.cfs-field label {
			font-size:10px; font-weight:600; color:#8a94a6;
			text-transform:uppercase; letter-spacing:.02em; margin:0; white-space:nowrap;
		}
		.cfs-field select.form-control {
			min-width:120px; width:auto; height:26px; padding:1px 22px 1px 8px; font-size:12px;
		}
		.cfs-filters .cfs-refresh { margin-left:auto; height:26px; padding:2px 12px; }

		.cfs-scroll { overflow-x:auto; border:1px solid #e6ebf1; border-radius:12px; background:#fff; }
		table.cfs-table { border-collapse:separate; border-spacing:0; width:100%; font-size:12.5px; }
		.cfs-table th, .cfs-table td {
			padding:7px 12px; border-bottom:1px solid #eef2f4;
		}
		.cfs-table thead th {
			background:#f4f8f5; color:#14351b; font-weight:600;
			border-bottom:2px solid #cdebd6; vertical-align:bottom;
		}
		/* Numeric cells never wrap; they hold the figures. */
		.cfs-num { text-align:right; font-variant-numeric:tabular-nums; min-width:104px; white-space:nowrap; }

		/* Grouped (company / consolidate) header spanning CY | PY */
		.cfs-group { text-align:center; border-bottom:1px solid #cdebd6; }
		.cfs-table th.cfs-comp-head {
			white-space:normal; overflow-wrap:break-word; line-height:1.25; vertical-align:middle;
		}
		.cfs-subhead th { font-weight:600; font-size:11px; color:#5a6b7b; padding-top:4px; padding-bottom:4px; }

		/* Previous-year sub-column: muted; group separators */
		.cfs-py { color:#97a2b0; }
		.cfs-group-start { border-left:1px solid #e3e9f0; }
		.cfs-table thead th.cfs-group-start { border-left:1px solid #d5dee7; }

		/* Sticky Particular column — fixed width, wraps long labels */
		.cfs-table td.cfs-particular, .cfs-table th.cfs-particular {
			text-align:left; width:320px; min-width:320px; max-width:320px;
			white-space:normal; overflow-wrap:break-word; word-break:normal; line-height:1.3;
		}
		.cfs-sticky { position:sticky; left:0; z-index:2; background:#fff; box-shadow:1px 0 0 #e6ebf1; }
		.cfs-table thead th.cfs-sticky { z-index:4; background:#f4f8f5; }

		/* Highlighted Consolidate column */
		.cfs-consol-col { background:#eef7ef; font-weight:600; color:#1B5E20; }
		.cfs-table thead th.cfs-consol-col { background:#e3f1e5; }

		/* Header / group rows */
		.cfs-header-row td { background:#f7faf8; font-weight:700; color:#14351b; text-transform:none; }
		.cfs-header-row td.cfs-sticky { background:#f7faf8; }
		.cfs-header-row td.cfs-consol-col { background:#eaf4ec; }

		/* Bold subtotal / total rows */
		.cfs-bold-row td { font-weight:700; border-top:1px solid #d7e3da; }
		.cfs-bold-row td.cfs-consol-col { background:#e3f1e5; }

		/* Derived KPI rows (Gross Margin, Gross Margin %) — hidden until toggled on */
		.cfs-derived-row { display:none; }
		.cfs-kpi-on .cfs-derived-row { display:table-row; }
		.cfs-derived-row td { font-weight:700; font-style:italic; background:#f3f8ff; color:#123a63; }
		.cfs-derived-row td.cfs-particular { font-style:normal; }
		.cfs-derived-row td.cfs-consol-col { background:#e6f0fb; color:#0d2f52; }

		/* Gross Margin toggle button */
		.cfs-kpi-toggle {
			display:inline-flex; align-items:center; gap:7px; height:26px; padding:2px 12px;
			font-size:12px; font-weight:600; color:#0d2f52; margin-left:auto;
			background:#eef4fc; border:1px solid #cfe0f5; border-radius:14px;
		}
		.cfs-kpi-toggle + .cfs-refresh { margin-left:8px; }
		.cfs-kpi-toggle:hover { background:#e2edfb; }
		.cfs-kpi-toggle .cfs-kpi-dot {
			width:9px; height:9px; border-radius:50%; background:#b7c7db; flex:0 0 auto;
			transition:background .15s;
		}
		.cfs-kpi-toggle.active { background:#0d6efd; border-color:#0d6efd; color:#fff; }
		.cfs-kpi-toggle.active .cfs-kpi-dot { background:#fff; }

		.cfs-table tbody tr:hover td { background:#fbfdfb; }
		.cfs-table tbody tr:hover td.cfs-consol-col { background:#e3f1e5; }
		.cfs-table tbody tr:hover td.cfs-sticky { background:#fbfdfb; }

		.cfs-foot { font-size:11.5px; color:#8a94a6; padding:10px 4px 0; }
		.cfs-loading, .cfs-empty { padding:40px; text-align:center; color:#78849a; font-size:14px; }
		.cfs-empty { background:#fafbfc; border:1px dashed #dbe2ea; border-radius:12px; }
	`;
	document.head.appendChild(style);
}
