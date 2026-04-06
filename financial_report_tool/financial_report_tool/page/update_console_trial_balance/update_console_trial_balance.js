frappe.pages['update-console-trial-balance'].on_page_load = function(wrapper) {

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

		$('.table-container tbody tr').each(function(index) {
			let report_type = $(this).find('.report-type').val();

			if (report_type !== table_data[index].report_type) {
				updated_rows.push({
					name: table_data[index].name,
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

		let container = $('<div class="table-container" style="margin-top:20px;"></div>').appendTo(wrapper);

		let html = `
			<table class="table table-bordered">
				<thead>
					<tr>
						<th>Name</th>
						<th>GL Account</th>
						<th>Currency</th>
						<th>Amount</th>
						<th>Exchange Rate</th>
						<th>Amount (INR)</th>
						<th>Report Type</th>
					</tr>
				</thead>
				<tbody>
		`;

		data.forEach(row => {
			html += `
				<tr>
					<td>${row.name}</td>
					<td>${row.gl_account || ''}</td>
					<td>${row.currency || ''}</td>
					<td>${row.amount || 0}</td>
					<td>${row.exchange_rate || 0}</td>
					<td>${row.amount_inr || 0}</td>
					<td>
						<select class="report-type">
							<option ${row.report_type === "Profit and Loss" ? "selected" : ""}>Profit and Loss</option>
							<option ${row.report_type === "Balance Sheet" ? "selected" : ""}>Balance Sheet</option>
						</select>
					</td>
				</tr>
			`;
		});

		html += `</tbody></table>`;
		container.append(html);
	}
};