# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from vat_compliance.vat_challan.vendor_url import check_base_url
from vat_compliance.vschallan import VATSmartChallan


class POSVendorConfiguration(Document):
	def validate(self):
		check_base_url(self.base_url)


@frappe.whitelist(methods=["POST"])
def fetch_pos_vendor_token():
	frappe.has_permission("POS Vendor Configuration", "write", throw=True)
	vschallan = VATSmartChallan()
	vschallan.get_access_token()
