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
		all_ftm: false, // FTM view: show every month (April -> selected) instead of one
		show_kpi: true, // KPI rows (Gross Margin, EBITDA / Litigation) shown by default
		hidden: new Set(), // companies the user crossed out of the matrix
		all_companies: [], // full domestic company list (for the Company filter)
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
						<option value="FTM">FTM</option>
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
				<div class="cfs-field" id="cfs-company-field" style="display:none;">
					<label>Company</label>
					<div class="cfs-company-wrap">
						<button class="form-control input-sm cfs-company-btn" id="cfs-company-btn" type="button">All companies</button>
						<div class="cfs-company-menu" id="cfs-company-menu" style="display:none;"></div>
					</div>
				</div>
				<div class="cfs-field" id="cfs-allftm-field" style="display:none;">
					<label>All FTM</label>
					<button class="cfs-switch" id="cfs-allftm-toggle" type="button" role="switch" aria-checked="false" title="Show FTM for every month from April to the selected month">
						<span class="cfs-switch-knob"></span>
					</button>
				</div>
				<div class="cfs-field cfs-kpi-field">
					<label>KPIs</label>
					<button class="cfs-switch active" id="cfs-kpi-toggle" type="button" role="switch" aria-checked="true" title="Show / hide KPI rows (Gross Margin, EBITDA / Litigation)">
						<span class="cfs-switch-knob"></span>
					</button>
				</div>
				<button class="btn btn-sm btn-default cfs-refresh" id="cfs-refresh">Refresh</button>
			</div>
			<div class="cfs-table-wrap" id="cfs-table">
				<div class="cfs-loading">Loading…</div>
			</div>
		</div>
	`);

	inject_styles();
	apply_kpi_visibility(page, state); // reflect the default KPI toggle state
	page.cfs = { state };

	// Top-of-page action: enter Strategic Expense amounts (per company) in a dialog.
	page.set_primary_action(
		__('Strategic Expense'),
		() => open_strategic_dialog(page, state),
		'add'
	);

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
	$body.find('#cfs-allftm-toggle').on('click', function () {
		state.all_ftm = !state.all_ftm;
		$(this).toggleClass('active', state.all_ftm).attr('aria-checked', state.all_ftm ? 'true' : 'false');
		load_statement(page, state);
	});

	// Cross out a company column — recompute the matrix without it.
	$body.on('click', '.cfs-col-x', function (e) {
		e.stopPropagation();
		const c = $(this).attr('data-company');
		if (c) {
			state.hidden.add(c);
			render_company_filter(page, state);
			load_statement(page, state);
		}
	});

	// --- Company filter (multi-select) — same source of truth as ×/+ --------
	$body.on('click', '#cfs-company-btn', function (e) {
		e.stopPropagation();
		const $m = $body.find('#cfs-company-menu');
		const open = $m.is(':visible');
		$body.find('.cfs-add-menu, #cfs-company-menu').hide();
		if (!open) $m.show();
	});
	$body.on('click', '#cfs-company-menu', (e) => e.stopPropagation());
	$body.on('change', '.cfs-company-check', function () {
		const c = $(this).attr('data-company');
		if (!this.checked) {
			// Keep at least one company visible.
			if (state.all_companies.length - (state.hidden.size + 1) < 1) {
				this.checked = true;
				return;
			}
			state.hidden.add(c);
		} else {
			state.hidden.delete(c);
		}
		render_company_filter(page, state);
		load_statement(page, state);
	});
	$body.on('click', '#cfs-company-all', function (e) {
		e.stopPropagation();
		state.hidden.clear();
		render_company_filter(page, state);
		load_statement(page, state);
	});
	// Open the "+" menu of crossed-out companies.
	$body.on('click', '.cfs-col-add', function (e) {
		e.stopPropagation();
		const $menu = $(this).siblings('.cfs-add-menu');
		const open = $menu.is(':visible');
		$body.find('.cfs-add-menu').hide();
		if (!open) $menu.show();
	});
	// Restore one (or all) crossed-out companies.
	$body.on('click', '.cfs-add-item', function (e) {
		e.stopPropagation();
		const c = $(this).attr('data-company');
		if (c === '__all__') state.hidden.clear();
		else if (c) state.hidden.delete(c);
		render_company_filter(page, state);
		load_statement(page, state);
	});
	// Any other click closes open "+"/Company menus.
	$body.on('click', () => $body.find('.cfs-add-menu, #cfs-company-menu').hide());

	// Expand / collapse the Revenue from operations breakdown (note bifurcation).
	$body.on('click', '.cfs-bif-toggle', function (e) {
		e.stopPropagation();
		toggle_revenue_bifurcation(page, state, $(this));
	});

	// Keep the gutter "+" aligned to its row when the layout reflows — on window
	// resize, on browser/page zoom (visualViewport), and on any block reflow
	// (ResizeObserver catches zoom-driven wraps that don't fire a resize event).
	let _rev_rz;
	const reposition = () => {
		clearTimeout(_rev_rz);
		_rev_rz = setTimeout(() => position_rev_button(page), 60);
	};
	$(window).on('resize.cfs', reposition);
	if (window.visualViewport) {
		window.visualViewport.addEventListener('resize', reposition);
		window.visualViewport.addEventListener('scroll', reposition);
	}
	if (typeof ResizeObserver !== 'undefined') {
		page.cfs._revObs = new ResizeObserver(reposition);
	}

	load_context(page, state);
};

// --- Render the Company multi-select filter (checkbox dropdown) -----------
function render_company_filter(page, state) {
	const $body = $(page.body);
	const all = state.all_companies || [];
	const $field = $body.find('#cfs-company-field');
	if (!all.length) {
		$field.hide();
		return;
	}
	$field.show();

	const visible = all.filter((c) => !state.hidden.has(c));
	$body.find('#cfs-company-btn').text(
		state.hidden.size === 0 ? 'All companies' : `${visible.length}/${all.length} companies`
	);

	const items = all
		.map((c) => {
			const e = frappe.utils.escape_html(c);
			const checked = state.hidden.has(c) ? '' : 'checked';
			return `<label class="cfs-company-item"><input type="checkbox" class="cfs-company-check" data-company="${e}" ${checked}/> <span>${e}</span></label>`;
		})
		.join('');
	$body.find('#cfs-company-menu').html(
		`<div class="cfs-company-actions"><button type="button" class="btn btn-xs btn-default" id="cfs-company-all">Select all</button></div>${items}`
	);
}

// --- Toggle the Gross Margin (derived KPI) rows on/off --------------------
function apply_kpi_visibility(page, state) {
	const $body = $(page.body);
	$body.find('#cfs-table').toggleClass('cfs-kpi-on', !!state.show_kpi);
	const $btn = $body.find('#cfs-kpi-toggle');
	$btn.toggleClass('active', !!state.show_kpi);
	$btn.attr('aria-checked', state.show_kpi ? 'true' : 'false');
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

			// Company filter list (stable across report type / year changes).
			state.all_companies = ctx.companies || [];
			state.fiscal_years = ctx.fiscal_years || []; // for the Strategic Expense dialog
			// Drop any stale hidden names no longer in the master list.
			state.hidden.forEach((c) => {
				if (!state.all_companies.includes(c)) state.hidden.delete(c);
			});
			render_company_filter(page, state);

			// Server resolves the fiscal year so months always match it.
			const years = ctx.fiscal_years || [];
			const fy = ctx.resolved_fiscal_year || null;
			state.fiscal_year = fy;
			set_select(
				$body.find('#cfs-fiscal-year'),
				years.map((y) => ({ value: y, label: 'FY ' + y })),
				fy
			);

			// Month filter: relevant for the Monthly-driven views (Monthly, FTM).
			const is_monthly = state.report_type === 'Monthly' || state.report_type === 'FTM';
			$body.find('#cfs-month-field').toggle(is_monthly);

			// "All FTM" toggle only applies to the FTM view; reset it otherwise.
			const is_ftm = state.report_type === 'FTM';
			$body.find('#cfs-allftm-field').toggle(is_ftm);
			if (!is_ftm) state.all_ftm = false;
			$body
				.find('#cfs-allftm-toggle')
				.toggleClass('active', state.all_ftm)
				.attr('aria-checked', state.all_ftm ? 'true' : 'false');
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
	if ((state.report_type === 'Monthly' || state.report_type === 'FTM') && !state.month) return;
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
					all_ftm: state.all_ftm ? 1 : 0,
					exclude_companies: JSON.stringify(Array.from(state.hidden)),
				},
			})
			.then((r) => r.message || {});

	// P&L first, Balance Sheet below.
	Promise.all([fetch('Profit & Loss'), fetch('Balance Sheet')])
		.then(([pl, bs]) => {
			if (seq !== page.cfs.load_seq) return; // a newer load superseded this one
			const hidden = Array.from(state.hidden);
			page.cfs.pl_data = pl; // kept for aligning the Revenue breakdown to these columns
			const html =
				build_statement_block('Profit & Loss', pl, hidden) +
				build_statement_block('Balance Sheet', bs, hidden);
			$('#cfs-table').html(html);
			position_rev_button(page); // align the gutter "+" to the Revenue row
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
function build_statement_block(title, data, hidden) {
	const heading = `<div class="cfs-block-title">${frappe.utils.escape_html(title)}</div>`;
	// Single-column FTM is centred; All-FTM has many month columns, so keep them
	// right-aligned like the Monthly view.
	const is_ftm = data.report_type === 'FTM' && !data.all_ftm;
	const companies = data.companies || [];
	const rows = data.rows || [];
	hidden = hidden || [];
	const show_plus = hidden.length > 0; // "+" column appears once something is crossed out
	// Revenue from operations gets a "+" in the block's left gutter (outside the
	// table) to expand its note breakdown; positioned vertically by JS after render.
	const has_rev =
		title === 'Profit & Loss' && rows.some((r) => /^revenue from operation/i.test(r.particular || ''));
	const rev_btn = has_rev
		? '<button type="button" class="cfs-bif-toggle" aria-expanded="false" title="Show revenue breakdown" style="display:none;">+</button>'
		: '';
	if (!companies.length || !rows.length) {
		return `<div class="cfs-block">${heading}<div class="cfs-empty">No data available for the selected filters.</div></div>`;
	}

	// Measures (sub-columns) come from the server: 2 for Yearly, 3 for Monthly.
	const cols = data.columns && data.columns.length ? data.columns : [{ key: 'cy', label: '' }];
	const ncol = cols.length;
	const can_hide = companies.length > 1; // never let the user cross out the last company

	// Grouped two-row header: each company (and Consolidate) spans its measures.
	const group_head = (label, extra) =>
		`<th colspan="${ncol}" class="cfs-num cfs-group ${extra || ''}" title="${label}">${label}</th>`;
	// Company header: name + a "×" to cross the column out.
	const comp_head = (c) => {
		const e = frappe.utils.escape_html(c);
		const x = can_hide
			? `<button type="button" class="cfs-col-x" data-company="${e}" title="Hide ${e}">×</button>`
			: '';
		return `<th colspan="${ncol}" class="cfs-num cfs-group cfs-comp-head" title="${e}"><span class="cfs-comp-label">${e}</span>${x}</th>`;
	};
	// "+" header: a menu to restore crossed-out companies.
	const plus_head = show_plus
		? `<th rowspan="2" class="cfs-plus-head"><div class="cfs-add-wrap">
				<button type="button" class="cfs-col-add" title="Add hidden company">+</button>
				<div class="cfs-add-menu" style="display:none;">
					<div class="cfs-add-menu-title">Show company</div>
					${hidden
						.map((c) => {
							const e = frappe.utils.escape_html(c);
							return `<div class="cfs-add-item" data-company="${e}">${e}</div>`;
						})
						.join('')}
					${hidden.length > 1 ? `<div class="cfs-add-item cfs-add-all" data-company="__all__">Show all</div>` : ''}
				</div>
			</div></th>`
		: '';
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
			${companies.map((c) => comp_head(c)).join('')}
			${plus_head}
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

			// Revenue from operations (P&L only) gets a "+" to expand its note breakdown.
			const is_rev =
				title === 'Profit & Loss' && /^revenue from operation/i.test(row.particular || '');
			if (is_rev) cls.push('cfs-rev-row');

			const consol = num_cells(row.consolidate, 'cfs-consol-col', blank, fmt);
			const cells = companies.map((c, i) => num_cells(row.values[i], '', blank, fmt)).join('');
			const plus = show_plus ? '<td class="cfs-plus-col"></td>' : '';

			// The Revenue "+" lives in the block's left gutter (outside the table),
			// not in this cell — see the button appended to .cfs-block below.
			return `
				<tr class="${cls.join(' ')}">
					<td class="cfs-particular cfs-sticky" style="${indent}">${frappe.utils.escape_html(row.particular)}</td>
					${consol}
					${cells}
					${plus}
				</tr>`;
		})
		.join('');

	const missing = data.missing_companies || [];
	const miss_note = missing.length
		? ` • <span title="${frappe.utils.escape_html(missing.join(', '))}">${missing.length} company(ies) without a report excluded</span>`
		: '';
	const col_labels = cols.map((c) => frappe.utils.escape_html(c.label)).join(', ');

	return `
		<div class="cfs-block${has_rev ? ' cfs-has-gutter' : ''}">
			${heading}
			${rev_btn}
			<div class="cfs-scroll">
				<table class="cfs-table${is_ftm ? ' cfs-ftm' : ''}">
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

