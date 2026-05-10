# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from vat_compliance.vschallan import VATSmartChallan


class VATInvoice(Document):
	def sync_vat_invoice(self):
		"""Sync VAT Invoice to external system"""
		vschallan = VATSmartChallan()
		vschallan.sync_vat_invoice(self)

	def download_schallan(self):
		"""Download S Challan"""
		vschallan = VATSmartChallan()
		return vschallan.download_schallan(self)


@frappe.whitelist()
def sync_vat_invoice(vat_invoice_name: str):
	"""API method to sync VAT Invoice"""
	vat_invoice = frappe.get_doc("VAT Invoice", vat_invoice_name)
	vat_invoice.sync_vat_invoice()
	return {"success": True}


@frappe.whitelist()
def download_schallan(vat_invoice_name: str):
	"""API method to download VAT Invoice"""
	vat_invoice = frappe.get_doc("VAT Invoice", vat_invoice_name)
	return vat_invoice.download_schallan()
