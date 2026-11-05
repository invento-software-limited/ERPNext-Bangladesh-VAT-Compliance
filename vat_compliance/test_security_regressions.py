# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""Regression tests for vulnerabilities found by the v2.3.0 security re-check."""

import importlib
import unittest
from unittest.mock import patch

import frappe

from vat_compliance import access
from vat_compliance.hook_functions import purchase_invoice
from vat_compliance.vat_compliance.doctype.compliance_settings.compliance_settings import ComplianceSettings
from vat_compliance.vat_compliance.doctype.vat_deduction_certificate.vat_deduction_certificate import (
	VATDeductionCertificate,
)
from vat_compliance.vat_compliance.report.mushak_6_3 import mushak_6_3
from vat_compliance.vat_compliance.report.sales_vat_management import sales_vat_management

SCRIPT = "<script>alert(1)</script>"
COMPANY_SCOPED_REPORTS = (
	"sales_vat_management",
	"supplier_mushak_6_3",
	"sales_register___mushak_6_2",
	"purchase_register___mushak_6_1",
	"purchase_sales_ledger_for_trader",
	"vds_management",
)


class TestCertificateFields(unittest.TestCase):
	def certificate(self, saved):
		doc = frappe.new_doc("VAT Deduction Certificate")
		doc.certificate_html = doc.context = SCRIPT
		self.assertIsInstance(doc, VATDeductionCertificate)
		with patch.object(doc, "get_doc_before_save", return_value=saved):
			doc.keep_generated_fields()
		return doc

	def test_new_certificate_cannot_carry_html(self):
		doc = self.certificate(None)
		self.assertIsNone(doc.certificate_html)
		self.assertIsNone(doc.context)

	def test_saved_certificate_keeps_generated_html(self):
		doc = self.certificate(frappe._dict(certificate_html="<p>ok</p>", context="{}"))
		self.assertEqual((doc.certificate_html, doc.context), ("<p>ok</p>", "{}"))


class TestCertificateCompanyField(unittest.TestCase):
	def test_company_can_be_chosen_once(self):
		# A required read-only field with no value is hidden, so the form could never be saved.
		field = frappe.get_meta("VAT Deduction Certificate").get_field("company")
		self.assertTrue(field.reqd)
		self.assertFalse(field.read_only)
		self.assertTrue(field.set_only_once)


class TestMushak63Attachment(unittest.TestCase):
	def invoice(self, value, changed=True):
		doc = frappe.new_doc("Purchase Invoice")
		doc.custom_mushak_63 = value
		return doc, patch.object(doc, "has_value_changed", return_value=changed)

	@patch("vat_compliance.access.find_file_by_url", return_value=None)
	def test_script_payload_is_refused(self, _find):
		doc, changed = self.invoice('"><img src=x onerror=alert(1)>')
		with changed, self.assertRaises(frappe.PermissionError):
			purchase_invoice.validate_mushak_63(doc)

	@patch("vat_compliance.access.find_file_by_url", return_value=frappe._dict(name="F-1"))
	def test_readable_file_is_accepted(self, _find):
		doc, changed = self.invoice("/files/mushak.pdf")
		with changed:
			purchase_invoice.validate_mushak_63(doc)

	@patch("vat_compliance.access.find_file_by_url", return_value=None)
	def test_unchanged_value_does_not_block_other_edits(self, find):
		doc, changed = self.invoice("/private/files/theirs.pdf", changed=False)
		with changed:
			purchase_invoice.validate_mushak_63(doc)
		find.assert_not_called()

	def test_hook_covers_edits_after_submit(self):
		events = frappe.get_hooks("doc_events")["Purchase Invoice"]
		path = "vat_compliance.hook_functions.purchase_invoice.validate_mushak_63"
		self.assertIn(path, events["before_update_after_submit"])
		self.assertIn(path, events["validate"])


class TestChallanFile(unittest.TestCase):
	@patch.object(sales_vat_management, "require_doc")
	@patch("vat_compliance.access.find_file_by_url", return_value=None)
	def test_unreadable_file_is_refused(self, _find, require_doc):
		rows = [{"payment_entry_id": "PE-1", "invoice_id": "SINV-1"}]
		with self.assertRaises(frappe.PermissionError):
			sales_vat_management.upload_challan(rows, {"file": "/private/files/theirs.pdf"})
		require_doc.assert_not_called()


class TestCompanyScope(unittest.TestCase):
	def test_other_company_is_refused(self):
		with (
			patch.object(access, "allowed_companies", return_value=["Mine"]),
			self.assertRaises(frappe.PermissionError),
		):
			access.scope_report_to_company({"company": "Theirs"})

	def test_allowed_company_passes(self):
		with patch.object(access, "allowed_companies", return_value=["Mine"]):
			access.scope_report_to_company({"company": "Mine"})

	def test_restricted_user_must_name_a_company(self):
		with (
			patch.object(access, "get_user_permissions", return_value={"Company": [{"doc": "Mine"}]}),
			self.assertRaises(frappe.ValidationError),
		):
			access.scope_report_to_company({})

	def test_unrestricted_user_may_leave_company_blank(self):
		with patch.object(access, "get_user_permissions", return_value={}):
			access.scope_report_to_company(None)

	def test_every_raw_sql_report_applies_the_scope(self):
		for name in COMPANY_SCOPED_REPORTS:
			module = importlib.import_module(f"vat_compliance.vat_compliance.report.{name}.{name}")
			with (
				self.subTest(name),
				patch.object(access, "allowed_companies", return_value=[]),
				self.assertRaises(frappe.PermissionError),
			):
				module.execute({"company": "Theirs"})


class TestBulkDownload(unittest.TestCase):
	def test_status_filter_keeps_submitted_only(self):
		with patch.object(frappe, "get_list", return_value=[]) as get_list:
			mushak_6_3.get_data({"status": "Paid"})
		self.assertIn(["docstatus", "=", 1], get_list.call_args.kwargs["filters"])

	@patch.object(mushak_6_3, "require_report")
	def test_print_permission_is_required(self, _report):
		with (
			patch.object(frappe, "has_permission", side_effect=frappe.PermissionError) as has_permission,
			self.assertRaises(frappe.PermissionError),
		):
			mushak_6_3.download_all_invoices({})
		has_permission.assert_called_once_with("Sales Invoice", "print", throw=True)

	@patch.object(mushak_6_3, "require_report", side_effect=frappe.PermissionError)
	def test_report_access_is_required(self, _report):
		with self.assertRaises(frappe.PermissionError):
			mushak_6_3.download_all_invoices({})

	@patch.object(mushak_6_3, "require_report")
	def test_size_is_capped_before_any_pdf(self, _report):
		rows = [{"name": str(i)} for i in range(mushak_6_3.MAX_BULK_INVOICES + 1)]
		with (
			patch.object(frappe, "has_permission", return_value=True),
			patch.object(mushak_6_3, "get_data", return_value=rows),
			patch.object(frappe, "get_print") as get_print,
			self.assertRaises(frappe.ValidationError),
		):
			mushak_6_3.download_all_invoices({})
		get_print.assert_not_called()


class TestTaxTemplates(unittest.TestCase):
	def test_create_is_post_only(self):
		allowed = frappe.allowed_http_methods_for_whitelisted_func[ComplianceSettings.create_tax_templates]
		self.assertEqual(allowed, ["POST"])
