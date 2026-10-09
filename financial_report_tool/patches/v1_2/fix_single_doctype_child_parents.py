import frappe


def execute():
	"""Re-point child rows of Single doctypes at the renamed parent.

	rename_doc updates `parenttype` on child rows but leaves `parent` untouched, and a
	Single's `parent` is its own name. After "GL Account Request Settings" became
	"FR GL Account Request Settings" its Company Assignments kept the old `parent`, so
	loading the settings returned an empty table and no company had an assignee (Maker).
	"""
	singles = {
		r[0] for r in frappe.db.sql("select name from `tabDocType` where issingle = 1 and name like 'FR %%'")
	}
	for table in frappe.db.sql(
		"""select distinct table_name from information_schema.columns
		where table_schema = database() and column_name = 'parenttype' and table_name like 'tabFR %%'""",
		pluck=True,
	):
		for parenttype in singles:
			frappe.db.sql(
				f"update `{table}` set parent = %s where parenttype = %s and parent != %s",
				(parenttype, parenttype, parenttype),
			)
	frappe.clear_cache()
