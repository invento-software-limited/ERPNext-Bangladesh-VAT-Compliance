# Copyright (c) 2026, Invento Software Limited and Contributors
# See license.txt

import unittest
from datetime import date

import frappe

from vat_compliance.dashboard import period, vat_ledger


def _row(voucher_type, debit=0, credit=0, posted="2026-10-10"):
	return frappe._dict(voucher_type=voucher_type, voucher_no="X", debit=debit, credit=credit,
		posting_date=date.fromisoformat(posted), liability=credit - debit)


class TestVATLedger(unittest.TestCase):
	def test_every_posting_lands_in_one_source(self):
		self.assertEqual(vat_ledger._source(_row("Sales Invoice"), None), "output")
		self.assertEqual(vat_ledger._source(_row("POS Invoice"), None), "output")
		self.assertEqual(vat_ledger._source(_row("Purchase Invoice"), None), "input")
		self.assertEqual(vat_ledger._source(_row("Journal Entry"), "VAT Payment Entry"), "deposit")
		self.assertEqual(vat_ledger._source(_row("Journal Entry"), "Opening Entry"), "opening")
		self.assertEqual(vat_ledger._source(_row("Journal Entry"), "Journal Entry"), "adjustment")

	def test_balance_identity_holds(self):
		rows = [_row("Sales Invoice", credit=1000), _row("Sales Invoice", debit=100), _row("Purchase Invoice", debit=300),
			_row("Journal Entry", debit=200), _row("Journal Entry", credit=50)]
		for r, je in zip(rows, [None, None, None, "VAT Payment Entry", "Opening Entry"]):
			r.source = vat_ledger._source(r, je)
		t = vat_ledger.totals(rows)
		self.assertEqual(t["output"], 900)  # sales returns post as debits and net off
		self.assertEqual(t["input"], 300)
		self.assertEqual(t["deposit"], 200)
		self.assertEqual(t["opening"] + t["output"] - t["input"] - t["deposit"] + t["adjustment"], vat_ledger.balance(rows, "2026-12-31"))


class TestVATPeriod(unittest.TestCase):
	TODAY = "2026-10-19"

	def test_month_presets(self):
		self.assertEqual(period.resolve("tm", today=self.TODAY)[:2], (date(2026, 10, 1), date(2026, 10, 19)))
		self.assertEqual(period.resolve("lm", today=self.TODAY)[:2], (date(2026, 9, 1), date(2026, 9, 30)))

	def test_custom_range_is_validated(self):
		self.assertRaises(frappe.ValidationError, period.resolve, "custom", "2026-05-02", "2026-05-01")
		self.assertRaises(frappe.ValidationError, period.resolve, "bogus", today=self.TODAY)
