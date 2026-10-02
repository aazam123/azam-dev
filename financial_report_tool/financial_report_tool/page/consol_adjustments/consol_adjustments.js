// Consolidation Adjustments — elimination & regrouping entries for the group
// consolidated trial balance. Entry form docked left, register on the right;
// four derived reports as a second view. Companies and Primary/Secondary
// groups come from the existing Company and Standalone Group masters (the
// same ones GL Group Mapping and the Consolidated Financial Statement page
// use) — there is no separate masters editor on this page.

frappe.pages['consol-adjustments'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Consolidation Adjustments',
		single_column: true,
	});

	let ca_prev_fullwidth;
	$(wrapper).on('show', () => {
		ca_prev_fullwidth = $(document.body).hasClass('full-width');
		$(document.body).addClass('full-width');
	});
	$(wrapper).on('hide', () => {
		$(document.body).toggleClass('full-width', !!ca_prev_fullwidth);
	});

	const state = {
		unit: 'cr', // ₹ | Lakh | Crore
		view: 'input', // input | reports
		editing: null, // id of the row being edited, or null for "new"
		confirmDel: null,
		txns: [],
		masters: { companies: [], groups: [], fiscal_years: [] },
		imp: null, // pending import preview
	};
	try {
		const u = localStorage.getItem('ca.unit');
		if (CA_UNITS[u]) state.unit = u;
	} catch (e) {}

	page.body.html(`
		<div class="ca-wrap">
			<div class="ca-filters" id="ca-filters">
				<div class="ca-field">
					<label>Show in</label>
					<div class="ca-seg" id="ca-unit-seg" role="group" aria-label="Amount unit">
						<button type="button" data-unit="rs">₹</button>
						<button type="button" data-unit="lk">Lakh</button>
						<button type="button" data-unit="cr">Crore</button>
					</div>
				</div>
				<div class="ca-spacer"></div>
				<nav class="ca-tabs" role="tablist">
					<button role="tab" data-view="input" id="ca-tab-input">Transaction input</button>
					<button role="tab" data-view="reports" id="ca-tab-reports">Reports</button>
				</nav>
			</div>
			<div class="ca-kpis" id="ca-kpis"></div>
			<div id="ca-view-input">
				<div class="ca-grid">
					<div class="ca-panel">
						<div class="ca-hd"><h2 id="ca-form-title">New transaction</h2><span class="ca-txid" id="ca-txid"></span></div>
						<div class="ca-bd">
							<form id="ca-form" autocomplete="off" novalidate>
								<div class="ca-sec">Transaction details</div>
								<div class="ca-row2">
									<div class="ca-fld"><label for="ca-f-from">From company <span class="ca-req">*</span></label><select id="ca-f-from"></select></div>
									<div class="ca-fld"><label for="ca-f-to">To company <span class="ca-muted">(optional)</span></label><select id="ca-f-to"></select></div>
								</div>
								<div class="ca-row2" style="margin-top:10px"><div class="ca-fld"><label for="ca-f-fy">Fiscal year <span class="ca-req">*</span></label><select id="ca-f-fy"></select></div><div class="ca-fld"><label for="ca-f-month">Month <span class="ca-req">*</span></label><select id="ca-f-month"></select></div></div>
								<div class="ca-sec">Accounting classification</div>
								<div class="ca-fld"><label for="ca-f-pg">Primary group <span class="ca-req">*</span></label><select id="ca-f-pg"></select></div>
								<div class="ca-fld" style="margin-top:10px"><label for="ca-f-sg">Secondary group <span class="ca-req">*</span></label><select id="ca-f-sg"></select></div>
								<div class="ca-sec">Amount (₹, full value)</div>
								<div class="ca-row2">
									<div class="ca-fld"><label for="ca-f-dr">Debit <span class="ca-req">*</span> <span class="ca-muted">(or Credit)</span></label><input id="ca-f-dr" class="ca-num" inputmode="decimal" placeholder="0"></div>
									<div class="ca-fld"><label for="ca-f-cr">Credit <span class="ca-req">*</span> <span class="ca-muted">(or Debit)</span></label><input id="ca-f-cr" class="ca-num" inputmode="decimal" placeholder="0"></div>
								</div>
								<div class="ca-netline"><span>Net impact (Dr − Cr)</span><b id="ca-net-out">–</b></div>
								<div class="ca-sec">Adjustment</div>
								<div class="ca-fld"><label for="ca-f-type">Adjustment type <span class="ca-req">*</span></label>
									<select id="ca-f-type"><option>Elimination</option><option>Regrouping</option></select></div>
								<div class="ca-fld" style="margin-top:10px"><label for="ca-f-narr">Description / narration</label><textarea id="ca-f-narr" placeholder="e.g. MLSPL sales to Meril India eliminated"></textarea></div>
								<div class="ca-fld" style="margin-top:10px"><label for="ca-f-ref">Reference <span class="ca-muted">(optional)</span></label><input id="ca-f-ref" placeholder="e.g. IC confirmation Mar-26, JV 1042"></div>
								<div id="ca-form-err" class="ca-errs" hidden></div>
								<div class="ca-btns">
									<button type="submit" class="ca-btn pri" id="ca-save-btn">Add transaction</button>
									<button type="button" class="ca-btn" id="ca-reset-btn">Clear</button>
								</div>
							</form>
						</div>
					</div>
					<div class="ca-panel">
						<div class="ca-hd">
							<h2>Transaction register</h2>
							<div class="ca-btns" style="margin:0">
								<button type="button" class="ca-btn sm" id="ca-import-btn">Import Excel/CSV</button>
								<button type="button" class="ca-btn sm" id="ca-tmpl-btn">Import template</button>
								<button type="button" class="ca-btn sm" id="ca-export-btn">Export to Excel</button>
							</div>
						</div>
						<div class="ca-filters2">
							<input id="ca-q-search" placeholder="Search narration, ref, ID">
							<select id="ca-q-type"><option value="">All types</option><option>Elimination</option><option>Regrouping</option></select>
							<select id="ca-q-from"></select>
							<select id="ca-q-pg"></select>
							<select id="ca-q-fy"></select>
							<select id="ca-q-month"></select>
						</div>
						<div class="ca-tblwrap" style="max-height:70vh;overflow:auto">
							<table id="ca-reg">
								<thead><tr><th>ID</th><th>From → To</th><th>FY</th><th>Month</th><th>Primary group</th><th>Secondary group</th><th>Type</th><th class="n" id="ca-th-dr">Debit</th><th class="n" id="ca-th-cr">Credit</th><th></th></tr></thead>
								<tbody id="ca-reg-body"></tbody>
								<tfoot id="ca-reg-foot"></tfoot>
							</table>
						</div>
					</div>
				</div>
			</div>
			<div id="ca-view-reports" hidden>
				<div class="ca-panel" style="margin-top:16px">
					<div class="ca-hd">
						<h2 id="ca-rep-title">Report</h2>
						<div class="ca-repctl">
							<select id="ca-r-kind" aria-label="Report">
								<option value="tb">Adjustment TB – Primary / Secondary group</option>
								<option value="matrix">Company-to-company matrix</option>
								<option value="recon">Inter-company reconciliation</option>
								<option value="entity">Entity-wise summary</option>
							</select>
							<select id="ca-r-type" aria-label="Adjustment type"><option value="">Elimination + Regrouping</option><option>Elimination</option><option>Regrouping</option></select>
							<select id="ca-r-pg" aria-label="Primary group"></select>
							<select id="ca-r-fy" aria-label="Fiscal year"></select>
							<select id="ca-r-month" aria-label="Month"></select>
						</div>
					</div>
					<div class="ca-tblwrap" id="ca-rep-out"></div>
				</div>
			</div>
			<p class="ca-foot">Net = Debit − Credit. Companies and groups come from the Company and Standalone Group masters. Data is shared with every user of the site.</p>
		</div>
	`);

	inject_ca_styles();
	page.ca = { state };

	const $body = $(page.body);
	$body.find('#ca-unit-seg button').on('click', function () {
		set_ca_unit(page, $(this).data('unit'));
	});
	$body.find('nav.ca-tabs button').on('click', function () {
		set_ca_view(page, $(this).data('view'));
	});
	$body.find('#ca-f-pg').on('change', () => fill_ca_subs(page, ''));
	['ca-f-dr', 'ca-f-cr'].forEach((id) => {
		$body.find('#' + id).on('input', () => sync_ca_amounts(page));
		$body.find('#' + id).on('blur', function () {
			fmt_ca_input(this);
		});
	});
	$body.find('#ca-f-type').on('change', () => update_ca_txid(page));
	$body.find('#ca-form').on('submit', (ev) => submit_ca_form(ev, page));
	$body.find('#ca-reset-btn').on('click', () => reset_ca_form(page));
	['ca-q-search', 'ca-q-type', 'ca-q-from', 'ca-q-pg', 'ca-q-fy', 'ca-q-month'].forEach((id) => {
		$body.find('#' + id).on(id === 'ca-q-search' ? 'input' : 'change', () => render_ca_register(page));
	});
	['ca-r-kind', 'ca-r-type', 'ca-r-pg', 'ca-r-fy', 'ca-r-month'].forEach((id) => {
		$body.find('#' + id).on('change', () => render_ca_reports(page));
	});
	$body.find('#ca-reg-body').on('click', '[data-act]', (ev) => ca_register_click(ev, page));
	$body.find('#ca-import-btn').on('click', () => open_ca_import_dialog(page));
	$body.find('#ca-tmpl-btn').on('click', () => {
		window.open('/api/method/financial_report_tool.financial_report_tool.page.consol_adjustments.consol_adjustments.export_template');
	});
	$body.find('#ca-export-btn').on('click', () => {
		window.open('/api/method/financial_report_tool.financial_report_tool.page.consol_adjustments.consol_adjustments.export_transactions');
	});

	set_ca_unit(page, state.unit, /* skip_render */ true);
	set_ca_view(page, state.view);
	load_ca_masters(page).then(() => load_ca_transactions(page));
};

