# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""Every whitelisted method that changes data refuses a caller without access, and refuses GET."""

import unittest
from unittest.mock import MagicMock, patch

import frappe

from vat_compliance import api
from vat_compliance.hook_functions import payment_entry
from vat_compliance.vat_compliance.page.vat_payment import vat_payment
from vat_compliance.vat_compliance.report.sales_vat_management import sales_vat_management
from vat_compliance.vat_compliance.report.supplier_mushak_6_3 import supplier_mushak_6_3

REFUSED_FOR_GUEST = (
	(supplier_mushak_6_3.upload_mushak_63, ("PI-1", "/files/x.pdf")),
	(payment_entry.calculate_tax_rows, ({"doctype": "Payment Entry"},)),
	(vat_payment.get_vat_payment_data, ("2026-01-01", "2026-01-31", "Any Company")),
)

POST_ONLY = (
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
