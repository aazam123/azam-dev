# def get_monthly_other_equity_note_data(self, note_type=None, total=False, field=None):
# 	"""Generate monthly Other Equity note table (Retained Earnings & Capital Contribution)"""
# 	cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
# 	month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()
# 	p_and_l_template = self.get('financial_report_details', {'section_type': "Profit & Loss"})[0].section
# 	bs_template = self.get('financial_report_details', {'section_type': "Balance Sheet"})[0].section
# 	net_current_mnt, net_previous_mnt, net_previous_year = self.get_monthly_profit_and_loss_data(p_and_l_template, fetch_for_other_equity = True)
    
# 	default_currency = frappe.get_value("Company", self.company, 'default_currency')
# 	if default_currency != self.currency:
# 		sp_previous_year = round(frappe.get_value("Other Equity Opening Entry", {'company': self.company, 'fiscal_year': pre_year}, 'share_premium_inr')) or 0
# 		bal_previous_year = round(frappe.get_value("Other Equity Opening Entry", {'company': self.company, 'fiscal_year': pre_year}, 'pl_inr')) or 0
# 		tot_asset = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account = frappe.get_value("FR Particular", {'particular_type': 'Total Assets'}, 'name'))
# 		curr_mnt_tot_asset = tot_asset['current_month_amount']
# 		prev_mnt_tot_asset = tot_asset['previous_month_amount']
# 		prev_yr_mnt_tot_asset = tot_asset['previous_year']

# 		tot_cur_lib = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account = frappe.get_value("FR Particular", {'particular_type': 'Total Current Liabilities'}, 'name'))
# 		curr_mnt_tot_cur_lib = tot_cur_lib['current_month_amount']
# 		prev_mnt_tot_cur_lib = tot_cur_lib['previous_month_amount']
# 		prev_yr_mnt_tot_cur_lib = tot_cur_lib['previous_year']

# 		tot_n_cur_lib = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account = frappe.get_value("FR Particular", {'particular_type': 'Total Non Current Liabilities'}, 'name'))
# 		curr_mnt_tot_n_cur_lib = tot_n_cur_lib['current_month_amount']
# 		prev_mnt_tot_n_cur_lib = tot_n_cur_lib['previous_month_amount']
# 		prev_yr_mnt_tot_n_cur_lib = tot_n_cur_lib['previous_year']

# 		equity_share = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account = frappe.get_value("FR Particular", {'particular_type': 'Equity Share Capital'}, 'name'))
# 		curr_mnt_equity_share = equity_share['current_month_amount']
# 		prev_mnt_equity_share = equity_share['previous_month_amount']
# 		prev_yr_mnt_equity_share = equity_share['previous_year']

# 	else:
# 		add_sp_previous_year = 0
# 		sp_previous_year = round(self.sum_group_amt_monthly("Other Equity", "Other equity - Share Premium", cls_month, self.previous_fiscal_year)) or 0
# 		bal_previous_year = round(self.sum_group_amt_monthly("Other Equity", "Other equity - Retained earnings", cls_month, self.previous_fiscal_year)) or 0
# 		add_sp_previous_mnt = (round(self.sum_group_amt_monthly("Other Equity", "Other equity - Share Premium", self.current_month, self.fiscal_year)) or 0) - sp_previous_mnt
# 		add_sp_current_mnt = (round(self.sum_group_amt_monthly("Other Equity", "Other equity - Share Premium", self.current_month, self.fiscal_year)) or 0) - sp_current_mnt


# 	# bal_previous_year = round(self.sum_group_amt_monthly("Other Equity", "Other equity - Retained earnings", cls_month, self.previous_fiscal_year)) or 0
# 	oci_previous_year = round(self.sum_group_amt_monthly("OCI", "OCI", cls_month, self.previous_fiscal_year)) or 0
# 	retained_tot_prev_year = bal_previous_year + net_previous_year + oci_previous_year

# 	bal_current_mnt = retained_tot_prev_year
# 	bal_previous_mnt = retained_tot_prev_year

# 	oci_current_mnt = round(self.sum_group_amt_monthly("OCI", "OCI", self.current_month, self.fiscal_year)) or 0
# 	oci_previous_mnt = round(self.sum_group_amt_monthly("OCI", "OCI", self.previous_month, self.fiscal_year)) or 0

# 	retained_tot_current = bal_current_mnt + net_current_mnt + oci_current_mnt
# 	retained_tot_prev = bal_previous_mnt + net_previous_mnt + oci_previous_mnt

# 	cc_opening_previous_year = round(self.sum_group_amt_monthly("Other Equity", "Other equity - Capital Contribution", cls_month, pre_year)) or 0
# 	cc_add_previous_year = (round(self.sum_group_amt_monthly("Other Equity", "Other equity - Capital Contribution", cls_month, self.previous_fiscal_year)) or 0) - cc_opening_previous_year
# 	cc_closing_previous_year = cc_opening_previous_year + cc_add_previous_year

# 	cc_opening_current = cc_closing_previous_year
# 	cc_opening_previous = cc_closing_previous_year

# 	cc_add_current = (round(self.sum_group_amt_monthly("Other Equity", "Other equity - Capital Contribution", self.current_month, self.fiscal_year)) or 0) - cc_opening_current
# 	cc_add_previous = (round(self.sum_group_amt_monthly("Other Equity", "Other equity - Capital Contribution", self.previous_month, self.fiscal_year)) or 0) - cc_opening_previous

# 	cc_closing_current = cc_opening_current + cc_add_current
# 	cc_closing_previous = cc_opening_previous + cc_add_previous

