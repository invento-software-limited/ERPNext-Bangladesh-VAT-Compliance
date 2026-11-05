# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from vat_compliance.access import require_doc
from vat_compliance.vschallan import VATSmartChallan

DOCUMENT_CATEGORIES = (
	"nid_document",
	"business_identification_number",
	"trade_license",
	"tax_identification",
)


class RetailerRegistration(Document):
	def before_submit(self):
		vschallan = VATSmartChallan()
		vschallan.register_retailer(self)


@frappe.whitelist(methods=["POST"])
def upload_file(name: str, document_category_key: str, file_path: str):
	"""Send one of this Retailer's attachments to the vendor. The file must be attached to the
	Retailer, so this can never be used to send any other file on the site."""
	require_doc("Retailer Registration", name, "write")

	if document_category_key not in DOCUMENT_CATEGORIES:
		frappe.throw(_("Unknown document category"))
	retailer_id = frappe.db.get_value("Retailer Registration", name, "retailer_id")
	if not retailer_id:
		frappe.throw(_("Submit the Retailer Registration before uploading documents."))
	if not frappe.db.exists(
		"File",
		{"file_url": file_path, "attached_to_doctype": "Retailer Registration", "attached_to_name": name},
	):
		frappe.throw(_("This file is not attached to the Retailer Registration."), frappe.PermissionError)

	return VATSmartChallan().upload_file(
		document_category_key=document_category_key, file_path=file_path, retailer_id=retailer_id
	)
