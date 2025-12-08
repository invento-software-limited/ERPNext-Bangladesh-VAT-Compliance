# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from vat_compliance.vschallan import VATSmartChallan


class VCDivision(Document):
	pass


@frappe.whitelist()
def sync_vc_division():
	vschallan = VATSmartChallan()
	vschallan.get_division()
	return "success"
