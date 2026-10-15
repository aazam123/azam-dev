// Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt

// Spreadsheet-style view of one FR Financial Report: every section is a sheet, drawn as a grid with
// column letters, row numbers, range selection and a status bar. Route: /app/financial-report-excel-view[/<FR Financial Report name>]
frappe.pages["financial-report-excel-view"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "",
		single_column: true,
	});
	$(wrapper).addClass("xv-page");
	wrapper.excel_view = new FinancialReportExcelView(page);
};

frappe.pages["financial-report-excel-view"].on_page_show = function (wrapper) {
	const name = frappe.get_route()[1];
	if (name) wrapper.excel_view.open(decodeURIComponent(name));
};

const STATEMENT_TYPES = ["Profit & Loss", "Balance Sheet", "Cash Flow", "Equity"];
const NUMBER = /^\(?-?[\d,]+(\.\d+)?\)?%?$/;
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const REPORT_TYPES = ["Monthly", "Yearly", "MIS"];

class FinancialReportExcelView {
	constructor(page) {
		this.page = page;
		this.name = null;
		this.doc = null;
		this.sheets = [];
		this.active = 0;
		this.sel = null; // {r1, c1, r2, c2} in sheet coordinates; anchor = (r1, c1), focus = (r2, c2)
		this.hits = [];
		this.hit_index = -1;
		this.add_styles();

		// One filter row: Company, Fiscal Year, Month narrow down the Financial Report; Generate sits on the same line.
		this.company_field = page.add_field({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			change: () => this.find_report(),
		});
		this.fiscal_year_field = page.add_field({
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			change: () => this.find_report(),
		});
		this.month_field = page.add_field({
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			options: ["", ...MONTHS],
			change: () => this.find_report(),
		});
		this.report_type_field = page.add_field({
			fieldname: "report_type",
			label: __("Report Type"),
			fieldtype: "Select",
			options: ["", ...REPORT_TYPES],
			change: () => this.report_type_changed(),
		});
		this.report_field = page.add_field({
			fieldname: "financial_report",
			label: __("Financial Report"),
			fieldtype: "Link",
			options: "FR Financial Report",
			get_query: () => ({ filters: this.filters() }),
			change: () => {
				const value = this.report_field.get_value();
				if (value && value !== this.name) this.open(value);
			},
		});
		// Generates the report that is open (disabled until one is loaded)
		this.generate_field = page.add_field({
			fieldname: "generate",
			label: __("Generate"),
			fieldtype: "Button",
			primary: 1,
			click: () => this.generate(),
		});
		this.$generate = this.generate_field.$input.prop("disabled", true).attr("title", __("Generate (or regenerate) the open Financial Report"));

		this.$body = $(`
			<div class="xv">
				<div class="xv-top">
					<div class="xv-summary"></div>
					<div class="xv-tools">
						<span class="xv-find-wrap">
							<input type="search" class="xv-find form-control input-xs" placeholder="${__("Find in sheet")}" />
							<span class="xv-find-count"></span>
							<button type="button" class="xv-btn xv-find-prev" title="${__("Previous match")}">&uarr;</button>
							<button type="button" class="xv-btn xv-find-next" title="${__("Next match")}">&darr;</button>
						</span>
						<button type="button" class="xv-btn xv-copy" title="${__("Copy selection (or whole sheet)")}">${__("Copy")}</button>
						<button type="button" class="xv-btn xv-csv" title="${__("Download this sheet as CSV")}">CSV</button>
						<button type="button" class="xv-btn xv-excel" title="${__("Export the whole report as an Excel workbook")}" disabled>${__("Excel")}</button>
					</div>
				</div>
				<div class="xv-formula"><span class="xv-ref">&nbsp;</span><span class="xv-fx">fx</span><span class="xv-val"></span></div>
				<div class="xv-grid" tabindex="0"></div>
				<div class="xv-bottom">
					<input type="search" class="xv-side-search" placeholder="${__("Search sheets")}" />
					<nav class="xv-nav"></nav>
					<div class="xv-status"><span class="xv-stat-left"></span><span class="xv-zoom"><button type="button" class="xv-zbtn xv-zoom-out" title="${__("Zoom out")}">&minus;</button><span class="xv-zoom-val">100%</span><button type="button" class="xv-zbtn xv-zoom-in" title="${__("Zoom in")}">+</button></span></div>
				</div>
			</div>`).appendTo(page.body);

		const q = (s) => this.$body.find(s);
		this.$summary = q(".xv-summary");
		this.$nav = q(".xv-nav");
		this.$side_search = q(".xv-side-search");
		this.$find = q(".xv-find");
		this.$find_count = q(".xv-find-count");
		this.$ref = q(".xv-ref");
		this.$val = q(".xv-val");
		this.$grid = q(".xv-grid");
		this.$stat_left = q(".xv-stat-left");
		this.$excel = q(".xv-excel");
		this.$zoom_val = q(".xv-zoom-val");
		this.zoom = 1;
		this.message(__("Select a Financial Report to view it as a spreadsheet."));
		this.bind_events();
		this.listen_generation();
	}

