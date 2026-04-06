frappe.pages['update-console-trial-balance'].on_page_load = function(wrapper) {

	// wrap content
	let main_container = $('<div class="update-ctb-container"></div>').appendTo(wrapper);

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Update Console Trial Balance',
		single_column: true
	});

	let table_data = [];
	let debounce_timeout = null;

	// 🔹 Fetch + Render function
	function fetch_and_render() {

		clearTimeout(debounce_timeout);

		debounce_timeout = setTimeout(() => {

			const fy = fiscal_year.get_value();
			const m = month.get_value();
			const comp = company.get_value();

			// remove old table
			$(wrapper).find('.table-container').remove();

			if (!fy || !m || !comp) return;

			frappe.call({
				method: 'financial_report_tool.financial_report_tool.page.update_console_trial_balance.update_console_trial_balance.get_entries',
				args: {
					fiscal_year: fy,
					month: m,
					company: comp
				},
				freeze: true,
				callback: function(r) {
					if (r.message && r.message.length) {
						render_datatable(wrapper, r.message);
					} else {
						frappe.msgprint("No records found");
					}
				}
			});

		}, 400);
	}

	// 🔹 Fields
	const fiscal_year = page.add_field({
		label: 'Fiscal Year',
		fieldname: 'fiscal_year',
		fieldtype: 'Link',
		options: 'Fiscal Year',
		reqd: 1,
		change: fetch_and_render
	});

	const month = page.add_field({
		label: 'Month',
		fieldname: 'month',
		fieldtype: 'Select',
		options: '\nJanuary\nFebruary\nMarch\nApril\nMay\nJune\nJuly\nAugust\nSeptember\nOctober\nNovember\nDecember',
		reqd: 1,
		change: fetch_and_render
	});

	const company = page.add_field({
		label: 'Company',
		fieldname: 'company',
		fieldtype: 'Link',
		options: 'Company',
		reqd: 1,
		change: fetch_and_render
	});

	const closing_rate = page.add_field({
		label: 'Update Closing Rate (P&L)',
		fieldname: 'update_closing',
		fieldtype: 'Check'
	});

	const avg_rate = page.add_field({
		label: 'Update Average Rate (BS)',
		fieldname: 'update_average',
		fieldtype: 'Check'
	});

	// 🔹 Update Button
	page.set_primary_action('Update', () => {

		if (!table_data.length) {
			frappe.msgprint("No data to update");
			return;
		}

		let updated_rows = [];

		$('.table-container tbody tr').each(function() {

			let row_name = $(this).data('name');
			let report_type = $(this).find('.report-type').val();
		
			let original_row = table_data.find(r => r.name === row_name);
		
			if (original_row && report_type !== original_row.report_type) {
				updated_rows.push({
					name: row_name,
					report_type: report_type
				});
			}
		});

		frappe.call({
			method: 'financial_report_tool.financial_report_tool.page.update_console_trial_balance.update_console_trial_balance.update_entries',
			args: {
				fiscal_year: fiscal_year.get_value(),
				month: month.get_value(),
				company: company.get_value(),
				update_closing: closing_rate.get_value(),
				update_average: avg_rate.get_value(),
				updated_rows: updated_rows
			},
			freeze: true,
			freeze_message: 'Updating entries...',
			callback: function(r) {
				if (!r.exc) {
					frappe.msgprint("Updated successfully");
					fetch_and_render(); // refresh data
				}
			}
		});
	});

	function render_datatable(wrapper, data) {

		table_data = data;
	
		let total_dc = 0;
		let total_inr = 0;
	
		$(wrapper).find('.table-container').remove();
	
		let tbody = '';
	
		data.forEach(function(row, idx) {
	
			let amount = parseFloat(row.amount) || 0;
			let amount_inr = parseFloat(row.amount_inr) || 0;
	
			total_dc += amount;
			total_inr += amount_inr;
	
			tbody += `
				<tr data-name="${row.name}">
					<td class="text-right">${idx + 1}</td>
					<td>${row.name}</td>
					<td>${row.gl_account || ''}</td>
					<td>${row.currency || ''}</td>
					<td class="text-right">${row.exchange_rate || 0}</td>
					<td class="text-right">${format_number(amount)}</td>
					<td class="text-right">${format_number(amount_inr)}</td>
					<td>
						<select class="report-type form-control input-sm">
							<option ${row.report_type === "Profit and Loss" ? "selected" : ""}>Profit and Loss</option>
							<option ${row.report_type === "Balance Sheet" ? "selected" : ""}>Balance Sheet</option>
						</select>
					</td>
				</tr>
			`;
		});
	
		let html = `
			<div class="table-container" style="margin: 80px;">
	
				<div class="section-header">
					<h5>Trial Balance Entries (${data.length})</h5>
	
					<input type="text" class="form-control input-sm global-search" 
						placeholder="Search..." style="width: 220px;">
				</div>
	
				<div class="table-wrapper">
					<table class="table table-bordered preview-table">
						<thead>
							<tr>
								<th>#</th>
								<th>Name</th>
								<th>GL Account</th>
								<th>Currency</th>
								<th class="text-right">Exchange Rate</th>
								<th class="text-right">Amount (DC)</th>
								<th class="text-right">Amount (INR)</th>
								<th>Report Type</th>
							</tr>
						</thead>
	
						<tbody>
							${tbody}
						</tbody>
	
						<tfoot>
							<tr class="total-row">
								<td colspan="5" class="text-right"><b>Total</b></td>
								<td class="text-right total-dc"><b>${format_number(total_dc)}</b></td>
								<td class="text-right total-inr"><b>${format_number(total_inr)}</b></td>
								<td></td>
							</tr>
						</tfoot>
					</table>
				</div>
			</div>
		`;
	
		$(wrapper).append(html);
	
		// 🔥 GLOBAL SEARCH ONLY
		function apply_search() {
	
			let search_val = $('.global-search').val().toLowerCase();
	
			let visible_dc = 0;
			let visible_inr = 0;
	
			$('.table-container tbody tr').each(function() {
	
				let row = $(this);
				let text = row.text().toLowerCase();
	
				if (!search_val || text.includes(search_val)) {
	
					row.show();
	
					let dc = parseFloat(row.find('td:eq(5)').text().replace(/,/g, '')) || 0;
					let inr = parseFloat(row.find('td:eq(6)').text().replace(/,/g, '')) || 0;
	
					visible_dc += dc;
					visible_inr += inr;
	
				} else {
					row.hide();
				}
			});
	
			// ✅ update totals dynamically
			$('.total-dc').html(`<b>${format_number(visible_dc)}</b>`);
			$('.total-inr').html(`<b>${format_number(visible_inr)}</b>`);
		}
	
		// 🔹 Bind search
		$('.global-search').on('input', apply_search);
	}
};

function format_number(num) {
    if (num == null) return '0.00';
    return parseFloat(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
