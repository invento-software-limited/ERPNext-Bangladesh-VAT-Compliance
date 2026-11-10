# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

import unittest

from vat_compliance.stock_movements import RunningStock
from vat_compliance.vat_rates import payment_ratio


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
