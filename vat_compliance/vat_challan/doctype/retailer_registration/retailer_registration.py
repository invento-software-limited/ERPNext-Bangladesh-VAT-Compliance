# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from vat_compliance.vschallan import VATSmartChallan


class RetailerRegistration(Document):
	def before_submit(self):
		vschallan = VATSmartChallan()
		vschallan.register_retailer(self)


@frappe.whitelist()
def get_service_types(force_refresh: bool = False):
	vschallan = VATSmartChallan()
	result = vschallan.get_service_types(force_refresh=frappe.utils.cint(force_refresh))
	return result


@frappe.whitelist()
def get_zone(force_refresh: bool = False):
	vschallan = VATSmartChallan()
	result = vschallan.get_zone(force_refresh=frappe.utils.cint(force_refresh))
	return result


@frappe.whitelist()
def get_vat_commission_rate(force_refresh: bool = False, zone_id: str | None = None):
	vschallan = VATSmartChallan()
	result = vschallan.get_vat_commission_rate(
		force_refresh=frappe.utils.cint(force_refresh), zone_id=zone_id
	)
	return result


@frappe.whitelist()
def get_division(force_refresh: bool = False, vat_commissionrate_id: str | None = None):
	vschallan = VATSmartChallan()
	result = vschallan.get_division(
		force_refresh=frappe.utils.cint(force_refresh), vat_commissionrate_id=vat_commissionrate_id
	)
	return result


@frappe.whitelist()
def get_circle(force_refresh: bool = False, division_id: str | None = None):
	vschallan = VATSmartChallan()
	result = vschallan.get_circle(force_refresh=frappe.utils.cint(force_refresh), division_id=division_id)
	return result


@frappe.whitelist()
def upload_file(retailer_id: str, document_category_key: str, file_path: str):
	"""
	Whitelisted wrapper to upload a retailer document file to NBR API.

	Args:
		retailer_id (str): Retailer's ID.
		document_category_key (str): Document type key (nid_document, trade_license, etc.).
		file_path (str): Path to the local file to upload.
	"""
	vschallan = VATSmartChallan()
	return vschallan.upload_file(
		document_category_key=document_category_key, file_path=file_path, retailer_id=retailer_id
	)
