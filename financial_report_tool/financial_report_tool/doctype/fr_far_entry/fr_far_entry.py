# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class FRFAREntry(Document):
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
		return "Calculation completed successfully."

	def process_property_plant_and_equipment(self):
		self.ppe_gross_carrying = []
		self.ppe_accumulated_depreciation = []

		ppe_asset_classes = frappe.get_list(
			"FR Asset Group",
			filters={"asset_group_type": "Property Plant and Equipment", "is_group": 1},
			pluck="asset_group"
		)
	
		for asset_class in ppe_asset_classes:
			self.append("ppe_gross_carrying", {
				'particulars': asset_class,
				'as_at_pre_previous_year': 0,
				'prev_addition': 0,
				'prev_disposals': 0,
				'as_at_previous_year': 0,
				'current_addition': 0,
				'current_disposals': 0,
				'as_at_current_year': 0
			})

		for asset_class in ppe_asset_classes:
			self.append("ppe_accumulated_depreciation", {
				'particulars': asset_class,
				'as_at_pre_previous_year': 0,
				'prev_addition': 0,
				'prev_disposals': 0,
				'as_at_previous_year': 0,
				'current_addition': 0,
				'current_disposals': 0,
				'as_at_current_year': 0
			})

	def process_other_intangible_assets(self):
		self.other_gross_carrying = []
		self.other_accumulated_depreciation = []

		intangible_asset_classes = frappe.get_list(
			"FR Asset Group",
			filters={"asset_group_type": "Other Intangible Assets", "is_group": 1},
			pluck="asset_group"
		)

		for asset_class in intangible_asset_classes:
			self.append("other_gross_carrying", {
				'particulars': asset_class,
				'as_at_pre_previous_year': 0,
				'prev_addition': 0,
				'prev_disposals': 0,
				'as_at_previous_year': 0,
				'current_addition': 0,
				'current_disposals': 0,
				'as_at_current_year': 0
			})

			self.append("other_accumulated_depreciation", {
				'particulars': asset_class,
				'as_at_pre_previous_year': 0,
				'prev_addition': 0,
				'prev_disposals': 0,
				'as_at_previous_year': 0,
				'current_addition': 0,
				'current_disposals': 0,
				'as_at_current_year': 0
			})

	def process_right_of_use_assets(self):
		self.rou_gross_carrying = []
		self.rou_accumulated_depreciation = []

		rou_asset_classes = frappe.get_list(
			"FR Asset Group",
			filters={"asset_group_type": "Right of Use Assets", "is_group": 1},
			pluck="asset_group"
		)

		for asset_class in rou_asset_classes:
			self.append("rou_gross_carrying", {
				'particulars': asset_class,
				'as_at_pre_previous_year': 0,
				'prev_addition': 0,
				'prev_disposals': 0,
				'as_at_previous_year': 0,
				'current_addition': 0,
				'current_disposals': 0,
				'as_at_current_year': 0
			})

			self.append("rou_accumulated_depreciation", {
				'particulars': asset_class,
				'as_at_pre_previous_year': 0,
				'prev_addition': 0,
				'prev_disposals': 0,
				'as_at_previous_year': 0,
				'current_addition': 0,
				'current_disposals': 0,
				'as_at_current_year': 0
			})

