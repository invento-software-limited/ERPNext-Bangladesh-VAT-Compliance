# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""Every whitelisted method that changes data or reaches a vendor refuses a caller without
access, and refuses GET."""

import unittest
from unittest.mock import MagicMock, patch

import frappe

from vat_compliance import api
from vat_compliance.hook_functions import payment_entry
from vat_compliance.vat_challan.doctype.pos_vendor_configuration import pos_vendor_configuration as vendor
from vat_compliance.vat_challan.doctype.retailer_registration import retailer_registration as retailer
from vat_compliance.vat_challan.doctype.vat_invoice import vat_invoice
from vat_compliance.vat_challan.doctype.vc_circle import vc_circle
from vat_compliance.vat_challan.doctype.vc_division import vc_division
from vat_compliance.vat_challan.doctype.vc_service_type import vc_service_type
from vat_compliance.vat_challan.doctype.vc_vat_commission_rate import vc_vat_commission_rate
from vat_compliance.vat_challan.doctype.vc_zone import vc_zone
from vat_compliance.vat_compliance.page.vat_payment import vat_payment
from vat_compliance.vat_compliance.report.sales_vat_management import sales_vat_management
from vat_compliance.vat_compliance.report.supplier_mushak_6_3 import supplier_mushak_6_3
from vat_compliance import vschallan

REFUSED_FOR_GUEST = (
	(vat_invoice.sync_vat_invoice, ("VI-1",)),
	(vat_invoice.download_schallan, ("VI-1",)),
	(retailer.upload_file, ("R-1", "trade_license", "/files/x.pdf")),
	(vendor.fetch_pos_vendor_token, ()),
	(vc_zone.sync_zone, ()),
	(vc_division.sync_vc_division, ()),
	(vc_circle.sync_vc_circle, ()),
	(vc_service_type.sync_vc_service_type, ()),
	(vc_vat_commission_rate.sync_vc_vat_commission_rate, ()),
	(vschallan.auto_sync_vat_invoices, ()),
	(supplier_mushak_6_3.upload_mushak_63, ("PI-1", "/files/x.pdf")),
	(payment_entry.calculate_tax_rows, ({"doctype": "Payment Entry"},)),
	(vat_payment.get_vat_payment_data, ("2026-01-01", "2026-01-31", "Any Company")),
)

POST_ONLY = (
	vat_invoice.sync_vat_invoice,
	retailer.upload_file,
	vendor.fetch_pos_vendor_token,
	vc_zone.sync_zone,
	vc_division.sync_vc_division,
	vc_circle.sync_vc_circle,
	vc_service_type.sync_vc_service_type,
	vc_vat_commission_rate.sync_vc_vat_commission_rate,
	vschallan.auto_sync_vat_invoices,
	supplier_mushak_6_3.upload_mushak_63,
	sales_vat_management.upload_challan,
	vat_payment.make_journal_entry,
	api.validate_bin,
	api.validate_tin,
)


class TestEndpointAccess(unittest.TestCase):
	def setUp(self):
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user("Guest")

	def test_guest_is_refused_before_any_work(self):
		for method, args in REFUSED_FOR_GUEST:
			with self.subTest(method.__name__), self.assertRaises(frappe.PermissionError):
				method(*args)
			frappe.clear_messages()

	def test_guest_cannot_verify_bin_or_tin(self):
		with self.assertRaises(frappe.PermissionError):
			api._require_party_write()

	def test_changes_are_post_only(self):
		for method in POST_ONLY:
			with self.subTest(method.__name__):
				self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[method], ["POST"])


class TestUploadGuards(unittest.TestCase):
	@patch.object(retailer, "require_doc")
	def test_unknown_document_category_is_refused(self, _require):
		with self.assertRaises(frappe.ValidationError):
			retailer.upload_file("R-1", "site_config", "/files/x.pdf")

	@patch.object(retailer, "VATSmartChallan")
	@patch.object(retailer, "require_doc")
	def test_file_must_be_attached_to_that_retailer(self, _require, client):
		with patch.object(frappe, "db", MagicMock()) as db:
			db.get_value.return_value = "RID-1"
			db.exists.return_value = None
			with self.assertRaises(frappe.PermissionError):
				retailer.upload_file("R-1", "trade_license", "/private/files/other.pdf")
		client.assert_not_called()

	@patch("vat_compliance.access.find_file_by_url", return_value=None)
	@patch.object(supplier_mushak_6_3, "require_doc")
	def test_mushak_6_3_needs_a_readable_file(self, _require, _find):
		with self.assertRaises(frappe.PermissionError):
			supplier_mushak_6_3.upload_mushak_63("PI-1", "/private/files/other.pdf")

	def test_challan_invoices_must_be_on_the_payment(self):
		with patch.object(frappe, "get_all", return_value=["SINV-1"]):
			sales_vat_management._require_references("PE-1", ["SINV-1"])
			with self.assertRaises(frappe.ValidationError):
				sales_vat_management._require_references("PE-1", ["SINV-1", "SINV-OTHER"])
