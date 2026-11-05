# Copyright (c) 2025, na and Contributors
# See license.txt

import unittest
from unittest.mock import MagicMock, patch

import frappe

from vat_compliance.vat_compliance.doctype.vat_deduction_certificate.vat_deduction_certificate import (
	generate_mushak_6_6,
)

MODULE = "vat_compliance.vat_compliance.doctype.vat_deduction_certificate.vat_deduction_certificate"


class TestVATDeductionCertificate(unittest.TestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_generate_only_accepts_post(self):
		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[generate_mushak_6_6], ["POST"])

	def test_generate_rejects_user_without_permission(self):
		frappe.set_user("Guest")
		with patch(f"{MODULE}.frappe.get_doc") as get_doc:
			self.assertRaises(frappe.PermissionError, generate_mushak_6_6, "VDC-ANY")
		get_doc.assert_not_called()

	def test_generate_rejects_user_without_write_permission(self):
		def read_only(doctype, ptype="read", **kwargs):
			if ptype == "write":
				raise frappe.PermissionError
			return True

		certificate = MagicMock()
		with (
			patch(f"{MODULE}.frappe.has_permission", side_effect=read_only),
			patch(f"{MODULE}.frappe.get_doc", return_value=certificate),
		):
			self.assertRaises(frappe.PermissionError, generate_mushak_6_6, "VDC-ANY")
		certificate.update_references_and_context.assert_not_called()

	def test_generate_regenerates_for_permitted_user(self):
		certificate = MagicMock()
		with (
			patch(f"{MODULE}.frappe.has_permission", return_value=True),
			patch(f"{MODULE}.frappe.get_doc", return_value=certificate),
		):
			self.assertIs(generate_mushak_6_6("VDC-ANY"), certificate)
		certificate.update_references_and_context.assert_called_once()


class TestCertificateContent(unittest.TestCase):
	def certificate(self):
		return frappe.get_doc(
			{
				"doctype": "VAT Deduction Certificate",
				"company": "Co",
				"vendor": "SUP-1",
				"from_date": "2026-01-01",
				"to_date": "2026-01-31",
			}
		)

	def context(self, supplier_bin="B1", company_bin="C1", rows=None):
		docs = {
			"Supplier": frappe._dict(
				name="SUP-1", supplier_name="<img src=x onerror=alert(1)>", custom_bin_no=supplier_bin
			),
			"Company": frappe._dict(name="Co", custom_bin_no=company_bin),
			"Purchase Invoice": frappe._dict(posting_date=None, total_taxes_and_charges=15),
		}
		certificate = self.certificate()
		with (
			patch(f"{MODULE}.get_company_address", return_value=None),
			patch(f"{MODULE}.frappe.get_doc", side_effect=lambda doctype, name: docs[doctype]),
		):
			return certificate.prepare_context(rows or [])

	def test_only_this_supplier_is_requested(self):
		with patch(f"{MODULE}.get_data", return_value=[]) as get_data:
			self.certificate().get_vds_withheld_data()
		self.assertEqual(get_data.call_args.args[0]["supplier"], "SUP-1")

	def test_child_tax_rows_roll_into_their_invoice(self):
		rows = [
			{"invoice_id": "PI-1", "invoice_amount": 100, "vds_amount": 10},
			{"indent": 1, "vds_amount": 5},
			{"invoice_id": "PI-2", "invoice_amount": 50, "vds_amount": 2},
		]
		withheld = self.context(rows=rows)["withheld_data"]
		self.assertEqual([r["amount_of_vat_withheld"] for r in withheld], [15, 2])
		self.assertEqual([r["sl_no"] for r in withheld], [1, 2])

	def test_stored_values_are_escaped(self):
		withheld = self.context(rows=[{"invoice_id": "PI-1", "vds_amount": 1}])["withheld_data"]
		self.assertNotIn("<img", withheld[0]["supplier_name"])

	def test_supplier_bin_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.context(supplier_bin=None)

	def test_company_bin_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.context(company_bin=None)