# 	grand_total_current = retained_tot_current + cc_closing_current + bal_sp_tot_current
# 	grand_total_previous = retained_tot_prev + cc_closing_previous + bal_sp_tot_prev
# 	grand_total_prev_year = retained_tot_prev_year + cc_closing_previous_year + bal_sp_tot_prev_year

# 	if default_currency != self.currency:
# 		add_sp_current_mnt = round(curr_mnt_tot_asset - (curr_mnt_tot_cur_lib + curr_mnt_tot_n_cur_lib + curr_mnt_equity_share) - retained_tot_current) or 0
# 		add_sp_previous_mnt = round(prev_mnt_tot_asset - (prev_mnt_tot_cur_lib + prev_mnt_tot_n_cur_lib + prev_mnt_equity_share) - retained_tot_prev) or 0
# 		add_sp_previous_year = round(prev_yr_mnt_tot_asset - (prev_yr_mnt_tot_cur_lib + prev_yr_mnt_tot_n_cur_lib + prev_yr_mnt_equity_share) - retained_tot_prev_year) or 0

# 	bal_sp_tot_prev_year = sp_previous_year + add_sp_previous_year
# 	sp_current_mnt = bal_sp_tot_prev_year
# 	bal_sp_tot_current = sp_current_mnt + add_sp_current_mnt

# 	sp_previous_mnt = bal_sp_tot_prev_year
# 	bal_sp_tot_prev = sp_previous_mnt + add_sp_previous_mnt

# 	if total and field:
# 		if field == "grand_total_current":
# 			return grand_total_current

# 		elif field == "grand_total_prev_year":
# 			return grand_total_prev_year
# 		else:
# 			return 0

# 	# --- Table Rows ---
# 	data = [
# 		("Securities premium account", "", "", "", True),
# 		("Balance as at the beginning of the year", sp_current_mnt, sp_previous_mnt, sp_previous_year, False),
# 		("Addition: During the year on issue of equity shares", add_sp_current_mnt, add_sp_previous_mnt, add_sp_previous_year, False),
# 		("Balance as at the end of the year", bal_sp_tot_current, bal_sp_tot_prev, bal_sp_tot_prev_year, True),

# 		("Retained earnings", "", "", "", True),
# 		("Balance as at the beginning of the year", bal_current_mnt, bal_previous_mnt, bal_previous_year, False),
# 		("Net Profit for the year", net_current_mnt, net_previous_mnt, net_previous_year, False),
# 		("Other comprehensive income", oci_current_mnt, oci_previous_mnt, oci_previous_year, False),
# 		("Balance as at the end of the year", retained_tot_current, retained_tot_prev, retained_tot_prev_year, True),

# 		("Capital Contribution", "", "", "", True),
# 		("Balance as at the beginning of the year", cc_opening_current, cc_opening_previous, cc_opening_previous_year, False),
# 		("Add: Equity contribution on financial guarantee taken", cc_add_current, cc_add_previous, cc_add_previous_year, False),
# 		("Balance as at the end of the year", cc_closing_current, cc_closing_previous, cc_closing_previous_year, True),
# 		("Total", grand_total_current, grand_total_previous, grand_total_prev_year, True),
# 	]



# def get_monthly_balance_sheet_data(self, template_name, for_other_equity=False, account = None):
# 	"""Get monthly balance sheet data with current month, previous month, and FTM amounts"""
# 	balance_sheet_doc = frappe.get_doc("Balance Sheet Template", template_name)
# 	amount_cache = {}
# 	group_mapping_cache = {}
# 	standalone_group_cache = {}
# 	fr_section_cache = {}
# 	fr_particular_cache = {}

# 	def get_fr_particular(name):
# 		if name not in fr_particular_cache:
# 			fr_particular_cache[name] = frappe.get_doc("FR Particular", name)
# 		return fr_particular_cache[name]

# 	def get_fr_section(name):
# 		if name not in fr_section_cache:
# 			fr_section_cache[name] = frappe.get_doc("FR Section", name)
# 		return fr_section_cache[name]

# 	def get_standalone_group(name):
# 		if name not in standalone_group_cache:
# 			standalone_group_cache[name] = frappe.get_value("Standalone Group", name, ["show_reversed_value", "group_type"], as_dict=True)
# 		return standalone_group_cache[name]

# 	def get_secondary_groups(primary_group):
# 		if primary_group not in group_mapping_cache:
# 			group_mapping_cache[primary_group] = sorted(set(g for g in frappe.get_list("GL Group Mapping", {"primary_group": primary_group}, pluck="secondary_group") if g))
# 		return group_mapping_cache[primary_group]

# 	def get_grouped_gl_amount(gl_accounts, year, month=None):
# 		if not gl_accounts:
# 			return 0
# 		placeholders = ','.join(['%s'] * len(gl_accounts))
# 		query = f"""
# 			SELECT SUM(uploaded_amount) FROM `tabFR Trial Balance Entry`
# 			WHERE company=%s AND fiscal_year=%s AND gl_account IN ({placeholders})
# 		"""
# 		params = [self.company, year] + gl_accounts
# 		if month:
# 			query += " AND month=%s"
# 			params.append(month)
# 		return (frappe.db.sql(query, params)[0][0] or 0) / 100000

# 	def calc_amount_for_particular_monthly(particular_name, month, year, is_current=False, is_yearly=False):
# 		cache_key = (particular_name, month, year)
# 		if cache_key in amount_cache:
# 			return amount_cache[cache_key]

