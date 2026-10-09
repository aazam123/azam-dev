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
								<div class="ca-row2">
									<div class="ca-fld"><label for="ca-f-from">From company <span class="ca-req">*</span></label><select id="ca-f-from"></select></div>
									<div class="ca-fld"><label for="ca-f-to">To company <span class="ca-muted">(optional)</span></label><select id="ca-f-to"></select></div>
								</div>
								<div class="ca-row2" style="margin-top:10px"><div class="ca-fld"><label for="ca-f-fy">Fiscal year <span class="ca-req">*</span></label><select id="ca-f-fy"></select></div><div class="ca-fld"><label for="ca-f-month">Month <span class="ca-req">*</span></label><select id="ca-f-month"></select></div></div>
								<div class="ca-fld"><label for="ca-f-pg">Primary group <span class="ca-req">*</span></label><select id="ca-f-pg"></select></div>
								<div class="ca-fld"><label for="ca-f-sg">Secondary group <span class="ca-req">*</span></label><select id="ca-f-sg"></select></div>
								<div class="ca-row2">
									<div class="ca-fld"><label for="ca-f-dr">Debit <span class="ca-req">*</span> <span class="ca-muted">(or Credit)</span></label><input id="ca-f-dr" class="ca-num" inputmode="decimal" placeholder="0"></div>
									<div class="ca-fld"><label for="ca-f-cr">Credit <span class="ca-req">*</span> <span class="ca-muted">(or Debit)</span></label><input id="ca-f-cr" class="ca-num" inputmode="decimal" placeholder="0"></div>
								</div>
								<div class="ca-fld"><label for="ca-f-type">Adjustment type <span class="ca-req">*</span></label>
									<select id="ca-f-type"><option>Elimination</option><option>Regrouping</option></select></div>
								<div class="ca-fld"><label for="ca-f-narr">Description / narration</label><textarea id="ca-f-narr" rows="1" placeholder="e.g. MLSPL sales to Meril India eliminated"></textarea></div>
								<div class="ca-fld"><label for="ca-f-ref">Reference <span class="ca-muted">(optional)</span></label><input id="ca-f-ref" placeholder="e.g. IC confirmation Mar-26, JV 1042"></div>
								<div class="ca-btns">
									<button type="submit" class="ca-btn pri" id="ca-save-btn">Add transaction</button>
									<button type="button" class="ca-btn" id="ca-reset-btn">Clear</button>
								</div>
								<div id="ca-form-err" class="ca-errs" hidden></div>
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
							${ca_ms_html('ca-q-type', 'All types', 'Type')}
							${ca_ms_html('ca-q-from', 'All From companies', 'From company')}
							${ca_ms_html('ca-q-pg', 'All primary groups', 'Primary group')}
							${ca_ms_html('ca-q-sg', 'All secondary groups', 'Secondary group')}
							${ca_ms_html('ca-q-fy', 'All fiscal years', 'Fiscal year')}
							${ca_ms_html('ca-q-month', 'All months', 'Month')}
							<button type="button" class="ca-reset" id="ca-q-reset" hidden>Clear filters</button>
						</div>
						<div class="ca-tblwrap" style="max-height:70vh;overflow:auto">
							<table id="ca-reg">
								<thead><tr><th>ID</th><th>From → To</th><th>FY / Month</th><th>Primary group</th><th>Secondary group</th><th>Type</th><th class="n" id="ca-th-dr">Debit</th><th class="n" id="ca-th-cr">Credit</th><th></th></tr></thead>
								<tbody id="ca-reg-body"></tbody>
								<tfoot id="ca-reg-foot"></tfoot>
							</table>
						</div>
					</div>
				</div>
			</div>
			<div id="ca-view-reports" hidden>
				<div class="ca-panel" style="margin-top:16px">
					<div class="ca-filters2">
						<div class="ca-ff ca-ff-kind"><span class="ca-ms-lab">Report</span>
							<select id="ca-r-kind" aria-label="Report">
								<option value="tb">Adjustment TB – Primary / Secondary group</option>
								<option value="matrix">Company-to-company matrix</option>
								<option value="recon">Inter-company reconciliation</option>
								<option value="entity">Entity-wise summary</option>
							</select>
						</div>
						${ca_ms_html('ca-r-type', 'All types', 'Type')}
						${ca_ms_html('ca-r-pg', 'All primary groups', 'Primary group')}
						${ca_ms_html('ca-r-sg', 'All secondary groups', 'Secondary group')}
						${ca_ms_html('ca-r-fy', 'All fiscal years', 'Fiscal year')}
						${ca_ms_html('ca-r-month', 'All months', 'Month')}
						<button type="button" class="ca-reset" id="ca-r-reset" hidden>Clear filters</button>
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
	CA_SS_IDS.forEach((id) => ca_ss_init($body, id, id === 'ca-f-to'));
	['ca-f-dr', 'ca-f-cr'].forEach((id) => {
		$body.find('#' + id).on('input', () => sync_ca_amounts(page));
		$body.find('#' + id).on('blur', function () {
			fmt_ca_input(this);
		});
	});
	$body.find('#ca-f-type').on('change', () => update_ca_txid(page));
	$body.find('#ca-form').on('submit', (ev) => submit_ca_form(ev, page));
	$body.find('#ca-reset-btn').on('click', () => reset_ca_form(page));
	const ca_types = ['Elimination', 'Regrouping'];
	['q', 'r'].forEach((scope) => {
		const rerender = () => (scope === 'q' ? render_ca_register(page) : render_ca_reports(page));
		CA_FILTER_IDS[scope].forEach((id) => {
			ca_ms_init(
				$body,
				id,
				() => {
					// Secondary-group choices follow the picked Primary groups.
					if (id === `ca-${scope}-pg`) ca_refresh_sg(page, scope);
					ca_filters_sync(page, scope);
					rerender();
				},
				id.endsWith('-type') ? ca_types : null
			);
		});
		$body.find(`#ca-${scope}-reset`).on('click', () => ca_filters_reset(page, scope));
	});
	$body.find('#ca-r-kind').on('change', () => render_ca_reports(page));
	$(document).on('click.ca_ms', ca_ms_close_all); // click outside closes an open filter
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