// --- Vertically align the gutter "+" with the Revenue from operations row --
function position_rev_button(page) {
	const $body = $(page.body);
	const $block = $body.find('.cfs-block.cfs-has-gutter').first();
	if (!$block.length) return;
	const $btn = $block.find('.cfs-bif-toggle').first();
	const $row = $block.find('.cfs-rev-row').first();
	if (!$btn.length || !$row.length) {
		$btn.hide();
		return;
	}
	const br = $row[0].getBoundingClientRect();
	const kr = $block[0].getBoundingClientRect();
	const top = br.top - kr.top + (br.height - $btn.outerHeight()) / 2;
	$btn.css('top', Math.max(0, Math.round(top)) + 'px').show();

	// Watch this block so any reflow (incl. zoom) re-runs the alignment.
	if (page.cfs && page.cfs._revObs) {
		page.cfs._revObs.disconnect();
		page.cfs._revObs.observe($block[0]);
	}
}

// --- Revenue from operations: expand / collapse the note breakdown -------
function toggle_revenue_bifurcation(page, state, $btn) {
	// The button lives in the block gutter (outside the table), so reach the
	// Revenue row through the block rather than a DOM ancestor.
	const $row = $btn.closest('.cfs-block').find('.cfs-rev-row').first();
	if (!$row.length) return;
	const expanded = $row.attr('data-bif') === '1';

	// Remove any breakdown rows already sitting directly beneath this row.
	$row.nextUntil(':not(.cfs-bif-row)').remove();
	if (expanded) {
		$row.removeAttr('data-bif');
		$btn.attr('aria-expanded', 'false').text('+').attr('title', 'Show revenue breakdown');
		return;
	}

	$btn.prop('disabled', true).text('…');
	const pl = page.cfs.pl_data || {};
	frappe
		.call({
			method:
				'financial_report_tool.financial_report_tool.page.domestic_financials.domestic_financials.get_revenue_bifurcation',
			args: {
				fiscal_year: state.fiscal_year,
				report_type: state.report_type,
				month: state.month,
				all_ftm: state.all_ftm ? 1 : 0,
				exclude_companies: JSON.stringify(Array.from(state.hidden)),
			},
		})
		.then((r) => {
			$btn.prop('disabled', false);
			const bif = r.message || {};
			// Align the breakdown to the P&L face's columns and company order.
			const cols = pl.columns && pl.columns.length ? pl.columns : bif.columns || [{ key: 'cy', label: '' }];
			const face_companies = pl.companies || bif.companies || [];
			const show_plus = state.hidden.size > 0;
			const ncell = 1 + (1 + face_companies.length) * cols.length + (show_plus ? 1 : 0);
			const html = build_bif_rows_html(bif, face_companies, cols, show_plus);
			$row.after(
				html ||
					`<tr class="cfs-bif-row cfs-bif-empty"><td class="cfs-particular cfs-sticky">Revenue breakdown</td><td class="cfs-bif-note" colspan="${ncell - 1}">No breakdown available for the selected filters.</td></tr>`
			);
			$row.attr('data-bif', '1');
			$btn.attr('aria-expanded', 'true').text('−').attr('title', 'Hide revenue breakdown');
		})
		.catch(() => {
			$btn.prop('disabled', false).attr('aria-expanded', 'false').text('+');
		});
}