# 		fr_particular = get_fr_particular(particular_name)

# 		if getattr(fr_particular, "is_total", 1):
# 			amount = sum(calc_amount_for_particular_monthly(p.particular, month, year) for p in fr_particular.get("particulars", []))

# 		elif getattr(fr_particular, "fetch_from_schedule", 1):
# 			note_type = frappe.get_value("FR Section", fr_particular.schedule, 'note_type')
# 			if note_type == "Changes in inventories of Finished Goods and Work-In-Progress":
# 				field = 'ftm_total' if is_current else 'net_increase_total'
# 				amount = self.get_monthly_finished_goods_and_wip(note_type, total=True, field=field)
# 			elif note_type == "Cost of Materials Consumed":
# 				field = 'cost_consumed_previous' if is_current else 'cost_consumed_current'
# 				amount = self.get_monthly_cost_of_material_consumed(note_type, total=True, field=field)
# 			elif note_type == "Other Equity" and not for_other_equity and not account:
# 				field = 'grand_total_current' if is_current else 'grand_total_prev_year'
# 				amount = self.get_monthly_other_equity_note_data(note_type, total=True, field=field)
# 			else:
# 				amount = 0

# 		elif getattr(fr_particular, "schedule"):
# 			fr_section = get_fr_section(fr_particular.schedule)
# 			amount = 0
# 			if fr_section.fetch_data_from_trial_balance:
# 				group_info = get_standalone_group(fr_section.primary_consolidation_group)
# 				group_type = group_info.group_type
# 				primary_groups = (set(frappe.get_list("Standalone Group", filters={"is_primary_group": 1,"group_type": ["in", ["Current Tax Liabilities", "Income Tax Assets"]]}, pluck="name")) if group_type in ("Other Income", "Other Expense") else {fr_section.primary_consolidation_group})
# 				for pg in primary_groups:
# 					for sec in get_secondary_groups(pg):
# 						face_amount = self.sum_group_amt_monthly(pg, sec, month, year)
# 						if ((group_type == "Current Tax Liabilities" and face_amount < 0) or (group_type == "Income Tax Assets" and face_amount > 0) or (group_type not in ("Current Tax Liabilities", "Income Tax Assets") and face_amount != 0)):
# 							amount += face_amount
# 			else:
# 				gl_accounts = []
# 				for g in fr_particular.get('primary_and_secondary_group_mapping') or []:
# 					gl_accounts.extend(frappe.get_list("GL Group Mapping",{"company": self.company, "report_type": self.report_type,"primary_group": g.primary_group, "secondary_group": g.secondary_group},pluck='gl_account'))
# 				amount = get_grouped_gl_amount(gl_accounts, year, month)

# 		else:
# 			gl_accounts = []
# 			for g in fr_particular.get('primary_and_secondary_group_mapping') or []:
# 				gl_accounts.extend(frappe.get_list(
# 					"GL Group Mapping",
# 					{"company": self.company, "report_type": self.report_type,
# 					"primary_group": g.primary_group, "secondary_group": g.secondary_group},
# 					pluck='gl_account'
# 				))
# 			amount = get_grouped_gl_amount(gl_accounts, year, month)

# 		if getattr(fr_particular, "show_reversed_value", 0):
# 			amount = -amount

# 		amount_cache[cache_key] = int(round(amount))
# 		return amount_cache[cache_key]

# 	data = []
# 	default_currency = frappe.get_value("Company", self.company, "default_currency")
# 	cls_month = frappe.get_single_value("FR Financial Settings", "closing_month")

# 	current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, "closing_rate")
# 	previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, "closing_rate")
# 	prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, "closing_rate")
# 	for row in balance_sheet_doc.balance_sheet_template_details:
# 		if not row.account:
# 			continue

# 		current_month_amount = calc_amount_for_particular_monthly(row.account, self.current_month, self.fiscal_year, is_current=True) or 0
# 		previous_month_amount = calc_amount_for_particular_monthly(row.account, self.previous_month, self.fiscal_year) or 0
# 		previous_year_amount = calc_amount_for_particular_monthly(row.account, cls_month, self.previous_fiscal_year, is_yearly=True) or 0
# 		ftm_amount = current_month_amount - previous_month_amount

# 		fr_particular = get_fr_particular(row.account)
# 		schedule = getattr(fr_particular, "schedule", "")
# 		note_no = self.get_note_number_for_schedule(schedule) if schedule else ""
# 		particular_type = getattr(fr_particular, "particular_type", "")
# 		if default_currency != self.currency:
# 			if particular_type == "Equity Share Capital":
# 				investment_value = frappe.get_value("FR Equity Entry", {'company': self.company, 'category': "Equity Shares", 'default_currency': default_currency}, 'investment_value')
# 				current_month_amount = previous_month_amount = previous_year_amount = investment_value
# 			elif particular_type == "Other Equity" and not for_other_equity and not account:
# 				pass
# 			else:
# 				current_month_amount *= current_fx
# 				previous_month_amount *= previous_fx
# 				previous_year_amount *= prev_year_fx
# 				ftm_amount = current_month_amount - previous_month_amount


# 		data.append({
# 			"id": row.account,
# 			"account": row.particular_name,
# 			"note_no": note_no,
# 			"current_month_amount": current_month_amount,
# 			"previous_month_amount": previous_month_amount,
# 			"ftm_amount": ftm_amount,
# 			"previous_year": previous_year_amount,
# 			"indent": int(row.indent_level or 0),
# 			"is_bold": row.is_bold,
# 			"header": row.header,
# 			"group": row.group,
# 			"schedule": schedule,
# 		})
    