	message(text) {
		this.$grid.html(`<div class="xv-msg">${frappe.utils.escape_html(text)}</div>`);
		this.$nav.empty();
		this.$stat_left.empty();
	}

	open(name) {
		if (name === this.name && this.sheets.length) return;
		this.name = name;
		this.report_field.set_value(name);
		this.$excel.prop("disabled", true);
		this.$generate.prop("disabled", true);
		this.$summary.empty();
		this.message(__("Loading..."));
		frappe
			.xcall("frappe.client.get", { doctype: "FR Financial Report", name })
			.then((doc) => {
				if (name !== this.name) return;
				this.doc = doc;
				this.show_filters(doc);
				this.$generate.prop("disabled", false); // also enabled for an empty report: that is when it is needed most
				this.render_summary(doc);
				this.sheets = (doc.financial_report_details || []).map((row, i) => this.build_sheet(row, i));
				this.active = 0;
				if (!this.sheets.length) return this.message(__("This report has no financial details yet. Generate it first."));
				this.$excel.prop("disabled", false);
				this.render_nav();
				this.show_sheet(0);
			})
			.catch(() => {
				this.name = null;
				this.doc = null;
				this.sheets = [];
				this.$summary.empty();
				this.message(__("Could not load the report."));
			});
	}

	// --- model ---------------------------------------------------------------------------------

	// One section -> {title, kind, note, rows: [{cells: [{t, th, cs, rs, bold, bg}], text}], width}
	build_sheet(row, index) {
		const note = row.note_no ? String(row.note_no).trim() : "";
		const title = note
			? `Note ${note} ${row.section || ""}`.trim()
			: row.section || row.section_type || `Sheet ${index + 1}`;
		const kind = STATEMENT_TYPES.includes(row.section_type) ? "statement" : note ? "note" : "info";
		const doc = new DOMParser().parseFromString(`<div>${row.section_description || ""}</div>`, "text/html");
		const rows = [];
		const walk = (el) => {
			if (el.tagName === "TABLE") return this.read_table(el, rows);
			if (el.querySelector("table")) return [...el.children].forEach(walk);
			const text = el.textContent.replace(/\s+/g, " ").trim();
			if (text) rows.push({ text });
		};
		[...doc.body.firstElementChild.children].forEach(walk);
		const sheet = { title, kind, note, rows, index };
		sheet.width = this.layout(rows);
		sheet.note_col = this.find_note_column(rows);
		return sheet;
	}

	read_table(table, rows) {
		const own = [...table.querySelectorAll("tr")].filter((tr) => tr.closest("table") === table);
		own.forEach((tr) => {
			const cells = [...tr.children]
				.filter((c) => /^(TD|TH)$/.test(c.tagName))
				.map((c) => ({
					t: c.textContent.replace(/\s+/g, " ").trim(),
					th: c.tagName === "TH",
					cs: Math.max(1, c.colSpan || 1),
					rs: Math.max(1, c.rowSpan || 1),
					bold: c.tagName === "TH" || !!c.querySelector("b, strong") || /bold|[6-9]00/.test(c.style.fontWeight || tr.style.fontWeight || ""),
					bg: this.usable_bg(c.style.backgroundColor || tr.style.backgroundColor || ""),
				}));
			if (cells.length) rows.push({ cells });
		});
		rows.push({ cells: [] }); // blank spacer row between blocks
	}

