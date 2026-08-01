# Copyright (c) 2026, Hybrowlabs Pvt Ltd
# For license information, please see license.txt

from frappe.model.document import Document


class SAPCompanyMapping(Document):
	"""Per-Company SAP connection template.

	Holds the fixed SAP parameters for a company (company code, chart of
	accounts, version, layout, client). ``Sync SAP Trial Balance`` reads these by
	company so they never have to be retyped per run — see
	``SyncSAPTrialBalance._apply_company_template``.
	"""

	pass