// Build the breakdown <tr>s, one per note line item, aligned to the face columns.
function build_bif_rows_html(bif, face_companies, cols, show_plus) {
	const rows = (bif && bif.rows) || [];
	if (!rows.length) return '';
	const bif_companies = bif.companies || [];
	const idx_of = {};
	bif_companies.forEach((c, i) => (idx_of[c] = i));

	const num_cells = (obj, extra, blank) =>
		cols
			.map((c, ci) => {
				const cls = (ci === 0 ? 'cfs-group-start' : 'cfs-py') + (extra ? ' ' + extra : '');
				const val = obj ? obj[c.key] : null;
				return `<td class="cfs-num ${cls}">${blank ? '' : fmt_num(val)}</td>`;
			})
			.join('');

	return rows
		.map((row) => {
			const blank = !row.consolidate;
			const pad = 12 + (Number(row.indent || 0) + 1) * 18; // sit under the Revenue row
			const cls = ['cfs-bif-row'];
			if (blank && row.is_header) cls.push('cfs-bif-head');
			else if (row.is_bold) cls.push('cfs-bif-total');

			const consol = num_cells(row.consolidate, 'cfs-consol-col', blank);
			const cells = face_companies
				.map((c) => {
					const i = idx_of[c];
					// A company shown on the face but absent from the note renders blank.
					if (i === undefined) return num_cells(null, '', true);
					return num_cells(row.values[i] || null, '', blank);
				})
				.join('');
			const plus = show_plus ? '<td class="cfs-plus-col"></td>' : '';

			return `
				<tr class="${cls.join(' ')}">
					<td class="cfs-particular cfs-sticky" style="padding-left:${pad}px;">${frappe.utils.escape_html(row.particular)}</td>
					${consol}
					${cells}
					${plus}
				</tr>`;
		})
		.join('');
}

