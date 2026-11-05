# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from vat_compliance.vschallan import VATSmartChallan


class VCDivision(Document):
	pass


@frappe.whitelist(methods=["POST"])
def sync_vc_division():
	frappe.has_permission("VC Division", "create", throw=True)
	vschallan = VATSmartChallan()
	vschallan.get_division()
	return "success"
