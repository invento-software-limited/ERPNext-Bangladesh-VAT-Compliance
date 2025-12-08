# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from vat_compliance.vschallan import VATSmartChallan


class RetailerBranchRegistration(Document):
	def before_submit(self):
		vschallan = VATSmartChallan()
		vschallan.retailer_branch_registration(self)