// --- Strategic Expense entry dialog --------------------------------------
// Fiscal-order months (April -> March), matching the Strategic Expense DocType.
const CFS_FISCAL_MONTHS = [
	'April', 'May', 'June', 'July', 'August', 'September',
	'October', 'November', 'December', 'January', 'February', 'March',
];

function open_strategic_dialog(page, state) {
	const companies = state.all_companies || [];
	if (!companies.length) {
		frappe.msgprint(__('No domestic companies found.'));
		return;
	}
	const fys =
		state.fiscal_years && state.fiscal_years.length
			? state.fiscal_years
			: state.fiscal_year
				? [state.fiscal_year]
				: [];
	// Yearly view has no month concept — default the entry month to March (year-end).
	const default_month = state.report_type === 'Yearly' ? 'March' : state.month || 'April';

	const d = new frappe.ui.Dialog({
		title: __('Enter Strategic Expense'),
		size: 'large',
		fields: [
			{
				fieldtype: 'Select',
				fieldname: 'fiscal_year',
				label: __('Fiscal Year'),
				options: fys.join('\n'),
				default: state.fiscal_year || fys[0] || '',
				reqd: 1,
			},
			{ fieldtype: 'Column Break' },
			{
				fieldtype: 'Select',
				fieldname: 'month',
				label: __('Month'),
				options: CFS_FISCAL_MONTHS.join('\n'),
				default: default_month,
				reqd: 1,
			},
			{ fieldtype: 'Section Break' },
			{ fieldtype: 'HTML', fieldname: 'grid' },
		],
		primary_action_label: __('Save'),
		primary_action: () => save_strategic_dialog(page, state, d),
	});
	d.show();

	const reload = () => load_strategic_grid(d);
	d.fields_dict.fiscal_year.$input.on('change', reload);
	d.fields_dict.month.$input.on('change', reload);
	reload();
}