# 	if for_other_equity and account:
# 		matching_row = next((row for row in data if row["id"] == account), None)
# 		return matching_row

# 	return data



# def get_monthly_finished_goods_and_wip(self, note_type, total, get_face=None, field=None):
#     rows = []
#     cls_month, pre_year = self.get_previous_year_cls_month(self.previous_fiscal_year)
#     default_currency = frappe.get_value("Company", self.company, 'default_currency')

#     month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()

#     current_month_finished_goods = self.sum_group_amt_monthly("Inventories", "Finished Goods", self.current_month, self.fiscal_year)
#     current_month_wip = self.sum_group_amt_monthly("Inventories", "Work in Progress", self.current_month, self.fiscal_year)
#     current_month_sit = self.sum_group_amt_monthly("Inventories", "Stock In Trade", self.current_month, self.fiscal_year)
#     current_month_total = current_month_finished_goods + current_month_wip + current_month_sit

#     cls_previous_month_finished_goods = self.sum_group_amt_monthly("Inventories", "Finished Goods", self.previous_month, self.fiscal_year)
#     cls_previous_month_wip = self.sum_group_amt_monthly("Inventories", "Work in Progress", self.previous_month, self.fiscal_year)
#     cls_previous_month_sit = self.sum_group_amt_monthly("Inventories", "Stock In Trade", self.previous_month, self.fiscal_year)
#     cls_previous_month_total = cls_previous_month_finished_goods + cls_previous_month_wip + cls_previous_month_sit
    
#     previous_month_finished_goods = self.sum_group_amt_monthly("Inventories", "Finished Goods", cls_month, self.previous_fiscal_year)
#     previous_month_wip = self.sum_group_amt_monthly("Inventories", "Work in Progress", cls_month, self.previous_fiscal_year)
#     previous_month_sit = self.sum_group_amt_monthly("Inventories", "Stock In Trade", cls_month, self.previous_fiscal_year)
#     previous_month_total = previous_month_finished_goods + previous_month_wip + previous_month_sit
    
#     ftm_finished_goods =current_month_finished_goods - cls_previous_month_finished_goods
#     ftm_wip = current_month_wip - cls_previous_month_wip
#     ftm_sit = current_month_sit - cls_previous_month_sit
#     ftm_total = ftm_finished_goods + ftm_wip + ftm_sit
    
#     net_increase_finished_goods = current_month_finished_goods - previous_month_finished_goods
#     net_increase_wip = previous_month_wip - current_month_wip
#     net_increase_total = previous_month_total - current_month_total
#     prev_net_total = previous_month_total - cls_previous_month_total
    
#     closing_wip_pre_previous = self.sum_group_amt("Inventories", "Work in Progress", pre_year)
#     closing_fg_pre_previous = self.sum_group_amt("Inventories", "Finished Goods", pre_year)
#     closing_sit_pre_previous = self.sum_group_amt("Inventories", "Stock In Trade", pre_year)

#     prev_year_closing_fg = self.sum_group_amt("Inventories", "Finished Goods", self.previous_fiscal_year)
#     prev_year_closing_wip = self.sum_group_amt("Inventories", "Work in Progress", self.previous_fiscal_year)
#     prev_year_closing_sit = self.sum_group_amt("Inventories", "Stock In Trade", self.previous_fiscal_year)
#     prev_year_amt = (closing_wip_pre_previous+closing_fg_pre_previous+closing_sit_pre_previous) - (prev_year_closing_wip+prev_year_closing_fg+prev_year_closing_sit)
    
#     if total and not get_face:
#         if field == 'net_increase_total':
#             return net_increase_total
#         elif field == 'ftm_total':
#             return ftm_total
#         elif field == 'previous_month_amt':
#             return prev_net_total
#         elif field == 'prev_year_amt':
#             return prev_year_amt
#         else:
#             return 0

#     if default_currency != self.currency:
#         current_fx = self.get_fx_rate(default_currency, self.current_month, self.fiscal_year, 'closing_rate')
#         previous_fx = self.get_fx_rate(default_currency, self.previous_month, self.fiscal_year, 'closing_rate')
#         prev_year_fx = self.get_fx_rate(default_currency, cls_month, self.previous_fiscal_year, 'closing_rate')
#         pre_prev_year_fx = self.get_fx_rate(default_currency, cls_month, pre_year, 'closing_rate')

#         current_month_finished_goods *= current_fx
#         current_month_wip *= current_fx
#         current_month_sit *= current_fx
#         current_month_total *= current_fx

#         cls_previous_month_finished_goods *= previous_fx
#         cls_previous_month_wip *= previous_fx
#         cls_previous_month_sit *= previous_fx
#         cls_previous_month_total *= previous_fx

#         previous_month_finished_goods *= prev_year_fx
#         previous_month_wip *= prev_year_fx
#         previous_month_sit *= prev_year_fx
#         previous_month_total *= prev_year_fx

#         ftm_finished_goods = current_month_finished_goods - cls_previous_month_finished_goods
#         ftm_wip = current_month_wip - cls_previous_month_wip
#         ftm_sit = current_month_sit - cls_previous_month_sit
#         ftm_total = ftm_finished_goods + ftm_wip + ftm_sit

#         net_increase_finished_goods = current_month_finished_goods - previous_month_finished_goods
#         net_increase_wip = current_month_wip - previous_month_wip
#         net_increase_total = previous_month_total - current_month_total
#         prev_net_total = previous_month_total - cls_previous_month_total