// --- Multi-select filter: search box + checkboxes ------------------------
// A labelled dropdown replacing a single-value <select> in the filter bars.
// Empty selection means "no filter" (shows the "All ..." text); otherwise the
// picked values are OR-ed. Several picks show the first plus a "+N" badge.
const CA_CARET = '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const CA_SEARCH_ICO = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="4.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="m10.5 10.5 3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';
function ca_ms_html(id, allLabel, fieldLabel) {
	const esc = frappe.utils.escape_html;
	return `<div class="ca-ff ca-ms" id="${id}" data-all="${esc(allLabel)}">
		<span class="ca-ms-lab">${esc(fieldLabel)}</span>
		<button type="button" class="ca-ms-btn" aria-haspopup="listbox" aria-expanded="false">
			<span class="ca-ms-txt"></span><span class="ca-ms-badge" hidden></span><span class="ca-ms-car">${CA_CARET}</span>
		</button>
		<div class="ca-ms-menu" hidden>
			<div class="ca-ms-sw">${CA_SEARCH_ICO}<input type="search" class="ca-ms-search" placeholder="${esc(__('Search…'))}" autocomplete="off"></div>
			<div class="ca-ms-tools"><span class="ca-ms-count"></span><span><button type="button" data-a="all">${esc(__('Select all'))}</button><button type="button" data-a="clear">${esc(__('Clear'))}</button></span></div>
			<div class="ca-ms-list" role="listbox" aria-multiselectable="true"></div>
		</div>
	</div>`;
}
function ca_ms_val($body, id) {
	return ($body.find('#' + id).data('sel') || []).slice();
}
function ca_ms_close_all() {
	$('.ca-ms-menu:not([hidden])').prop('hidden', true).closest('.ca-ms').find('.ca-ms-btn').attr('aria-expanded', 'false');
}
function ca_ms_paint_button($el) {
	const sel = $el.data('sel');
	const $txt = $el.find('.ca-ms-txt');
	$txt.text(sel.length ? sel[0] : $el.attr('data-all'));
	$el.find('.ca-ms-btn').attr('title', sel.length ? sel.join(', ') : $el.attr('data-all'));
	$el.find('.ca-ms-badge').text('+' + (sel.length - 1)).prop('hidden', sel.length < 2);
	$el.toggleClass('has', sel.length > 0);
}
function ca_ms_mark(text, q) {
	const esc = frappe.utils.escape_html;
	const i = q ? text.toLowerCase().indexOf(q) : -1;
	if (i < 0) return esc(text);
	return esc(text.slice(0, i)) + '<mark>' + esc(text.slice(i, i + q.length)) + '</mark>' + esc(text.slice(i + q.length));
}
function ca_ms_render($el) {
	const esc = frappe.utils.escape_html;
	const sel = new Set($el.data('sel'));
	const q = $el.find('.ca-ms-search').val().trim().toLowerCase();
	const shown = $el.data('opts').filter((o) => !q || o.toLowerCase().includes(q));
	$el.find('.ca-ms-list').html(
		shown.length
			? shown
					.map(
						(o) =>
							`<label class="ca-ms-opt${sel.has(o) ? ' on' : ''}"><input type="checkbox" value="${esc(o)}"${sel.has(o) ? ' checked' : ''}><span>${ca_ms_mark(o, q)}</span></label>`
					)
					.join('')
			: `<div class="ca-ms-none">${esc(__('No match'))}</div>`
	);
	$el.find('.ca-ms-count').text(__('{0} of {1} selected', [sel.size, $el.data('opts').length]));
	ca_ms_paint_button($el);
}
function ca_ms_set($el, list) {
	const opts = [...list];
	$el.data('opts', opts);
	// Drop picks that are no longer offered, keep the rest across refreshes.
	$el.data('sel', $el.data('sel').filter((v) => opts.includes(v)));
	ca_ms_render($el);
}
function ca_ms_init($body, id, onchange, options) {
	const $el = $body.find('#' + id);
	$el.data({ opts: [], sel: [] });
	const $btn = $el.find('.ca-ms-btn');
	const changed = () => {
		ca_ms_paint_button($el);
		onchange();
	};
	const close = () => {
		ca_ms_close_all();
		$btn.trigger('focus');
	};
	$btn.on('click', (ev) => {
		ev.stopPropagation();
		const $menu = $el.find('.ca-ms-menu');
		const opening = $menu.prop('hidden');
		ca_ms_close_all();
		if (opening) {
			$menu.prop('hidden', false).removeClass('right');
			// Keep the menu inside the viewport for controls near the right edge.
			if ($menu[0].getBoundingClientRect().right > window.innerWidth - 8) $menu.addClass('right');
			$btn.attr('aria-expanded', 'true');
			$el.find('.ca-ms-search').val('');
			ca_ms_render($el);
			$el.find('.ca-ms-search').trigger('focus');
		}
	});
	$el.find('.ca-ms-menu').on('click', (ev) => ev.stopPropagation());
	$el.find('.ca-ms-search').on('input', () => ca_ms_render($el));
	$el.find('.ca-ms-search').on('keydown', (ev) => {
		if (ev.key === 'Escape') close();
	});
	$el.on('change', '.ca-ms-opt input', function () {
		const sel = new Set($el.data('sel'));
		if (this.checked) sel.add(this.value);
		else sel.delete(this.value);
		// Keep the master option order so the label/title read naturally.
		$el.data('sel', $el.data('opts').filter((o) => sel.has(o)));
		$(this).closest('.ca-ms-opt').toggleClass('on', this.checked);
		$el.find('.ca-ms-count').text(__('{0} of {1} selected', [$el.data('sel').length, $el.data('opts').length]));
		changed();
	});
	$el.find('.ca-ms-tools').on('click', 'button', function () {
		if ($(this).data('a') === 'clear') {
			$el.data('sel', []);
		} else {
			// "Select all" applies to what the search currently shows.
			const q = $el.find('.ca-ms-search').val().trim().toLowerCase();
			const sel = new Set($el.data('sel'));
			$el.data('opts').filter((o) => !q || o.toLowerCase().includes(q)).forEach((o) => sel.add(o));
			$el.data('sel', $el.data('opts').filter((o) => sel.has(o)));
		}
		ca_ms_render($el);
		changed();
	});
	if (options) ca_ms_set($el, options);
	else ca_ms_render($el);
}

