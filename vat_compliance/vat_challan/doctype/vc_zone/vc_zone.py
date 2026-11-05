# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from vat_compliance.vschallan import VATSmartChallan


class VCZone(Document):
	pass


@frappe.whitelist(methods=["POST"])
def sync_zone():
	frappe.has_permission("VC Zone", "create", throw=True)
	vschallan = VATSmartChallan()
	vschallan.get_zone()
	return "success"
