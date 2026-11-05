# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

import unittest
from unittest.mock import patch

import frappe

from vat_compliance.hook_functions import payment_entry as pe

VDS_ROW = {"custom_reference_doctype": "Purchase Invoice", "custom_reference_name": "PI-1", "account": "VAT", "amount": 5}


class TestVdsRows(unittest.TestCase):
	def rows(self, payment_type, allocated=57.5):
		invoice = frappe._dict(
			doctype="Purchase Invoice", name="PI-1", company="Co", grand_total=115, items=[{"net_amount": 100, "item_code": "A"}]
		)
		ref = frappe._dict(allocated_amount=allocated)
		with (
			patch.object(pe, "get_cost_center", return_value="Main"),
			patch.object(pe, "is_taxable_line", return_value=True),
			patch.object(pe, "line_tax_map", return_value={"VAT": 15}),
		):
			return pe._invoice_vds_rows(frappe._dict(payment_type=payment_type, company="Co"), ref, invoice)

	def test_half_payment_withholds_half_the_vat(self):
		self.assertAlmostEqual(self.rows("Receive")[0]["amount"], 7.5)

	def test_paying_a_supplier_is_negative(self):
		self.assertAlmostEqual(self.rows("Pay")[0]["amount"], -7.5)

	def test_full_payment_withholds_all_the_vat(self):
		self.assertAlmostEqual(self.rows("Receive", allocated=115)[0]["amount"], 15)


class TestSyncDeductions(unittest.TestCase):
	def entry(self, *rows):
		doc = frappe.new_doc("Payment Entry")
		for row in rows:
			doc.append("deductions", row)
		return doc

	def test_write_offs_survive_and_vds_rows_are_replaced(self):
		doc = self.entry({"account": "Write Off", "amount": 1}, dict(VDS_ROW, amount=99))
		with patch.object(pe, "get_vds_rows", return_value=[VDS_ROW]):
			pe.sync_vds_deductions(doc)
		self.assertEqual([(d.account, d.amount) for d in doc.deductions], [("Write Off", 1), ("VAT", 5)])

	def test_withheld_flag_removed_clears_vds_rows(self):
		doc = self.entry(dict(VDS_ROW))
		with patch.object(pe, "get_vds_rows", return_value=[]):
			pe.sync_vds_deductions(doc)
		self.assertEqual(doc.deductions, [])

	def test_manual_rows_untouched_without_vds(self):
		doc = self.entry({"account": "Write Off", "amount": 1})
		with patch.object(pe, "get_vds_rows", return_value=[]):
			pe.sync_vds_deductions(doc)
		self.assertEqual(len(doc.deductions), 1)

	def test_submitted_entry_is_not_changed(self):
		doc = self.entry(dict(VDS_ROW))
		doc.docstatus = 1
		with patch.object(pe, "get_vds_rows") as rows:
			pe.sync_vds_deductions(doc)
		rows.assert_not_called()