// --- Formatting -------------------------------------------------------
const CA_UNITS = { rs: { d: 1, lab: '₹' }, lk: { d: 1e5, lab: '₹ Lakh' }, cr: { d: 1e7, lab: '₹ Cr' } };
const ca_nf2 = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
function ca_fmt(state, v) {
	if (!v || Math.abs(v) < 0.005) return '–';
	return ca_nf2.format(v / CA_UNITS[state.unit].d);
}
function ca_fmt_net(state, v) {
	if (!v || Math.abs(v) < 0.005) return '–';
	return ca_nf2.format(Math.abs(v) / CA_UNITS[state.unit].d) + (v > 0 ? ' Dr' : ' Cr');
}
function ca_parse_amt(s) {
	s = String(s ?? '').replace(/[₹,\s]/g, '');
	if (s === '') return 0;
	const n = Number(s);
	return isFinite(n) ? n : NaN;
}
const ca_net = (t) => (t.debit || 0) - (t.credit || 0);

// --- Shell: unit / tab switching --------------------------------------
function set_ca_unit(page, u, skip_render) {
	const { state } = page.ca;
	state.unit = u;
	try {
		localStorage.setItem('ca.unit', u);
	} catch (e) {}
	$(page.body)
		.find('#ca-unit-seg button')
		.each(function () {
			$(this).attr('aria-pressed', $(this).data('unit') === u ? 'true' : 'false');
		});
	if (!skip_render) render_ca_all(page);
}
function set_ca_view(page, v) {
	const { state } = page.ca;
	state.view = v;
	const $body = $(page.body);
	$body.find('#ca-view-input').prop('hidden', v !== 'input');
	$body.find('#ca-view-reports').prop('hidden', v !== 'reports');
	$body.find('#ca-tab-input').attr('aria-selected', v === 'input' ? 'true' : 'false');
	$body.find('#ca-tab-reports').attr('aria-selected', v === 'reports' ? 'true' : 'false');
	if (v === 'reports') render_ca_reports(page);
}

