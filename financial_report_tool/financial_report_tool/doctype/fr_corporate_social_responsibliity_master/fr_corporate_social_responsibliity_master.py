# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from financial_report_tool.financial_report_tool.fiscal_cycle import get_closing_month

class FRCorporateSocialResponsibliityMaster(Document):
	def before_save(self):
		if not self.allow_manually_input:
			template = frappe.get_doc("FR Balance Sheet Template", "Balance Sheet")
			first_year = self.fiscal_year
			_, second_year = self.get_previous_fiscal_year(first_year)
			_, third_year = self.get_previous_fiscal_year(second_year) if second_year else (None, None)

			first_year_profit = self.get_yearly_profit_and_loss_data(template, first_year, get_closing_month(self.company, first_year))
			second_year_profit = self.get_yearly_profit_and_loss_data(template, second_year, get_closing_month(self.company, second_year)) if second_year else 0
			third_year_profit = self.get_yearly_profit_and_loss_data(template, third_year, get_closing_month(self.company, third_year)) if third_year else 0

			total_profit = first_year_profit + second_year_profit + third_year_profit
			average_profit = round(((total_profit / 3)/100)*2, 3)

			self.shortfall_at_the_beginning_of_the_year = frappe.get_value("FR Corporate Social Responsibliity Master", {'company': self.company, 'fiscal_year':second_year, 'month': self.month}, 'shortfall_at_the_end_of_the_year') or 0
			self.amount_required_to_be_spent_by_the_company_during_the_year = average_profit
			self.amount_of_expenditure_incurred = self.get_sum_grouping_amount("Other expenses", "Corporate Social Responsibility Expenditure", get_closing_month(self.company, self.fiscal_year), self.fiscal_year)
			self.shortfall_at_the_end_of_the_year = self.amount_of_expenditure_incurred - self.amount_required_to_be_spent_by_the_company_during_the_year
			
			self.calculation_details_data = self._build_calculation_html(
				first_year, second_year, third_year,
				first_year_profit, second_year_profit, third_year_profit,
				total_profit, average_profit,
			)
		else:
			required_fields = [
				"amount_required_to_be_spent_by_the_company_during_the_year", "amount_of_expenditure_incurred"
			]

			for field in required_fields:
				if not self.get(field):
					frappe.throw(f"{field.replace('_', ' ').title()} is required when manual input is enabled")

			# ✅ Calculate shortfall based on manual input
			diff = flt(self.amount_of_expenditure_incurred) - flt(self.amount_required_to_be_spent_by_the_company_during_the_year)

			self.shortfall_at_the_end_of_the_year = 0 if diff < 0 else diff

			# ✅ Keep beginning shortfall (if not filled, fetch previous year)
			if not self.shortfall_at_the_beginning_of_the_year:
				_, prev_year = self.get_previous_fiscal_year(self.fiscal_year)
				self.shortfall_at_the_beginning_of_the_year = frappe.get_value(
					"FR Corporate Social Responsibliity Master",
					{
						"company": self.company,
						"fiscal_year": prev_year,
						"month": self.month
					},
					"shortfall_at_the_end_of_the_year"
				) or 0

			# ✅ Generate simple manual calculation view
			self.calculation_details_data = f"""
			<div class="csr-calc">
				<h6>Manual CSR Calculation</h6>
				<table>
					<tr><th>Description</th><th>Value</th></tr>
					<tr><td>Shortfall at Beginning</td><td>{flt(self.shortfall_at_the_beginning_of_the_year, 3)}</td></tr>
					<tr><td>Amount Required</td><td>{flt(self.amount_required_to_be_spent_by_the_company_during_the_year, 3)}</td></tr>
					<tr><td>Expenditure Incurred</td><td>{flt(self.amount_of_expenditure_incurred, 3)}</td></tr>
					<tr><td>Shortfall at End</td><td>{flt(self.shortfall_at_the_end_of_the_year, 3)}</td></tr>
				</table>
				<p><i>Note: Values are manually entered by user.</i></p>
			</div>
			"""

	def _build_calculation_html(self, fy1, fy2, fy3, p1, p2, p3, total_profit, average_profit):
		diff = self.amount_of_expenditure_incurred - self.amount_required_to_be_spent_by_the_company_during_the_year

		return f"""
		<style>
			.csr-calc table {{ width:100%; border-collapse:collapse; font-size:13px; border:2px solid #000; }}
			.csr-calc th, .csr-calc td {{ border:1px solid #000; padding:6px 10px; text-align:left; }}
			.csr-calc th {{ background:var(--subtle-fg); font-weight:600; }}
			.csr-calc .val {{ text-align:right; font-family:monospace; }}
			.csr-calc .formula {{ color:var(--text-muted); font-size:12px; font-style:italic; margin:0 0 8px 0; }}
			.csr-calc .result {{ font-weight:700; background:var(--highlight-color, #fffde8); }}
			.csr-calc h6 {{ margin:8px 0 4px 0; }}
		</style>
		<div class="csr-calc">

		<h6>Step 1: Three-Year Profit (from P&amp;L)</h6>
		<table>
			<tr><th>Fiscal Year</th><th class="val">Profit (in Lakhs)</th></tr>
			<tr><td>{fy1 or "N/A"} (Current Year)</td><td class="val">{flt(p1, 3)}</td></tr>
			<tr><td>{fy2 or "N/A"} (Previous Year)</td><td class="val">{flt(p2, 3)}</td></tr>
			<tr><td>{fy3 or "N/A"} (Year Before Previous)</td><td class="val">{flt(p3, 3)}</td></tr>
			<tr class="result"><td>Total Profit</td><td class="val">{flt(total_profit, 3)}</td></tr>
		</table>
		<p class="formula">Total Profit = {flt(p1, 3)} + {flt(p2, 3)} + {flt(p3, 3)} = {flt(total_profit, 3)}</p>

		<h6>Step 2: Amount Required to be Spent (2% of 3-Year Average)</h6>
		<table>
			<tr><th>Description</th><th class="val">Value</th></tr>
			<tr><td>3-Year Average Profit</td><td class="val">{flt(total_profit / 3, 3)}</td></tr>
			<tr class="result"><td>2% of Average = Amount Required</td><td class="val">{flt(average_profit, 3)}</td></tr>
		</table>
		<p class="formula">Amount Required = (Total Profit / 3) / 100 &times; 2 = ({flt(total_profit, 3)} / 3) / 100 &times; 2 = {flt(average_profit, 3)}</p>

		<h6>Step 3: Shortfall at Beginning of Year</h6>
		<table>
			<tr><th>Description</th><th class="val">Value</th></tr>
			<tr><td>Picked from previous year ({fy2 or "N/A"}) &rarr; Shortfall at End of Year</td>
				<td class="val">{flt(self.shortfall_at_the_beginning_of_the_year, 3)}</td></tr>
		</table>

		<h6>Step 4: Expenditure Incurred</h6>
		<table>
			<tr><th>Description</th><th class="val">Value</th></tr>
			<tr><td>GL Group: Other Expenses &rarr; Corporate Social Responsibility Expenditure</td>
				<td class="val">{flt(self.amount_of_expenditure_incurred, 3)}</td></tr>
		</table>

		<h6>Step 5: Shortfall at End of Year</h6>
		<table>
			<tr><th>Description</th><th class="val">Value</th></tr>
			<tr><td>Expenditure Incurred &minus; Amount Required</td><td class="val">{flt(diff, 3)}</td></tr>
			<tr class="result"><td>Shortfall at End of Year = max(0, above)</td>
				<td class="val">{flt(self.shortfall_at_the_end_of_the_year, 3)}</td></tr>
		</table>
		<p class="formula">If (Expenditure &minus; Required) &lt; 0 &rArr; 0, else (Expenditure &minus; Required) = {flt(diff, 3)} &rArr; {flt(self.shortfall_at_the_end_of_the_year, 3)}</p>

		</div>
		"""

	def get_previous_fiscal_year(self, year):
		month = get_closing_month(self.company, year)
		previous_year = frappe.get_value("FR Previous Fiscal Year",{"current_fiscal_year": year},"previous_fiscal_year")
		return month, previous_year

	def get_sum_grouping_amount(self, primary_group, group, month, year, is_ftm=False, hg_sec_group=""):
		filters = {"company": self.company,"report_type": "Yearly","primary_group": primary_group,"secondary_group": group, "higher_secondary_group": hg_sec_group}
		gl_accounts = frappe.get_list("FR GL Group Mapping", filters, pluck="gl_account")
		if not gl_accounts: return 0
		field = "amount" if is_ftm else "uploaded_amount"
		query = f"SELECT SUM({field}) FROM `tabFR Trial Balance Entry` WHERE company=%s AND fiscal_year=%s AND gl_account IN ({','.join(['%s']*len(gl_accounts))}) AND month=%s"
		return round((frappe.db.sql(query, [self.company, year]+gl_accounts+[month])[0][0] or 0) / 100000, 0)


	def get_yearly_finished_goods_and_wip(self, year, total=False, field=None, section_description=""):
		rows = []
		add = lambda p, cy=0, py=0, st=False: rows.append({"p": p, "cy": cy, "py": py, "st": st})
		_, previous_fiscal_year = self.get_previous_fiscal_year(year)
		_, pre_year = self.get_previous_fiscal_year(previous_fiscal_year)

		cur_total = prev_total = prev_prev_total = 0
		add("Inventories at the end of the year", st=True)

		def add_group(sec, label):
			nonlocal cur_total, prev_total
			cy = self.get_sum_grouping_amount("Inventories", sec, get_closing_month(self.company, year), year) or 0
			py = self.get_sum_grouping_amount("Inventories", sec, get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year) or 0
			add(label, cy, py)
			cur_total += cy; prev_total += py

			hgs = frappe.get_all(
				"FR GL Group Mapping",
				{"company": self.company, "primary_group": "Inventories", "secondary_group": sec, "higher_secondary_group": ["!=", None]},
				pluck="higher_secondary_group", distinct=True
			)

			for hg in hgs:
				cy_hg = self.get_sum_grouping_amount("Inventories", sec, get_closing_month(self.company, year), year, hg_sec_group=hg) or 0
				py_hg = self.get_sum_grouping_amount("Inventories", sec, get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year, hg_sec_group=hg) or 0
				add(f"  {hg}", cy_hg, py_hg)
			return cy, py

		cur_fg, py_fg = add_group("Finished Goods", "Finished goods")
		cur_wip, py_wip = add_group("Work in Progress", "Work-in-progress")
		cur_sit, py_sit = add_group("Stock In Trade", "Stock-in-trade")

		add("", cur_total, prev_total)

		add("Inventories at the beginning of the year", st=True)

		def add_prev_group(sec, label):
			nonlocal prev_prev_total
			py = self.get_sum_grouping_amount("Inventories", sec, get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year) or 0
			pp = self.get_sum_grouping_amount("Inventories", sec, get_closing_month(self.company, pre_year), pre_year) or 0
			add(label, py, pp)
			prev_prev_total += pp
			return py, pp

		p_fg, pp_fg = add_prev_group("Finished Goods", "Finished goods")
		p_wip, pp_wip = add_prev_group("Work in Progress", "Work-in-progress")
		p_sit, pp_sit = add_prev_group("Stock In Trade", "Stock-in-trade")

		prev_year_opening = p_fg + p_wip + p_sit
		prev_prev_total = pp_fg + pp_wip + pp_sit

		net_increase = cur_total - prev_year_opening
		prev_year_net = prev_total - prev_prev_total

		add("", prev_year_opening, prev_prev_total)
		add("Net increase", net_increase, prev_year_net, st=True)

		if total:
			if field == "net_increase_total": return net_increase
			if field == "prev_year_amt": return prev_year_net
			return 0

	def get_yearly_cost_of_material_consumed(self, section_description, total, year, field=None):
		rows = []
		_, previous_fiscal_year = self.get_previous_fiscal_year(year)
		_, pre_year = self.get_previous_fiscal_year(previous_fiscal_year)

		default_currency = frappe.get_value("Company", self.company, 'default_currency')

		# --- Current & Previous Month Stocks ---
		opening_stock = self.get_sum_grouping_amount("Inventories", "Raw Materials and Packing Material", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)
		closing_stock_current = self.get_sum_grouping_amount("Inventories", "Raw Materials and Packing Material", get_closing_month(self.company, year), year)

		# --- Purchases & SIT ---
		curr_month_purchase_sit = 0 if default_currency != "INR" else self.get_sum_grouping_amount("Purchases of Stock in Trade", "Purchases of Stock in Trade", get_closing_month(self.company, year), year)
		prev_month_purchase_sit = 0 if default_currency != "INR" else self.get_sum_grouping_amount("Purchases of Stock in Trade", "Purchases of Stock in Trade", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)

		purchases_current = (
			self.get_sum_grouping_amount("Material consumed", "Cost of Goods Sold", get_closing_month(self.company, year), year)
			- (0 if default_currency != "INR" else self.get_yearly_finished_goods_and_wip(year, total=True, field='net_increase_total'))
			+ (closing_stock_current - opening_stock)
			- curr_month_purchase_sit
		)

		# --- Cost of Materials Consumed ---
		cost_consumed_current = opening_stock + purchases_current - closing_stock_current

		# --- Previous Year (same month) ---
		closing_stock_pre_previous = self.get_sum_grouping_amount("Inventories", "Raw Materials and Packing Material", get_closing_month(self.company, pre_year), pre_year)
		prev_year_closing_stock = self.get_sum_grouping_amount("Inventories", "Raw Materials and Packing Material", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)

		closing_wip_pre_previous = (
			self.get_sum_grouping_amount("Inventories", "Work in Progress", get_closing_month(self.company, pre_year), pre_year)
			+ self.get_sum_grouping_amount("Inventories", "Finished Goods", get_closing_month(self.company, pre_year), pre_year)
			+ self.get_sum_grouping_amount("Inventories", "Stock In Trade", get_closing_month(self.company, pre_year), pre_year)
		)
		prev_year_closing_wip = (
			self.get_sum_grouping_amount("Inventories", "Work in Progress", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)
			+ self.get_sum_grouping_amount("Inventories", "Finished Goods", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)
			+ self.get_sum_grouping_amount("Inventories", "Stock In Trade", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)
		)

		pre_purchase_sit = 0 if default_currency != "INR" else self.get_sum_grouping_amount("Purchases of Stock in Trade", "Purchases of Stock in Trade", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)
		prev_year_purchases = (
			self.get_sum_grouping_amount("Material consumed", "Cost of Goods Sold", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)
			+ (0 if default_currency != "INR" else (prev_year_closing_wip - closing_wip_pre_previous))
			+ (prev_year_closing_stock - closing_stock_pre_previous)
			- pre_purchase_sit
		)

		prev_year_cost_consumed = closing_stock_pre_previous + prev_year_purchases - prev_year_closing_stock

		# --- Currency Conversion ---
		# if default_currency != self.currency:
		# 	current_fx = self.get_fx_rate(default_currency, cls_month, year, 'average_rate')
		# 	prev_year_fx = self.get_fx_rate(default_currency, cls_month, previous_fiscal_year, 'average_rate')
		# 	pre_prev_year_fx = self.get_fx_rate(default_currency, cls_month, pre_year, 'average_rate')

		# 	# Apply conversion
		# 	cost_consumed_current *= current_fx
		# 	prev_year_cost_consumed *= prev_year_fx

		# 	purchases_current *= current_fx
		# 	closing_stock_current *= current_fx
		# 	prev_year_purchases *= prev_year_fx
		# 	closing_stock_pre_previous *= pre_prev_year_fx

		# --- If only returning totals ---
		if total:
			if field == 'cost_consumed_current':
				return cost_consumed_current
			elif field == 'prev_year_cost_consumed':
				return prev_year_cost_consumed
			else:
				return 0


	def get_yearly_profit_and_loss_data(self, template_name, fiscal_year, month):
		"""Optimized: Get monthly P&L data with current month, previous month, FTM, and previous year amounts"""
		profit_and_loss_doc = frappe.get_doc("FR Profit And Loss Template", template_name)
		first_year = fiscal_year
		_, previous_fiscal_year = self.get_previous_fiscal_year(first_year)
		_, pre_year = self.get_previous_fiscal_year(previous_fiscal_year) if previous_fiscal_year else (None, None)

		amount_cache = {}
		group_mapping_cache = {}
		fr_particular_cache = {}
		fr_section_cache = {}
		standalone_group_cache = {}

		def get_fr_section(name):
			if name not in fr_section_cache:
				fr_section_cache[name] = frappe.get_doc("FR Section", name)
			return fr_section_cache[name]

		def get_fr_particular(name):
			if name not in fr_particular_cache:
				fr_particular_cache[name] = frappe.get_doc("FR Particular", name)
			return fr_particular_cache[name]

		def get_standalone_group(name):
			if name not in standalone_group_cache:
				standalone_group_cache[name] = frappe.get_value(
					"FR Standalone Group", name, ["show_reversed_value", "group_type"], as_dict=True
				)
			return standalone_group_cache[name]

		def get_secondary_groups(primary_group):
			"""Cached retrieval of secondary groups"""
			if primary_group not in group_mapping_cache:
				group_mapping_cache[primary_group] = sorted(set(
					g for g in frappe.get_list("FR GL Group Mapping", {"primary_group": primary_group}, pluck="secondary_group") if g
				))
			return group_mapping_cache[primary_group]

		def calc_amount_for_particular_monthly(particular_name, month, year, is_current=False, is_yearly=False, fx_rate=1, convert=True):
			"""
			Calculate amount for a particular in base currency, then apply FX conversion only for non-total nodes.
			"""
			cache_key = (particular_name, month, year, is_current, is_yearly, fx_rate)
			if cache_key in amount_cache:
				return amount_cache[cache_key]

			fr_particular = get_fr_particular(particular_name)
			amount = 0

			if fr_particular.is_total:
				for idx, p in enumerate(fr_particular.particulars or []):
					child_key = (p.particular, month, year, is_current, is_yearly, fx_rate)
					child_amount = amount_cache.get(child_key, 0)
					if fr_particular.to_subtract:
						amount = (child_amount if idx == 0 and amount == 0 else amount - child_amount)
					else:
						amount += child_amount

			elif fr_particular.fetch_from_schedule:
				note_type = get_fr_section(fr_particular.schedule).note_type
				if note_type == "Changes in inventories of Finished Goods and Work-In-Progress":
					field = 'net_increase_total' if is_current else ('prev_year_amt' if is_yearly else 'previous_month_amt')
					amount = self.get_yearly_finished_goods_and_wip(fiscal_year, total=True, field=field)
				elif note_type == "Cost of Materials Consumed":
					field = 'cost_consumed_current' if is_current else ('prev_year_cost_consumed' if is_yearly else 'cost_consumed_previous')
					amount = self.get_yearly_cost_of_material_consumed(note_type, total=True, year=fiscal_year, field=field)

			elif fr_particular.schedule and fr_particular.is_purchase_of_stock_in_trade:
				_, pre_year = self.get_previous_fiscal_year(previous_fiscal_year)
				opening_stock = self.get_sum_grouping_amount("Inventories", "Raw Materials and Packing Material", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)
				closing_stock_current = self.get_sum_grouping_amount("Inventories", "Raw Materials and Packing Material", get_closing_month(self.company, fiscal_year), fiscal_year)

				if is_current:
					amount = (
						self.get_sum_grouping_amount("Purchases of Stock in Trade", "Purchases of Stock in Trade", get_closing_month(self.company, year), year)
						- self.get_yearly_finished_goods_and_wip(fiscal_year, total=True, field='net_increase_total')
						+ (closing_stock_current - opening_stock)
					)

				elif is_yearly:
					closing_stock_pre_previous = self.get_sum_grouping_amount("Inventories", "Raw Materials and Packing Material", get_closing_month(self.company, pre_year), pre_year)
					prev_year_closing_stock = self.get_sum_grouping_amount("Inventories", "Raw Materials and Packing Material", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)

					closing_wip_pre_previous = (
						self.get_sum_grouping_amount("Inventories", "Work in Progress", get_closing_month(self.company, pre_year), pre_year)
						+ self.get_sum_grouping_amount("Inventories", "Finished Goods", get_closing_month(self.company, pre_year), pre_year)
						+ self.get_sum_grouping_amount("Inventories", "Stock In Trade", get_closing_month(self.company, pre_year), pre_year)
					)

					prev_year_closing_wip = (
						self.get_sum_grouping_amount("Inventories", "Work in Progress", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)
						+ self.get_sum_grouping_amount("Inventories", "Finished Goods", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)
						+ self.get_sum_grouping_amount("Inventories", "Stock In Trade", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)
					)

					amount = (
						self.get_sum_grouping_amount("Purchases of Stock in Trade", "Purchases of Stock in Trade", get_closing_month(self.company, previous_fiscal_year), previous_fiscal_year)
						+ (prev_year_closing_wip - closing_wip_pre_previous)
						+ (prev_year_closing_stock - closing_stock_pre_previous)
					)

			elif fr_particular.schedule:
				fr_section = get_fr_section(fr_particular.schedule)
				if fr_section.fetch_data_from_trial_balance:
					group_info = get_standalone_group(fr_section.primary_consolidation_group)
					group_type = group_info.group_type
					primary_groups = (
						set(frappe.get_list("FR Standalone Group", filters={"is_primary_group": 1, "group_type": ["in", ["Other Income", "Other Expense"]]}, pluck="name"))
						if group_type in ("Other Income", "Other Expense") else {fr_section.primary_consolidation_group}
					)

					for pg in primary_groups:
						for sec in get_secondary_groups(pg):
							face_amount = self.get_sum_grouping_amount(pg, sec, month, year)
							has_hg_sec_group = frappe.get_all("FR GL Group Mapping",{"company": self.company, "primary_group": pg, "secondary_group": sec, "higher_secondary_group": ["!=", None]}, pluck="higher_secondary_group", distinct=True)
							for hg_sec in has_hg_sec_group:
								face_amount += self.get_sum_grouping_amount(pg, sec, month, year, hg_sec_group=hg_sec)
							if group_type == "Other Income":
								face_amount = face_amount if face_amount < 0 else 0 
							if group_type == "Other Expense":
								face_amount = face_amount if face_amount > 0 else 0 
							if (group_type == "Other Income" and face_amount < 0) or (group_type == "Other Expense" and face_amount > 0) or (group_type not in ("Other Income", "Other Expense") and face_amount != 0):
								amount += face_amount
				else:
					gl_accounts = []
					for g in fr_particular.get('primary_and_secondary_group_mapping') or []:
						gl_accounts.extend(
							frappe.get_list("FR GL Group Mapping", {
								"company": self.company,
								"report_type": "Yearly",
								"primary_group": g.primary_group,
								"secondary_group": g.secondary_group
							}, pluck='gl_account')
						)
					if gl_accounts:
						placeholders = ','.join(['%s'] * len(gl_accounts))
						query = f"""
							SELECT SUM(uploaded_amount) FROM `tabFR Trial Balance Entry`
							WHERE company = %s AND fiscal_year = %s AND month = %s AND gl_account IN ({placeholders})
						"""
						params = [self.company, year, month] + gl_accounts
						amount = (frappe.db.sql(query, params)[0][0] or 0) / 100000
			else:
				gl_accounts = []
				for g in fr_particular.get('primary_and_secondary_group_mapping') or []:
					gl_accounts.extend(
						frappe.get_list("FR GL Group Mapping", {
							"company": self.company,
							"report_type": "Yearly",
							"primary_group": g.primary_group,
							"secondary_group": g.secondary_group
						}, pluck='gl_account')
					)
				if gl_accounts:
					placeholders = ','.join(['%s'] * len(gl_accounts))
					query = f"""
						SELECT SUM(uploaded_amount) FROM `tabFR Trial Balance Entry`
						WHERE company = %s AND fiscal_year = %s AND month = %s AND gl_account IN ({placeholders})
					"""
					params = [self.company, year, month] + gl_accounts
					amount = (frappe.db.sql(query, params)[0][0] or 0) / 100000

			if fr_particular.show_reversed_value:
				amount = -amount

			# Currency conversion commented out
			# if convert and not fr_particular.is_total and not fr_particular.fetch_from_schedule:
			# 	amount *= fx_rate

			amount_cache[cache_key] = flt(round(amount, 3))
			return amount_cache[cache_key]

		# Currency conversion commented out
		# default_currency = frappe.get_value("Company", self.company, 'default_currency')
		# current_fx = self.get_fx_rate(default_currency, cls_month, fiscal_year, 'average_rate') if self.currency != default_currency else 1
		# prev_year_fx = self.get_fx_rate(default_currency, cls_month, previous_fiscal_year, 'average_rate') if self.currency != default_currency else 1

		for row in profit_and_loss_doc.profit_and_loss_template_details:
			if not row.account:
				continue
			current_month_amount = calc_amount_for_particular_monthly(row.account, month, fiscal_year, is_current=True)
		return current_month_amount