def get_yearly_property_plant_and_equipment_data(self, section_description=""):
	prev_year_end_date = getdate(self.previous_year_ending_date)
	curr_year_end_date = getdate(self.current_year_ending_date)

	previous_year_start = prev_year_end_date.replace(year=prev_year_end_date.year - 1, month=4, day=1)
	current_year_start = curr_year_end_date.replace(year=curr_year_end_date.year - 1, month=4, day=1)

	previous_year = {"start": previous_year_start, "end": prev_year_end_date}
	current_year = {"start": current_year_start, "end": curr_year_end_date}

	previous_year_starting_date = previous_year_start.strftime("%d %B %Y")
	previous_year_ending_date = prev_year_end_date.strftime("%d %B %Y")
	current_year_ending_date = curr_year_end_date.strftime("%d %B %Y")

	asset_classes = frappe.get_list(
		"FR Asset Group",
		filters={"asset_group_type": "Property Plant and Equipment", "is_group": 1},
		pluck="asset_group"
	)

	result = {
		"previous_year": {}, "current_year": {},
		"previous_year_acc_dep": {}, "current_year_acc_dep": {}
	}

	for asset in asset_classes:
		# ✅ FIX 1: include parent + children
		valid_asset_groups = [asset] + self.get_all_child_groups(asset)

		# Opening
		prev_opening_data = frappe.db.get_all(
			"FR Asset Register Entry",
			fields=["sap_cav", "sap_acc_dep"],
			filters={
				"company": self.company,
				"asset_group": ["in", valid_asset_groups],
				"ordinary_depreciation_start_date": ["<", previous_year["start"]]
			}
		)

		prev_opening_value = sum(float(d.sap_cav or 0) for d in prev_opening_data)
		prev_acc_opening = sum(float(d.sap_acc_dep or 0) for d in prev_opening_data)

		# Previous Year Movement
		prev_data = frappe.db.get_all(
			"FR Asset Register Entry",
			fields=[
				"sap_transaction_acq_value", "sap_tran_acq_value",
				"sap_plan_dep", "sap_tran_accu_dep"
			],
			filters={
				"company": self.company,
				"asset_group": ["in", valid_asset_groups],
				"ordinary_depreciation_start_date": ["between", [previous_year["start"], previous_year["end"]]]
			}
		)

		prev_add = sum(float(d.sap_transaction_acq_value or 0) for d in prev_data)
		prev_dis = sum(float(d.sap_tran_acq_value or 0) for d in prev_data)
		prev_close = prev_opening_value + prev_add + prev_dis

		prev_acc_add = sum(float(d.sap_plan_dep or 0) for d in prev_data)
		prev_acc_dis = sum(float(d.sap_tran_accu_dep or 0) for d in prev_data)
		prev_acc_close = prev_acc_opening + prev_acc_add + prev_acc_dis

		# Current Year Movement
		curr_data = frappe.db.get_all(
			"FR Asset Register Entry",
			fields=[
				"sap_transaction_acq_value", "sap_tran_acq_value",
				"sap_plan_dep", "sap_tran_accu_dep"
			],
			filters={
				"company": self.company,
				"asset_group": ["in", valid_asset_groups],
				"ordinary_depreciation_start_date": ["between", [current_year["start"], current_year["end"]]]
			}
		)

		curr_add = sum(float(d.sap_transaction_acq_value or 0) for d in curr_data)
		curr_dis = sum(float(d.sap_tran_acq_value or 0) for d in curr_data)
		curr_close = prev_close + curr_add + curr_dis

		curr_acc_add = sum(float(d.sap_plan_dep or 0) for d in curr_data)
		curr_acc_dis = sum(float(d.sap_tran_accu_dep or 0) for d in curr_data)
		curr_acc_close = prev_acc_close + curr_acc_add + curr_acc_dis

		# Store
		result["previous_year"][asset] = {
			"opening_value": prev_opening_value,
			"positive_transaction": prev_add,
			"negative_transaction": prev_dis,
			"closing_value": prev_close
		}

		result["current_year"][asset] = {
			"opening_value": prev_close,
			"positive_transaction": curr_add,
			"negative_transaction": curr_dis,
			"closing_value": curr_close
		}

		result["previous_year_acc_dep"][asset] = {
			"opening_value": prev_acc_opening,
			"positive_transaction": prev_acc_add,
			"negative_transaction": prev_acc_dis,
			"closing_value": prev_acc_close
		}

		result["current_year_acc_dep"][asset] = {
			"opening_value": prev_acc_close,
			"positive_transaction": curr_acc_add,
			"negative_transaction": curr_acc_dis,
			"closing_value": curr_acc_close
		}

	def fmt(val):
		return f"{(val or 0) / 100000:,.2f}"

	def get_val(d, a, k):
		return d.get(a, {}).get(k) or 0

	num_cols = len(asset_classes)
	col_width = round((100 - 21 - 8) / num_cols, 1) if num_cols else 10

	def data_cells(data_dict, total_val, style, bold=False):
		cells = ""
		for asset in asset_classes:
			val = fmt(data_dict.get(asset))
			val = f"<b>{val}</b>" if bold else val
			cells += f'<td style="{style}">{val}</td>'
		total = fmt(total_val)
		total = f"<b>{total}</b>" if bold else total
		cells += f'<td style="background:#E8F5E8;{style}">{total}</td>'
		return cells

	def empty_cells(style):
		return "".join(f'<td style="{style}"></td>' for _ in asset_classes) + f'<td style="{style}"></td>'

	def build_map(key, source):
		return {a: get_val(source, a, key) for a in asset_classes}

	py_opening = build_map("opening_value", result["previous_year"])
	py_additions = build_map("positive_transaction", result["previous_year"])
	py_disposals = build_map("negative_transaction", result["previous_year"])
	py_closing = build_map("closing_value", result["previous_year"])

	cy_additions = build_map("positive_transaction", result["current_year"])
	cy_disposals = build_map("negative_transaction", result["current_year"])
	cy_closing = build_map("closing_value", result["current_year"])

	py_acc_opening = build_map("opening_value", result["previous_year_acc_dep"])
	py_acc_for_year = build_map("positive_transaction", result["previous_year_acc_dep"])
	py_acc_disposals = build_map("negative_transaction", result["previous_year_acc_dep"])
	py_acc_closing = build_map("closing_value", result["previous_year_acc_dep"])

	cy_acc_for_year = build_map("positive_transaction", result["current_year_acc_dep"])
	cy_acc_disposals = build_map("negative_transaction", result["current_year_acc_dep"])
	cy_acc_closing = build_map("closing_value", result["current_year_acc_dep"])

	sum_map = lambda m: sum(m.values())

	py_opening_total = sum_map(py_opening)
	py_additions_total = sum_map(py_additions)
	py_disposals_total = sum_map(py_disposals)
	py_closing_total = sum_map(py_closing)

	cy_additions_total = sum_map(cy_additions)
	cy_disposals_total = sum_map(cy_disposals)
	cy_closing_total = sum_map(cy_closing)

	py_acc_opening_total = sum_map(py_acc_opening)
	py_acc_for_year_total = sum_map(py_acc_for_year)
	py_acc_disposals_total = sum_map(py_acc_disposals)
	py_acc_closing_total = sum_map(py_acc_closing)

	cy_acc_for_year_total = sum_map(cy_acc_for_year)
	cy_acc_disposals_total = sum_map(cy_acc_disposals)
	cy_acc_closing_total = sum_map(cy_acc_closing)

	# ✅ FIX 2: safe net calc
	py_net = {a: py_closing.get(a, 0) - py_acc_closing.get(a, 0) for a in asset_classes}
	cy_net = {a: cy_closing.get(a, 0) - cy_acc_closing.get(a, 0) for a in asset_classes}

	py_net_total = sum_map(py_net)
	cy_net_total = sum_map(cy_net)

	s_mid  = "border-right:1px solid black;border-top:none;border-bottom:none;"
	s_top  = "border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;"
	s_bot  = "border-right:1px solid black;border-top:none;border-bottom:1px solid black;"
	s_full = "border:1px solid black;"
	s_sec_top = "border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"
	s_no_bot  = "border-right:1px solid black;border-bottom:none;"

	header_cols = "".join(
		f'<th style="border: 1px solid black; border-bottom:1px solid black; width: {col_width}%;">{asset}</th>'
		for asset in asset_classes
	)
	header_cols += f'<th style="background-color: #E8F5E8; border: 1px solid black; border-bottom:1px solid black; width: 8%;">Total</th>'

	html = f'''
	<div class="landscape-table-wrapper" style="page-break-before: always; page-break-after: always; transform-origin: top left; position: relative; top: -30px; width: 1200px;">
		<table style="margin-bottom: -90px; margin-top: -20px; border-collapse: collapse; border: 1px solid black; width: 100%; table-layout: fixed;">
		<thead>
			<tr style="color: #4472C4;">
				<th style="border: 1px solid black; border-bottom:1px solid black; width: 21%;">Particulars</th>
				{header_cols}
			</tr>
		</thead>
		<tbody>
			<tr>
				<td style="border-left: 1px solid black;border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"><b>I. Gross carrying amount</b></td>
				{empty_cells(s_sec_top)}
			</tr>
			<tr>
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">As at {previous_year_starting_date}</td>
				{data_cells(py_opening, py_opening_total, s_top)}
			</tr>
			<tr>
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Additions</td>
				{data_cells(py_additions, py_additions_total, s_mid)}
			</tr>
			<tr>
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">Disposals</td>
				{data_cells(py_disposals, py_disposals_total, s_bot)}
			</tr>
			<tr style="background-color: #E8F5E8">
				<td style="{s_full}"><b>As at {previous_year_ending_date}</b></td>
				{data_cells(py_closing, py_closing_total, s_full, bold=True)}
			</tr>
			<tr style="background-color: #E8F5E8">
				<td style="border-left:1px solid black; border-right: 1px solid black;border-bottom:none;">Additions</td>
				{data_cells(cy_additions, cy_additions_total, s_no_bot)}
			</tr>
			<tr style="background-color: #E8F5E8">
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:1px solid black;">Disposals</td>
				{data_cells(cy_disposals, cy_disposals_total, s_bot)}
			</tr>
			<tr style="background-color: #E8F5E8">
				<td style="{s_full}"><b>As at {current_year_ending_date}</b></td>
				{data_cells(cy_closing, cy_closing_total, s_full, bold=True)}
			</tr>
			<tr>
				<td style="border-left: 1px solid black;border-right: 1px solid black; border-bottom: none;"><b>II. Accumulated depreciation</b></td>
				{empty_cells("border-right: 1px solid black; border-bottom: none;")}
			</tr>
			<tr>
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">As at {previous_year_starting_date}</td>
				{data_cells(py_acc_opening, py_acc_opening_total, s_top)}
			</tr>
			<tr>
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Year Ended {previous_year_ending_date}</td>
				{data_cells(py_acc_for_year, py_acc_for_year_total, s_mid)}
			</tr>
			<tr>
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">Disposals</td>
				{data_cells(py_acc_disposals, py_acc_disposals_total, s_bot)}
			</tr>
			<tr style="background-color: #E8F5E8">
				<td style="{s_full}"><b>Upto {previous_year_ending_date}</b></td>
				{data_cells(py_acc_closing, py_acc_closing_total, s_full, bold=True)}
			</tr>
			<tr style="background-color: #E8F5E8">
				<td style="border-left:1px solid black; border-right: 1px solid black;border-bottom:none;">Year Ended {current_year_ending_date}</td>
				{data_cells(cy_acc_for_year, cy_acc_for_year_total, s_no_bot)}
			</tr>
			<tr style="background-color: #E8F5E8">
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:1px solid black;">Disposals</td>
				{data_cells(cy_acc_disposals, cy_acc_disposals_total, s_bot)}
			</tr>
			<tr style="background-color: #E8F5E8">
				<td style="{s_full}"><b>Upto {current_year_ending_date}</b></td>
				{data_cells(cy_acc_closing, cy_acc_closing_total, s_full, bold=True)}
			</tr>
			<tr>
				<td style="{s_full}"><b>III. Net carrying amount</b></td>
				{empty_cells(s_full)}
			</tr>
			<tr>
				<td style="{s_full}"><b>As at {previous_year_ending_date}</b></td>
				{data_cells(py_net, py_net_total, s_full, bold=True)}
			</tr>
			<tr style="background-color: #E8F5E8">
				<td style="{s_full}"><b>As at {current_year_ending_date}</b></td>
				{data_cells(cy_net, cy_net_total, s_full, bold=True)}
			</tr>
		</tbody>
	</table>
	</div>
	'''
	return section_description.replace("{{note_table}}", html)