#         prev_year_closing_fg *= prev_year_fx
#         prev_year_closing_wip *= prev_year_fx
#         prev_year_closing_sit *= prev_year_fx

#         closing_fg_pre_previous *= pre_prev_year_fx
#         closing_wip_pre_previous *= pre_prev_year_fx
#         closing_sit_pre_previous *= pre_prev_year_fx

#         prev_year_amt = ((closing_wip_pre_previous + closing_fg_pre_previous + closing_sit_pre_previous) - (prev_year_closing_wip + prev_year_closing_fg + prev_year_closing_sit))

#     if get_face and total:
#         if field == 'net_increase_total':
#             return net_increase_total
#         elif field == 'ftm_total':
#             return ftm_total
#         elif field == 'previous_month_amt':
#             return prev_net_total
#         elif field == 'prev_year_amt':
#             return prev_year_amt
#         else:
#             return 0

#     rows.extend([
#         {"particulars": "Inventories at the end of the month","current_month_amt": 0,"previous_month_amt": 0,"ftm_amt": 0, "previous_year_amt": 0, "is_subtotal": True},
#         {"particulars": "Finished goods","current_month_amt": current_month_finished_goods,"previous_month_amt": cls_previous_month_finished_goods ,"ftm_amt": ftm_finished_goods, "previous_year_amt": prev_year_closing_fg, "is_subtotal": False},
#         {"particulars": "Work-in-progress","current_month_amt": current_month_wip,"previous_month_amt": cls_previous_month_wip,"ftm_amt": ftm_wip, "previous_year_amt": prev_year_closing_wip, "is_subtotal": False},
#         {"particulars": "Stock-in-trade","current_month_amt": current_month_sit,"previous_month_amt": cls_previous_month_sit,"ftm_amt": ftm_sit, "previous_year_amt": prev_year_closing_sit, "is_subtotal": False},
#         {"particulars": "","current_month_amt": current_month_total,"previous_month_amt": cls_previous_month_total ,"ftm_amt": ftm_total, "previous_year_amt": (prev_year_closing_wip+prev_year_closing_fg+prev_year_closing_sit), "is_subtotal": False},
#         {"particulars": "Inventories at the beginning of the month","current_month_amt": 0,"previous_month_amt": 0,"ftm_amt": 0, "previous_year_amt": 0, "is_subtotal": True},
#         {"particulars": "Finished goods","current_month_amt": previous_month_finished_goods,"previous_month_amt": previous_month_finished_goods,"ftm_amt": 0, "previous_year_amt": closing_fg_pre_previous, "is_subtotal": False},
#         {"particulars": "Work-in-progress","current_month_amt": previous_month_wip,"previous_month_amt": previous_month_wip,"ftm_amt": 0, "previous_year_amt": closing_wip_pre_previous, "is_subtotal": False},
#         {"particulars": "Stock-in-trade", "current_month_amt": previous_month_sit, "previous_month_amt": previous_month_sit, "ftm_amt": 0, "previous_year_amt": closing_sit_pre_previous, "is_subtotal": False},
#         {"particulars": "","current_month_amt": previous_month_total,"previous_month_amt": previous_month_total,"ftm_amt": 0, "previous_year_amt": (closing_wip_pre_previous + closing_fg_pre_previous+closing_sit_pre_previous), "is_subtotal": False},
#         {"particulars": "Net increase","current_month_amt": net_increase_total,"previous_month_amt": prev_net_total,"ftm_amt": prev_net_total - net_increase_total, "previous_year_amt": prev_year_amt,"is_subtotal": True}
#     ])
    
#     html = f'''
#     <table style="width:100%; border-collapse:collapse; font-size:13px;">
#         <thead>
#             <tr>
#                 <th style="border:1px solid #222; text-align:left; width:40%; padding:6px 8px;"><b>Particulars</b></th>
#                 <th style="border:1px solid #222; text-align:center; padding:6px 8px;"><b>{month_end_label}</b></th>
#                 <th style="border:1px solid #222; text-align:center; padding:6px 8px;"><b>FTM</b></th>
#                 <th style="border:1px solid #222; text-align:center; padding:6px 8px;"><b>{current_fiscal_year_end_label}</b></th>
#                 <th style="border:1px solid #222; text-align:center; padding:6px 8px;"><b>{previous_fiscal_year_end_label}</b></th>
#             </tr>
#         </thead>
#         <tbody>
#     '''
    
#     for row in rows:
#         # Format amounts
#         current_month_amt_str = f"{row['current_month_amt']:,.0f}" if row['current_month_amt'] else ""
#         previous_month_amt_str = f"{row['previous_month_amt']:,.0f}" if row['previous_month_amt'] else ""
#         ftm_amt_str = f"{row['ftm_amt']:,.0f}" if row['ftm_amt'] else ""
#         previous_year_amt = f"{row['previous_year_amt']:,.0f}" if row['previous_year_amt'] else ""
        
#         # Style for totals
#         bold_style = "font-weight: bold;" if row["is_subtotal"] else ""
#         border_style = "border:1px solid #222;" if row["is_subtotal"] else "border-left:1px solid #222; border-right:1px solid #222; border-top:none; border-bottom:none;"
        
#         html += f'''
#             <tr>
#                 <td style="{border_style} text-align:left; padding:6px 8px; {bold_style}">{row['particulars']}</td>
#                 <td style="{border_style} text-align:right; padding:6px 8px; {bold_style} background-color:#e8f5e8;">{current_month_amt_str}</td>
#                 <td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{ftm_amt_str}</td>
#                 <td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{previous_month_amt_str}</td>
#                 <td style="{border_style} text-align:right; padding:6px 8px; {bold_style}">{previous_year_amt}</td>
#             </tr>
#         '''
    
