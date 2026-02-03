# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class FRUndrawnFacilities(Document):
	def before_save(self):
		self.bank_details = [d for d in self.bank_details if d.bank != "Total"]
		self.utilisation_details = [d for d in self.utilisation_details if d.utilisation != "Total"]

		b_wc_limits, b_fdod, b_non_fund, b_term_loan, b_eclgs, b_total = 0, 0, 0, 0, 0, 0

		for i in self.bank_details:

			wc = i.wc_limits or 0
			fd = i.fdod or 0
			nf = i.non_fund or 0
			tl = i.term_loan or 0
			ec = i.eclgs or 0

			i.total = wc + fd + nf + tl + ec

			b_wc_limits += wc
			b_fdod += fd
			b_non_fund += nf
			b_term_loan += tl
			b_eclgs += ec
			b_total += i.total


		self.append("bank_details", {
			"bank": "Total",
			"particulars": "",
			"wc_limits": b_wc_limits,
			"fdod": b_fdod,
			"non_fund": b_non_fund,
			"term_loan": b_term_loan,
			"eclgs": b_eclgs,
			"total": b_total,
		})

		u_wc_limits, u_fdod, u_non_fund, u_term_loan, u_eclgs, u_total = 0, 0, 0, 0, 0, 0

		for i in self.utilisation_details:
			wc = i.wc_limits or 0
			fd = i.fdod or 0
			nf = i.non_fund or 0
			tl = i.term_loan or 0
			ec = i.eclgs or 0

			i.total = wc + fd + nf + tl + ec

			u_wc_limits += wc
			u_fdod += fd
			u_non_fund += nf
			u_term_loan += tl
			u_eclgs += ec
			u_total += i.total

		self.append("utilisation_details", {
			"utilisation": "Total",
			"particulars": "",
			"wc_limits": u_wc_limits,
			"fdod": u_fdod,
			"non_fund": u_non_fund,
			"term_loan": u_term_loan,
			"eclgs": u_eclgs,
			"total": u_total,
		})

		self.wc_limits = b_wc_limits - u_wc_limits
		self.fdod = b_fdod - u_fdod
		self.non_fund = b_non_fund - u_non_fund
		self.term_loan = b_term_loan - u_term_loan
		self.eclgs = b_eclgs - u_eclgs
		self.total = b_total - u_total
