# Copyright (c) 2026, Invento Software Limited and Contributors
# See license.txt

import unittest

import frappe

from vat_compliance import report_kit as kit
from vat_compliance.vat_compliance.report.vds_management import vds_management as vds


class TestReportKit(unittest.TestCase):
	def test_monthly_buckets_cover_the_filter_window(self):
		rows = [{"d": "2026-01-15", "v": 10}, {"d": "2026-01-20", "v": 5}, {"d": "2026-03-02", "v": 7}]
		out = kit.monthly(rows, lambda r: r["d"], lambda r: r["v"], {"from_date": "2026-01-01", "to_date": "2026-06-30"})
		self.assertEqual(out["labels"], ["Jan", "Feb", "Mar", "Apr", "May", "Jun"])
		self.assertEqual(out["values"][:3], [15, 0, 7])
		self.assertEqual((out["starts"][0], out["ends"][0]), ("2026-01-01", "2026-01-31"))

	def test_group_ranks_by_value_and_skips_blank_keys(self):
		rows = [{"k": "A", "v": 1}, {"k": "B", "v": 5}, {"k": "A", "v": 2}, {"k": "", "v": 9}]
		self.assertEqual(kit.group(rows, lambda r: r["k"], lambda r: r["v"]),
			[{"key": "B", "value": 5, "count": 1}, {"key": "A", "value": 3, "count": 2}])

	def test_vds_child_rows_inherit_their_payment_status(self):
		data = [
			frappe._dict(payment_date="2026-02-03", supplier_name="S1", status="DNGT", vds_amount=100, payment_entry_id="PE-1"),
			frappe._dict(indent=1, vds_amount=40, status=""),
			frappe._dict(payment_date="2026-02-10", supplier_name="S2", status="DDGT", vds_amount=60, payment_entry_id="PE-2"),
		]
		m = vds.get_meta({"company": None, "from_date": "2026-02-01", "to_date": "2026-02-28"}, data)
		self.assertEqual((m["deducted"], m["pending"], m["deposited"]), (200, 140, 60))
		self.assertEqual((m["pending_count"], m["deposited_count"], m["payments"]), (1, 1, 2))