#     html += "</tbody></table>"
#     return html



# def get_monthly_investment_non_current_note_data(self, total=False, field=None):
#     month_end_label, current_fiscal_year_end_label, previous_fiscal_year_end_label = self.get_monthly_dates()

#     data = [{
#         "particulars": "Investment in equity Instruments of subsidiaries measured at Cost (Unquoted, Fully paid Up)",
#         "face_value": "", "shares_current": "", "amount_current": "",
#         "shares_previous": "", "amount_previous": "",
#         "shares_previous_year": "", "amount_previous_year": "",
#         "bold": 1
#     }]

#     fiscal_doc = frappe.get_doc("Fiscal Year", self.fiscal_year)
#     all_companies = frappe.get_list("FR Equity Entry", {"holding_company": self.company}, pluck="company")

#     total_current = total_previous = total_previous_year = 0

#     for company in all_companies:
#         current_month_start = self.get_month_start_date(self.current_month)
#         current_month_end = self.get_month_end_date(self.current_month)
#         previous_month_start = self.get_month_start_date(self.previous_month)
#         previous_month_end = self.get_month_end_date(self.previous_month)
#         prev_year_same_month_start = self.get_same_month_last_year_start()
#         prev_year_same_month_end = self.get_same_month_last_year_end()

#         face_value = f"{(frappe.get_value('Company', company, 'share_capital_amount')) / 100} {frappe.get_value('Company', company, 'default_currency')}"
#         previous_equity_entries = frappe.get_all("FR Equity Entry", 
#             filters={"company": company, "holding_company": self.company, "category": "Equity Shares", "posting_date": ["between", [prev_year_same_month_start, prev_year_same_month_end]]},
#             fields=["no_of_shares", "investment_value"], order_by="posting_date desc")

#         current_month_entries = frappe.get_all("FR Equity Entry", 
#             filters={"company": company, "holding_company": self.company, "category": "Equity Shares", "posting_date": ["between", [current_month_start, current_month_end]]},
#             fields=["no_of_shares", "investment_value"], order_by="posting_date desc")

#         previous_month_entries = frappe.get_all("FR Equity Entry", 
#             filters={"company": company, "holding_company": self.company, "category": "Equity Shares", "posting_date": ["between", [previous_month_start, previous_month_end]]},
#             fields=["no_of_shares", "investment_value"], order_by="posting_date desc")

#         e_previous = previous_equity_entries[0] if previous_equity_entries else None
#         e_current_month = current_month_entries[0] if current_month_entries else None
#         e_previous_month = previous_month_entries[0] if previous_month_entries else None

#         face_value = face_value
#         shares_current = e_current_month.get("no_of_shares", 0) if e_current_month else 0
#         amount_current = e_current_month.get("investment_value", 0) if e_current_month else 0
#         shares_previous = e_previous_month.get("no_of_shares", 0) if e_previous_month else 0
#         amount_previous = e_previous_month.get("investment_value", 0) if e_previous_month else 0
#         shares_previous_year = e_previous.get("no_of_shares", 0) if e_previous else 0
#         amount_previous_year = e_previous.get("investment_value", 0) if e_previous else 0

#         total_current += amount_current
#         total_previous += amount_previous
#         total_previous_year += amount_previous_year

#         data.append({
#             "particulars": company,
#             "face_value": face_value,
#             "shares_current": shares_current,
#             "amount_current": amount_current,
#             "shares_previous": shares_previous,
#             "amount_previous": amount_previous,
#             "shares_previous_year": shares_previous_year,
#             "amount_previous_year": amount_previous_year,
#             "bold": 0
#         })

#     if is_total:
#         if field == "total_current":
#             return total_current
#         if field == "total_previous_year":
#             return total_previous_year

#     data.append({
#         "particulars": "Total of Equity Instruments Measured at cost",
#         "face_value": "",
#         "shares_current": "",
#         "amount_current": f"{total_current:,.0f}",
#         "shares_previous": "",
#         "amount_previous": f"{total_previous:,.0f}",
#         "shares_previous_year": "",
#         "amount_previous_year": f"{total_previous_year:,.0f}",
#         "bold": 1
#     })

#     # HTML table
#     table = f'''
#     <table style="width:100%; border-collapse:collapse; font-size:12px; margin-top:-25pt;">
#         <thead>
#             <tr>
#                 <th rowspan="2" style="border:1px solid #222; width:35%; text-align:left; padding:6px 8px; background:#fafbfc;"><b>Particulars</b></th>
#                 <th rowspan="2" style="border:1px solid #222; width:10%; text-align:center; background:#fafbfc;"><b>Face Value</b></th>
#                 <th colspan="2" style="border:1px solid #222; text-align:center; background:#e8f5e8;"><b>{month_end_label}</b></th>
#                 <th colspan="2" style="border:1px solid #222; text-align:center; background:#fafbfc;"><b>{current_fiscal_year_end_label}</b></th>
#                 <th colspan="2" style="border:1px solid #222; text-align:center; background:#fafbfc;"><b>{previous_fiscal_year_end_label}</b></th>
#             </tr>
#             <tr>
#                 <th style="border:1px solid #222; text-align:center; background:#e8f5e8;">No. of Shares</th>
#                 <th style="border:1px solid #222; text-align:center; background:#e8f5e8;">(₹ in lacs)</th>
#                 <th style="border:1px solid #222; text-align:center; width:8%;">No. of Shares</th>
#                 <th style="border:1px solid #222; text-align:center;">(₹ in lacs)</th>
#                 <th style="border:1px solid #222; text-align:center;">No. of Shares</th>
#                 <th style="border:1px solid #222; text-align:center;">(₹ in lacs)</th>
#             </tr>
#         </thead>
#         <tbody>
#     '''

