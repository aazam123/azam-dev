# Copyright (c) 2026, Hybrowlabs Pvt Ltd
# For license information, please see license.txt

from frappe.model.document import Document


class FRSAPCompanyMapping(Document):
	"""Per-company SAP connection template and fiscal cycle.

	The fiscal cycle defaults to Apr-Mar for existing mappings. A selected
	Fiscal Year's dates take precedence over this company default; Jan-Dec
	companies can therefore also prepare Apr-Mar reporting years.
	"""

	pass