// Fetch existing amounts for the chosen FY+month and render the editable grid.
function load_strategic_grid(d) {
	const fy = d.get_value('fiscal_year');
	const month = d.get_value('month');
	const $wrap = $(d.fields_dict.grid.wrapper);
	$wrap.html('<div class="cfs-se-loading">Loading…</div>');
	frappe
		.call({
			method:
				'financial_report_tool.financial_report_tool.page.domestic_financials.domestic_financials.get_strategic_entries',
			args: { fiscal_year: fy, month: month },
		})
		.then((r) => {
			const data = r.message || {};
			const companies = data.companies || [];
			const amounts = data.amounts || {};
			const rows = companies
				.map((c) => {
					const e = frappe.utils.escape_html(c);
					const val = amounts[c] ? amounts[c] : '';
					return `<tr>
						<td class="cfs-se-comp" title="${e}">${e}</td>
						<td class="cfs-se-amt"><input type="number" step="any" class="cfs-se-input" data-company="${e}" value="${val}" placeholder="0"></td>
					</tr>`;
				})
				.join('');
			$wrap.html(`
				<div class="cfs-se-hint">Monthly amount per company, in ₹ Lacs. Blank or 0 removes the entry. The Consolidated total updates live.</div>
				<div class="cfs-se-table-wrap">
					<table class="cfs-se-table">
						<thead><tr><th>Company</th><th class="cfs-se-amt">Amount (₹ Lacs)</th></tr></thead>
						<tbody>${rows}</tbody>
						<tfoot><tr><td class="cfs-se-total-label">Consolidated Total</td><td class="cfs-se-amt cfs-se-total">-</td></tr></tfoot>
					</table>
				</div>`);
			const recompute = () => {
				let t = 0;
				$wrap.find('.cfs-se-input').each(function () {
					t += Number(this.value) || 0;
				});
				$wrap
					.find('.cfs-se-total')
					.text(t ? t.toLocaleString('en-US', { maximumFractionDigits: 2 }) : '-');
			};
			$wrap.find('.cfs-se-input').on('input', recompute);
			recompute();
		})
		.catch(() => $wrap.html('<div class="cfs-se-loading">Failed to load. Try again.</div>'));
}