#     for row in data:
#         bold = "font-weight: bold;" if row["bold"] else ""
#         bg = "#e8f5e8" if not row["bold"] else "#f4f4f4"

#         table += f'''
#         <tr>
#             <td style="border:1px solid #222; padding:6px 8px; text-align:left; {bold}">{row["particulars"]}</td>
#             <td style="border:1px solid #222; text-align:center;">{row["face_value"]}</td>
#             <td style="border:1px solid #222; text-align:right; background:{bg};">{row["shares_current"]}</td>
#             <td style="border:1px solid #222; text-align:right; background:{bg};">{row["amount_current"]}</td>
#             <td style="border:1px solid #222; text-align:right;">{row["shares_previous"]}</td>
#             <td style="border:1px solid #222; text-align:right;">{row["amount_previous"]}</td>
#             <td style="border:1px solid #222; text-align:right;">{row["shares_previous_year"]}</td>
#             <td style="border:1px solid #222; text-align:right;">{row["amount_previous_year"]}</td>
#         </tr>
#         '''

#     table += "</tbody></table>"
#     return table



# Code Before Indrageets Change of Other Equity Note
# def get_yearly_other_equity_note_data(self, current_year, previous_year, section_description="", total=False, field=None):
# 	"""Generate yearly Other Equity note table"""
# 	cls_month, pre_year = self.get_previous_year_cls_month(previous_year)
# 	month_end_label, prev_fy_label = self.get_yearly_dates()

# 	pnl_template = self.get("financial_report_details", {"section_type": "Profit & Loss"})[0].section
# 	bs_template = self.get("financial_report_details", {"section_type": "Balance Sheet"})[0].section

# 	net_cur, net_prev, net_prev_year = self.get_monthly_profit_and_loss_data(pnl_template, fetch_for_other_equity=True)

# 	default_currency = frappe.get_value("Company", self.company, "default_currency")

# 	if default_currency != self.currency:
# 		sp_prev_year = round(frappe.get_value("Other Equity Opening Entry", {"company": self.company, "fiscal_year": pre_year}, "share_premium_inr") or 0, self.show_decimal_value)
# 		bal_prev_year = round(frappe.get_value("Other Equity Opening Entry", {"company": self.company, "fiscal_year": pre_year}, "pl_inr") or 0, self.show_decimal_value)

# 		tot_asset = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account=frappe.get_value("FR Particular", {"particular_type": "Total Assets"}, "name"))
# 		tot_cur_liab = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account=frappe.get_value("FR Particular", {"particular_type": "Total Current Liabilities"}, "name"))
# 		tot_ncur_liab = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account=frappe.get_value("FR Particular", {"particular_type": "Total Non Current Liabilities"}, "name"))
# 		equity_share = self.get_monthly_balance_sheet_data(bs_template, for_other_equity=True, account=frappe.get_value("FR Particular", {"particular_type": "Equity Share Capital"}, "name"))

# 		cur_tot_asset, prev_tot_asset = tot_asset["current_month_amount"], tot_asset["previous_year"]
# 		cur_cur_liab, prev_cur_liab = tot_cur_liab["current_month_amount"], tot_cur_liab["previous_year"]
# 		cur_ncur_liab, prev_ncur_liab = tot_ncur_liab["current_month_amount"], tot_ncur_liab["previous_year"]
# 		cur_eq_share, prev_eq_share = equity_share["current_month_amount"], equity_share["previous_year"]

# 	else:
# 		sp_prev_year = abs(round(self.get_sum_grouping_amount("Other Equity", "Other equity - Share Premium", cls_month, previous_year), self.show_decimal_value))
# 		bal_prev_year = -round(self.get_sum_grouping_amount("Other Equity", "Other equity - Retained earnings", cls_month, previous_year), self.show_decimal_value)
# 		add_sp_prev_year = add_sp_cur = add_sp_prev = 0

# 	oci_prev_year = round(self.get_sum_grouping_amount("OCI", "OCI", cls_month, previous_year), self.show_decimal_value)
# 	retained_prev_year = round(bal_prev_year + net_prev_year + oci_prev_year, self.show_decimal_value)

# 	oci_cur = round(self.get_sum_grouping_amount("OCI", "OCI", self.current_month, current_year), self.show_decimal_value)
# 	retained_cur = round(retained_prev_year + net_cur + oci_cur, self.show_decimal_value)
# 	retained_prev = round(retained_prev_year + net_prev, self.show_decimal_value)

# 	cc_open_prev = round(self.get_sum_grouping_amount("Other Equity", "Other equity - Capital Contribution", cls_month, pre_year), self.show_decimal_value)
# 	cc_add_prev = round(self.get_sum_grouping_amount("Other Equity", "Other equity - Capital Contribution", cls_month, previous_year), self.show_decimal_value) - cc_open_prev
# 	cc_close_prev = round(cc_open_prev + cc_add_prev, self.show_decimal_value)

# 	cc_add_cur = round(self.get_sum_grouping_amount("Other Equity", "Other equity - Capital Contribution", cls_month, current_year), self.show_decimal_value) - cc_close_prev
# 	cc_close_cur = round(cc_close_prev + cc_add_cur, self.show_decimal_value)

