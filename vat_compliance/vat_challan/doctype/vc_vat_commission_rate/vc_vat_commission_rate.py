# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from vat_compliance.vschallan import VATSmartChallan


class VCVATCommissionRate(Document):
	pass


@frappe.whitelist(methods=["POST"])
def sync_vc_vat_commission_rate():
	frappe.has_permission("VC VAT Commission Rate", "create", throw=True)
	vschallan = VATSmartChallan()
	vschallan.get_vat_commission_rate()
	return "success"
