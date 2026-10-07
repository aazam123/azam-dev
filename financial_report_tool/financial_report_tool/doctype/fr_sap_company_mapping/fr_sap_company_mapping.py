# Copyright (c) 2026, Hybrowlabs Pvt Ltd
# For license information, please see license.txt

from frappe.model.document import Document


class FRSAPCompanyMapping(Document):
	"""Per-Company SAP connection template.

	Holds the fixed SAP parameters for a company (company code, chart of
	accounts, version, layout, client). ``FR Sync SAP Trial Balance`` reads these by
	company so they never have to be retyped per run — see
	``FRSyncSAPTrialBalance._apply_company_template``.
	"""

	pass
