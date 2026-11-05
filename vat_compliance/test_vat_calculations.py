# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import frappe

from vat_compliance.stock_movements import RunningStock
from vat_compliance.vat_challan.challan_lines import invoice_timestamp, line_amounts
from vat_compliance.vat_rates import payment_ratio


def line(**values):
	return frappe._dict({"qty": 1, "rate": 0, "amount": 0, "discount_amount": 0, **values})


class TestLineAmounts(unittest.TestCase):
	def test_line_discount_is_not_deducted_twice(self):
		# A 27.00 item with 1.50 off is sold at rate 25.50.
		result = line_amounts(frappe._dict(), line(rate=25.5, amount=25.5, discount_amount=1.5), 0, False)
		self.assertEqual(result.unit_price, 27.0)
		self.assertEqual(result.discount_amount, 1.5)
		self.assertEqual(result.total_amount_before_tax, 25.5)

	def test_inclusive_vat_is_taken_out_of_the_price(self):
		result = line_amounts(frappe._dict(), line(rate=115, amount=115), 15, True)
		self.assertAlmostEqual(result.total_amount_before_tax, 100)
		self.assertAlmostEqual(result.vat_amount, 15)
		self.assertAlmostEqual(result.total_amount, 115)

	def test_exclusive_vat_is_added_to_the_price(self):
		result = line_amounts(frappe._dict(), line(rate=100, amount=100), 15, False)
		self.assertAlmostEqual(result.vat_amount, 15)
		self.assertAlmostEqual(result.total_amount, 115)

	def test_invoice_discount_is_shared_by_line_value(self):
		doc = frappe._dict(total=200, discount_amount=20)
		result = line_amounts(doc, line(rate=100, amount=100), 15, False)
		self.assertAlmostEqual(result.discount_amount, 10)
		self.assertAlmostEqual(result.total_amount_before_tax, 90)

	def test_return_line_is_positive(self):
		result = line_amounts(frappe._dict(), line(qty=-2, rate=100, amount=-200), 15, False)
		self.assertEqual(result.qty, 2)
		self.assertAlmostEqual(result.total_amount, 230)


class TestInvoiceTimestamp(unittest.TestCase):
	def expected(self):
		return int(datetime(2026, 10, 31, 17, 0, tzinfo=UTC).timestamp())

	@patch("vat_compliance.vat_challan.challan_lines.get_system_timezone", return_value="Asia/Dhaka")
	def test_uses_site_time_zone(self, _zone):
		self.assertEqual(invoice_timestamp("2026-10-31", "23:00:00"), self.expected())

	@patch("vat_compliance.vat_challan.challan_lines.get_system_timezone", return_value="Asia/Dhaka")
	def test_accepts_timedelta_from_the_database(self, _zone):
		self.assertEqual(invoice_timestamp("2026-10-31", timedelta(hours=23)), self.expected())


class TestPaymentRatio(unittest.TestCase):
	def test_half_payment_of_gross_total(self):
		self.assertEqual(payment_ratio({"grand_total": 115}, 57.5), 0.5)

	def test_rounded_total_wins(self):
		self.assertEqual(payment_ratio({"rounded_total": 100, "grand_total": 99.6}, 50), 0.5)

	def test_never_above_one(self):
		self.assertEqual(payment_ratio({"grand_total": 100}, 150), 1.0)

	def test_zero_total(self):
		self.assertEqual(payment_ratio({"grand_total": 0}, 50), 0.0)

	def test_return_is_positive(self):
		self.assertEqual(payment_ratio({"grand_total": -100}, -50), 0.5)


class TestRunningStock(unittest.TestCase):
	def stock(self):
		return RunningStock(
			{"A": {"qty": 10, "value": 100}},
			[
				{"item_code": "A", "posting_date": "2026-01-05", "qty": 2, "value": 20},
				{"item_code": "A", "posting_date": "2026-01-01", "qty": 1, "value": 10},
			],
		)

	def test_movement_counts_once_across_rows(self):
		stock = self.stock()
		self.assertEqual(stock.take_movements("A", "2026-01-02"), (1, 10))
		self.assertEqual(stock.take_movements("A", "2026-01-03"), (0, 0))
		self.assertEqual(stock.take_movements("A", "2026-01-31"), (2, 20))

	def test_opening_follows_the_previous_close(self):
		stock = self.stock()
		self.assertEqual(stock.opening("A"), (10, 100))
		stock.close("A", 7, 70)
		self.assertEqual(stock.opening("A"), (7, 70))

	def test_unknown_item_starts_at_zero(self):
		self.assertEqual(self.stock().opening("B"), (0.0, 0.0))