// --- Masters / selects --------------------------------------------------
function ca_opts(list, sel, blankLabel) {
	return (
		(blankLabel != null ? `<option value="">${frappe.utils.escape_html(blankLabel)}</option>` : '') +
		(list || []).map((v) => `<option${v === sel ? ' selected' : ''}>${frappe.utils.escape_html(v)}</option>`).join('')
	);
}
function ca_grp(page, name) {
	return (page.ca.state.masters.groups || []).find((g) => g.name === name);
}
function load_ca_masters(page) {
	return frappe
		.call({
			method: 'financial_report_tool.financial_report_tool.page.consol_adjustments.consol_adjustments.get_masters',
		})
		.then((r) => {
			page.ca.state.masters = r.message || { companies: [], groups: [], fiscal_years: [] };
			fill_ca_form_selects(page, { from: '', to: '', pg: '', sg: '', fy: '' });
			fill_ca_filter_selects(page);
		});
}
function fill_ca_form_selects(page, keep) {
	const $body = $(page.body);
	const M = page.ca.state.masters;
	const v = keep || {
		from: $body.find('#ca-f-from').val(),
		to: $body.find('#ca-f-to').val(),
		pg: $body.find('#ca-f-pg').val(),
		sg: $body.find('#ca-f-sg').val(),
		fy: $body.find('#ca-f-fy').val(),
		month: $body.find('#ca-f-month').val(),
	};
	const cos = M.companies.slice();
	if (v.from && !cos.includes(v.from)) cos.push(v.from);
	$body.find('#ca-f-from').html(ca_opts(cos, v.from, 'Select company'));
	const tos = cos.slice();
	if (v.to && !tos.includes(v.to)) tos.push(v.to);
	$body.find('#ca-f-to').html(`<option value="">Not applicable</option>${tos.map((c) => `<option${c === v.to ? ' selected' : ''}>${frappe.utils.escape_html(c)}</option>`).join('')}`);
	const fys = M.fiscal_years.slice();
	if (v.fy && !fys.includes(v.fy)) fys.push(v.fy);
	$body.find('#ca-f-fy').html(ca_opts(fys, v.fy, 'Select fiscal year'));
	const months = (M.months || []).slice();
	if (v.month && !months.includes(v.month)) months.push(v.month);
	$body.find('#ca-f-month').html(ca_opts(months, v.month, 'Select month'));
	const pgs = M.groups.map((g) => g.name);
	if (v.pg && !pgs.includes(v.pg)) pgs.push(v.pg);
	$body.find('#ca-f-pg').html(ca_opts(pgs, v.pg, 'Select primary group'));
	fill_ca_subs(page, v.sg);
}
function fill_ca_subs(page, sel) {
	const $body = $(page.body);
	const g = ca_grp(page, $body.find('#ca-f-pg').val());
	const subs = g ? g.subs.slice() : [];
	if (sel && !subs.includes(sel) && $body.find('#ca-f-pg').val()) subs.push(sel);
	$body.find('#ca-f-sg').html(ca_opts(subs, sel, g ? 'Select secondary group' : 'Pick a primary group first'));
	$body.find('#ca-f-sg').prop('disabled', !g);
}
function fill_ca_filter_selects(page) {
	const $body = $(page.body);
	const M = page.ca.state.masters;
	const cur = {
		f: $body.find('#ca-q-from').val(),
		p: $body.find('#ca-q-pg').val(),
		y: $body.find('#ca-q-fy').val(),
		m: $body.find('#ca-q-month').val(),
		rp: $body.find('#ca-r-pg').val(),
		ry: $body.find('#ca-r-fy').val(),
		rm: $body.find('#ca-r-month').val(),
	};
	const txns = page.ca.state.txns || [];
	const cos = [...new Set([...M.companies, ...txns.map((t) => t.from).filter(Boolean)])];
	$body.find('#ca-q-from').html(ca_opts(cos, cur.f, 'All From companies'));
	const pgs = [...new Set([...M.groups.map((g) => g.name), ...txns.map((t) => t.pg)])];
	$body.find('#ca-q-pg').html(ca_opts(pgs, cur.p, 'All primary groups'));
	$body.find('#ca-r-pg').html(ca_opts(pgs, cur.rp, 'All primary groups'));
	const fys = [...new Set([...M.fiscal_years, ...txns.map((t) => t.fy).filter(Boolean)])];
	$body.find('#ca-q-fy').html(ca_opts(fys, cur.y, 'All fiscal years'));
	$body.find('#ca-r-fy').html(ca_opts(fys, cur.ry, 'All fiscal years'));
	const months = [...new Set([...(M.months || []), ...txns.map((t) => t.month).filter(Boolean)])];
	$body.find('#ca-q-month').html(ca_opts(months, cur.m, 'All months'));
	$body.find('#ca-r-month').html(ca_opts(months, cur.rm, 'All months'));
}

