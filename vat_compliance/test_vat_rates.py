# Copyright (c) 2026, Invento Software Limited and Contributors
# See license.txt

"""VAT on invoice lines with and without an Item Tax Template, across the reports
and the payment VDS calculation that share vat_compliance.vat_rates."""

import unittest
from unittest.mock import patch

import frappe

from vat_compliance import vat_rates
from vat_compliance.hook_functions import payment_entry
from vat_compliance.vat_compliance.report.purchase_sales_ledger_for_trader import (
	purchase_sales_ledger_for_trader as trader,
)
from vat_compliance.vat_compliance.report.sales_register___mushak_6_2 import sales_register___mushak_6_2 as m62
from vat_compliance.vat_compliance.report.sales_vat_management import sales_vat_management as svm
from vat_compliance.vat_compliance.report.vds_management import vds_management as vds

VAT = "VAT - T"
OTHER = "AIT - T"


def _line(net, rates, template=None, **kw):
	return frappe._dict(net_amount=net, item_tax_rate=frappe.as_json(rates), item_tax_template=template,
		item_code="ITEM", item_name="Item", expense_account="Expense - T", **kw)


class _Doc:
	"""Just enough of a Document for the code under test: attributes plus .get()."""

	def __init__(self, **fields):
		self.__dict__.update(fields)

	def get(self, key, default=None):
		return self.__dict__.get(key, default)


def _vat_accounts(_company):
	return [VAT]


class TestVatAccounts(unittest.TestCase):
	def tearDown(self):
		frappe.local.vat_compliance_vat_accounts = None

	def test_resolved_once_per_request_and_per_company(self):
		frappe.local.vat_compliance_vat_accounts = None
		with patch.object(vat_rates, "_resolve_vat_accounts", side_effect=lambda c: [f"VAT - {c}"]) as resolve:
			self.assertEqual(vat_rates.vat_accounts("A"), ["VAT - A"])
			self.assertEqual(vat_rates.vat_accounts("A"), ["VAT - A"])
			self.assertEqual(vat_rates.vat_accounts("B"), ["VAT - B"])
		self.assertEqual(resolve.call_count, 2)


@patch.object(vat_rates, "vat_accounts", _vat_accounts)
class TestLineVat(unittest.TestCase):
	def test_line_without_template_uses_its_vat_account_rate(self):
		self.assertEqual(vat_rates.line_vat(_line(100, {VAT: 15}), "T"), (VAT, 15))

	def test_another_tax_is_never_read_as_vat(self):
		self.assertEqual(vat_rates.line_vat(_line(100, {OTHER: 5, VAT: 15}), "T"), (VAT, 15))
		self.assertEqual(vat_rates.line_vat(_line(100, {OTHER: 5}), "T"), (None, 0))
		self.assertEqual(vat_rates.line_vat(_line(100, {}), "T"), (None, 0))

	def test_template_line_keeps_its_old_reading(self):
		line = _line(100, {OTHER: 5, VAT: 15}, template="Any Template")
		self.assertEqual(vat_rates.line_vat(line, "T"), (OTHER, 5))

	def test_rate_may_be_stored_as_a_dict(self):
		self.assertEqual(vat_rates.parse_item_tax_rate('{"VAT - T": {"tax_rate": 7.5}}'), {VAT: 7.5})
		self.assertEqual(vat_rates.parse_item_tax_rate("not json"), {})

	def test_taxable_lines_for_payment_allocation(self):
		self.assertTrue(vat_rates.is_taxable_line(_line(100, {}, template="Zero Rated"), "T"))
		self.assertTrue(vat_rates.is_taxable_line(_line(100, {VAT: 15}), "T"))
		self.assertFalse(vat_rates.is_taxable_line(_line(100, {OTHER: 5}), "T"))

	def test_payment_tax_map(self):
		self.assertEqual(vat_rates.line_tax_map(_line(100, {OTHER: 5, VAT: 15}), "T"), {VAT: 15})
		self.assertEqual(vat_rates.line_tax_map(_line(100, {OTHER: 5, VAT: 15}, template="X"), "T"), {OTHER: 5, VAT: 15})


@patch.object(vat_rates, "vat_accounts", _vat_accounts)
class TestReports(unittest.TestCase):
	def test_mushak_6_2_counts_vat_without_a_template(self):
		self.assertEqual(m62.calculate_vat_amount(None, 240000, "T", frappe.as_json({VAT: 15})), 36000)
		self.assertEqual(m62.calculate_vat_amount(None, 240000, "T", "{}"), 0)

	def test_trader_ledger_counts_vat_without_a_template(self):
		self.assertEqual(trader.calculate_purchase_vat(None, 89000, "T", frappe.as_json({VAT: 15})), 13350)
		self.assertEqual(trader.calculate_sales_vat(None, 1000, "T", frappe.as_json({OTHER: 5})), 0)

	def test_sales_vat_management_reads_lines_without_a_template(self):
		inv = _Doc(company="T", items=[_line(240000, {VAT: 15}), _line(10000, {})])
		heads, vat = svm._calculate_vat_amount_and_accounts(inv, {})
		self.assertEqual((heads, vat), ({VAT}, 36000))

	def test_sales_vat_management_credit_note_vat_is_negative(self):
		inv = _Doc(company="T", items=[_line(-120000, {VAT: 15})])
		self.assertEqual(svm._calculate_vat_amount_and_accounts(inv, {})[1], -18000)

	def test_vds_groups_include_lines_without_a_template(self):
		inv = _Doc(company="T", items=[_line(1000, {VAT: 15}), _line(1000, {})])
		groups = vds._get_tax_template_groups(inv, 500)
		self.assertEqual(len(groups), 1)
		self.assertEqual(groups[0]["liability_head"], VAT)
		self.assertAlmostEqual(groups[0]["vds_amount"], 75)  # 500 of 1,000 taxable × 15%


@patch.object(vat_rates, "vat_accounts", _vat_accounts)
class TestPaymentVds(unittest.TestCase):
	def test_withheld_payment_deducts_vat_on_a_line_without_template(self):
		inv = _Doc(doctype="Purchase Invoice", name="PI-1", company="T", cost_center="Main - T",
			items=[_line(1000, {VAT: 15, OTHER: 5})])
		pe = _Doc(payment_type="Pay", company="T", references=[frappe._dict(
			reference_doctype="Purchase Invoice", reference_name="PI-1", custom_vdsvcs="Withheld", allocated_amount=1000)])
		with patch.object(payment_entry.frappe, "get_doc", return_value=inv):
			rows = payment_entry.calculate_tax_rows(pe)
		self.assertEqual([(r["account"], r["amount"]) for r in rows], [(VAT, -150)])
