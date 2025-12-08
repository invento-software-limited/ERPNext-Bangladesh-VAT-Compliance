# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from vat_compliance.vschallan import VATSmartChallan


class POSVendorConfiguration(Document):
	pass


@frappe.whitelist()
def fetch_pos_vendor_token():
	vschallan = VATSmartChallan()
	vschallan.get_access_token()