// --- Searchable single-select for the entry form -------------------------
// Wraps a native <select> (hidden, still the source of truth) with a button and a
// search menu in the same look as the filter dropdowns above. Everything that reads
// or refills the <select> keeps working; ca_ss_sync() repaints the button afterwards.
const CA_SS_IDS = ['ca-f-from', 'ca-f-to', 'ca-f-pg', 'ca-f-sg'];
function ca_ss_opts($sel) {
	// The blank option is a placeholder, except where "no value" is a real choice.
	return $sel
		.find('option')
		.map(function () {
			return { v: this.value, t: $(this).text() };
		})
		.get()
		.filter((o) => o.v !== '' || $sel.data('clearable'));
}
function ca_ss_sync($sel) {
	const $w = $sel.next('.ca-ss');
	if (!$w.length) return;
	const $o = $sel.find('option:selected');
	$w.find('.ca-ms-txt').text($o.text()).toggleClass('ca-ss-val', ($sel.val() || '') !== '');
	$w.find('.ca-ms-btn').prop('disabled', $sel.prop('disabled')).attr('title', $o.text());
}
function ca_ss_mark_active($w, i) {
	const $opts = $w.find('.ca-ss-opt');
	if (!$opts.length) return;
	i = Math.max(0, Math.min(i, $opts.length - 1));
	$w.data('act', i);
	$opts.removeClass('act').eq(i).addClass('act')[0].scrollIntoView({ block: 'nearest' });
}
function ca_ss_render($sel) {
	const $w = $sel.next('.ca-ss');
	const esc = frappe.utils.escape_html;
	const q = $w.find('.ca-ss-search').val().trim().toLowerCase();
	const cur = $sel.val() || '';
	const shown = ca_ss_opts($sel).filter((o) => !q || o.t.toLowerCase().includes(q));
	$w.find('.ca-ms-list').html(
		shown.length
			? shown
					.map(
						(o) =>
							`<div class="ca-ms-opt ca-ss-opt${o.v === cur ? ' on' : ''}" role="option" aria-selected="${o.v === cur}" data-v="${esc(o.v)}">${ca_ms_mark(o.t, q)}</div>`
					)
					.join('')
			: `<div class="ca-ms-none">${esc(__('No match'))}</div>`
	);
	// Start on the current pick, or on the first match while searching.
	const at = q ? 0 : Math.max(0, shown.findIndex((o) => o.v === cur));
	ca_ss_mark_active($w, at);
}
function ca_ss_init($body, id, clearable) {
	const $sel = $body.find('#' + id);
	$sel.data('clearable', !!clearable).addClass('ca-ss-native').attr('tabindex', '-1');
	const $w = $(`<div class="ca-ms ca-ss">
		<button type="button" class="ca-ms-btn" aria-haspopup="listbox" aria-expanded="false"><span class="ca-ms-txt"></span><span class="ca-ms-car">${CA_CARET}</span></button>
		<div class="ca-ms-menu" hidden>
			<div class="ca-ms-sw">${CA_SEARCH_ICO}<input type="search" class="ca-ss-search" placeholder="${frappe.utils.escape_html(__('Search…'))}" autocomplete="off"></div>
			<div class="ca-ms-list" role="listbox"></div>
		</div>
	</div>`);
	$sel.after($w);
	const $btn = $w.find('.ca-ms-btn');
	const $menu = $w.find('.ca-ms-menu');
	const $search = $w.find('.ca-ss-search');

	const open = () => {
		ca_ms_close_all();
		$menu.prop('hidden', false).removeClass('right');
		if ($menu[0].getBoundingClientRect().right > window.innerWidth - 8) $menu.addClass('right');
		$btn.attr('aria-expanded', 'true');
		$search.val('');
		ca_ss_render($sel);
		$search.trigger('focus');
	};
	const pick = (v) => {
		ca_ms_close_all();
		if (($sel.val() || '') !== v) $sel.val(v).trigger('change');
		ca_ss_sync($sel);
		$btn.trigger('focus');
	};

	$btn.on('click', (ev) => {
		ev.stopPropagation();
		if ($menu.prop('hidden')) open();
		else ca_ms_close_all();
	});
	$btn.on('keydown', (ev) => {
		if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(ev.key)) {
			ev.preventDefault();
			open();
		}
	});
	$menu.on('click', (ev) => ev.stopPropagation());
	$menu.on('click', '.ca-ss-opt', function () {
		pick($(this).attr('data-v'));
	});
	$search.on('input', () => ca_ss_render($sel));
	$search.on('keydown', (ev) => {
		const i = $w.data('act') || 0;
		if (ev.key === 'ArrowDown') {
			ev.preventDefault();
			ca_ss_mark_active($w, i + 1);
		} else if (ev.key === 'ArrowUp') {
			ev.preventDefault();
			ca_ss_mark_active($w, i - 1);
		} else if (ev.key === 'Enter') {
			ev.preventDefault();
			const $a = $w.find('.ca-ss-opt.act');
			if ($a.length) pick($a.attr('data-v'));
		} else if (ev.key === 'Escape' || ev.key === 'Tab') {
			ca_ms_close_all();
			if (ev.key === 'Escape') $btn.trigger('focus');
		}
	});
	// The native <select> is hidden, so its label would focus nothing: send it to the button.
	$body.find(`label[for="${id}"]`).on('click', () => $btn.trigger('focus'));
	ca_ss_sync($sel);
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
	CA_SS_IDS.forEach((id) => ca_ss_sync($body.find('#' + id)));
}
function fill_ca_subs(page, sel) {
	const $body = $(page.body);
	const g = ca_grp(page, $body.find('#ca-f-pg').val());
	const subs = g ? g.subs.slice() : [];
	if (sel && !subs.includes(sel) && $body.find('#ca-f-pg').val()) subs.push(sel);
	$body.find('#ca-f-sg').html(ca_opts(subs, sel, g ? 'Select secondary group' : 'Pick a primary group first'));
	$body.find('#ca-f-sg').prop('disabled', !g);
	ca_ss_sync($body.find('#ca-f-sg'));
}
function fill_ca_filter_selects(page) {
	const $body = $(page.body);
	const M = page.ca.state.masters;
	const txns = page.ca.state.txns || [];
	const set = (id, list) => ca_ms_set($body.find('#' + id), list);
	const cos = [...new Set([...M.companies, ...txns.map((t) => t.from).filter(Boolean)])];
	set('ca-q-from', cos);
	const pgs = [...new Set([...M.groups.map((g) => g.name), ...txns.map((t) => t.pg)])];
	set('ca-q-pg', pgs);
	set('ca-r-pg', pgs);
	const fys = [...new Set([...M.fiscal_years, ...txns.map((t) => t.fy).filter(Boolean)])];
	set('ca-q-fy', fys);
	set('ca-r-fy', fys);
	const months = [...new Set([...(M.months || []), ...txns.map((t) => t.month).filter(Boolean)])];
	set('ca-q-month', months);
	set('ca-r-month', months);
	ca_refresh_sg(page, 'q');
	ca_refresh_sg(page, 'r');
	ca_filters_sync(page, 'q');
	ca_filters_sync(page, 'r');
}
// Secondary-group choices follow the Primary groups picked in the same filter
// bar (all of them when none is picked). Picks no longer offered are dropped.
function ca_refresh_sg(page, scope) {
	const $body = $(page.body);
	const M = page.ca.state.masters;
	const txns = page.ca.state.txns || [];
	const pgs = ca_ms_val($body, `ca-${scope}-pg`);
	const inScope = (name) => !pgs.length || pgs.includes(name);
	const subs = [
		...M.groups.filter((g) => inScope(g.name)).flatMap((g) => g.subs),
		...txns.filter((t) => inScope(t.pg)).map((t) => t.sg),
	].filter(Boolean);
	ca_ms_set($body.find(`#ca-${scope}-sg`), [...new Set(subs)]);
}
const CA_FILTER_IDS = {
	q: ['ca-q-type', 'ca-q-from', 'ca-q-pg', 'ca-q-sg', 'ca-q-fy', 'ca-q-month'],
	r: ['ca-r-type', 'ca-r-pg', 'ca-r-sg', 'ca-r-fy', 'ca-r-month'],
};
// Show "Clear filters" only while something is filtered.
function ca_filters_sync(page, scope) {
	const $body = $(page.body);
	let active = CA_FILTER_IDS[scope].some((id) => ca_ms_val($body, id).length);
	$body.find(`#ca-${scope}-reset`).prop('hidden', !active);
}
function ca_filters_reset(page, scope) {
	const $body = $(page.body);
	CA_FILTER_IDS[scope].forEach((id) => {
		const $el = $body.find('#' + id);
		$el.data('sel', []);
		ca_ms_render($el);
	});
	ca_refresh_sg(page, scope);
	ca_filters_sync(page, scope);
	if (scope === 'q') render_ca_register(page);
	else render_ca_reports(page);
}