function save_strategic_dialog(page, state, d) {
	const fy = d.get_value('fiscal_year');
	const month = d.get_value('month');
	if (!fy || !month) {
		frappe.msgprint(__('Please select Fiscal Year and Month.'));
		return;
	}
	const amounts = {};
	$(d.fields_dict.grid.wrapper)
		.find('.cfs-se-input')
		.each(function () {
			amounts[$(this).attr('data-company')] = Number(this.value) || 0;
		});
	const $btn = d.get_primary_btn().prop('disabled', true);
	frappe
		.call({
			method:
				'financial_report_tool.financial_report_tool.page.domestic_financials.domestic_financials.save_strategic_entries',
			args: { fiscal_year: fy, month: month, amounts: JSON.stringify(amounts) },
		})
		.then((r) => {
			const m = r.message || {};
			frappe.show_alert(
				{ message: __('Strategic Expense saved ({0} updated, {1} removed)', [m.saved || 0, m.deleted || 0]), indicator: 'green' },
				4
			);
			d.hide();
			load_statement(page, state); // refresh so the Strategic Expense row updates
		})
		.catch(() => $btn.prop('disabled', false));
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
		/* Left gutter (padding-left) reserves room for the Revenue "+" button,
		   kept on every block so both tables stay left-aligned. */
		.cfs-block { margin-bottom:28px; position:relative; padding-left:30px; }
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

		/* Company multi-select filter */
		.cfs-company-wrap { position:relative; }
		.cfs-company-btn {
			min-width:150px; width:auto; height:26px; padding:1px 22px 1px 8px; font-size:12px;
			text-align:left; background:#fff; cursor:pointer; position:relative;
		}
		.cfs-company-btn::after {
			content:'▾'; position:absolute; right:8px; top:50%; transform:translateY(-50%); color:#8a94a6;
		}
		.cfs-company-menu {
			position:absolute; top:30px; left:0; z-index:30; background:#fff;
			border:1px solid #d5dee7; border-radius:8px; box-shadow:0 6px 18px rgba(0,0,0,.14);
			min-width:240px; max-height:320px; overflow-y:auto; padding:4px;
		}
		.cfs-company-actions { padding:4px 6px 6px; border-bottom:1px solid #eef2f4; margin-bottom:4px; }
		.cfs-company-item {
			display:flex; align-items:center; gap:8px; padding:5px 8px; margin:0;
			font-size:12px; font-weight:400; color:#14351b; cursor:pointer; border-radius:6px; white-space:nowrap;
		}
		.cfs-company-item:hover { background:#eef7ef; }
		.cfs-company-item input { margin:0; cursor:pointer; }

		.cfs-scroll { overflow-x:auto; border:1px solid #e6ebf1; border-radius:12px; background:#fff; margin-left:-30px; }
		table.cfs-table { border-collapse:separate; border-spacing:0; width:100%; font-size:12.5px; }
		.cfs-table th, .cfs-table td {
			padding:3px 12px; border-bottom:1px solid #eef2f4;
		}
		.cfs-table thead th {
			background:#f4f8f5; color:#14351b; font-weight:600;
			border-bottom:2px solid #cdebd6; vertical-align:bottom;
		}
		/* Numeric cells never wrap; they hold the figures. */
		.cfs-num { text-align:right; font-variant-numeric:tabular-nums; min-width:104px; white-space:nowrap; }

		/* FTM view: single movement column per company — centre the figures. */
		.cfs-table.cfs-ftm th.cfs-num, .cfs-table.cfs-ftm td.cfs-num { text-align:center; }

		/* Grouped (company / consolidate) header spanning CY | PY */
		.cfs-group { text-align:center; border-bottom:1px solid #cdebd6; }
		.cfs-table th.cfs-comp-head {
			white-space:normal; overflow-wrap:break-word; line-height:1.25; vertical-align:middle;
		}

		/* Cross-out (hide) button on each company header */
		.cfs-col-x {
			border:none; background:transparent; color:#c0392b; font-size:14px; line-height:1;
			cursor:pointer; margin-left:5px; padding:0 4px; border-radius:50%; vertical-align:middle;
		}
		.cfs-col-x:hover { background:#f8d7da; color:#a11; }

		/* "+" header column and its restore menu */
		.cfs-table th.cfs-plus-head {
			vertical-align:middle; text-align:center; min-width:40px; width:40px;
			border-left:1px solid #d5dee7; position:relative;
		}
		.cfs-add-wrap { position:relative; display:inline-block; }
		.cfs-col-add {
			border:1px solid #cfe0f5; background:#eef4fc; color:#0d6efd; font-weight:700;
			font-size:15px; line-height:1; cursor:pointer; width:24px; height:24px; border-radius:50%;
		}
		.cfs-col-add:hover { background:#0d6efd; color:#fff; }
		.cfs-add-menu {
			position:absolute; top:28px; right:0; z-index:20; background:#fff;
			border:1px solid #d5dee7; border-radius:8px; box-shadow:0 6px 18px rgba(0,0,0,.14);
			min-width:210px; padding:4px; text-align:left;
		}
		.cfs-add-menu-title {
			font-size:10px; text-transform:uppercase; letter-spacing:.02em; color:#8a94a6; padding:5px 8px 3px;
		}
		.cfs-add-item {
			padding:6px 10px; font-size:12px; font-weight:400; color:#14351b;
			cursor:pointer; border-radius:6px; white-space:nowrap;
		}
		.cfs-add-item:hover { background:#eef7ef; }
		.cfs-add-all { border-top:1px solid #eef2f4; margin-top:2px; color:#0d6efd; font-weight:600; }
		.cfs-plus-col { background:#fafbfc; border-left:1px solid #eef2f4; min-width:40px; width:40px; }
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

		/* Gross Margin toggle switch (fixed label + iOS-style switch) */
		.cfs-switch {
			position:relative; width:38px; height:20px; border-radius:20px; border:none;
			background:#c7ced8; cursor:pointer; padding:0; flex:0 0 auto; transition:background .15s;
		}
		.cfs-switch:hover { background:#b9c1cc; }
		.cfs-switch.active, .cfs-switch.active:hover { background:#0d6efd; }
		.cfs-switch-knob {
			position:absolute; top:2px; left:2px; width:16px; height:16px; border-radius:50%;
			background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.3); transition:left .15s;
		}
		.cfs-switch.active .cfs-switch-knob { left:20px; }

		.cfs-table tbody tr:hover td { background:#fbfdfb; }
		.cfs-table tbody tr:hover td.cfs-consol-col { background:#e3f1e5; }
		.cfs-table tbody tr:hover td.cfs-sticky { background:#fbfdfb; }

		/* Revenue from operations breakdown ("+" toggle + note rows) */
		/* The "+" sits in the block's left gutter, outside the table border. */
		.cfs-bif-toggle {
			position:absolute; left:2px; margin-left:-30px; z-index:3;
			border:1px solid #cfe0f5; background:#eef4fc; color:#0d6efd; font-weight:700;
			font-size:13px; line-height:1; cursor:pointer; width:22px; height:22px; border-radius:5px;
			padding:0; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,.08);
		}
		.cfs-bif-toggle:hover { background:#0d6efd; color:#fff; }
		.cfs-bif-toggle[disabled] { opacity:.5; cursor:default; }
		.cfs-rev-row > td.cfs-particular { font-weight:600; }
		.cfs-bif-row td { background:#f7fbff; font-size:12px; color:#334; }
		.cfs-bif-row td.cfs-particular { color:#334; font-style:italic; }
		.cfs-bif-row td.cfs-sticky { background:#f7fbff; }
		.cfs-bif-row td.cfs-consol-col { background:#eaf3fb; }
		.cfs-bif-head td, .cfs-bif-head td.cfs-particular { font-weight:600; font-style:normal; color:#123a63; }
		.cfs-bif-total td { font-weight:700; border-top:1px solid #d3e4f4; border-bottom:1px solid #d3e4f4; }
		.cfs-bif-note { text-align:left; color:#8a94a6; font-style:italic; }

		/* Strategic Expense entry dialog grid */
		.cfs-se-hint { font-size:12px; color:#6b7684; margin:0 0 10px; }
		.cfs-se-loading { padding:24px; text-align:center; color:#78849a; }
		.cfs-se-table-wrap { max-height:46vh; overflow-y:auto; border:1px solid #e6ebf1; border-radius:8px; }
		table.cfs-se-table { width:100%; border-collapse:separate; border-spacing:0; font-size:13px; }
		.cfs-se-table th, .cfs-se-table td { padding:7px 12px; border-bottom:1px solid #eef2f4; }
		.cfs-se-table thead th {
			position:sticky; top:0; z-index:1; background:#f4f8f5; color:#14351b;
			font-weight:600; border-bottom:2px solid #cdebd6; text-align:left;
		}
		.cfs-se-table th.cfs-se-amt, .cfs-se-table td.cfs-se-amt { text-align:right; width:180px; }
		.cfs-se-comp { color:#22303c; }
		.cfs-se-input {
			width:150px; text-align:right; font-variant-numeric:tabular-nums;
			padding:4px 8px; border:1px solid #d5dee7; border-radius:6px; background:#fff;
		}
		.cfs-se-input:focus { border-color:#0d6efd; outline:none; box-shadow:0 0 0 2px rgba(13,110,253,.12); }
		.cfs-se-table tbody tr:hover td { background:#fbfdfb; }
		.cfs-se-table tfoot td {
			position:sticky; bottom:0; background:#eef7ef; font-weight:700; color:#1B5E20;
			border-top:2px solid #cdebd6; border-bottom:none;
		}
		.cfs-se-total-label { text-align:left; }

		.cfs-foot { font-size:11.5px; color:#8a94a6; padding:10px 4px 0; }
		.cfs-loading, .cfs-empty { padding:40px; text-align:center; color:#78849a; font-size:14px; }
		.cfs-empty { background:#fafbfc; border:1px dashed #dbe2ea; border-radius:12px; }
	`;
	document.head.appendChild(style);
}