	// White backgrounds only fight the theme; keep real tints.
	usable_bg(bg) {
		return /^(rgb\(255,\s*255,\s*255\)|#fff(fff)?|white)$/i.test(bg.trim()) ? "" : bg;
	}

	// Assigns each cell a column index (honouring rowspans) and returns the sheet width; text rows span the full width.
	layout(rows) {
		const taken = new Set();
		let width = 1;
		rows.forEach((row, r) => {
			if (!row.cells) return;
			let col = 0;
			row.cells.forEach((cell) => {
				while (taken.has(`${r},${col}`)) col++;
				cell.col = col;
				for (let dr = 0; dr < cell.rs; dr++) for (let dc = 0; dc < cell.cs; dc++) taken.add(`${r + dr},${col + dc}`);
				col += cell.cs;
			});
			width = Math.max(width, col);
		});
		return width;
	}

	// Column whose header reads "Note No." -> numbers in it jump to that note's sheet.
	find_note_column(rows) {
		for (const row of rows.slice(0, 6)) {
			for (const cell of row.cells || []) {
				if (/^note\s*no/i.test(cell.t)) return cell.col;
			}
		}
		return -1;
	}

	letters(n) {
		let s = "";
		for (n += 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
		return s;
	}

	// --- rendering -----------------------------------------------------------------------------

	render_summary(doc) {
		const e = frappe.utils.escape_html;
		const status = doc.report_status || doc.workflow_state || "";
		// Same wording as the form's status banner: Under Generation (red), Report Generated (green), Generation Failed (red)
		const STATUS = {
			"Under Generation": { color: "red", label: __("Under Generation") },
			Successful: { color: "green", label: __("Report Generated") },
			Failed: { color: "red", label: __("Generation Failed") },
		}[status];
		const color = STATUS ? STATUS.color : "gray";
		const status_label = STATUS ? STATUS.label : status;
		const period = doc.report_type === "Monthly" ? `${doc.current_month || ""} ${doc.fiscal_year || ""}` : doc.fiscal_year || "";
		const generated = doc.report_generated_on ? frappe.datetime.str_to_user(doc.report_generated_on) : "";
		const item = (label, value) => (value ? `<div class="xv-chip"><span class="xv-chip-l">${e(label)}</span><span class="xv-chip-v">${e(String(value))}</span></div>` : "");
		this.$summary.html(`
			<div class="xv-company">${e(doc.company || this.name)}</div>
			<div class="xv-chips">
				${item(__("Report"), doc.report_type)}
				${item(__("Period"), period.trim())}
				${item(__("Currency"), doc.currency)}
				${item(__("Generated"), generated)}
				${status ? `<div class="xv-chip"><span class="indicator-pill ${color}">${e(status_label)}</span></div>` : ""}
			</div>`);
	}

	render_nav() {
		const e = frappe.utils.escape_html;
		const filter = (this.$side_search.val() || "").toLowerCase().trim();
		const order = ["statement", "info", "note"];
		const items = this.sheets
			.filter((s) => !filter || s.title.toLowerCase().includes(filter))
			.sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind) || a.index - b.index);
		const h = items
			.map((s) => {
				const active = s.index === this.active ? "active" : "";
				const label = s.kind === "note" ? `${s.note ? `<b>${e(s.note)}</b>` : ""}${e(s.title.replace(/^Note\s+\S+\s*/, ""))}` : e(s.title);
				return `<button type="button" class="xv-item ${active}" data-index="${s.index}" title="${e(s.title)}"><span class="xv-item-t">${label}</span></button>`;
			})
			.join("");
		this.$nav.html(h || `<div class="xv-none">${__("No sheets match")}</div>`);
	}

	show_sheet(index, keep_find) {
		this.active = index;
		this.sel = null;
		this.render_nav();
		this.render_sheet();
		if (!keep_find) this.$find.val("");
		this.run_find();
		this.$nav.find(".xv-item.active")[0]?.scrollIntoView({ block: "nearest", inline: "nearest" });
	}

