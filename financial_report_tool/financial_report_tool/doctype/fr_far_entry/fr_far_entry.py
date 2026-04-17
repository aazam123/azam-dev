# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, getdate
from frappe.model.document import Document

class FRFAREntry(Document):
	def before_insert(self):
		if self.fiscal_year and self.company:
			existing_entry = frappe.db.exists("FR FAR Entry", {"fiscal_year": self.fiscal_year, "company": self.company})
			if existing_entry:
				frappe.throw(f"An entry for fiscal year {self.fiscal_year} and company {self.company} already exists.")
	
	def to_lakhs(self, value):
		return flt(value) / 100000

	def get_all_child_groups(self, parent):
		children = frappe.get_all(
			"FR Asset Group",
			filters={"parent_fr_asset_group": parent},
			pluck="asset_group"
		)
		all_groups = [parent]
		for child in children:
			all_groups.extend(self.get_all_child_groups(child))
		return all_groups

	def get_previous_fiscal_year_name(self, fiscal_year):
		return frappe.get_value(
			"FR Previous Fiscal Year",
			{"current_fiscal_year": fiscal_year},
			"previous_fiscal_year"
		)

	def before_save(self):
		if self.fiscal_year and self.company:
			previous_fiscal_year = self.get_previous_fiscal_year_name(self.fiscal_year)
			if previous_fiscal_year and previous_fiscal_year != self.previous_fiscal_year:
				self.previous_fiscal_year = previous_fiscal_year

		ppe_tot_curr_close, ppe_tot_curr_acc_close, ppe_tot_prev_close, ppe_tot_prev_acc_close = 0, 0, 0, 0
		oth_tot_prev_close, oth_tot_prev_acc_close, oth_tot_curr_close, oth_tot_curr_acc_close = 0, 0, 0, 0
		rou_tot_prev_close, rou_tot_prev_acc_close, rou_tot_curr_close, rou_tot_curr_acc_close = 0, 0, 0, 0
		cwip_cy_total, cwip_py_total, iaud_cy_total, iaud_py_total = 0, 0, 0, 0
		cwip_cy_suspended_total, cwip_py_suspended_total, iaud_cy_suspended_total, iaud_py_suspended_total = 0, 0, 0, 0

		for i in self.ppe_gross_carrying:
			i.as_at_previous_year = i.as_at_pre_previous_year + i.prev_addition + i.prev_disposals
			i.as_at_current_year = i.as_at_previous_year + i.curr_addition + i.curr_disposals
			ppe_tot_curr_close += flt(i.as_at_current_year)
			ppe_tot_prev_close += flt(i.as_at_previous_year)

		for i in self.ppe_accumulated_depreciation:
			i.as_at_previous_year = i.as_at_pre_previous_year + i.prev_addition + i.prev_disposals
			i.as_at_current_year = i.as_at_previous_year + i.curr_addition + i.curr_disposals
			ppe_tot_curr_acc_close += flt(i.as_at_current_year)
			ppe_tot_prev_acc_close += flt(i.as_at_previous_year)

		for i in self.other_gross_carrying:
			i.as_at_previous_year = i.as_at_pre_previous_year + i.prev_addition + i.prev_disposals
			i.as_at_current_year = i.as_at_previous_year + i.curr_addition + i.curr_disposals
			oth_tot_curr_close += flt(i.as_at_current_year)
			oth_tot_prev_close += flt(i.as_at_previous_year)

		for i in self.other_accumulated_depreciation:
			i.as_at_previous_year = i.as_at_pre_previous_year + i.prev_addition + i.prev_disposals
			i.as_at_current_year = i.as_at_previous_year + i.curr_addition + i.curr_disposals
			oth_tot_curr_acc_close += flt(i.as_at_current_year)
			oth_tot_prev_acc_close += flt(i.as_at_previous_year)

		for i in self.rou_gross_carrying:
			i.as_at_previous_year = i.as_at_pre_previous_year + i.prev_addition + i.prev_disposals
			i.as_at_current_year = i.as_at_previous_year + i.curr_addition + i.curr_disposals
			rou_tot_curr_close += flt(i.as_at_current_year)
			rou_tot_prev_close += flt(i.as_at_previous_year)

		for i in self.rou_accumulated_depreciation:
			i.as_at_previous_year = i.as_at_pre_previous_year + i.prev_addition + i.prev_disposals
			i.as_at_current_year = i.as_at_previous_year + i.curr_addition + i.curr_disposals
			rou_tot_curr_acc_close += flt(i.as_at_current_year)
			rou_tot_prev_acc_close += flt(i.as_at_previous_year)

		for i in self.intangible_details:
			if i.amount_in_iaud_for_a_period_of != "Total":
				iaud_py_total += i.previous_projects_in_progress
				iaud_cy_total += i.current_projects_in_progress
				iaud_py_suspended_total += i.previous_projects_temporarily_suspended
				iaud_cy_suspended_total += i.current_projects_temporarily_suspended
			elif i.amount_in_iaud_for_a_period_of == "Total":
				i.previous_projects_in_progress = iaud_py_total
				i.current_projects_in_progress = iaud_cy_total
				i.previous_projects_temporarily_suspended = iaud_py_suspended_total
				i.current_projects_temporarily_suspended = iaud_cy_suspended_total

		for i in self.cwip_details:
			if i.amount_in_cwip_for_a_period_of != "Total":
				cwip_py_total += i.previous_projects_in_progress
				cwip_cy_total += i.current_projects_in_progress
				cwip_py_suspended_total += i.previous_projects_temporarily_suspended
				cwip_cy_suspended_total += i.current_projects_temporarily_suspended
			elif i.amount_in_cwip_for_a_period_of == "Total":
				i.previous_projects_in_progress = cwip_py_total
				i.current_projects_in_progress = cwip_cy_total
				i.previous_projects_temporarily_suspended = cwip_py_suspended_total
				i.current_projects_temporarily_suspended = cwip_cy_suspended_total

		self.ppe_net_py_total = self.to_lakhs(ppe_tot_prev_close) - self.to_lakhs(ppe_tot_prev_acc_close)
		self.ppe_net_cy_total = self.to_lakhs(ppe_tot_curr_close) - self.to_lakhs(ppe_tot_curr_acc_close)
		self.other_py_total = self.to_lakhs(oth_tot_prev_close) - self.to_lakhs(oth_tot_prev_acc_close)
		self.other_cy_total = self.to_lakhs(oth_tot_curr_close) - self.to_lakhs(oth_tot_curr_acc_close)
		self.rou_net_py_total = self.to_lakhs(rou_tot_prev_close) - self.to_lakhs(rou_tot_prev_acc_close)
		self.rou_net_cy_total = self.to_lakhs(rou_tot_curr_close) - self.to_lakhs(rou_tot_curr_acc_close)
		self.cwip_py_total = self.to_lakhs(cwip_py_total)
		self.cwip_cy_total = self.to_lakhs(cwip_cy_total)
		self.iaud_py_total = self.to_lakhs(iaud_py_total)
		self.iaud_cy_total = self.to_lakhs(iaud_cy_total)

	@frappe.whitelist()
	def get_previous_fiscal_year(self, fiscal_year):
		"""Get the previous fiscal year for a given fiscal year."""
		return frappe.get_value(
			"FR Previous Fiscal Year",
			{"current_fiscal_year": fiscal_year},
			"previous_fiscal_year"
		)

	@frappe.whitelist()
	def process_calculation(self):
		"""Process the calculation for the FR FAR Entry."""
		self.process_property_plant_and_equipment()
		self.process_other_intangible_assets()
		self.process_right_of_use_assets()
		self.process_cwip()
		self.process_iaud()
		self.save()
		return "Calculation completed successfully."

	def process_property_plant_and_equipment(self):
		self.ppe_gross_carrying = []
		self.ppe_accumulated_depreciation = []
		tot_curr_close, tot_curr_acc_close, tot_prev_close, tot_prev_acc_close = 0, 0, 0, 0
		ppe_asset_classes = frappe.get_list(
			"FR Asset Group",
			filters={"asset_group_type": "Property Plant and Equipment", "is_group": 1},
			pluck="asset_group"
		)

		if not self.fiscal_year:
			return

		previous_fiscal_year = self.previous_fiscal_year or self.get_previous_fiscal_year_name(self.fiscal_year)
		if previous_fiscal_year and previous_fiscal_year != self.previous_fiscal_year:
			self.previous_fiscal_year = previous_fiscal_year
		pre_previous_fiscal_year = self.get_previous_fiscal_year_name(previous_fiscal_year) if previous_fiscal_year else None
		if pre_previous_fiscal_year and hasattr(self, "pre_previous_year"):
			self.pre_previous_year = pre_previous_fiscal_year

		def get_fy_dates(fiscal_year):
			if not fiscal_year:
				return None, None
			fy_doc = frappe.get_doc("Fiscal Year", fiscal_year)
			return getdate(fy_doc.year_start_date), getdate(fy_doc.year_end_date)

		prev_start, prev_end = get_fy_dates(previous_fiscal_year)
		curr_start, curr_end = get_fy_dates(self.fiscal_year)

		if not (prev_start and prev_end and curr_start and curr_end):
			return

		for asset_class in ppe_asset_classes:
			valid_asset_groups = self.get_all_child_groups(asset_class)

			prev_opening_data = frappe.db.get_all(
				"FR Asset Register Entry",
				fields=["sap_cav", "sap_acc_dep"],
				filters={
					"company": self.company,
					"asset_group": ["in", valid_asset_groups],
					"ordinary_depreciation_start_date": ["<", prev_start],
					"fiscal_year": self.pre_previous_year
				}
			)

			prev_opening_value = sum(flt(d.sap_cav) for d in prev_opening_data)
			prev_acc_opening = sum(flt(d.sap_acc_dep) for d in prev_opening_data)

			prev_data = frappe.db.get_all(
				"FR Asset Register Entry",
				fields=[
					"sap_transaction_acq_value",
					"sap_tran_acq_value",
					"sap_plan_dep",
					"sap_tran_accu_dep"
				],
				filters={
					"company": self.company,
					"asset_group": ["in", valid_asset_groups],
					"ordinary_depreciation_start_date": ["between", [prev_start, prev_end]],
					'fiscal_year': self.previous_fiscal_year
				}
			)

			prev_add = sum(flt(d.sap_transaction_acq_value) for d in prev_data)
			prev_dis = sum(flt(d.sap_tran_acq_value) for d in prev_data)
			prev_close = prev_opening_value + prev_add + prev_dis

			prev_acc_add = sum(flt(d.sap_plan_dep) for d in prev_data)
			prev_acc_dis = sum(flt(d.sap_tran_accu_dep) for d in prev_data)
			prev_acc_close = prev_acc_opening + prev_acc_add + prev_acc_dis

			curr_data = frappe.db.get_all(
				"FR Asset Register Entry",
				fields=[
					"sap_transaction_acq_value",
					"sap_tran_acq_value",
					"sap_plan_dep",
					"sap_tran_accu_dep"
				],
				filters={
					"company": self.company,
					"asset_group": ["in", valid_asset_groups],
					"ordinary_depreciation_start_date": ["between", [curr_start, curr_end]],
					'fiscal_year': self.fiscal_year
				}
			)

			curr_add = sum(flt(d.sap_transaction_acq_value) for d in curr_data)
			curr_dis = sum(flt(d.sap_tran_acq_value) for d in curr_data)
			curr_close = prev_close + curr_add + curr_dis

			curr_acc_add = sum(flt(d.sap_plan_dep) for d in curr_data)
			curr_acc_dis = sum(flt(d.sap_tran_accu_dep) for d in curr_data)
			curr_acc_close = prev_acc_close + curr_acc_add + curr_acc_dis

			self.append("ppe_gross_carrying", {
				"particulars": asset_class,
				"as_at_pre_previous_year": prev_opening_value,
				"prev_addition": prev_add,
				"prev_disposals": prev_dis,
				"as_at_previous_year": prev_close,
				"curr_addition": curr_add,
				"curr_disposals": curr_dis,
				"as_at_current_year": curr_close
			})

			self.append("ppe_accumulated_depreciation", {
				"particulars": asset_class,
				"as_at_pre_previous_year": (prev_acc_opening),
				"prev_addition": (prev_acc_add),
				"prev_disposals": (prev_acc_dis),
				"as_at_previous_year": (prev_acc_close),
				"curr_addition": (curr_acc_add),
				"curr_disposals": (curr_acc_dis),
				"as_at_current_year": (curr_acc_close)
			})
			tot_curr_close += (curr_close)
			tot_curr_acc_close += (curr_acc_close)
			tot_prev_close += (prev_close)
			tot_prev_acc_close += (prev_acc_close)

		self.ppe_net_py_total = self.to_lakhs(tot_prev_close) - self.to_lakhs(tot_prev_acc_close)
		self.ppe_net_cy_total = self.to_lakhs(tot_curr_close) - self.to_lakhs(tot_curr_acc_close)

	def process_other_intangible_assets(self):
		self.other_gross_carrying = []
		self.other_accumulated_depreciation = []
		tot_prev_close, tot_prev_acc_close, tot_curr_close, tot_curr_acc_close = 0, 0, 0, 0
		intangible_asset_classes = frappe.get_list(
			"FR Asset Group",
			filters={"asset_group_type": "Other Intangible Assets", "is_group": 1},
			pluck="asset_group"
		)

		if not self.fiscal_year:
			return

		previous_fiscal_year = self.previous_fiscal_year or self.get_previous_fiscal_year_name(self.fiscal_year)
		if previous_fiscal_year and previous_fiscal_year != self.previous_fiscal_year:
			self.previous_fiscal_year = previous_fiscal_year
		pre_previous_fiscal_year = self.get_previous_fiscal_year_name(previous_fiscal_year) if previous_fiscal_year else None
		if pre_previous_fiscal_year and hasattr(self, "pre_previous_year"):
			self.pre_previous_year = pre_previous_fiscal_year

		def get_fy_dates(fiscal_year):
			if not fiscal_year:
				return None, None
			fy_doc = frappe.get_doc("Fiscal Year", fiscal_year)
			return getdate(fy_doc.year_start_date), getdate(fy_doc.year_end_date)

		prev_start, prev_end = get_fy_dates(previous_fiscal_year)
		curr_start, curr_end = get_fy_dates(self.fiscal_year)

		if not (prev_start and prev_end and curr_start and curr_end):
			return

		for asset_class in intangible_asset_classes:
			valid_asset_groups = self.get_all_child_groups(asset_class)

			prev_opening_data = frappe.db.get_all(
				"FR Asset Register Entry",
				fields=["sap_cav", "sap_acc_dep"],
				filters={
					"company": self.company,
					"asset_group": ["in", valid_asset_groups],
					"ordinary_depreciation_start_date": ["<", prev_start],
					"fiscal_year": self.pre_previous_year
				}
			)

			prev_opening_value = sum(flt(d.sap_cav) for d in prev_opening_data)
			prev_acc_opening = sum(flt(d.sap_acc_dep) for d in prev_opening_data)

			prev_data = frappe.db.get_all(
				"FR Asset Register Entry",
				fields=[
					"sap_transaction_acq_value",
					"sap_tran_acq_value",
					"sap_plan_dep",
					"sap_tran_accu_dep"
				],
				filters={
					"company": self.company,
					"asset_group": ["in", valid_asset_groups],
					"ordinary_depreciation_start_date": ["between", [prev_start, prev_end]],
					'fiscal_year': self.previous_fiscal_year
				}
			)

			prev_add = sum(flt(d.sap_transaction_acq_value) for d in prev_data)
			prev_dis = sum(flt(d.sap_tran_acq_value) for d in prev_data)
			prev_close = prev_opening_value + prev_add + prev_dis

			prev_acc_add = sum(flt(d.sap_plan_dep) for d in prev_data)
			prev_acc_dis = sum(flt(d.sap_tran_accu_dep) for d in prev_data)
			prev_acc_close = prev_acc_opening + prev_acc_add + prev_acc_dis

			curr_data = frappe.db.get_all(
				"FR Asset Register Entry",
				fields=[
					"sap_transaction_acq_value",
					"sap_tran_acq_value",
					"sap_plan_dep",
					"sap_tran_accu_dep"
				],
				filters={
					"company": self.company,
					"asset_group": ["in", valid_asset_groups],
					"ordinary_depreciation_start_date": ["between", [curr_start, curr_end]],
					'fiscal_year': self.fiscal_year
				}
			)

			curr_add = sum(flt(d.sap_transaction_acq_value) for d in curr_data)
			curr_dis = sum(flt(d.sap_tran_acq_value) for d in curr_data)
			curr_close = prev_close + curr_add + curr_dis

			curr_acc_add = sum(flt(d.sap_plan_dep) for d in curr_data)
			curr_acc_dis = sum(flt(d.sap_tran_accu_dep) for d in curr_data)
			curr_acc_close = prev_acc_close + curr_acc_add + curr_acc_dis

			self.append("other_gross_carrying", {
				"particulars": asset_class,
				"as_at_pre_previous_year": (prev_opening_value),
				"prev_addition": (prev_add),
				"prev_disposals": (prev_dis),
				"as_at_previous_year": (prev_close),
				"curr_addition": (curr_add),
				"curr_disposals": (curr_dis),
				"as_at_current_year": (curr_close)
			})

			self.append("other_accumulated_depreciation", {
				"particulars": asset_class,
				"as_at_pre_previous_year": (prev_acc_opening),
				"prev_addition": (prev_acc_add),
				"prev_disposals": (prev_acc_dis),
				"as_at_previous_year": (prev_acc_close),
				"curr_addition": (curr_acc_add),
				"curr_disposals": (curr_acc_dis),
				"as_at_current_year": (curr_acc_close)
			})
			tot_curr_close += (curr_close)
			tot_curr_acc_close += (curr_acc_close)
			tot_prev_close += (prev_close)
			tot_prev_acc_close += (prev_acc_close)

		self.other_py_total = self.to_lakhs(tot_prev_close) - self.to_lakhs(tot_prev_acc_close)
		self.other_cy_total = self.to_lakhs(tot_curr_close) - self.to_lakhs(tot_curr_acc_close)

	def process_right_of_use_assets(self):
		self.rou_gross_carrying = []
		self.rou_accumulated_depreciation = []
		tot_prev_close, tot_prev_acc_close, tot_curr_close, tot_curr_acc_close = 0, 0, 0, 0
		rou_asset_classes = frappe.get_list(
			"FR Asset Group",
			filters={"asset_group_type": "Right of Use Assets", "is_group": 1},
			pluck="asset_group"
		)

		if not self.fiscal_year:
			return

		previous_fiscal_year = self.previous_fiscal_year or self.get_previous_fiscal_year_name(self.fiscal_year)
		if previous_fiscal_year and previous_fiscal_year != self.previous_fiscal_year:
			self.previous_fiscal_year = previous_fiscal_year
		pre_previous_fiscal_year = self.get_previous_fiscal_year_name(previous_fiscal_year) if previous_fiscal_year else None
		if pre_previous_fiscal_year and hasattr(self, "pre_previous_year"):
			self.pre_previous_year = pre_previous_fiscal_year

		def get_fy_dates(fiscal_year):
			if not fiscal_year:
				return None, None
			fy_doc = frappe.get_doc("Fiscal Year", fiscal_year)
			return getdate(fy_doc.year_start_date), getdate(fy_doc.year_end_date)

		prev_start, prev_end = get_fy_dates(previous_fiscal_year)
		curr_start, curr_end = get_fy_dates(self.fiscal_year)

		if not (prev_start and prev_end and curr_start and curr_end):
			return

		for asset_class in rou_asset_classes:
			valid_asset_groups = self.get_all_child_groups(asset_class)

			prev_opening_data = frappe.db.get_all(
				"FR Asset Register Entry",
				fields=["sap_cav", "sap_acc_dep"],
				filters={
					"company": self.company,
					"asset_group": ["in", valid_asset_groups],
					"ordinary_depreciation_start_date": ["<", prev_start],
					"fiscal_year": self.pre_previous_year
				}
			)

			prev_opening_value = sum(flt(d.sap_cav) for d in prev_opening_data)
			prev_acc_opening = sum(flt(d.sap_acc_dep) for d in prev_opening_data)

			prev_data = frappe.db.get_all(
				"FR Asset Register Entry",
				fields=[
					"sap_transaction_acq_value",
					"sap_tran_acq_value",
					"sap_plan_dep",
					"sap_tran_accu_dep"
				],
				filters={
					"company": self.company,
					"asset_group": ["in", valid_asset_groups],
					"ordinary_depreciation_start_date": ["between", [prev_start, prev_end]],
					'fiscal_year': self.previous_fiscal_year
				}
			)

			prev_add = sum(flt(d.sap_transaction_acq_value) for d in prev_data)
			prev_dis = sum(flt(d.sap_tran_acq_value) for d in prev_data)
			prev_close = prev_opening_value + prev_add + prev_dis

			prev_acc_add = sum(flt(d.sap_plan_dep) for d in prev_data)
			prev_acc_dis = sum(flt(d.sap_tran_accu_dep) for d in prev_data)
			prev_acc_close = prev_acc_opening + prev_acc_add + prev_acc_dis

			curr_data = frappe.db.get_all(
				"FR Asset Register Entry",
				fields=[
					"sap_transaction_acq_value",
					"sap_tran_acq_value",
					"sap_plan_dep",
					"sap_tran_accu_dep"
				],
				filters={
					"company": self.company,
					"asset_group": ["in", valid_asset_groups],
					"ordinary_depreciation_start_date": ["between", [curr_start, curr_end]],
					'fiscal_year': self.fiscal_year
				}
			)

			curr_add = sum(flt(d.sap_transaction_acq_value) for d in curr_data)
			curr_dis = sum(flt(d.sap_tran_acq_value) for d in curr_data)
			curr_close = prev_close + curr_add + curr_dis

			curr_acc_add = sum(flt(d.sap_plan_dep) for d in curr_data)
			curr_acc_dis = sum(flt(d.sap_tran_accu_dep) for d in curr_data)
			curr_acc_close = prev_acc_close + curr_acc_add + curr_acc_dis

			self.append("rou_gross_carrying", {
				"particulars": asset_class,
				"as_at_pre_previous_year": (prev_opening_value),
				"prev_addition": (prev_add),
				"prev_disposals": (prev_dis),
				"as_at_previous_year": (prev_close),
				"curr_addition": (curr_add),
				"curr_disposals": (curr_dis),
				"as_at_current_year": (curr_close)
			})

			self.append("rou_accumulated_depreciation", {
				"particulars": asset_class,
				"as_at_pre_previous_year": (prev_acc_opening),
				"prev_addition": (prev_acc_add),
				"prev_disposals": (prev_acc_dis),
				"as_at_previous_year": (prev_acc_close),
				"curr_addition": (curr_acc_add),
				"curr_disposals": (curr_acc_dis),
				"as_at_current_year": (curr_acc_close)
			})
			tot_prev_close += (prev_close)
			tot_prev_acc_close += (prev_acc_close)
			tot_curr_close += (curr_close)
			tot_curr_acc_close += (curr_acc_close)

		self.rou_net_py_total = self.to_lakhs(tot_prev_close) - self.to_lakhs(tot_prev_acc_close)
		self.rou_net_cy_total = self.to_lakhs(tot_curr_close) - self.to_lakhs(tot_curr_acc_close)

	def process_cwip(self):
		self.cwip_details = []

		if not self.fiscal_year:
			return

		previous_fiscal_year = self.previous_fiscal_year or self.get_previous_fiscal_year_name(self.fiscal_year)
		if previous_fiscal_year and previous_fiscal_year != self.previous_fiscal_year:
			self.previous_fiscal_year = previous_fiscal_year
		pre_previous_fiscal_year = self.get_previous_fiscal_year_name(previous_fiscal_year) if previous_fiscal_year else None
		if pre_previous_fiscal_year and hasattr(self, "pre_previous_year"):
			self.pre_previous_year = pre_previous_fiscal_year

		asset_group_list = frappe.get_list(
			"FR Asset Group",
			filters={"asset_group_type": "Capital Work In Progress"},
			pluck="asset_group"
		)

		def get_cwip_values_for_fy(current_fy):
			if not current_fy or not asset_group_list:
				return 0, 0, 0, 0

			fy_list = []
			fy = current_fy
			for _ in range(4):
				fy_list.append(fy)
				fy = self.get_previous_fiscal_year_name(fy) if fy else None

			def get_cwip_total(fiscal_year):
				if not fiscal_year:
					return 0, 0

				result = frappe.db.sql("""
					SELECT
						COALESCE(SUM(sap_transaction_acq_value), 0) AS total_acq_value,
						COALESCE(SUM(sap_ebv), 0) AS total_ebv
					FROM `tabFR Asset Register Entry`
					WHERE company = %(company)s
					AND fiscal_year = %(fiscal_year)s
					AND asset_group IN %(asset_groups)s
				""", {
					"company": self.company,
					"fiscal_year": fiscal_year,
					"asset_groups": tuple(asset_group_list),
				}, as_dict=True)

				row = result[0] if result else {}
				return flt(row.get("total_acq_value")), flt(row.get("total_ebv"))

			acq_0, ebv_0 = get_cwip_total(fy_list[0])
			acq_1, ebv_1 = get_cwip_total(fy_list[1])
			acq_2, ebv_2 = get_cwip_total(fy_list[2])

			less_1_year = acq_0
			one_to_2_years = max(ebv_0 - acq_0, 0)
			two_to_3_years = max(ebv_1 - acq_1, 0)
			more_3_years = max(ebv_2 - acq_2, 0)

			return less_1_year, one_to_2_years, two_to_3_years, more_3_years

		cy_pip_less_1, cy_pip_1_to_2, cy_pip_2_to_3, cy_pip_more_3 = get_cwip_values_for_fy(self.fiscal_year)
		py_pip_less_1, py_pip_1_to_2, py_pip_2_to_3, py_pip_more_3 = get_cwip_values_for_fy(previous_fiscal_year)

		cy_pip_total = cy_pip_less_1 + cy_pip_1_to_2 + cy_pip_2_to_3 + cy_pip_more_3
		py_pip_total = py_pip_less_1 + py_pip_1_to_2 + py_pip_2_to_3 + py_pip_more_3

		cwip_data = [
			{
				"amount_in_cwip_for_a_period_of": "Less than 1 year",
				"current_projects_in_progress": (cy_pip_less_1),
				"current_projects_temporarily_suspended": 0,
				"previous_projects_in_progress": (py_pip_less_1),
				"previous_projects_temporarily_suspended": 0,
			},
			{
				"amount_in_cwip_for_a_period_of": "1-2 years",
				"current_projects_in_progress": (cy_pip_1_to_2),
				"current_projects_temporarily_suspended": 0,
				"previous_projects_in_progress": (py_pip_1_to_2),
				"previous_projects_temporarily_suspended": 0,
			},
			{
				"amount_in_cwip_for_a_period_of": "2-3 years",
				"current_projects_in_progress": (cy_pip_2_to_3),
				"current_projects_temporarily_suspended": 0,
				"previous_projects_in_progress": (py_pip_2_to_3),
				"previous_projects_temporarily_suspended": 0,
			},
			{
				"amount_in_cwip_for_a_period_of": "More than 3 years",
				"current_projects_in_progress": (cy_pip_more_3),
				"current_projects_temporarily_suspended": 0,
				"previous_projects_in_progress": (py_pip_more_3),
				"previous_projects_temporarily_suspended": 0,
			},
			{
				"amount_in_cwip_for_a_period_of": "Total",
				"current_projects_in_progress": (cy_pip_total),
				"current_projects_temporarily_suspended": 0,
				"previous_projects_in_progress": (py_pip_total),
				"previous_projects_temporarily_suspended": 0,
			},
		]

		for row in cwip_data:
			self.append("cwip_details", row)

		self.cwip_py_total = self.to_lakhs(py_pip_total)
		self.cwip_cy_total = self.to_lakhs(cy_pip_total)

	def process_iaud(self):
		self.intangible_details = []

		if not self.fiscal_year:
			return

		previous_fiscal_year = self.previous_fiscal_year or self.get_previous_fiscal_year_name(self.fiscal_year)
		if previous_fiscal_year and previous_fiscal_year != self.previous_fiscal_year:
			self.previous_fiscal_year = previous_fiscal_year
		pre_previous_fiscal_year = self.get_previous_fiscal_year_name(previous_fiscal_year) if previous_fiscal_year else None
		if pre_previous_fiscal_year and hasattr(self, "pre_previous_year"):
			self.pre_previous_year = pre_previous_fiscal_year

		asset_group_list = frappe.get_list(
			"FR Asset Group",
			filters={"asset_group_type": "Intangible Assets Under Development"},
			pluck="asset_group"
		)

		def get_iaud_values_for_fy(current_fy):
			if not current_fy or not asset_group_list:
				return 0, 0, 0, 0

			fy_list = []
			fy = current_fy
			for _ in range(4):
				fy_list.append(fy)
				fy = self.get_previous_fiscal_year_name(fy) if fy else None

			def get_iaud_total(fiscal_year):
				if not fiscal_year:
					return 0, 0

				result = frappe.db.sql("""
					SELECT
						COALESCE(SUM(sap_transaction_acq_value), 0) AS total_acq_value,
						COALESCE(SUM(sap_ebv), 0) AS total_ebv
					FROM `tabFR Asset Register Entry`
					WHERE company = %(company)s
					AND fiscal_year = %(fiscal_year)s
					AND asset_group IN %(asset_groups)s
				""", {
					"company": self.company,
					"fiscal_year": fiscal_year,
					"asset_groups": tuple(asset_group_list),
				}, as_dict=True)

				row = result[0] if result else {}
				return flt(row.get("total_acq_value")), flt(row.get("total_ebv"))

			acq_0, ebv_0 = get_iaud_total(fy_list[0])
			acq_1, ebv_1 = get_iaud_total(fy_list[1])
			acq_2, ebv_2 = get_iaud_total(fy_list[2])

			less_1_year = acq_0
			one_to_2_years = max(ebv_0 - acq_0, 0)
			two_to_3_years = max(ebv_1 - acq_1, 0)
			more_3_years = max(ebv_2 - acq_2, 0)

			return less_1_year, one_to_2_years, two_to_3_years, more_3_years

		cy_pip_less_1, cy_pip_1_to_2, cy_pip_2_to_3, cy_pip_more_3 = get_iaud_values_for_fy(self.fiscal_year)
		py_pip_less_1, py_pip_1_to_2, py_pip_2_to_3, py_pip_more_3 = get_iaud_values_for_fy(previous_fiscal_year)

		cy_pip_total = cy_pip_less_1 + cy_pip_1_to_2 + cy_pip_2_to_3 + cy_pip_more_3
		py_pip_total = py_pip_less_1 + py_pip_1_to_2 + py_pip_2_to_3 + py_pip_more_3

		iaud_data = [
			{
				"amount_in_iaud_for_a_period_of": "Less than 1 year",
				"current_projects_in_progress": (cy_pip_less_1),
				"current_projects_temporarily_suspended": 0,
				"previous_projects_in_progress": (py_pip_less_1),
				"previous_projects_temporarily_suspended": 0,
			},
			{
				"amount_in_iaud_for_a_period_of": "1-2 years",
				"current_projects_in_progress": (cy_pip_1_to_2),
				"current_projects_temporarily_suspended": 0,
				"previous_projects_in_progress": (py_pip_1_to_2),
				"previous_projects_temporarily_suspended": 0,
			},
			{
				"amount_in_iaud_for_a_period_of": "2-3 years",
				"current_projects_in_progress": (cy_pip_2_to_3),
				"current_projects_temporarily_suspended": 0,
				"previous_projects_in_progress": (py_pip_2_to_3),
				"previous_projects_temporarily_suspended": 0,
			},
			{
				"amount_in_iaud_for_a_period_of": "More than 3 years",
				"current_projects_in_progress": (cy_pip_more_3),
				"current_projects_temporarily_suspended": 0,
				"previous_projects_in_progress": (py_pip_more_3),
				"previous_projects_temporarily_suspended": 0,
			},
			{
				"amount_in_iaud_for_a_period_of": "Total",
				"current_projects_in_progress": (cy_pip_total),
				"current_projects_temporarily_suspended": 0,
				"previous_projects_in_progress": (py_pip_total),
				"previous_projects_temporarily_suspended": 0,
			},
		]

		for row in iaud_data:
			self.append("intangible_details", row)

		self.iaud_py_total = self.to_lakhs(py_pip_total)
		self.iaud_cy_total = self.to_lakhs(cy_pip_total)