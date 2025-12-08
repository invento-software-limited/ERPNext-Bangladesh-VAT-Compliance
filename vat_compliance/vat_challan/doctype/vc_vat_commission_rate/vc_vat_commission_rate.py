# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from vat_compliance.vschallan import VATSmartChallan


class VCVATCommissionRate(Document):
	pass


@frappe.whitelist()
def sync_vc_vat_commission_rate():
	vschallan = VATSmartChallan()
	vschallan.get_vat_commission_rate()
	return "success"