# 	if default_currency != self.currency:
# 		add_sp_prev_year = round(prev_tot_asset - (prev_cur_liab + prev_ncur_liab + prev_eq_share) - retained_prev_year - sp_prev_year, self.show_decimal_value)
# 		add_sp_cur = round(cur_tot_asset - (cur_cur_liab + cur_ncur_liab + cur_eq_share) - retained_cur - (sp_prev_year + add_sp_prev_year), self.show_decimal_value)
# 		add_sp_prev = round(prev_tot_asset - (prev_cur_liab + prev_ncur_liab + prev_eq_share) - retained_prev - (sp_prev_year + add_sp_prev_year), self.show_decimal_value)

# 	sp_open = sp_prev_year + add_sp_prev_year
# 	sp_cur, sp_prev = sp_open + add_sp_cur, sp_open + add_sp_prev

# 	for_exc_open = -round(self.get_sum_grouping_amount("Other Equity", "Opening - Currency Fluctuation", cls_month, previous_year), self.show_decimal_value)
# 	for_exc_add_prev = -round(self.get_sum_grouping_amount("Other Equity", "Currency Fluctuation", cls_month, previous_year), self.show_decimal_value)
# 	for_exc_prev_year = round(for_exc_open + for_exc_add_prev, self.show_decimal_value)

# 	for_exc_add_cur = -round(self.get_sum_grouping_amount("Other Equity", "Currency Fluctuation", cls_month, current_year), self.show_decimal_value)
# 	for_exc_cur = round(for_exc_prev_year + for_exc_add_cur, self.show_decimal_value)

# 	grand_cur = round(retained_cur + cc_close_cur + sp_cur + for_exc_cur, self.show_decimal_value)
# 	grand_prev = round(retained_prev + cc_close_prev + sp_prev + for_exc_prev_year, self.show_decimal_value)
# 	grand_prev_year = round(retained_prev_year + cc_close_prev + sp_open + for_exc_prev_year, self.show_decimal_value)

# 	if total and field:
# 		if field == "grand_total_current":
# 			return grand_cur
# 		elif field == "grand_total_prev_year":
# 			return grand_prev_year
        
# 	rows = [
# 		("Securities premium account", "", "", True),
# 		("Balance as at the beginning of the year", sp_open, sp_prev_year, False),
# 		("Addition during the year", add_sp_cur, add_sp_prev_year, False),
# 		("Balance as at the end of the year", sp_cur, sp_open, True),

# 		("Surplus in Foreign Exchange Reserves", "", "", True),
# 		("Balance as at the beginning of the year", for_exc_prev_year, for_exc_open, False),
# 		("Addition during the year", for_exc_add_cur, for_exc_add_prev, False),
# 		("Balance as at the end of the year", for_exc_cur, for_exc_prev_year, True),

# 		("Retained earnings", "", "", True),
# 		("Balance as at the beginning of the year", retained_prev_year, bal_prev_year, False),
# 		("Net Profit for the year", net_cur, net_prev_year, False),
# 		("Other comprehensive income", oci_cur, oci_prev_year, False),
# 		("Balance as at the end of the year", retained_cur, retained_prev_year, True),

# 		("Capital Contribution", "", "", True),
# 		("Balance as at the beginning of the year", cc_close_prev, cc_open_prev, False),
# 		("Add: Equity contribution on financial guarantee taken", cc_add_cur, cc_add_prev, False),
# 		("Balance as at the end of the year", cc_close_cur, cc_close_prev, True),

# 		("Total", grand_cur, grand_prev_year, True),
# 	]

# 	html = f"""
# 	<table style="width:100%; border-collapse:collapse; border-spacing:0; font-size:13px; border:1px solid #000; background-color:#fff;">
# 	<thead>
# 	<tr style="border-bottom:2px solid #222; background-color:#fff;">
# 		<th style="border-left:1px solid #222; color: #4472C4; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; width:60%; padding:6px 8px; background-color:#fff; text-align:left;"><b>Particulars</b></th>
# 		<th style="border-left:1px solid #222; color: #4472C4; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:6px 8px; background-color:#fff; text-align:center;"><b>{month_end_label}</b></th>
# 		<th style="border-left:1px solid #222; color: #4472C4; border-right:1px solid #222; border-top:1px solid #222; border-bottom:2px solid #222; padding:6px 8px; background-color:#fff; text-align:center;"><b>{prev_fy_label}</b></th>
# 	</tr>
# 	</thead><tbody>
# 	"""

# 	for i, (p, c, py, b) in enumerate(rows):
# 		style = "font-weight:bold;" if b else ""
# 		# Only vertical borders for regular rows, full borders for bold/total rows
# 		if b:
# 			border = "border-top:1px solid #222; border-bottom:1px solid #222;"
# 		else:
# 			border = "border-top:none; border-bottom:none;"
# 		html += f"""<tr style='background-color:#fff;'>
# 			<td style='{border} border-left:1px solid #222; border-right:1px solid #222; padding:6px 8px; text-align:left; background-color:#fff; {style}'>{p}</td>
# 			<td style='{border} border-left:1px solid #222; border-right:1px solid #222; padding:6px 8px; text-align:right; background-color:#E8F5E8; {style}'>{c}</td>
# 			<td style='{border} border-left:1px solid #222; border-right:1px solid #222; padding:6px 8px; text-align:right; background-color:#fff; {style}'>{py}</td></tr>"""

# 	html += "</tbody></table>"
# 	return section_description.replace("{{note_table}}", html)