// --- Form -----------------------------------------------------------
function sync_ca_amounts(page) {
	const $body = $(page.body);
	const dr = ca_parse_amt($body.find('#ca-f-dr').val());
	const cr = ca_parse_amt($body.find('#ca-f-cr').val());
	$body.find('#ca-f-cr').prop('disabled', dr > 0);
	$body.find('#ca-f-dr').prop('disabled', cr > 0);
	const n = (isNaN(dr) ? 0 : dr) - (isNaN(cr) ? 0 : cr);
	$body.find('#ca-net-out').text(n ? ca_nf2.format(Math.abs(n)) + (n > 0 ? ' Dr' : ' Cr') : '–');
}
function fmt_ca_input(el) {
	const v = ca_parse_amt(el.value);
	if (v > 0) el.value = ca_nf2.format(v);
}
function ca_txn_label(t) {
	return t.no || ((t.type === 'Regrouping' ? 'RGP-' : 'ELM-') + '0000');
}
function update_ca_txid(page) {
	const { state } = page.ca;
	const $body = $(page.body);
	if (state.editing) {
		const t = state.txns.find((x) => x.id === state.editing);
		$body.find('#ca-txid').text(t ? ca_txn_label(t) : '');
	} else {
		$body.find('#ca-txid').text('New: ' + ($body.find('#ca-f-type').val() === 'Regrouping' ? 'RGP-' : 'ELM-') + '####');
	}
}
function reset_ca_form(page) {
	const { state } = page.ca;
	const $body = $(page.body);
	state.editing = null;
	$body.find('#ca-form')[0].reset();
	fill_ca_form_selects(page, { from: '', to: '', pg: '', sg: '', fy: '', month: '' });
	$body.find('#ca-f-dr, #ca-f-cr').prop('disabled', false);
	$body.find('#ca-form-err').prop('hidden', true);
	$body.find('#ca-form-title').text('New transaction');
	$body.find('#ca-save-btn').text('Add transaction');
	sync_ca_amounts(page);
	update_ca_txid(page);
	render_ca_register(page);
}
function read_ca_form(page) {
	const $body = $(page.body);
	return {
		from: $body.find('#ca-f-from').val(),
		to: $body.find('#ca-f-to').val(),
		fy: $body.find('#ca-f-fy').val(),
		month: $body.find('#ca-f-month').val(),
		pg: $body.find('#ca-f-pg').val(),
		sg: $body.find('#ca-f-sg').val(),
		debit: ca_parse_amt($body.find('#ca-f-dr').val()),
		credit: ca_parse_amt($body.find('#ca-f-cr').val()),
		type: $body.find('#ca-f-type').val(),
		narration: $body.find('#ca-f-narr').val().trim(),
		ref: $body.find('#ca-f-ref').val().trim(),
	};
}
function validate_ca_form(page, t) {
	const e = [];
	if (!t.from) e.push('Choose the From company.');
	if (t.to && t.to === t.from) e.push('From and To company cannot be the same entity.');
	if (!t.fy) e.push('Choose a fiscal year.');
	if (!t.month) e.push('Choose a month.');
	if (!t.pg) e.push('Choose a primary group.');
	const g = ca_grp(page, t.pg);
	if (t.pg && !g) e.push(`Primary group "${t.pg}" is not in the master.`);
	if (!t.sg) e.push('Choose a secondary group.');
	else if (g && !g.subs.includes(t.sg)) e.push(`"${t.sg}" is not a secondary group under ${t.pg}.`);
	if (isNaN(t.debit) || isNaN(t.credit)) e.push('Amounts must be numbers.');
	else if (t.debit < 0 || t.credit < 0) e.push('Enter amounts as positive values; use the other column for the opposite side.');
	else if (t.debit > 0 && t.credit > 0) e.push('Enter either a debit or a credit, not both.');
	else if (!(t.debit > 0) && !(t.credit > 0)) e.push('Enter a debit or a credit amount.');
	if (!['Elimination', 'Regrouping'].includes(t.type)) e.push('Adjustment type must be Elimination or Regrouping.');
	return e;
}
function ca_err_msg(err) {
	return (err && err.message) || 'The change could not be saved. Try again.';
}
function submit_ca_form(ev, page) {
	ev.preventDefault();
	const { state } = page.ca;
	const $body = $(page.body);
	const t = read_ca_form(page);
	const errs = validate_ca_form(page, t);
	if (errs.length) {
		$body.find('#ca-form-err').html('<ul>' + errs.map((x) => `<li>${frappe.utils.escape_html(x)}</li>`).join('') + '</ul>').prop('hidden', false);
		return;
	}
	$body.find('#ca-form-err').prop('hidden', true);
	t.debit = t.debit || 0;
	t.credit = t.credit || 0;
	const $btn = $body.find('#ca-save-btn').prop('disabled', true);
	const editing = state.editing;
	const call = editing
		? frappe.call({
				method: 'financial_report_tool.financial_report_tool.page.consol_adjustments.consol_adjustments.update_transaction',
				args: { id: editing, txn: JSON.stringify(t) },
			})
		: frappe.call({
				method: 'financial_report_tool.financial_report_tool.page.consol_adjustments.consol_adjustments.create_transaction',
				args: { txn: JSON.stringify(t) },
			});
	call
		.then(() => load_ca_transactions(page))
		.then(() => {
			const keep = { from: t.from, pg: t.pg, type: t.type, fy: t.fy, month: t.month };
			const wasEdit = !!editing;
			reset_ca_form(page);
			if (!wasEdit) {
				fill_ca_form_selects(page, { from: keep.from, to: '', pg: keep.pg, sg: '', fy: keep.fy, month: keep.month });
				$body.find('#ca-f-type').val(keep.type);
				update_ca_txid(page);
			}
		})
		.catch((err) => {
			$body.find('#ca-form-err').html(frappe.utils.escape_html(ca_err_msg(err))).prop('hidden', false);
		})
		.finally(() => $btn.prop('disabled', false));
}
function start_ca_edit(page, id) {
	const { state } = page.ca;
	const t = state.txns.find((x) => x.id === id);
	if (!t) return;
	state.editing = id;
	state.confirmDel = null;
	const $body = $(page.body);
	fill_ca_form_selects(page, { from: t.from, to: t.to || '', pg: t.pg, sg: t.sg, fy: t.fy, month: t.month || '' });
	$body.find('#ca-f-dr').val(t.debit ? ca_nf2.format(t.debit) : '');
	$body.find('#ca-f-cr').val(t.credit ? ca_nf2.format(t.credit) : '');
	$body.find('#ca-f-type').val(t.type);
	$body.find('#ca-f-narr').val(t.narration || '');
	$body.find('#ca-f-ref').val(t.ref || '');
	$body.find('#ca-form-title').text('Edit transaction');
	$body.find('#ca-save-btn').text('Update transaction');
	$body.find('#ca-form-err').prop('hidden', true);
	sync_ca_amounts(page);
	update_ca_txid(page);
	render_ca_register(page);
	$body.find('#ca-form')[0].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

// --- Persistence ------------------------------------------------------
function load_ca_transactions(page) {
	return frappe
		.call({ method: 'financial_report_tool.financial_report_tool.page.consol_adjustments.consol_adjustments.list_transactions' })
		.then((r) => {
			page.ca.state.txns = r.message || [];
			if (page.ca.state.editing && !page.ca.state.txns.some((t) => t.id === page.ca.state.editing)) {
				page.ca.state.editing = null;
			}
			render_ca_all(page);
		});
}
function delete_ca_txn(page, id) {
	return frappe
		.call({ method: 'financial_report_tool.financial_report_tool.page.consol_adjustments.consol_adjustments.delete_transaction', args: { id } })
		.then(() => load_ca_transactions(page));
}

// --- Register ---------------------------------------------------------
function ca_filtered(page) {
	const { state } = page.ca;
	const $body = $(page.body);
	const q = $body.find('#ca-q-search').val().trim().toLowerCase();
	const ty = $body.find('#ca-q-type').val();
	const fr = $body.find('#ca-q-from').val();
	const pg = $body.find('#ca-q-pg').val();
	const fy = $body.find('#ca-q-fy').val();
	const mo = $body.find('#ca-q-month').val();
	return state.txns.filter(
		(t) =>
			(!ty || t.type === ty) &&
			(!fr || t.from === fr) &&
			(!pg || t.pg === pg) &&
			(!fy || t.fy === fy) &&
			(!mo || t.month === mo) &&
			(!q || [ca_txn_label(t), t.narration, t.ref, t.to, t.sg].join(' ').toLowerCase().includes(q))
	);
}
function render_ca_register(page) {
	const { state } = page.ca;
	const $body = $(page.body);
	const u = CA_UNITS[state.unit].lab;
	$body.find('#ca-th-dr').text('Debit (' + u + ')');
	$body.find('#ca-th-cr').text('Credit (' + u + ')');
	const rows = ca_filtered(page);
	if (!state.txns.length) {
		$body.find('#ca-reg-body').html(`<tr><td colspan="10" class="ca-empty">No transactions yet. Add the first one with the form, or import your elimination sheet.</td></tr>`);
		$body.find('#ca-reg-foot').html('');
		return;
	}
	if (!rows.length) {
		$body.find('#ca-reg-body').html(`<tr><td colspan="10" class="ca-empty">No transactions match these filters.</td></tr>`);
		$body.find('#ca-reg-foot').html('');
		return;
	}
	$body.find('#ca-reg-body').html(
		rows
			.map((t) => {
				const g = ca_grp(page, t.pg);
				const bad = !g || !g.subs.includes(t.sg);
				const acts =
					state.confirmDel === t.id
						? `<button class="ca-btn sm danger" data-act="delok" data-id="${t.id}">Delete</button><button class="ca-icon" data-act="delno">Keep</button>`
						: `<button class="ca-icon" data-act="edit" data-id="${t.id}" aria-label="Edit ${ca_txn_label(t)}">Edit</button><button class="ca-icon del" data-act="del" data-id="${t.id}" aria-label="Delete ${ca_txn_label(t)}">Delete</button>`;
				return `<tr class="${state.editing === t.id ? 'editing' : ''}">
					<td class="ca-txid">${ca_txn_label(t)}</td>
					<td>${frappe.utils.escape_html(t.from)} <span class="ca-muted">→</span> ${t.to ? frappe.utils.escape_html(t.to) : '<span class="ca-muted">N/A</span>'}${t.narration ? `<span class="ca-sub">${frappe.utils.escape_html(t.narration)}</span>` : ''}</td>
					<td>${frappe.utils.escape_html(t.fy || '')}</td>
					<td>${frappe.utils.escape_html(t.month || '')}</td>
					<td>${frappe.utils.escape_html(t.pg)}</td>
					<td>${frappe.utils.escape_html(t.sg)}${bad ? '<span class="ca-sub neg">Not in current master</span>' : ''}${t.ref ? `<span class="ca-sub">Ref: ${frappe.utils.escape_html(t.ref)}</span>` : ''}</td>
					<td><span class="ca-pill ${frappe.utils.escape_html(t.type)}">${frappe.utils.escape_html(t.type)}</span></td>
					<td class="n">${ca_fmt(state, t.debit)}</td><td class="n">${ca_fmt(state, t.credit)}</td>
					<td><div class="ca-acts">${acts}</div></td></tr>`;
			})
			.join('')
	);
	const dr = rows.reduce((a, t) => a + (t.debit || 0), 0);
	const cr = rows.reduce((a, t) => a + (t.credit || 0), 0);
	$body.find('#ca-reg-foot').html(
		`<tr class="tot"><td colspan="7">${rows.length} of ${state.txns.length} transactions · Net ${ca_fmt_net(state, dr - cr)}</td><td class="n">${ca_fmt(state, dr)}</td><td class="n">${ca_fmt(state, cr)}</td><td></td></tr>`
	);
}
function ca_register_click(ev, page) {
	const { state } = page.ca;
	const $b = $(ev.target).closest('[data-act]');
	if (!$b.length) return;
	const id = $b.data('id');
	const act = $b.data('act');
	if (act === 'edit') start_ca_edit(page, id);
	if (act === 'del') {
		state.confirmDel = id;
		render_ca_register(page);
	}
	if (act === 'delno') {
		state.confirmDel = null;
		render_ca_register(page);
	}
	if (act === 'delok') {
		state.confirmDel = null;
		delete_ca_txn(page, id)
			.then(() => {
				if (state.editing === id) reset_ca_form(page);
			})
			.catch((err) => frappe.show_alert({ message: ca_err_msg(err), indicator: 'red' }));
	}
}

// --- KPIs ---------------------------------------------------------------
function ca_recon_rows(page, filters) {
	filters = filters || {};
	const pairs = new Map();
	for (const t of page.ca.state.txns) {
		if (filters.type && t.type !== filters.type) continue;
		if (filters.pg && t.pg !== filters.pg) continue;
		if (filters.fy && t.fy !== filters.fy) continue;
		if (!t.from || !t.to) continue;
		const [a, b] = [t.from, t.to].sort((x, y) => x.localeCompare(y));
		const k = a + '\u0000' + b;
		if (!pairs.has(k)) pairs.set(k, { a, b, ab: 0, ba: 0, n: 0 });
		const p = pairs.get(k);
		if (t.from === a) p.ab += ca_net(t);
		else p.ba += ca_net(t);
		p.n++;
	}
	return [...pairs.values()].map((p) => ({ ...p, diff: p.ab + p.ba })).sort((x, y) => Math.abs(y.diff) - Math.abs(x.diff));
}
function render_ca_kpis(page) {
	const { state } = page.ca;
	const sum = (arr, f) => arr.reduce((a, t) => a + f(t), 0);
	const el = state.txns.filter((t) => t.type === 'Elimination');
	const rg = state.txns.filter((t) => t.type === 'Regrouping');
	const dr = sum(state.txns, (t) => t.debit || 0);
	const cr = sum(state.txns, (t) => t.credit || 0);
	const diff = dr - cr;
	const recon = ca_recon_rows(page, {});
	const open = recon.filter((r) => Math.abs(r.diff) >= 1).length;
	$(page.body).find('#ca-kpis').html(`
		<div class="ca-kpi"><div class="l">Total debit</div><div class="v">${ca_fmt(state, dr)}</div><div class="s">${CA_UNITS[state.unit].lab} · ${state.txns.length} entries</div></div>
		<div class="ca-kpi"><div class="l">Total credit</div><div class="v">${ca_fmt(state, cr)}</div><div class="s">${CA_UNITS[state.unit].lab}</div></div>
		<div class="ca-kpi ${Math.abs(diff) < 1 ? 'ok' : 'bad'}"><div class="l">Dr − Cr difference</div><div class="v">${Math.abs(diff) < 1 ? 'Balanced' : ca_fmt_net(state, diff)}</div><div class="s">Adjustments should net to zero</div></div>
		<div class="ca-kpi"><div class="l">Elimination / Regrouping</div><div class="v">${el.length} / ${rg.length}</div><div class="s">Net ${ca_fmt_net(state, sum(el, ca_net))} / ${ca_fmt_net(state, sum(rg, ca_net))}</div></div>
		<div class="ca-kpi ${open ? 'bad' : 'ok'}"><div class="l">IC pairs unreconciled</div><div class="v">${open} of ${recon.length}</div><div class="s">From ↔ To pairs with a difference</div></div>`);
}

// --- Reports (server-computed) ------------------------------------------
function ca_rep_args(page) {
	const $body = $(page.body);
	return {
		adj_type: $body.find('#ca-r-type').val() || undefined,
		primary_group: $body.find('#ca-r-pg').val() || undefined,
		fiscal_year: $body.find('#ca-r-fy').val() || undefined,
		month: $body.find('#ca-r-month').val() || undefined,
	};
}
function render_ca_reports(page) {
	const { state } = page.ca;
	const $body = $(page.body);
	const kind = $body.find('#ca-r-kind').val();
	const u = CA_UNITS[state.unit].lab;
	$body.find('#ca-rep-title').text($body.find('#ca-r-kind option:selected').text());
	const out = $body.find('#ca-rep-out');
	out.html('<div class="ca-loading">Loading…</div>');
	const args = ca_rep_args(page);
	const methodByKind = {
		tb: 'report_adjustment_tb',
		matrix: 'report_company_matrix',
		recon: 'report_ic_reconciliation',
		entity: 'report_entity_summary',
	};
	frappe
		.call({
			method: `financial_report_tool.financial_report_tool.page.consol_adjustments.consol_adjustments.${methodByKind[kind]}`,
			args,
		})
		.then((r) => {
			const rows = r.message || [];
			if (!rows.length) {
				out.html('<div class="ca-empty">No transactions for this selection yet.</div>');
				return;
			}
			if (kind === 'tb') render_ca_tb(out, rows, u, state);
			else if (kind === 'matrix') render_ca_matrix(out, rows, u, state);
			else if (kind === 'recon') render_ca_recon(out, rows, u, state);
			else render_ca_entity(out, rows, u, state);
		});
}
function render_ca_tb(out, rows, u, state) {
	const fmt = (v) => ca_fmt(state, v);
	const fmtNet = (v) => ca_fmt_net(state, v);
	const stLabel = { 'P&L': 'Statement of Profit & Loss', BS: 'Balance Sheet', Unmapped: 'Not in master' };
	const bySt = new Map();
	for (const r of rows) {
		if (!bySt.has(r.statement)) bySt.set(r.statement, []);
		bySt.get(r.statement).push(r);
	}
	let h = `<table><thead><tr><th>Primary group</th><th>Secondary group</th><th class="n">Entries</th><th class="n">Debit (${u})</th><th class="n">Credit (${u})</th><th class="n">Net (${u})</th></tr></thead><tbody>`;
	let T = { dr: 0, cr: 0 };
	for (const st of ['P&L', 'BS', 'Unmapped']) {
		const list = bySt.get(st);
		if (!list || !list.length) continue;
		h += `<tr class="stmt"><td colspan="6">${stLabel[st]}</td></tr>`;
		const byPg = new Map();
		for (const r of list) {
			if (!byPg.has(r.pg)) byPg.set(r.pg, []);
			byPg.get(r.pg).push(r);
		}
		let ST = { dr: 0, cr: 0 };
		for (const [pg, items] of byPg) {
			let G = { dr: 0, cr: 0, n: 0 };
			let inner = '';
			// Same secondary group can appear twice here (once per Adjustment
			// Type) -- each combination is its own row, never merged.
			for (const c of items) {
				G.dr += c.debit;
				G.cr += c.credit;
				G.n += c.entries;
				const typeTag = ` <span class="ca-muted" style="font-size:11px">(${frappe.utils.escape_html(c.type)})</span>`;
				inner += `<tr><td></td><td>${frappe.utils.escape_html(c.sg)}${typeTag}</td><td class="n">${c.entries}</td><td class="n">${fmt(c.debit)}</td><td class="n">${fmt(c.credit)}</td><td class="n">${fmtNet(c.net)}</td></tr>`;
			}
			h += `<tr class="grp"><td colspan="2">${frappe.utils.escape_html(pg)}</td><td class="n">${G.n}</td><td class="n">${fmt(G.dr)}</td><td class="n">${fmt(G.cr)}</td><td class="n">${fmtNet(G.dr - G.cr)}</td></tr>${inner}`;
			ST.dr += G.dr;
			ST.cr += G.cr;
		}
		h += `<tr class="tot"><td colspan="3">Total – ${st === 'P&L' ? 'P&L' : st === 'BS' ? 'Balance Sheet' : 'unmapped'}</td><td class="n">${fmt(ST.dr)}</td><td class="n">${fmt(ST.cr)}</td><td class="n">${fmtNet(ST.dr - ST.cr)}</td></tr>`;
		T.dr += ST.dr;
		T.cr += ST.cr;
	}
	const d = T.dr - T.cr;
	h += `</tbody><tfoot><tr class="tot"><td colspan="3">Grand total ${Math.abs(d) < 1 ? '<span class="ca-pill ok">Balanced</span>' : '<span class="ca-pill bad">Out of balance</span>'}</td><td class="n">${fmt(T.dr)}</td><td class="n">${fmt(T.cr)}</td><td class="n">${fmtNet(d)}</td></tr></tfoot></table>`;
	out.html(h);
}
function render_ca_matrix(out, rows, u, state) {
	const froms = [...new Set(rows.map((r) => r.from))].sort();
	const tos = [...new Set(rows.map((r) => r.to))].sort();
	const cell = {};
	for (const r of rows) cell[r.from + '|' + r.to] = r.net;
	let h = `<table class="ca-matrix"><thead><tr><th class="rh">From \\ To (${u}, net)</th>${tos.map((c) => `<th class="n">${frappe.utils.escape_html(c)}</th>`).join('')}<th class="n">Row total</th></tr></thead><tbody>`;
	const colT = {};
	for (const f of froms) {
		let rt = 0;
		h +=
			`<tr><td class="rh"><b>${frappe.utils.escape_html(f)}</b></td>` +
			tos
				.map((c) => {
					const v = cell[f + '|' + c] || 0;
					rt += v;
					colT[c] = (colT[c] || 0) + v;
					return `<td class="n">${ca_fmt_net(state, v)}</td>`;
				})
				.join('') +
			`<td class="n"><b>${ca_fmt_net(state, rt)}</b></td></tr>`;
	}
	const gt = Object.values(colT).reduce((a, b) => a + b, 0);
	h += `</tbody><tfoot><tr class="tot"><td class="rh">Column total</td>${tos.map((c) => `<td class="n">${ca_fmt_net(state, colT[c])}</td>`).join('')}<td class="n">${ca_fmt_net(state, gt)}</td></tr></tfoot></table>`;
	out.html(h);
}
function render_ca_recon(out, rows, u, state) {
	let h = `<table><thead><tr><th>Entity A</th><th>Entity B</th><th class="n">Entries</th><th class="n">A → B net (${u})</th><th class="n">B → A net (${u})</th><th class="n">Difference (${u})</th><th>Status</th></tr></thead><tbody>`;
	h += rows
		.map((p) => {
			const status =
				Math.abs(p.diff) < 1
					? '<span class="ca-pill ok">Matched</span>'
					: !p.ab || !p.ba
						? '<span class="ca-pill bad">One side only</span>'
						: '<span class="ca-pill bad">Difference</span>';
			return `<tr><td>${frappe.utils.escape_html(p.a)}</td><td>${frappe.utils.escape_html(p.b)}</td><td class="n">${p.entries}</td><td class="n">${ca_fmt_net(state, p.ab)}</td><td class="n">${ca_fmt_net(state, p.ba)}</td><td class="n ${Math.abs(p.diff) >= 1 ? 'neg' : ''}">${ca_fmt_net(state, p.diff)}</td><td>${status}</td></tr>`;
		})
		.join('');
	h += `</tbody></table><p class="ca-muted" style="padding:10px 14px;margin:0;font-size:12px">Each pair should net to zero: A's entry against B (e.g. sales Cr) is offset by B's entry against A (e.g. purchases Dr). "One side only" means the counterparty entry has not been recorded yet.</p>`;
	out.html(h);
}
function render_ca_entity(out, rows, u, state) {
	let T = { dr: 0, cr: 0, n: 0 };
	let h = `<table><thead><tr><th>Company</th><th class="n">Entries</th><th class="n">Debit (${u})</th><th class="n">Credit (${u})</th><th class="n">Net as originator (${u})</th><th class="n">Net recorded by counterparties (${u})</th></tr></thead><tbody>`;
	h += rows
		.map((v) => {
			T.dr += v.debit;
			T.cr += v.credit;
			T.n += v.entries;
			return `<tr><td>${frappe.utils.escape_html(v.company)}</td><td class="n">${v.entries}</td><td class="n">${ca_fmt(state, v.debit)}</td><td class="n">${ca_fmt(state, v.credit)}</td><td class="n">${ca_fmt_net(state, v.net)}</td><td class="n">${ca_fmt_net(state, v.counterparty_net)}</td></tr>`;
		})
		.join('');
	h += `</tbody><tfoot><tr class="tot"><td>Total</td><td class="n">${T.n}</td><td class="n">${ca_fmt(state, T.dr)}</td><td class="n">${ca_fmt(state, T.cr)}</td><td class="n">${ca_fmt_net(state, T.dr - T.cr)}</td><td></td></tr></tfoot></table>`;
	out.html(h);
}

// --- Import (Excel/CSV, server-side parsing) -----------------------------
function open_ca_import_dialog(page) {
	const d = new frappe.ui.Dialog({
		title: __('Import Excel/CSV'),
		fields: [
			{
				fieldtype: 'HTML',
				options: `<div class="ca-import-hint">Accepted headers: From Company, To Company (optional), Fiscal Year, Month, Primary Group, Secondary Group, Debit, Credit (or a signed Amount), Adjustment Type, Narration, Reference. Download the <b>Import template</b> button on the register for the expected layout.</div>`,
			},
			{
				fieldtype: 'Attach',
				fieldname: 'file',
				label: __('Excel or CSV file'),
				reqd: 1,
			},
			{ fieldtype: 'Section Break' },
			{ fieldtype: 'HTML', fieldname: 'preview' },
		],
		primary_action_label: __('Preview'),
		primary_action: () => {
			const file_url = d.get_value('file');
			if (!file_url) {
				frappe.msgprint(__('Please attach a file.'));
				return;
			}
			const $wrap = $(d.fields_dict.preview.wrapper);
			$wrap.html('<div class="ca-se-loading">Reading file…</div>');
			frappe
				.call({
					method: 'financial_report_tool.financial_report_tool.page.consol_adjustments.consol_adjustments.preview_import',
					args: { file_url },
					freeze: true,
					freeze_message: __('Reading file…'),
				})
				.then((r) => {
					const s = r.message || { ok: [], errors: [], skipped: 0 };
					page.ca.state.imp = s;
					render_ca_import_preview(page, d, $wrap, s);
				})
				.catch((err) => {
					$wrap.html(`<div class="ca-errs">${frappe.utils.escape_html(ca_err_msg(err))}</div>`);
				});
		},
	});
	d.show();
}
function render_ca_import_preview(page, d, $wrap, s) {
	const errHtml = s.errors.length
		? `<ul>${s.errors.slice(0, 12).map((e) => `<li>${frappe.utils.escape_html(e)}</li>`).join('')}${s.errors.length > 12 ? `<li>…and ${s.errors.length - 12} more</li>` : ''}</ul>`
		: '';
	$wrap.html(`
		<div class="ca-import-summary">
			<b>${s.ok.length}</b> row(s) ready${s.skipped ? `, ${s.skipped} zero-value rows skipped` : ''}${s.errors.length ? `, <span class="neg">${s.errors.length} rows need fixing</span>` : ''}.
			${errHtml}
		</div>`);
	d.set_primary_action(__('Import {0} transactions', [s.ok.length]), () => {
		if (!s.ok.length) return;
		const $btn = d.get_primary_btn().prop('disabled', true);
		frappe
			.call({
				method: 'financial_report_tool.financial_report_tool.page.consol_adjustments.consol_adjustments.bulk_create',
				args: { rows: JSON.stringify(s.ok) },
			})
			.then((r) => {
				frappe.show_alert({ message: __('Imported {0} transactions', [r.message.inserted]), indicator: 'green' }, 4);
				d.hide();
				page.ca.state.imp = null;
				load_ca_transactions(page);
			})
			.catch((err) => {
				frappe.msgprint({ title: __('Import failed'), indicator: 'red', message: ca_err_msg(err) });
			})
			.finally(() => $btn.prop('disabled', false));
	});
	if (!s.ok.length) d.get_primary_btn().prop('disabled', true);
}

// --- Render everything ----------------------------------------------
function render_ca_all(page) {
	fill_ca_filter_selects(page);
	render_ca_kpis(page);
	render_ca_register(page);
	update_ca_txid(page);
	if (page.ca.state.view === 'reports') render_ca_reports(page);
}

// --- Styles -----------------------------------------------------------
function inject_ca_styles() {
	if (document.getElementById('ca-styles')) return;
	const css = `
	:root{
		--ca-bg:#f4f6f8; --ca-surface:#ffffff; --ca-ink:#15202b; --ca-muted:#5b6a78; --ca-line:#dce2e8; --ca-line-strong:#c3ccd5;
		--ca-accent:#1c5a78; --ca-accent-ink:#ffffff; --ca-accent-soft:#e2edf3;
		--ca-elim-bg:#e2edf3; --ca-elim-fg:#1c5a78; --ca-reg-bg:#f5ebd8; --ca-reg-fg:#7a5211;
		--ca-ok:#2d7a4c; --ca-ok-bg:#e1f1e7; --ca-bad:#b1362e; --ca-bad-bg:#f8e3e1;
		--ca-row-alt:#f9fafb;
	}
	.dark .ca-wrap, [data-theme="dark"] .ca-wrap{
		--ca-bg:#0f151a; --ca-surface:#161f27; --ca-ink:#e3e9ee; --ca-muted:#93a2af; --ca-line:#26323c; --ca-line-strong:#364552;
		--ca-accent:#6db2d5; --ca-accent-ink:#0c1a22; --ca-accent-soft:#1b3342;
		--ca-elim-bg:#1b3342; --ca-elim-fg:#8cc6e4; --ca-reg-bg:#372c19; --ca-reg-fg:#e8c07c;
		--ca-ok:#6cc28f; --ca-ok-bg:#16301f; --ca-bad:#ee7b71; --ca-bad-bg:#3a1c1a;
		--ca-row-alt:#131b22;
	}
	.ca-wrap{color:var(--ca-ink);font-size:14px;line-height:1.45}
	.ca-filters{display:flex;flex-wrap:wrap;gap:10px 20px;align-items:center;padding:8px 2px;margin-bottom:6px}
	.ca-field{display:flex;align-items:center;gap:8px}
	.ca-field label{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--ca-muted);font-weight:600}
	.ca-spacer{flex:1}
	.ca-seg{display:inline-flex;border:1px solid var(--ca-line-strong);border-radius:6px;overflow:hidden;background:var(--ca-surface)}
	.ca-seg button{border:0;background:transparent;color:var(--ca-muted);font:500 12px inherit;padding:6px 10px;cursor:pointer}
	.ca-seg button+button{border-left:1px solid var(--ca-line)}
	.ca-seg button[aria-pressed="true"]{background:var(--ca-accent);color:var(--ca-accent-ink)}
	nav.ca-tabs{display:flex;gap:4px;border-bottom:1px solid var(--ca-line)}
	nav.ca-tabs button{border:0;background:none;color:var(--ca-muted);font:500 13px inherit;padding:8px 14px;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}
	nav.ca-tabs button[aria-selected="true"]{color:var(--ca-ink);border-bottom-color:var(--ca-accent)}
	.ca-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:14px 0}
	.ca-kpi{background:var(--ca-surface);border:1px solid var(--ca-line);border-radius:8px;padding:10px 14px}
	.ca-kpi .l{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--ca-muted)}
	.ca-kpi .v{font:500 18px monospace;margin-top:2px}
	.ca-kpi .s{font-size:12px;color:var(--ca-muted)}
	.ca-kpi.bad .v{color:var(--ca-bad)} .ca-kpi.ok .v{color:var(--ca-ok)}
	.ca-grid{display:grid;grid-template-columns:minmax(300px,380px) minmax(0,1fr);gap:16px;align-items:start}
	@media (max-width:900px){.ca-grid{grid-template-columns:minmax(0,1fr)}}
	.ca-panel{background:var(--ca-surface);border:1px solid var(--ca-line);border-radius:8px;min-width:0}
	.ca-hd{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid var(--ca-line)}
	.ca-hd h2{font-weight:600;font-size:16px;margin:0}
	.ca-bd{padding:14px}
	.ca-sec{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--ca-muted);margin:14px 0 6px;font-weight:600}
	.ca-sec:first-child{margin-top:0}
	.ca-row2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
	.ca-fld{display:flex;flex-direction:column;gap:4px;min-width:0}
	.ca-fld label{font-size:12px;color:var(--ca-muted);font-weight:500}
	.ca-req{color:var(--ca-bad);font-weight:700}
	.ca-wrap input,.ca-wrap select,.ca-wrap textarea{font:14px inherit;color:var(--ca-ink);background:var(--ca-surface);border:1px solid var(--ca-line-strong);border-radius:6px;padding:7px 9px;width:100%;min-width:0}
	.ca-wrap input.ca-num{font-family:monospace;text-align:right}
	.ca-wrap input:disabled{background:var(--ca-row-alt);color:var(--ca-muted)}
	.ca-wrap textarea{resize:vertical;min-height:54px}
	.ca-netline{display:flex;justify-content:space-between;align-items:baseline;margin-top:8px;padding:8px 10px;border-radius:6px;background:var(--ca-row-alt);font-size:12px;color:var(--ca-muted)}
	.ca-netline b{font:500 14px monospace;color:var(--ca-ink)}
	.ca-txid{font:500 12px monospace;color:var(--ca-muted)}
	.ca-errs{margin-top:10px;padding:8px 10px;border-radius:6px;background:var(--ca-bad-bg);color:var(--ca-bad);font-size:13px}
	.ca-errs ul{margin:0;padding-left:18px}
	.ca-btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
	.ca-btn{font:500 13px inherit;padding:8px 14px;border-radius:6px;border:1px solid var(--ca-line-strong);background:var(--ca-surface);color:var(--ca-ink);cursor:pointer}
	.ca-btn.pri{background:var(--ca-accent);border-color:var(--ca-accent);color:var(--ca-accent-ink)}
	.ca-btn.danger{background:var(--ca-bad);border-color:var(--ca-bad);color:#fff}
	.ca-btn.sm{padding:5px 10px;font-size:12px}
	.ca-btn:disabled{opacity:.5;cursor:not-allowed}
	.ca-filters2{display:flex;flex-wrap:wrap;gap:8px;padding:10px 14px;border-bottom:1px solid var(--ca-line)}
	.ca-filters2>*{flex:1 1 130px;max-width:220px}
	.ca-tblwrap{overflow-x:auto}
	.ca-wrap table{border-collapse:collapse;width:100%;font-size:13px}
	.ca-wrap th,.ca-wrap td{padding:7px 10px;border-bottom:1px solid var(--ca-line);text-align:left;vertical-align:top}
	.ca-wrap th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--ca-muted);font-weight:600;background:var(--ca-row-alt);position:sticky;top:0;white-space:nowrap}
	.ca-wrap td.n,.ca-wrap th.n{text-align:right;font-family:monospace;white-space:nowrap}
	.ca-wrap tbody tr:hover td{background:var(--ca-row-alt)}
	.ca-wrap tr.editing td{background:var(--ca-accent-soft)!important}
	.ca-sub{display:block;color:var(--ca-muted);font-size:12px;margin-top:2px;max-width:320px}
	.ca-wrap tr.grp td{font-weight:600;background:var(--ca-row-alt)}
	.ca-wrap tr.stmt td{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--ca-accent);background:var(--ca-surface);padding-top:14px}
	.ca-wrap tr.tot td{font-weight:600;border-top:2px solid var(--ca-line-strong)}
	.ca-pill{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:999px;white-space:nowrap}
	.ca-pill.Elimination{background:var(--ca-elim-bg);color:var(--ca-elim-fg)}
	.ca-pill.Regrouping{background:var(--ca-reg-bg);color:var(--ca-reg-fg)}
	.ca-pill.ok{background:var(--ca-ok-bg);color:var(--ca-ok)} .ca-pill.bad{background:var(--ca-bad-bg);color:var(--ca-bad)}
	.ca-acts{display:flex;gap:4px;white-space:nowrap}
	.ca-icon{border:1px solid transparent;background:none;color:var(--ca-muted);cursor:pointer;padding:3px 7px;border-radius:5px;font:500 12px inherit}
	.ca-icon:hover{border-color:var(--ca-line-strong);color:var(--ca-ink)}
	.ca-icon.del:hover{color:var(--ca-bad)}
	.ca-empty,.ca-loading{padding:28px 14px;text-align:center;color:var(--ca-muted)}
	.ca-muted{color:var(--ca-muted)} .neg{color:var(--ca-bad)}
	.ca-repctl{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
	.ca-repctl select{width:auto;min-width:150px}
	.ca-matrix td,.ca-matrix th{font-size:12px}
	.ca-matrix th.rh,.ca-matrix td.rh{position:sticky;left:0;background:var(--ca-surface);z-index:1}
	.ca-foot{margin-top:18px;color:var(--ca-muted);font-size:12px}
	.ca-import-hint{font-size:12px;color:var(--ca-muted);margin-bottom:10px}
	.ca-import-summary{font-size:13px}
	.ca-import-summary ul{margin:8px 0 0;padding-left:18px;color:var(--ca-bad)}
	`;
	const style = document.createElement('style');
	style.id = 'ca-styles';
	style.textContent = css;
	document.head.appendChild(style);
}