// --- Form -----------------------------------------------------------
function sync_ca_amounts(page) {
	const $body = $(page.body);
	const dr = ca_parse_amt($body.find('#ca-f-dr').val());
	const cr = ca_parse_amt($body.find('#ca-f-cr').val());
	$body.find('#ca-f-cr').prop('disabled', dr > 0);
	$body.find('#ca-f-dr').prop('disabled', cr > 0);
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
	const ty = ca_ms_val($body, 'ca-q-type');
	const fr = ca_ms_val($body, 'ca-q-from');
	const pg = ca_ms_val($body, 'ca-q-pg');
	const sg = ca_ms_val($body, 'ca-q-sg');
	const fy = ca_ms_val($body, 'ca-q-fy');
	const mo = ca_ms_val($body, 'ca-q-month');
	return state.txns.filter(
		(t) =>
			(!ty.length || ty.includes(t.type)) &&
			(!fr.length || fr.includes(t.from)) &&
			(!pg.length || pg.includes(t.pg)) &&
			(!sg.length || sg.includes(t.sg)) &&
			(!fy.length || fy.includes(t.fy)) &&
			(!mo.length || mo.includes(t.month))
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
		$body.find('#ca-reg-body').html(`<tr><td colspan="9" class="ca-empty">No transactions yet. Add the first one with the form, or import your elimination sheet.</td></tr>`);
		$body.find('#ca-reg-foot').html('');
		return;
	}
	if (!rows.length) {
		$body.find('#ca-reg-body').html(`<tr><td colspan="9" class="ca-empty">No transactions match these filters.</td></tr>`);
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
				const esc = frappe.utils.escape_html;
				return `<tr class="${state.editing === t.id ? 'editing' : ''}">
					<td class="ca-txid">${ca_txn_label(t)}</td>
					<td class="c-ft"><span class="ca-ft" title="${esc(t.from)}${t.to ? ' → ' + esc(t.to) : ''}"><b>${esc(t.from)}</b>${t.to ? ` <span class="ca-arrow">→</span> ${esc(t.to)}` : ' <span class="ca-muted">(no counterparty)</span>'}</span>${t.narration ? `<span class="ca-sub" title="${esc(t.narration)}">${esc(t.narration)}</span>` : ''}</td>
					<td class="ca-nw">${esc(t.fy || '')}<span class="ca-sub">${esc((t.month || '').slice(0, 3))}</span></td>
					<td class="c-pg" title="${esc(t.pg)}">${esc(t.pg)}</td>
					<td class="c-sg" title="${esc(t.sg)}">${esc(t.sg)}${bad ? '<span class="ca-sub neg">Not in current master</span>' : ''}${t.ref ? `<span class="ca-sub" title="${esc(t.ref)}">Ref: ${esc(t.ref)}</span>` : ''}</td>
					<td><span class="ca-pill ${esc(t.type)}">${esc(t.type)}</span></td>
					<td class="n">${ca_fmt(state, t.debit)}</td><td class="n">${ca_fmt(state, t.credit)}</td>
					<td><div class="ca-acts">${acts}</div></td></tr>`;
			})
			.join('')
	);
	const dr = rows.reduce((a, t) => a + (t.debit || 0), 0);
	const cr = rows.reduce((a, t) => a + (t.credit || 0), 0);
	$body.find('#ca-reg-foot').html(
		`<tr class="tot"><td colspan="6">${rows.length} of ${state.txns.length} transactions · Net ${ca_fmt_net(state, dr - cr)}</td><td class="n">${ca_fmt(state, dr)}</td><td class="n">${ca_fmt(state, cr)}</td><td></td></tr>`
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
	const val = (id) => {
		const v = ca_ms_val($body, id);
		return v.length ? v : undefined;
	};
	return {
		adj_type: val('ca-r-type'),
		primary_group: val('ca-r-pg'),
		secondary_group: val('ca-r-sg'),
		fiscal_year: val('ca-r-fy'),
		month: val('ca-r-month'),
	};
}
function render_ca_reports(page) {
	const { state } = page.ca;
	const $body = $(page.body);
	const kind = $body.find('#ca-r-kind').val();
	const u = CA_UNITS[state.unit].lab;
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
	.ca-wrap{--ca-shadow:0 1px 2px rgba(15,32,46,.05),0 1px 3px rgba(15,32,46,.04);--ca-r:10px;color:var(--ca-ink);font-size:14px;line-height:1.45;font-variant-numeric:tabular-nums}
	.dark .ca-wrap,[data-theme="dark"] .ca-wrap{--ca-shadow:0 1px 2px rgba(0,0,0,.35)}
	.ca-wrap *{box-sizing:border-box}

	/* ---- top bar: unit switch + view tabs ---- */
	.ca-filters{display:flex;flex-wrap:wrap;gap:10px 20px;align-items:center;padding:4px 0 0;margin-bottom:14px;border-bottom:1px solid var(--ca-line)}
	.ca-field{display:flex;align-items:center;gap:10px;padding-bottom:6px}
	.ca-field label{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--ca-muted);font-weight:600;margin:0}
	.ca-spacer{flex:1}
	.ca-seg{display:inline-flex;padding:3px;gap:2px;border:1px solid var(--ca-line);border-radius:9px;background:var(--ca-row-alt)}
	.ca-seg button{border:0;background:transparent;color:var(--ca-muted);font:500 12.5px inherit;padding:5px 12px;border-radius:6px;cursor:pointer;transition:background .12s,color .12s}
	.ca-seg button:hover{color:var(--ca-ink)}
	.ca-seg button[aria-pressed="true"]{background:var(--ca-surface);color:var(--ca-accent);font-weight:600;box-shadow:0 1px 2px rgba(15,32,46,.12)}
	nav.ca-tabs{display:flex;gap:2px}
	nav.ca-tabs button{border:0;background:none;color:var(--ca-muted);font:500 14px inherit;padding:10px 16px;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .12s,border-color .12s}
	nav.ca-tabs button:hover{color:var(--ca-ink)}
	nav.ca-tabs button[aria-selected="true"]{color:var(--ca-accent);font-weight:600;border-bottom-color:var(--ca-accent)}

	/* ---- KPI cards ---- */
	.ca-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:0 0 16px}
	.ca-kpi{position:relative;background:var(--ca-surface);border:1px solid var(--ca-line);border-radius:var(--ca-r);padding:12px 16px 12px 19px;box-shadow:var(--ca-shadow);overflow:hidden}
	.ca-kpi::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--ca-line-strong)}
	.ca-kpi.ok::before{background:var(--ca-ok)} .ca-kpi.bad::before{background:var(--ca-bad)}
	.ca-kpi .l{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--ca-muted);font-weight:600}
	.ca-kpi .v{font:600 20px/1.25 inherit;margin-top:4px;letter-spacing:-.01em}
	.ca-kpi .s{font-size:12px;color:var(--ca-muted);margin-top:1px}
	.ca-kpi.bad .v{color:var(--ca-bad)} .ca-kpi.ok .v{color:var(--ca-ok)}

	/* ---- layout + panels ---- */
	.ca-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:16px;align-items:start}
	/* The entry form always sits above the register as a wide 4-column grid, so the
	   register keeps the full width. .ca-row2 wrappers are flattened; each .ca-fld
	   keeps its label above the control. Row 2 holds Primary group, Secondary group,
	   Debit and Credit on a single line. */
	.ca-grid>.ca-panel:first-child form{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px 16px;align-items:start}
	.ca-grid>.ca-panel:first-child .ca-row2{display:contents}
	.ca-grid>.ca-panel:first-child .ca-fld{margin-top:0!important}
	.ca-grid>.ca-panel:first-child .ca-fld label{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
	.ca-grid>.ca-panel:first-child .ca-errs{grid-column:1/-1;margin-top:0}
	/* Last row: Adjustment type, Description, Reference and the buttons share one line. */
	.ca-grid>.ca-panel:first-child .ca-btns{margin:0;align-self:end;flex-wrap:nowrap}
	.ca-grid>.ca-panel:first-child .ca-btns .ca-btn{height:38px;white-space:nowrap}
	.ca-grid>.ca-panel:first-child .ca-btns .ca-btn.pri{flex:1}
	#ca-f-narr{min-height:38px;height:38px}
	/* Below 1100px the buttons no longer fit beside the three fields: they get their own row. */
	@media (max-width:1099px){.ca-grid>.ca-panel:first-child .ca-btns{grid-column:1/-1;margin-top:4px}.ca-grid>.ca-panel:first-child .ca-btns .ca-btn.pri{flex:none;min-width:160px}}
	/* Four columns hold down to tablet width so Primary / Secondary group and
	   Debit / Credit stay on one line; the "(or Credit)" hints drop out first. */
	@media (max-width:900px){.ca-grid>.ca-panel:first-child form{gap:12px 10px}.ca-grid>.ca-panel:first-child .ca-fld label .ca-muted{display:none}}
	@media (max-width:700px){.ca-grid>.ca-panel:first-child form{grid-template-columns:repeat(2,minmax(0,1fr))}.ca-grid>.ca-panel:first-child .ca-fld label .ca-muted{display:inline}}
	@media (max-width:560px){.ca-grid>.ca-panel:first-child form{grid-template-columns:minmax(0,1fr)}}
	.ca-panel{background:var(--ca-surface);border:1px solid var(--ca-line);border-radius:var(--ca-r);box-shadow:var(--ca-shadow);min-width:0}
	.ca-panel>.ca-hd:first-child,.ca-panel>.ca-filters2:first-child{border-top-left-radius:var(--ca-r);border-top-right-radius:var(--ca-r)}
	.ca-hd{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid var(--ca-line)}
	.ca-hd h2{font-weight:600;font-size:15px;margin:0;letter-spacing:-.005em}
	.ca-bd{padding:16px}

	/* ---- entry form ---- */
	.ca-row2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
	.ca-fld{display:flex;flex-direction:column;gap:5px;min-width:0}
	.ca-fld label{font-size:12px;color:var(--ca-muted);font-weight:500;margin:0}
	.ca-req{color:var(--ca-bad);font-weight:700}
	.ca-wrap input:not([type=checkbox]),.ca-wrap select,.ca-wrap textarea{font:14px inherit;color:var(--ca-ink);background-color:var(--ca-surface);border:1px solid var(--ca-line-strong);border-radius:8px;padding:8px 10px;width:100%;min-width:0;height:auto;box-shadow:none;transition:border-color .12s,box-shadow .12s}
	.ca-wrap input:not([type=checkbox]):hover,.ca-wrap select:hover,.ca-wrap textarea:hover{border-color:var(--ca-muted)}
	.ca-wrap input:not([type=checkbox]):focus,.ca-wrap select:focus,.ca-wrap textarea:focus{outline:none;border-color:var(--ca-accent);box-shadow:0 0 0 3px var(--ca-accent-soft)}
	.ca-wrap select{-webkit-appearance:none;appearance:none;padding-right:30px;cursor:pointer;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M2.5 4.5 6 8l3.5-3.5' fill='none' stroke='%2393a2af' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 10px center}
	.ca-wrap select:disabled{cursor:not-allowed}
	.ca-wrap input.ca-num{text-align:right;font-weight:500}
	.ca-wrap input::placeholder,.ca-wrap textarea::placeholder{color:var(--ca-muted);opacity:.6}
	.ca-wrap input:disabled,.ca-wrap select:disabled{background-color:var(--ca-row-alt);color:var(--ca-muted)}
	.ca-wrap textarea{resize:vertical;min-height:60px}
	.ca-txid{font:600 12px inherit;color:var(--ca-muted);letter-spacing:.02em}
	.ca-errs{margin-top:12px;padding:10px 12px;border-radius:8px;border:1px solid var(--ca-bad);background:var(--ca-bad-bg);color:var(--ca-bad);font-size:13px}
	.ca-errs ul{margin:0;padding-left:18px}
	.ca-btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
	.ca-btn{font:500 13px inherit;padding:8px 14px;border-radius:8px;border:1px solid var(--ca-line-strong);background:var(--ca-surface);color:var(--ca-ink);cursor:pointer;line-height:1.2;transition:background .12s,border-color .12s,box-shadow .12s}
	.ca-btn:hover{background:var(--ca-row-alt);border-color:var(--ca-muted)}
	.ca-btn:focus-visible{outline:none;box-shadow:0 0 0 3px var(--ca-accent-soft);border-color:var(--ca-accent)}
	.ca-btn.pri{background:var(--ca-accent);border-color:var(--ca-accent);color:var(--ca-accent-ink);font-weight:600}
	.ca-btn.pri:hover{filter:brightness(1.08);background:var(--ca-accent)}
	.ca-btn.danger{background:var(--ca-bad);border-color:var(--ca-bad);color:#fff}
	.ca-btn.danger:hover{background:var(--ca-bad);filter:brightness(1.08)}
	.ca-btn.sm{padding:6px 11px;font-size:12px}
	.ca-btn:disabled{opacity:.5;cursor:not-allowed}
	.ca-hd .ca-btns{gap:6px}

	/* ---- filter bar ---- */
	.ca-filters2{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px 14px;align-items:end;padding:14px 16px;background:var(--ca-row-alt);border-bottom:1px solid var(--ca-line)}
	.ca-ff{display:flex;flex-direction:column;gap:5px;min-width:0}
	.ca-ff-kind{grid-column:span 2}
	@media (max-width:700px){.ca-ff-kind{grid-column:auto}}
	.ca-ms-lab{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--ca-muted)}
	.ca-reset{align-self:end;justify-self:start;border:1px dashed var(--ca-line-strong);background:transparent;color:var(--ca-accent);font:600 12px inherit;border-radius:8px;padding:9px 12px;cursor:pointer;line-height:1.2;transition:background .12s,border-color .12s}
	.ca-reset:hover{background:var(--ca-accent-soft);border-color:var(--ca-accent)}
	.ca-reset[hidden]{display:none}

	/* ---- tables (register + reports) ---- */
	.ca-tblwrap{overflow-x:auto}
	.ca-wrap table{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}
	.ca-wrap th,.ca-wrap td{padding:10px 12px;border-bottom:1px solid var(--ca-line);text-align:left;vertical-align:top}
	.ca-wrap th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--ca-muted);font-weight:600;background:var(--ca-row-alt);position:sticky;top:0;z-index:2;white-space:nowrap;border-bottom:1px solid var(--ca-line-strong)}
	.ca-wrap td.n,.ca-wrap th.n{text-align:right;white-space:nowrap}
	.ca-wrap td.n{font-weight:500}
	.ca-wrap tbody tr:hover td{background:var(--ca-row-alt)}
	.ca-wrap tr.editing td{background:var(--ca-accent-soft)!important;box-shadow:inset 3px 0 0 var(--ca-accent)}
	.ca-wrap tbody tr:last-child td{border-bottom:0}
	.ca-sub{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;color:var(--ca-muted);font-size:12px;margin-top:3px;max-width:340px;font-weight:400}
	.ca-wrap tr.grp td{font-weight:600;background:var(--ca-row-alt)}
	.ca-wrap tr.stmt td{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--ca-accent);font-weight:700;background:var(--ca-surface);padding-top:18px;border-bottom:1px solid var(--ca-line-strong)}
	.ca-wrap tr.tot td{font-weight:700;background:var(--ca-row-alt);border-top:1px solid var(--ca-line-strong);border-bottom:0}
	.ca-wrap tfoot td{position:sticky;bottom:0;z-index:1}
	/* register: fixed-ish column sizing keeps every row to one or two lines */
	#ca-reg{table-layout:auto}
	#ca-reg th,#ca-reg td{padding:9px 8px;vertical-align:middle}
	#ca-reg th:first-child,#ca-reg td:first-child{padding-left:14px}
	#ca-reg td:nth-child(1),#ca-reg td:nth-child(3),#ca-reg td:nth-child(6),#ca-reg td:nth-child(9),.ca-nw{white-space:nowrap}
	#ca-reg td.c-ft{min-width:200px;max-width:280px}
	#ca-reg td.c-pg{min-width:110px;max-width:170px}
	#ca-reg td.c-sg{min-width:130px;max-width:190px}
	#ca-reg .ca-icon{padding:4px 6px}
	#ca-reg .ca-pill{padding:3px 8px}
	#ca-reg td.c-pg,#ca-reg td.c-sg{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
	.ca-ft{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
	.ca-ft b{font-weight:600}
	.ca-arrow{color:var(--ca-muted);margin:0 2px}
	#ca-reg .ca-sub{max-width:none;white-space:nowrap;display:block;overflow:hidden;text-overflow:ellipsis;-webkit-line-clamp:unset}
	#ca-reg td.ca-txid{color:var(--ca-accent);font-weight:600}
	.ca-pill{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;padding:3px 9px;border-radius:999px;white-space:nowrap;line-height:1.2}
	.ca-pill::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor;opacity:.7}
	.ca-pill.Elimination{background:var(--ca-elim-bg);color:var(--ca-elim-fg)}
	.ca-pill.Regrouping{background:var(--ca-reg-bg);color:var(--ca-reg-fg)}
	.ca-pill.ok{background:var(--ca-ok-bg);color:var(--ca-ok)} .ca-pill.bad{background:var(--ca-bad-bg);color:var(--ca-bad)}
	.ca-acts{display:flex;gap:2px;white-space:nowrap}
	.ca-icon{border:1px solid transparent;background:none;color:var(--ca-muted);cursor:pointer;padding:4px 9px;border-radius:6px;font:500 12px inherit;transition:background .12s,color .12s}
	.ca-icon:hover{background:var(--ca-accent-soft);color:var(--ca-accent)}
	.ca-icon.del:hover{background:var(--ca-bad-bg);color:var(--ca-bad)}
	.ca-icon:focus-visible{outline:none;border-color:var(--ca-accent)}
	.ca-empty,.ca-loading{padding:40px 16px;text-align:center;color:var(--ca-muted)}
	.ca-muted{color:var(--ca-muted)} .neg{color:var(--ca-bad)}

	/* ---- multi-select filter ---- */
	.ca-ms{position:relative}
	.ca-ms-btn{display:flex;align-items:center;gap:8px;width:100%;text-align:left;font:14px inherit;color:var(--ca-ink);background:var(--ca-surface);border:1px solid var(--ca-line-strong);border-radius:8px;padding:8px 10px;cursor:pointer;line-height:1.35;transition:border-color .12s,box-shadow .12s,background .12s}
	.ca-ms-btn:hover{border-color:var(--ca-muted)}
	.ca-ms-btn:focus-visible,.ca-ms-btn[aria-expanded="true"]{outline:none;border-color:var(--ca-accent);box-shadow:0 0 0 3px var(--ca-accent-soft)}
	.ca-ms-txt{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--ca-muted)}
	.ca-ms.has .ca-ms-btn{background:var(--ca-accent-soft);border-color:var(--ca-accent)}
	.ca-ms.has .ca-ms-txt{color:var(--ca-ink);font-weight:500}
	.ca-ms-badge{flex:none;font:600 11px inherit;line-height:1;padding:3px 7px;border-radius:999px;background:var(--ca-accent);color:var(--ca-accent-ink)}
	.ca-ms-badge[hidden]{display:none}
	.ca-ms-car{flex:none;display:flex;color:var(--ca-muted);transition:transform .15s}
	.ca-ms-btn[aria-expanded="true"] .ca-ms-car{transform:rotate(180deg)}
	.ca-ms-menu{position:absolute;z-index:30;top:calc(100% + 6px);left:0;min-width:max(100%,260px);width:max-content;max-width:min(380px,92vw);background:var(--ca-surface);border:1px solid var(--ca-line-strong);border-radius:10px;box-shadow:0 12px 32px rgba(15,32,46,.18);padding:10px}
	.ca-ms-menu.right{left:auto;right:0}
	.ca-ms-menu[hidden]{display:none}
	.ca-ms-sw{position:relative;display:flex;align-items:center}
	.ca-ms-sw svg{position:absolute;left:10px;color:var(--ca-muted);pointer-events:none}
	.ca-wrap .ca-ms-sw input{padding-left:30px}
	.ca-ms-tools{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:8px 2px 4px;font-size:12px;color:var(--ca-muted)}
	.ca-ms-tools button{border:0;background:none;color:var(--ca-accent);font:600 12px inherit;cursor:pointer;padding:2px 6px;border-radius:5px}
	.ca-ms-tools button:hover{background:var(--ca-accent-soft)}
	.ca-ms-list{max-height:260px;overflow:auto;margin:0 -4px;padding:0 4px}
	.ca-ms-opt{display:flex;align-items:center;gap:9px;padding:6px 8px;border-radius:6px;cursor:pointer;font-size:13px;line-height:1.3;margin:0;font-weight:400;color:var(--ca-ink)}
	.ca-ms-opt:hover{background:var(--ca-row-alt)}
	.ca-ms-opt.on{background:var(--ca-accent-soft);font-weight:500}
	.ca-ms-opt mark{background:#ffe9a8;color:#15202b;border-radius:2px;padding:0 1px}
	.ca-wrap .ca-ms-opt input[type=checkbox]{-webkit-appearance:none;appearance:none;position:relative;flex:none;width:16px;height:16px;min-width:16px;margin:0;padding:0;border:1.5px solid var(--ca-line-strong);border-radius:3px;background:var(--ca-surface);cursor:pointer;transition:background .1s,border-color .1s}
	.ca-wrap .ca-ms-opt input[type=checkbox]:hover{border-color:var(--ca-accent)}
	.ca-wrap .ca-ms-opt input[type=checkbox]:checked{background:var(--ca-accent);border-color:var(--ca-accent)}
	.ca-wrap .ca-ms-opt input[type=checkbox]:checked::after{content:"";position:absolute;left:4px;top:1px;width:4px;height:8px;border:solid var(--ca-accent-ink);border-width:0 2px 2px 0;transform:rotate(45deg)}
	.ca-wrap .ca-ms-opt input[type=checkbox]:focus-visible{outline:2px solid var(--ca-accent);outline-offset:2px}
	.ca-ms-none{padding:14px 8px;color:var(--ca-muted);font-size:13px;text-align:center}
	.ca-wrap select.ca-ss-native{display:none}
	.ca-ss .ca-ms-txt.ca-ss-val{color:var(--ca-ink);font-weight:500}
	.ca-ss .ca-ms-btn:disabled{background:var(--ca-row-alt);cursor:not-allowed}
	.ca-ss .ca-ms-list{margin-top:8px}
	.ca-ss-opt.act{background:var(--ca-row-alt)}
	.ca-ss-opt.on.act{background:var(--ca-accent-soft)}

	/* ---- report extras / footer / import dialog ---- */
	.ca-matrix td,.ca-matrix th{font-size:12px}
	.ca-matrix th.rh,.ca-matrix td.rh{position:sticky;left:0;background:var(--ca-surface);z-index:1}
	.ca-matrix th.rh{z-index:3;background:var(--ca-row-alt)}
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