def get_yearly_other_intangible_assets(self, section_description="", field=""):
		prev_year_end_date = frappe.utils.getdate(self.previous_year_ending_date)
		curr_year_end_date = frappe.utils.getdate(self.current_year_ending_date)

		previous_year_ending_date = prev_year_end_date.strftime("%d %B %Y")
		previous_year_starting_date = prev_year_end_date.replace(year=prev_year_end_date.year - 1, month=4, day=1).strftime("%d %B %Y")
		current_year_ending_date = curr_year_end_date.strftime("%d %B %Y")

		previous_year = {
			"start": prev_year_end_date.replace(year=prev_year_end_date.year - 1, month=4, day=1).strftime("%Y-%m-%d"),
			"end": prev_year_end_date.strftime("%Y-%m-%d")
		}
		current_year = {
			"start": curr_year_end_date.replace(year=curr_year_end_date.year - 1, month=4, day=1).strftime("%Y-%m-%d"),
			"end": curr_year_end_date.strftime("%Y-%m-%d")
		}

		filter_values = getattr(self, "filter_values", [])

		asset_classes = frappe.get_list(
			"FR Asset Group",
			filters={"asset_group_type": "Other Intangible Assets", "is_group": 1},
			pluck="asset_group"
		)

		result = {
			"previous_year": {}, "current_year": {},
			"previous_year_acc_dep": {}, "current_year_acc_dep": {}
		}

		for asset in asset_classes:
			valid_asset_groups = self.get_all_child_groups(asset)

			# Opening
			prev_opening_data = frappe.db.get_all(
				"FR Asset Register Entry",
				fields=["sap_cav", "sap_acc_dep"],
				filters={
					"company": self.company,
					"asset_group": ["in", valid_asset_groups],
					"ordinary_depreciation_start_date": ["<", previous_year["start"]]
				}
			)

			prev_opening_value = sum(float(d.sap_cav or 0) for d in prev_opening_data)
			prev_acc_opening = sum(float(d.sap_acc_dep or 0) for d in prev_opening_data)

			# Previous Year Transactions
			prev_data = frappe.db.get_all(
				"FR Asset Register Entry",
				fields=["sap_transaction_acq_value", "sap_tran_acq_value", "sap_plan_dep", "sap_tran_accu_dep"],
				filters={
					"company": self.company,
					"asset_group": ["in", valid_asset_groups],
					"ordinary_depreciation_start_date": ["between", [previous_year["start"], previous_year["end"]]]
				}
			)

			prev_positive = sum(float(d.sap_transaction_acq_value or 0) for d in prev_data)
			prev_negative = sum(float(d.sap_tran_acq_value or 0) for d in prev_data)
			prev_closing = prev_opening_value + prev_positive + prev_negative

			prev_acc_positive = sum(float(d.sap_plan_dep or 0) for d in prev_data)
			prev_acc_negative = sum(float(d.sap_tran_accu_dep or 0) for d in prev_data)
			prev_acc_closing = prev_acc_opening + prev_acc_positive + prev_acc_negative

			result["previous_year"][asset] = {
				"opening_value": prev_opening_value,
				"positive_transaction": prev_positive,
				"negative_transaction": prev_negative,
				"closing_value": prev_closing
			}

			result["previous_year_acc_dep"][asset] = {
				"opening_value": prev_acc_opening,
				"positive_transaction": prev_acc_positive,
				"negative_transaction": prev_acc_negative,
				"closing_value": prev_acc_closing
			}

			# Current Year
			curr_filters = {
				"company": self.company,
				"asset_group": ["in", valid_asset_groups],
				"ordinary_depreciation_start_date": ["between", [current_year["start"], current_year["end"]]]
			}
			if filter_values:
				curr_filters["asset_class"] = ["in", filter_values]

			curr_data = frappe.db.get_all(
				"FR Asset Register Entry",
				fields=["sap_transaction_acq_value", "sap_tran_acq_value", "sap_plan_dep", "sap_tran_accu_dep"],
				filters=curr_filters
			)

			curr_positive = sum(float(d.sap_transaction_acq_value or 0) for d in curr_data)
			curr_negative = sum(float(d.sap_tran_acq_value or 0) for d in curr_data)
			curr_closing = prev_closing + curr_positive + curr_negative

			curr_acc_positive = sum(float(d.sap_plan_dep or 0) for d in curr_data)
			curr_acc_negative = sum(float(d.sap_tran_accu_dep or 0) for d in curr_data)
			curr_acc_closing = prev_acc_closing + curr_acc_positive + curr_acc_negative

			result["current_year"][asset] = {
				"opening_value": prev_closing,
				"positive_transaction": curr_positive,
				"negative_transaction": curr_negative,
				"closing_value": curr_closing
			}

			result["current_year_acc_dep"][asset] = {
				"opening_value": prev_acc_closing,
				"positive_transaction": curr_acc_positive,
				"negative_transaction": curr_acc_negative,
				"closing_value": curr_acc_closing
			}

		# ----------- 🔥 MISSING PART (NOW ADDED) -----------

		def get_val(data, asset, key):
			return data.get(asset, {}).get(key) or 0

		def fmt(val):
			return f"{(val or 0)/100000:,.2f}"

		py_opening = {a: get_val(result["previous_year"], a, "opening_value") for a in asset_classes}
		py_additions = {a: get_val(result["previous_year"], a, "positive_transaction") for a in asset_classes}
		py_disposals = {a: get_val(result["previous_year"], a, "negative_transaction") for a in asset_classes}
		py_closing = {a: get_val(result["previous_year"], a, "closing_value") for a in asset_classes}

		cy_additions = {a: get_val(result["current_year"], a, "positive_transaction") for a in asset_classes}
		cy_disposals = {a: get_val(result["current_year"], a, "negative_transaction") for a in asset_classes}
		cy_closing = {a: get_val(result["current_year"], a, "closing_value") for a in asset_classes}

		py_opening_total = sum(py_opening.values())
		py_additions_total = sum(py_additions.values())
		py_disposals_total = sum(py_disposals.values())
		py_closing_total = sum(py_closing.values())

		cy_additions_total = sum(cy_additions.values())
		cy_disposals_total = sum(cy_disposals.values())
		cy_closing_total = sum(cy_closing.values())

		py_acc_opening = {a: get_val(result["previous_year_acc_dep"], a, "opening_value") for a in asset_classes}
		py_acc_for_year = {a: get_val(result["previous_year_acc_dep"], a, "positive_transaction") for a in asset_classes}
		py_acc_disposals = {a: get_val(result["previous_year_acc_dep"], a, "negative_transaction") for a in asset_classes}
		py_acc_closing = {a: get_val(result["previous_year_acc_dep"], a, "closing_value") for a in asset_classes}

		cy_acc_for_year = {a: get_val(result["current_year_acc_dep"], a, "positive_transaction") for a in asset_classes}
		cy_acc_disposals = {a: get_val(result["current_year_acc_dep"], a, "negative_transaction") for a in asset_classes}
		cy_acc_closing = {a: get_val(result["current_year_acc_dep"], a, "closing_value") for a in asset_classes}

		py_acc_opening_total = sum(py_acc_opening.values())
		py_acc_for_year_total = sum(py_acc_for_year.values())
		py_acc_disposals_total = sum(py_acc_disposals.values())
		py_acc_closing_total = sum(py_acc_closing.values())

		cy_acc_for_year_total = sum(cy_acc_for_year.values())
		cy_acc_disposals_total = sum(cy_acc_disposals.values())
		cy_acc_closing_total = sum(cy_acc_closing.values())

		py_net = {a: py_closing[a] - py_acc_closing[a] for a in asset_classes}
		cy_net = {a: cy_closing[a] - cy_acc_closing[a] for a in asset_classes}

		py_net_total = py_closing_total - py_acc_closing_total
		cy_net_total = cy_closing_total - cy_acc_closing_total

		s_mid     = "border-right:1px solid black;border-top:none;border-bottom:none;"
		s_top     = "border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;"
		s_bot     = "border-right:1px solid black;border-top:none;border-bottom:1px solid black;"
		s_full    = "border:1px solid black;"
		s_sec_top = "border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"
		s_no_bot  = "border-right:1px solid black;border-bottom:none;"

		num_cols = len(asset_classes)
		col_width = round((100 - 21 - 8) / num_cols, 1) if num_cols else 10

		def data_cells(data_dict, total_val, style, bold=False):
			cells = ""
			for asset in asset_classes:
				val = fmt(data_dict.get(asset))
				content = f"<b>{val}</b>" if bold else val
				cells += f'<td style="{style}">{content}</td>'
			total_content = f"<b>{fmt(total_val)}</b>" if bold else fmt(total_val)
			cells += f'<td style="background-color: #E8F5E8; {style}">{total_content}</td>'
			return cells

		def empty_cells(style):
			cells = "".join(f'<td style="{style}"></td>' for _ in asset_classes)
			cells += f'<td style="background-color: #E8F5E8; {style}"></td>'
			return cells
		
		header_cols = "".join(
			f'<th style="border: 1px solid black; border-bottom:1px solid black; width: {col_width}%;">{asset}</th>'
			for asset in asset_classes
		)
		header_cols += f'<th style="background-color: #E8F5E8; border: 1px solid black; border-bottom:1px solid black; width: 20%;">Total</th>'

		html = f'''
		<table style="margin-top: -10px; margin-bottom: -30px; border-collapse: collapse; border: 1px solid black; width: 100%; table-layout: fixed;">
			<thead>
				<tr style="color: #4472C4;">
					<th style="width: 30%; border: 1px solid black; border-bottom:1px solid black;">Particulars</th>
					{header_cols}
				</tr>
			</thead>
			<tbody>
				<tr>
					<td style="border-left: 1px solid black;border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"><b>I. Gross carrying amount</b></td>
					{empty_cells(s_sec_top)}
				</tr>
				<tr>
					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">As at {previous_year_starting_date}</td>
					{data_cells(py_opening, py_opening_total, s_top)}
				</tr>
				<tr>
					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Additions</td>
					{data_cells(py_additions, py_additions_total, s_mid)}
				</tr>
				<tr>
					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">Disposals</td>
					{data_cells(py_disposals, py_disposals_total, s_bot)}
				</tr>
				<tr style="background-color: #E8F5E8;">
					<td style="{s_full}"><b>As at {previous_year_ending_date}</b></td>
					{data_cells(py_closing, py_closing_total, s_full, bold=True)}
				</tr>
				<tr style="background-color: #E8F5E8;">
					<td style="border-left:1px solid black; border-right: 1px solid black;border-bottom:none;">Additions</td>
					{data_cells(cy_additions, cy_additions_total, s_no_bot)}
				</tr>
				<tr style="background-color: #E8F5E8;">
					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:1px solid black;">Disposals, transfer and adjustments</td>
					{data_cells(cy_disposals, cy_disposals_total, s_bot)}
				</tr>
				<tr style="background-color: #E8F5E8;">
					<td style="{s_full}"><b>As at {current_year_ending_date}</b></td>
					{data_cells(cy_closing, cy_closing_total, s_full, bold=True)}
				</tr>
				<tr>
					<td style="border-left: 1px solid black;border-right: 1px solid black; border-bottom: none;"><b>II. Accumulated amortisation</b></td>
					{empty_cells("border-right: 1px solid black; border-bottom: none;")}
				</tr>
				<tr>
					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">As at {previous_year_starting_date}</td>
					{data_cells(py_acc_opening, py_acc_opening_total, s_top)}
				</tr>
				<tr>
					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Year Ended {previous_year_ending_date}</td>
					{data_cells(py_acc_for_year, py_acc_for_year_total, s_mid)}
				</tr>
				<tr>
					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">Disposals</td>
					{data_cells(py_acc_disposals, py_acc_disposals_total, s_bot)}
				</tr>
				<tr style="background-color: #E8F5E8;">
					<td style="{s_full}"><b>Upto {previous_year_ending_date}</b></td>
					{data_cells(py_acc_closing, py_acc_closing_total, s_full, bold=True)}
				</tr>
				<tr style="background-color: #E8F5E8;">
					<td style="border-left:1px solid black; border-right: 1px solid black;border-bottom:none;">Year Ended {current_year_ending_date}</td>
					{data_cells(cy_acc_for_year, cy_acc_for_year_total, s_no_bot)}
				</tr>
				<tr style="background-color: #E8F5E8;">
					<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:1px solid black;">Disposals and adjustments</td>
					{data_cells(cy_acc_disposals, cy_acc_disposals_total, s_bot)}
				</tr>
				<tr style="background-color: #E8F5E8;">
					<td style="{s_full}"><b>Upto {current_year_ending_date}</b></td>
					{data_cells(cy_acc_closing, cy_acc_closing_total, s_full, bold=True)}
				</tr>
				<tr>
					<td style="{s_full}"><b>III. Net carrying amount</b></td>
					{empty_cells(s_full)}
				</tr>
				<tr>
					<td style="{s_full}"><b>As at {previous_year_ending_date}</b></td>
					{data_cells(py_net, py_net_total, s_full, bold=True)}
				</tr>
				<tr style="background-color: #E8F5E8;">
					<td style="{s_full}"><b>As at {current_year_ending_date}</b></td>
					{data_cells(cy_net, cy_net_total, s_full, bold=True)}
				</tr>
			</tbody>
		</table>
		'''
		return section_description.replace("{{note_table}}", html)


