# Copyright (c) 2026, Hybrowlabs Pvt Ltd and contributors
# For license information, please see license.txt

import csv
import io
import json
import os

import frappe
from frappe.model.document import Document
from frappe.utils.file_manager import get_file


ALLOWED_DOCUMENT_TYPES = [
	"FR Sales Register",
	"FR Purchase Register",
	"FR FAR Entry",
	"FR Account Payable Entry",
	"FR Account Receivable Entry",
	"FR Asset Register Entry",
]


class SyncSAP(Document):
	def validate(self):
		if not self.file:
			self.json_data = ""
			return

		if self.document_type and self.document_type not in ALLOWED_DOCUMENT_TYPES:
			frappe.throw(f"Invalid Document Type: {self.document_type}")

		self.json_data = read_file_to_json(self.file)


def read_file_to_json(file_url):
	"""Read attached file (CSV or JSON) and return its content as a JSON string."""
	file_name, content = get_file(file_url)
	ext = os.path.splitext(file_name)[1].lower()

	if isinstance(content, bytes):
		try:
			content = content.decode("utf-8-sig")
		except UnicodeDecodeError:
			content = content.decode("latin-1")

	if ext == ".json":
		try:
			data = json.loads(content)
		except ValueError as e:
			frappe.throw(f"Invalid JSON file: {e}")
	elif ext == ".csv":
		reader = csv.DictReader(io.StringIO(content))
		data = [row for row in reader]
	else:
		frappe.throw(f"Unsupported file type '{ext}'. Upload a .csv or .json file.")

	return json.dumps(data, ensure_ascii=False, indent=2)