	render_sheet() {
		const e = frappe.utils.escape_html;
		const sheet = this.sheets[this.active];
		let h = `<table class="xv-table"><thead><tr><th class="xv-corner"></th>`;
		for (let c = 0; c < sheet.width; c++) h += `<th class="xv-col" data-col="${c}">${this.letters(c)}</th>`;
		h += "</tr></thead><tbody>";
		sheet.rows.forEach((row, r) => {
			const n = r + 1;
			h += `<tr><th class="xv-rownum" data-row="${r}">${n}</th>`;
			if (row.text !== undefined) {
				h += `<td class="xv-cell xv-text" data-r="${r}" data-c="0" data-ref="A${n}" colspan="${sheet.width}">${e(row.text)}</td>`;
			} else if (!row.cells.length) {
				h += `<td class="xv-cell xv-empty" data-r="${r}" data-c="0" data-ref="A${n}" colspan="${sheet.width}"></td>`;
			} else {
				for (const cell of row.cells) {
					const numeric = cell.t && NUMBER.test(cell.t);
					const neg = numeric && /^\(|^-/.test(cell.t) && !/^-?0+(\.0+)?$/.test(cell.t.replace(/[(),%]/g, ""));
					const link = numeric && sheet.note_col === cell.col && !cell.th && this.note_target(cell.t) >= 0;
					const cls = ["xv-cell", cell.th ? "xv-head" : "", cell.bold ? "xv-b" : "", numeric ? "xv-num" : "", neg ? "xv-neg" : "", link ? "xv-link" : ""].join(" ");
					const style = cell.bg ? ` style="background:${e(cell.bg)}"` : "";
					h += `<td class="${cls}" data-r="${r}" data-c="${cell.col}" data-ref="${this.letters(cell.col)}${n}"${link ? ` data-note="${e(cell.t)}"` : ""}${style}${cell.cs > 1 ? ` colspan="${cell.cs}"` : ""}${cell.rs > 1 ? ` rowspan="${cell.rs}"` : ""}>${e(cell.t)}</td>`;
				}
			}
			h += "</tr>";
		});
		this.$grid.html(h + "</tbody></table>");
		this.$ref.html("&nbsp;");
		this.$val.text("");
		this.update_status();
		this.$grid.scrollTop(0).scrollLeft(0);
	}

	note_target(text) {
		const n = text.trim();
		return this.sheets.findIndex((s) => s.note === n);
	}

	// --- selection ---------------------------------------------------------------------------

	cell_at(r, c) {
		return this.$grid.find(`td.xv-cell[data-r="${r}"]`).filter((_, td) => {
			const col = Number(td.dataset.c);
			return c >= col && c < col + (td.colSpan || 1);
		})[0];
	}

	set_selection(r1, c1, r2, c2) {
		const sheet = this.sheets[this.active];
		r2 = Math.max(0, Math.min(sheet.rows.length - 1, r2));
		c2 = Math.max(0, Math.min(sheet.width - 1, c2));
		this.sel = { r1, c1, r2, c2 };
		const [ra, rb] = [Math.min(r1, r2), Math.max(r1, r2)];
		const [ca, cb] = [Math.min(c1, c2), Math.max(c1, c2)];
		this.$grid.find("td.selected, td.in-range").removeClass("selected in-range");
		this.$grid.find(".xv-col.hl, .xv-rownum.hl").removeClass("hl");
		this.$grid.find("td.xv-cell").each((_, td) => {
			const r = Number(td.dataset.r);
			const c = Number(td.dataset.c);
			const span = td.colSpan || 1;
			if (r >= ra && r <= rb && c + span - 1 >= ca && c <= cb) td.classList.add("in-range");
		});
		const focus = this.cell_at(r2, c2);
		if (focus) {
			focus.classList.remove("in-range");
			focus.classList.add("selected");
			focus.scrollIntoView({ block: "nearest", inline: "nearest" });
			this.$ref.text(ra === rb && ca === cb ? focus.dataset.ref : `${this.letters(ca)}${ra + 1}:${this.letters(cb)}${rb + 1}`);
			this.$val.text(focus.textContent);
		}
		for (let c = ca; c <= cb; c++) this.$grid.find(`.xv-col[data-col="${c}"]`).addClass("hl");
		for (let r = ra; r <= rb; r++) this.$grid.find(`.xv-rownum[data-row="${r}"]`).addClass("hl");
		this.update_status();
	}

	// Sum / average / count of the numeric cells in the selection (or the whole sheet when nothing is selected).
	update_status() {
		const sheet = this.sheets[this.active];
		if (!sheet) return;
		const area = this.sel_area();
		const nums = [];
		sheet.rows.forEach((row, r) => {
			(row.cells || []).forEach((cell) => {
				if (!cell.t || !NUMBER.test(cell.t) || cell.th) return;
				if (area && (r < area.ra || r > area.rb || cell.col + cell.cs - 1 < area.ca || cell.col > area.cb)) return;
				const neg = /^\(.*\)$/.test(cell.t);
				const v = parseFloat(cell.t.replace(/[(),%]/g, ""));
				if (!isNaN(v)) nums.push(neg ? -Math.abs(v) : v);
			});
		});
		const fmt = (v) => v.toLocaleString("en-US", { maximumFractionDigits: 2 });
		const total = nums.reduce((a, b) => a + b, 0);
		// Totals only make sense over a range the user picked: a whole statement already contains its own subtotals.
		this.$stat_left.text(!area ? "" : nums.length ? `${__("Count")} ${nums.length}    ${__("Sum")} ${fmt(total)}    ${__("Average")} ${fmt(total / nums.length)}` : __("No numeric cells in selection"));
	}

	// Zoom scales the grid text; row height and padding follow via the CSS zoom property so the layout stays proportional.
	set_zoom(z) {
		this.zoom = Math.max(0.6, Math.min(1.6, Math.round(z * 10) / 10));
		this.$grid.css("zoom", this.zoom);
		this.$zoom_val.text(`${Math.round(this.zoom * 100)}%`);
	}

	sel_area() {
		if (!this.sel) return null;
		const { r1, c1, r2, c2 } = this.sel;
		return { ra: Math.min(r1, r2), rb: Math.max(r1, r2), ca: Math.min(c1, c2), cb: Math.max(c1, c2) };
	}

	// --- find --------------------------------------------------------------------------------

	run_find() {
		this.$grid.find("td.hit, td.hit-current").removeClass("hit hit-current");
		const q = (this.$find.val() || "").toLowerCase().trim();
		this.hits = [];
		this.hit_index = -1;
		if (q) {
			this.$grid.find("td.xv-cell").each((_, td) => {
				if (td.textContent.toLowerCase().includes(q)) {
					td.classList.add("hit");
					this.hits.push(td);
				}
			});
		}
		this.$find_count.text(q ? `${this.hits.length} ${__("found")}` : "");
		if (this.hits.length) this.step_find(1);
	}

	step_find(dir) {
		if (!this.hits.length) return;
		this.hits[this.hit_index]?.classList.remove("hit-current");
		this.hit_index = (this.hit_index + dir + this.hits.length) % this.hits.length;
		const td = this.hits[this.hit_index];
		td.classList.add("hit-current");
		td.scrollIntoView({ block: "center", inline: "nearest" });
		this.$find_count.text(`${this.hit_index + 1} / ${this.hits.length}`);
	}

	// --- copy / csv / export -----------------------------------------------------------------

	// Rows x columns of text for the selection (whole sheet when nothing is selected), spans repeated as blanks.
	matrix() {
		const sheet = this.sheets[this.active];
		const area = this.sel_area() || { ra: 0, rb: sheet.rows.length - 1, ca: 0, cb: sheet.width - 1 };
		const out = [];
		for (let r = area.ra; r <= area.rb; r++) {
			const line = new Array(area.cb - area.ca + 1).fill("");
			const row = sheet.rows[r];
			if (row.text !== undefined) line[0] = row.text;
			(row.cells || []).forEach((cell) => {
				if (cell.col >= area.ca && cell.col <= area.cb) line[cell.col - area.ca] = cell.t;
			});
			out.push(line);
		}
		return out;
	}

	copy() {
		const text = this.matrix().map((l) => l.join("\t")).join("\n");
		frappe.utils.copy_to_clipboard(text);
	}

	download_csv() {
		const sheet = this.sheets[this.active];
		const quote = (v) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
		const csv = this.matrix().map((l) => l.map(quote).join(",")).join("\r\n");
		const url = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }));
		const a = Object.assign(document.createElement("a"), { href: url, download: `${this.name}-${sheet.title.replace(/[^\w-]+/g, "_")}.csv` });
		document.body.appendChild(a);
		a.click();
		a.remove();
		URL.revokeObjectURL(url);
	}

	export_excel() {
		if (!this.name) return;
		frappe.dom.freeze(__("Preparing Excel..."));
		frappe
			.xcall("run_doc_method", { dt: "FR Financial Report", dn: this.name, method: "export_to_excel" })
			.then((r) => {
				const res = r && (r.message || r);
				if (res && res.file_url) {
					const a = Object.assign(document.createElement("a"), { href: res.file_url, download: res.file_name || "" });
					document.body.appendChild(a);
					a.click();
					a.remove();
				}
			})
			.finally(() => frappe.dom.unfreeze());
	}

	// --- filters -------------------------------------------------------------------------------

	// The filters that are filled in (used to narrow the Financial Report picker and to look a report up).
	filters() {
		const f = {};
		const company = this.company_field.get_value();
		const fiscal_year = this.fiscal_year_field.get_value();
		const report_type = this.report_type_field.get_value();
		const month = this.month_field.get_value();
		if (company) f.company = company;
		if (fiscal_year) f.fiscal_year = fiscal_year;
		if (report_type) f.report_type = report_type;
		if (month) f.current_month = month;
		return f;
	}

	// Shows the open report's own Company / Fiscal Year / Report Type / Month in the filters (without triggering a lookup).
	show_filters(doc) {
		this.syncing_filters = true;
		Promise.all([
			this.company_field.set_value(doc.company || ""),
			this.fiscal_year_field.set_value(doc.fiscal_year || ""),
			this.report_type_field.set_value(doc.report_type || ""),
			this.month_field.set_value(doc.current_month || ""),
		]).finally(() => (this.syncing_filters = false));
	}

	// Only Monthly reports have a month: choosing another type drops a Month that was left over from a Monthly report.
	report_type_changed() {
		const type = this.report_type_field.get_value();
		if (!this.syncing_filters && type && type !== "Monthly" && this.month_field.get_value()) {
			// clearing Month looks the report up itself (its change handler calls find_report)
			return this.month_field.set_value("");
		}
		this.find_report();
	}

	// A filter changed: open the one Financial Report that matches Company + Fiscal Year (+ Report Type + Month).
	// The open report is left alone when nothing or several reports match.
	find_report() {
		if (this.syncing_filters) return;
		const f = this.filters();
		if (!f.company || !f.fiscal_year) return;
		const d = this.doc;
		if (d && d.company === f.company && d.fiscal_year === f.fiscal_year && (d.report_type || "") === (f.report_type || "") && (d.current_month || "") === (f.current_month || "")) return;
		frappe
			.xcall("frappe.client.get_list", {
				doctype: "FR Financial Report",
				filters: f,
				fields: ["name"],
				order_by: "modified desc",
				limit_page_length: 20,
			})
			.then((rows) => {
				if (!rows.length) {
					frappe.show_alert({ message: __("No Financial Report found for these filters."), indicator: "orange" });
				} else if (rows.length === 1) {
					this.open(rows[0].name);
				} else {
					frappe.show_alert({
						message: __("{0} Financial Reports match - pick a Month or choose one in the Financial Report field.", [rows.length]),
						indicator: "orange",
					});
				}
			});
	}

	// --- generate ------------------------------------------------------------------------------

	// Same checks and server call as the Generate Report button on the form; the work runs in a background job.
	generate() {
		const doc = this.doc;
		if (!doc || this.generating) return;
		if (!doc.company) return frappe.msgprint(__("Please select a Company"));
		if (!doc.fiscal_year) return frappe.msgprint(__("Please select a Fiscal Year"));
		if (doc.workflow_state === "Approved") {
			return frappe.msgprint(__("This report has already been approved. You cannot regenerate it."));
		}
		const name = this.name;
		this.generating = true;
		this.$generate.prop("disabled", true);
		frappe
			// by doctype + name: the server loads the document itself (this page has no form, so there is no local copy to send)
			.call({ method: "run_doc_method", args: { dt: "FR Financial Report", dn: name, method: "generate_report" } })
			.then(() => {
				frappe.show_alert({ message: __("Report generation started in background."), indicator: "blue" });
				this.reload(name); // shows the "Under Generation" status; the finished report is loaded when the job completes
			})
			.catch(() => this.$generate.prop("disabled", false))
			.always(() => (this.generating = false));
	}

	// Reloads the open report from the server (open() alone skips a report that is already shown).
	reload(name) {
		if (name !== this.name) return;
		this.name = null;
		this.open(name);
	}

	// The background job announces when it is done: load the generated report.
	listen_generation() {
		frappe.realtime.off("report_generation_complete");
		frappe.realtime.on("report_generation_complete", (data) => {
			if (!data || data.docname !== this.name) return;
			this.reload(data.docname);
			frappe.show_alert(
				data.status === "Successful"
					? { message: __("Report generated successfully!"), indicator: "green" }
					: { message: __("Report generation failed. Check the form for details."), indicator: "red" }
			);
		});
	}

	// --- events ------------------------------------------------------------------------------

	bind_events() {
		const g = this.$grid;
		let dragging = false;

		this.$nav.on("click", ".xv-item", (e) => this.show_sheet(Number($(e.currentTarget).data("index"))));
		this.$side_search.on("input", () => this.render_nav());
		this.$find.on("input", () => this.run_find());
		this.$find.on("keydown", (e) => {
			if (e.key === "Enter") {
				e.preventDefault();
				this.step_find(e.shiftKey ? -1 : 1);
			} else if (e.key === "Escape") {
				this.$find.val("");
				this.run_find();
				g.trigger("focus");
			}
		});
		this.$body.on("click", ".xv-find-next", () => this.step_find(1));
		this.$body.on("click", ".xv-find-prev", () => this.step_find(-1));
		this.$body.on("click", ".xv-copy", () => this.sheets.length && this.copy());
		this.$body.on("click", ".xv-csv", () => this.sheets.length && this.download_csv());
		this.$body.on("click", ".xv-excel", () => this.name && this.export_excel());
		this.$body.on("click", ".xv-zoom-in", () => this.set_zoom(this.zoom + 0.1));
		this.$body.on("click", ".xv-zoom-out", () => this.set_zoom(this.zoom - 0.1));

		g.on("mousedown", "td.xv-cell", (e) => {
			if (e.button !== 0) return;
			const td = e.currentTarget;
			const r = Number(td.dataset.r);
			const c = Number(td.dataset.c);
			if (e.shiftKey && this.sel) this.set_selection(this.sel.r1, this.sel.c1, r, c);
			else this.set_selection(r, c, r, c);
			dragging = true;
			g.trigger("focus");
		});
		g.on("mouseover", "td.xv-cell", (e) => {
			if (dragging && this.sel) this.set_selection(this.sel.r1, this.sel.c1, Number(e.currentTarget.dataset.r), Number(e.currentTarget.dataset.c));
		});
		$(document).on("mouseup.xv", () => (dragging = false));
		g.on("click", "td.xv-link", (e) => {
			const idx = this.note_target(e.currentTarget.dataset.note);
			if (idx >= 0 && !(this.sel && (this.sel.r1 !== this.sel.r2 || this.sel.c1 !== this.sel.c2))) this.show_sheet(idx);
		});
		g.on("click", ".xv-col", (e) => {
			const sheet = this.sheets[this.active];
			const c = Number(e.currentTarget.dataset.col);
			this.set_selection(0, c, sheet.rows.length - 1, c);
		});
		g.on("click", ".xv-rownum", (e) => {
			const sheet = this.sheets[this.active];
			const r = Number(e.currentTarget.dataset.row);
			this.set_selection(r, 0, r, sheet.width - 1);
		});
		g.on("keydown", (e) => {
			if (!this.sheets.length) return;
			const sheet = this.sheets[this.active];
			if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "c") {
				e.preventDefault();
				return this.copy();
			}
			if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
				e.preventDefault();
				return this.set_selection(0, 0, sheet.rows.length - 1, sheet.width - 1);
			}
			if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
				e.preventDefault();
				return this.$find.trigger("focus").select();
			}
			const move = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1], Tab: [0, e.shiftKey ? -1 : 1], Enter: [e.shiftKey ? -1 : 1, 0] }[e.key];
			if (!move) return;
			e.preventDefault();
			const cur = this.sel || { r1: 0, c1: 0, r2: 0, c2: 0 };
			const r = cur.r2 + move[0];
			const c = cur.c2 + move[1];
			if (e.shiftKey && e.key.startsWith("Arrow")) this.set_selection(cur.r1, cur.c1, r, c);
			else {
				const rr = Math.max(0, Math.min(sheet.rows.length - 1, r));
				const cc = Math.max(0, Math.min(sheet.width - 1, c));
				this.set_selection(rr, cc, rr, cc);
			}
		});
	}

	add_styles() {
		if (document.getElementById("xv-styles")) return;
		$(`<style id="xv-styles">
			.xv-page .page-head .title-area, .xv-page .page-head .title-text { display:none !important; }
			.xv-page .page-head { min-height:0; }
			.xv-page .page-head .page-head-content { height:auto; padding:6px 0; }
			.xv-page .page-body { padding-top:6px; }
			.xv { --xv-line:#e4e6e9; --xv-head:#f8f9fa; --xv-accent:#1a73e8; --xv-sel-bg:#e8f0fe; --xv-hl:#d3e3fd; display:flex; flex-direction:column; height:calc(100vh - 150px); min-height:380px; border:1px solid #dadce0; border-radius:6px; overflow:hidden; background:#fff; font-family:"Segoe UI", Arial, sans-serif; font-size:13px; color:#202124; box-shadow:0 1px 2px rgba(60,64,67,.1); }
			.xv-top { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:4px 16px; padding:7px 12px; border-bottom:1px solid #dadce0; background:var(--xv-head); }
			.xv-summary { display:flex; align-items:center; flex-wrap:wrap; gap:4px 14px; min-width:0; }
			.xv-company { font-size:14px; font-weight:600; }
			.xv-chips { display:flex; flex-wrap:wrap; align-items:center; gap:4px 12px; }
			.xv-chip { display:inline-flex; align-items:center; gap:5px; font-size:12px; }
			.xv-chip .indicator-pill { font-size:11px; padding:1px 8px; }
			.xv-chip-l { color:#5f6368; }
			.xv-chip-l::after { content:":"; }
			.xv-chip-v { font-weight:600; }
			.xv-tools { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
			.xv-find-wrap { display:inline-flex; align-items:center; gap:3px; margin-right:8px; }
			.xv-find { width:170px; height:26px; padding:0 9px; font-size:12px; border-radius:5px; }
			.xv-find-count { min-width:46px; padding:0 3px; font-size:11px; color:#5f6368; }
			.xv-btn { height:26px; padding:0 10px; border:1px solid #dadce0; border-radius:5px; background:#fff; font-size:12px; color:#202124; line-height:24px; }
			.xv-btn:hover { background:#f1f3f4; border-color:#c4c7cc; }
			.xv-btn:disabled { opacity:.4; pointer-events:none; }
			.xv-formula { display:flex; align-items:center; height:28px; border-bottom:1px solid #dadce0; background:#fff; font-size:12px; }
			.xv-ref { width:80px; height:100%; padding:0 10px; border-right:1px solid #dadce0; text-align:left; line-height:28px; font-weight:600; color:#202124; }
			.xv-fx { padding:0 10px; color:#5f6368; font-style:italic; font-family:"Times New Roman", serif; border-right:1px solid #dadce0; line-height:28px; }
			.xv-val { flex:1; padding:0 10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; line-height:28px; }
			.xv-grid { flex:1; min-height:0; overflow:auto; outline:none; background:#fff; position:relative; }
			.xv-table { border-collapse:separate; border-spacing:0; font-family:"Segoe UI", Arial, sans-serif; font-size:13px; }
			.xv-table th, .xv-table td { border-right:1px solid var(--xv-line); border-bottom:1px solid var(--xv-line); padding:0 8px; height:27px; line-height:25px; }
			.xv-table thead th { position:sticky; top:0; z-index:2; height:22px; line-height:20px; background:var(--xv-head); border-color:#cfd2d6; color:#5f6368; font-size:11px; font-weight:500; text-align:center; min-width:96px; user-select:none; cursor:pointer; }
			.xv-table .xv-corner { left:0; z-index:4; min-width:46px; cursor:default; }
			.xv-table .xv-rownum { position:sticky; left:0; z-index:1; background:var(--xv-head); border-color:#cfd2d6; color:#5f6368; font-size:11px; font-weight:400; text-align:center; min-width:46px; padding:0 6px; user-select:none; cursor:pointer; }
			.xv-col.hl, .xv-rownum.hl { background:var(--xv-hl) !important; color:#202124; }
			.xv-cell { background:#fff; white-space:nowrap; cursor:cell; user-select:none; }
			.xv-text { white-space:normal; min-width:500px; max-width:920px; line-height:1.55; padding:6px 10px; user-select:text; }
			.xv-num { text-align:right; font-variant-numeric:tabular-nums; }
			.xv-neg { color:#c0392b; }
			.xv-b { font-weight:700; }
			.xv-cell.xv-head { background:#f1f3f4; text-align:center; white-space:normal; line-height:1.3; padding-top:4px; padding-bottom:4px; min-width:100px; }
			.xv-link { color:#1a73e8; text-decoration:underline; cursor:pointer; text-align:center; }
			.xv-cell.in-range { background:var(--xv-sel-bg) !important; }
			.xv-cell.selected { outline:2px solid var(--xv-accent); outline-offset:-2px; background:#fff !important; }
			.xv-cell.hit { background:#fff3b0 !important; }
			.xv-cell.hit-current { background:#ffd54a !important; outline:2px solid #e09400; outline-offset:-2px; }
			.xv-bottom { display:flex; align-items:stretch; height:38px; border-top:1px solid #dadce0; background:var(--xv-head); }
			.xv-side-search { flex:none; width:140px; margin:6px 10px; padding:0 11px; height:26px; border:1px solid #dadce0; border-radius:13px; background:#fff; font-size:12px; outline:none; }
			.xv-nav { flex:1; min-width:0; display:flex; align-items:stretch; overflow-x:auto; overflow-y:hidden; scrollbar-width:thin; }
			.xv-item { flex:none; max-width:240px; padding:0 16px; border:0; border-bottom:3px solid transparent; background:transparent; font-size:12px; color:#5f6368; white-space:nowrap; }
			.xv-item:hover { background:#e8eaed; }
			.xv-item.active { background:#fff; color:#188038; font-weight:600; border-bottom-color:#188038; }
			.xv-item b { margin-right:7px; padding:1px 6px; border-radius:4px; background:#e8eaed; font-size:11px; }
			.xv-item.active b { background:#e6f4ea; }
			.xv-item-t { display:block; overflow:hidden; text-overflow:ellipsis; }
			.xv-none { align-self:center; padding:0 12px; color:#5f6368; font-size:12px; }
			.xv-status { flex:none; display:flex; align-items:center; gap:14px; padding:0 14px; font-size:11px; color:#5f6368; white-space:nowrap; }
			.xv-zoom { display:inline-flex; align-items:center; gap:2px; margin-left:auto; }
			.xv-zoom-val { min-width:40px; text-align:center; font-size:11px; color:#5f6368; }
			.xv-zbtn { width:24px; height:24px; border:0; border-radius:4px; background:transparent; font-size:16px; line-height:22px; color:#202124; }
			.xv-zbtn:hover { background:#e8eaed; }
			.xv-msg { padding:70px 20px; text-align:center; font-size:13px; color:#5f6368; }
		</style>`).appendTo(document.head);
	}
}