def get_yearly_right_of_use_assets(self, section_description=""):
	prev_year_end_date = frappe.utils.getdate(self.previous_year_ending_date)
	curr_year_end_date = frappe.utils.getdate(self.current_year_ending_date)

	previous_year_ending_date = prev_year_end_date.strftime("%d %B %Y")
	previous_year_starting_date = prev_year_end_date.replace(year=prev_year_end_date.year - 1, month=4, day=1).strftime("%d %B %Y")
	current_year_ending_date = curr_year_end_date.strftime("%d %B %Y")

	# Right of Use Asset classes
	asset_classes = [
		"Right-of-use assets - Vehicles",
		"Right-of-use assets - Immovable property"
	]

	# Define years
	previous_year = {
		"start": prev_year_end_date.replace(year=prev_year_end_date.year - 1, month=4, day=1).strftime("%Y-%m-%d"),
		"end": prev_year_end_date.strftime("%Y-%m-%d")
	}
	current_year = {
		"start": curr_year_end_date.replace(year=curr_year_end_date.year - 1, month=4, day=1).strftime("%Y-%m-%d"),
		"end": curr_year_end_date.strftime("%Y-%m-%d")
	}

	prev_year_start = frappe.utils.getdate(previous_year["start"])
	prev_year_end = frappe.utils.getdate(previous_year["end"])
	curr_year_start = frappe.utils.getdate(current_year["start"])
	curr_year_end = frappe.utils.getdate(current_year["end"])

	# Initialize result dictionaries
	result = {
		"previous_year": {},
		"current_year": {},
		"previous_year_acc_dep": {},
		"current_year_acc_dep": {}
	}

	for asset in asset_classes:
		# Fetch data for previous year
		prev_data = frappe.db.get_all(
			'FR Asset Register Entry',
			fields=['name', 'sap_transaction_acq_value', 'sap_cav', 'sap_tran_accu_dep', 'sap_acc_dep', 'sap_plan_dep', 'ordinary_depreciation_start_date'],
			filters={
				'company': self.company,
				'asset_class': asset,
				'ordinary_depreciation_start_date': ['between', [previous_year["start"], previous_year["end"]]]
			},
			order_by='ordinary_depreciation_start_date asc'
		)

		# Fetch data for current year
		curr_data = frappe.db.get_all(
			'FR Asset Register Entry',
			fields=['name', 'sap_transaction_acq_value', 'sap_cav', 'sap_tran_accu_dep', 'sap_acc_dep', 'sap_plan_dep', 'ordinary_depreciation_start_date'],
			filters={
				'company': self.company,
				'asset_class': asset,
				'ordinary_depreciation_start_date': ['between', [current_year["start"], current_year["end"]]]
			},
			order_by='ordinary_depreciation_start_date asc'
		)

		# PREVIOUS YEAR (SAP CAV) - Gross Carrying Amount
		prev_opening_value = 0.0
		prev_positive = 0.0
		prev_negative = 0.0

		for entry in prev_data:
			if entry.sap_cav:
				prev_opening_value = float(entry.sap_cav)
				break

		for entry in prev_data:
			value = float(entry.sap_transaction_acq_value) if entry.sap_transaction_acq_value else 0.0
			if value > 0:
				prev_positive += value
			elif value < 0:
				prev_negative += value

		prev_closing_value = prev_opening_value + prev_positive + prev_negative

		result["previous_year"][asset] = {
			"opening_value": prev_opening_value,
			"positive_transaction": prev_positive,
			"negative_transaction": prev_negative,
			"closing_value": prev_closing_value
		}

		# CURRENT YEAR (SAP CAV) - Gross Carrying Amount
		curr_opening_value = prev_closing_value
		curr_positive = 0.0
		curr_negative = 0.0

		for entry in curr_data:
			value = float(entry.sap_transaction_acq_value) if entry.sap_transaction_acq_value else 0.0
			if value > 0:
				curr_positive += value
			elif value < 0:
				curr_negative += value

		curr_closing_value = curr_opening_value + curr_positive + curr_negative

		result["current_year"][asset] = {
			"opening_value": curr_opening_value,
			"positive_transaction": curr_positive,
			"negative_transaction": curr_negative,
			"closing_value": curr_closing_value
		}

		# PREVIOUS YEAR (SAP Acc Dep) - Accumulated Amortisation
		prev_acc_opening_value = 0.0
		prev_acc_positive = 0.0
		prev_acc_negative = 0.0

		for entry in prev_data:
			if entry.sap_acc_dep:
				prev_acc_opening_value = abs(float(entry.sap_acc_dep))
				break

		for entry in prev_data:
			value = float(entry.sap_tran_accu_dep) if entry.sap_tran_accu_dep else 0.0
			if value > 0:
				prev_acc_negative += value
			elif value < 0:
				prev_acc_positive += abs(value)

			plan_value = float(entry.sap_plan_dep) if entry.sap_plan_dep else 0.0
			prev_acc_positive += abs(plan_value)

		prev_acc_closing_value = prev_acc_opening_value + prev_acc_positive - prev_acc_negative

		result["previous_year_acc_dep"][asset] = {
			"opening_value": prev_acc_opening_value,
			"positive_transaction": prev_acc_positive,
			"negative_transaction": prev_acc_negative,
			"closing_value": prev_acc_closing_value
		}

		# CURRENT YEAR (SAP Acc Dep) - Accumulated Amortisation
		curr_acc_opening_value = prev_acc_closing_value
		curr_acc_positive = 0.0
		curr_acc_negative = 0.0

		for entry in curr_data:
			value = float(entry.sap_tran_accu_dep) if entry.sap_tran_accu_dep else 0.0
			if value > 0:
				curr_acc_negative += value
			elif value < 0:
				curr_acc_positive += abs(value)

			plan_value = float(entry.sap_plan_dep) if entry.sap_plan_dep else 0.0
			curr_acc_positive += abs(plan_value)

		curr_acc_closing_value = curr_acc_opening_value + curr_acc_positive - curr_acc_negative

		result["current_year_acc_dep"][asset] = {
			"opening_value": curr_acc_opening_value,
			"positive_transaction": curr_acc_positive,
			"negative_transaction": curr_acc_negative,
			"closing_value": curr_acc_closing_value
		}

	# Helper function to format values in lacs (÷100000)
	def fmt(val):
		if val is None:
			return "0.00"
		return f"{val / 100000:,.2f}"

	# Get values for each asset class
	def get_val(data_dict, asset, key):
		if asset in data_dict and data_dict[asset].get(key) is not None:
			return data_dict[asset][key]
		return 0

	# I. Gross carrying amount values
	py_opening = {asset: get_val(result["previous_year"], asset, "opening_value") for asset in asset_classes}
	py_opening_total = sum(v for v in py_opening.values() if v)

	py_additions = {asset: get_val(result["previous_year"], asset, "positive_transaction") for asset in asset_classes}
	py_additions_total = sum(v for v in py_additions.values() if v)

	py_disposals = {asset: get_val(result["previous_year"], asset, "negative_transaction") for asset in asset_classes}
	py_disposals_total = sum(v for v in py_disposals.values() if v)

	py_closing = {asset: get_val(result["previous_year"], asset, "closing_value") for asset in asset_classes}
	py_closing_total = sum(v for v in py_closing.values() if v)

	cy_additions = {asset: get_val(result["current_year"], asset, "positive_transaction") for asset in asset_classes}
	cy_additions_total = sum(v for v in cy_additions.values() if v)

	cy_disposals = {asset: get_val(result["current_year"], asset, "negative_transaction") for asset in asset_classes}
	cy_disposals_total = sum(v for v in cy_disposals.values() if v)

	cy_closing = {asset: get_val(result["current_year"], asset, "closing_value") for asset in asset_classes}
	cy_closing_total = sum(v for v in cy_closing.values() if v)

	# II. Accumulated amortisation values
	py_acc_opening = {asset: get_val(result["previous_year_acc_dep"], asset, "opening_value") for asset in asset_classes}
	py_acc_opening_total = sum(v for v in py_acc_opening.values() if v)

	py_acc_for_year = {asset: get_val(result["previous_year_acc_dep"], asset, "positive_transaction") for asset in asset_classes}
	py_acc_for_year_total = sum(v for v in py_acc_for_year.values() if v)

	py_acc_disposals = {asset: get_val(result["previous_year_acc_dep"], asset, "negative_transaction") for asset in asset_classes}
	py_acc_disposals_total = sum(v for v in py_acc_disposals.values() if v)

	py_acc_closing = {asset: get_val(result["previous_year_acc_dep"], asset, "closing_value") for asset in asset_classes}
	py_acc_closing_total = sum(v for v in py_acc_closing.values() if v)

	cy_acc_for_year = {asset: get_val(result["current_year_acc_dep"], asset, "positive_transaction") for asset in asset_classes}
	cy_acc_for_year_total = sum(v for v in cy_acc_for_year.values() if v)

	cy_acc_disposals = {asset: get_val(result["current_year_acc_dep"], asset, "negative_transaction") for asset in asset_classes}
	cy_acc_disposals_total = sum(v for v in cy_acc_disposals.values() if v)

	cy_acc_closing = {asset: get_val(result["current_year_acc_dep"], asset, "closing_value") for asset in asset_classes}
	cy_acc_closing_total = sum(v for v in cy_acc_closing.values() if v)

	# III. Net carrying amount = Gross Closing - Accumulated Amortisation Closing
	py_net = {asset: (py_closing.get(asset, 0) or 0) - (py_acc_closing.get(asset, 0) or 0) for asset in asset_classes}
	py_net_total = py_closing_total - py_acc_closing_total

	cy_net = {asset: (cy_closing.get(asset, 0) or 0) - (cy_acc_closing.get(asset, 0) or 0) for asset in asset_classes}
	cy_net_total = cy_closing_total - cy_acc_closing_total

	html = f'''
	<table style="margin-top: -20px; margin-bottom: -20px; border-collapse: collapse; border: 1px solid black; width: 100%; table-layout: fixed;">
		<thead>
			<tr style="color: #4472C4;">
				<th style="width: 40%; border: 1px solid black; border-bottom:1px solid black;">Particulars</th>
				<th style="border: 1px solid black; border-bottom:1px solid black;">Right-of-use assets - Vehicles</th>
				<th style="border: 1px solid black; border-bottom:1px solid black;">Right-of-use assets - Immovable property</th>
				<th style="border: 1px solid black; border-bottom:1px solid black;">Total</th>
			</tr>
		</thead>
		<tbody>
			<tr>
				<td style="border-left: 1px solid black;border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"><b>I. Gross carrying amount</b></td>
				<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
				<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
				<td style="border-right: 1px solid black;border-top:1px solid black; border-bottom: none;"></td>
				
			</tr>
			<tr>
				<td style="border-top: 1px solid black;border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">As at {previous_year_starting_date}</td>
				<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Right-of-use assets - Vehicles"))}</td>
				<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening.get("Right-of-use assets - Immovable property"))}</td>
				<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_opening_total)}</td>					
			</tr>
			<tr>
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Additions</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Right-of-use assets - Vehicles"))}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions.get("Right-of-use assets - Immovable property"))}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_additions_total)}</td>
				
			</tr>
			<tr>
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">Disposals</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Right-of-use assets - Vehicles"))}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals.get("Right-of-use assets - Immovable property"))}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_disposals_total)}</td>					
			</tr>
			<tr style="background-color: #E8F5E8;">
				<td style="border:1px solid black;"><b>As at {previous_year_ending_date}</b></td>
				<td style="border:1px solid black;"><b>{fmt(py_closing.get("Right-of-use assets - Vehicles"))}</b></td>
				<td style="border:1px solid black;"><b>{fmt(py_closing.get("Right-of-use assets - Immovable property"))}</b></td>
				<td style="border:1px solid black;"><b>{fmt(py_closing_total)}</b></td>					
			</tr>
			<tr style="background-color: #E8F5E8;">
				<td style="border-left:1px solid black; border-right: 1px solid black;border-bottom:none;">Additions</td>
				<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Right-of-use assets - Vehicles"))}</td>
				<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions.get("Right-of-use assets - Immovable property"))}</td>
				<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_additions_total)}</td>					
			</tr>
			<tr style="background-color: #E8F5E8;">
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:1px solid black;">Disposals, transfer and adjustments</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Right-of-use assets - Vehicles"))}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals.get("Right-of-use assets - Immovable property"))}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_disposals_total)}</td>					
			</tr>
			<tr style="background-color: #E8F5E8;">
				<td style="border:1px solid black;"><b>As at {current_year_ending_date}</b></td>
				<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Right-of-use assets - Vehicles"))}</b></td>
				<td style="border:1px solid black;"><b>{fmt(cy_closing.get("Right-of-use assets - Immovable property"))}</b></td>
				<td style="border:1px solid black;"><b>{fmt(cy_closing_total)}</b></td>
			</tr>
			<tr>
				<td style="border-left: 1px solid black;border-right: 1px solid black; border-bottom: none;"><b>II.  Accumulated amortisation<b></td>
				<td style="border-right: 1px solid black; border-bottom: none;"></td>
				<td style="border-right: 1px solid black; border-bottom: none;"></td>
				<td style="border-right: 1px solid black; border-bottom: none;"></td>					
			</tr>
			<tr>
				<td style="border-top: 1px solid black;border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">As at {previous_year_starting_date}</td>
				<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Right-of-use assets - Vehicles"))}</td>
				<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening.get("Right-of-use assets - Immovable property"))}</td>
				<td style="border-top: 1px solid black;border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_opening_total)}</td>					
			</tr>
			<tr>
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:none;">Year Ended {previous_year_ending_date}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Right-of-use assets - Vehicles"))}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year.get("Right-of-use assets - Immovable property"))}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:none;">{fmt(py_acc_for_year_total)}</td>					
			</tr>
			<tr>
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none; border-bottom:1px solid black;">Disposals</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Right-of-use assets - Vehicles"))}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals.get("Right-of-use assets - Immovable property"))}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(py_acc_disposals_total)}</td>					
			</tr>
			<tr style="background-color: #E8F5E8;">
				<td style="border:1px solid black;"><b>Upto {previous_year_ending_date}</b></td>
				<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Right-of-use assets - Vehicles"))}</b></td>
				<td style="border:1px solid black;"><b>{fmt(py_acc_closing.get("Right-of-use assets - Immovable property"))}</b></td>
				<td style="border:1px solid black;"><b>{fmt(py_acc_closing_total)}</b></td>					
			</tr>
			<tr style="background-color: #E8F5E8;">
				<td style="border-left:1px solid black; border-right: 1px solid black;border-bottom:none;">Year Ended {current_year_ending_date}</td>
				<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Right-of-use assets - Vehicles"))}</td>
				<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year.get("Right-of-use assets - Immovable property"))}</td>
				<td style="border-right:1px solid black;border-bottom:none;">{fmt(cy_acc_for_year_total)}</td>					
			</tr>
			<tr style="background-color: #E8F5E8;">
				<td style="border-left:1px solid black; border-right: 1px solid black;border-top:none;border-bottom:1px solid black;">Disposals and adjustments</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Right-of-use assets - Vehicles"))}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals.get("Right-of-use assets - Immovable property"))}</td>
				<td style="border-right:1px solid black;border-top:none;border-bottom:1px solid black;">{fmt(cy_acc_disposals_total)}</td>					
			</tr>
			<tr style="background-color: #E8F5E8;">
				<td style="border:1px solid black;"><b>Upto {current_year_ending_date}</b></td>
				<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Right-of-use assets - Vehicles"))}</b></td>
				<td style="border:1px solid black;"><b>{fmt(cy_acc_closing.get("Right-of-use assets - Immovable property"))}</b></td>
				<td style="border:1px solid black;"><b>{fmt(cy_acc_closing_total)}</b></td>					
			</tr>
			<tr>
				<td style="border:1px solid black;"><b>III.  Net carrying amount</b></td>
				<td style="border:1px solid black;"><b></b></td>
				<td style="border:1px solid black;"><b></b></td>
				<td style="border:1px solid black;"><b></b></td>					
			</tr>
			<tr>
				<td style="border:1px solid black;"><b>As at {previous_year_ending_date}</b></td>
				<td style="border:1px solid black;"><b>{fmt(py_net.get("Right-of-use assets - Vehicles"))}</b></td>
				<td style="border:1px solid black;"><b>{fmt(py_net.get("Right-of-use assets - Immovable property"))}</b></td>
				<td style="border:1px solid black;"><b>{fmt(py_net_total)}</b></td>					
			</tr>
			<tr style="background-color: #E8F5E8;">
				<td style="border:1px solid black;"><b>As at {current_year_ending_date}</b></td>
				<td style="border:1px solid black;"><b>{fmt(cy_net.get("Right-of-use assets - Vehicles"))}</b></td>
				<td style="border:1px solid black;"><b>{fmt(cy_net.get("Right-of-use assets - Immovable property"))}</b></td>
				<td style="border:1px solid black;"><b>{fmt(cy_net_total)}</b></td>					
			</tr>
		</tbody>
	</table>

	'''
	return section_description.replace("{{note_table}}", html)
