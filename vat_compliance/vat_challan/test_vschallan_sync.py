# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

import json
import unittest
from unittest.mock import MagicMock, patch

import frappe

from vat_compliance.vat_challan import sync_health
from vat_compliance.vat_challan.hook_functions import vat_invoice as hook
from vat_compliance.vat_challan.vendor_url import check_base_url
from vat_compliance.vschallan import VATSmartChallan

ACCEPTED = {"status_code": 200, "data": {"vat_invoice_id": "V1", "s_challan_number": "C1"}}
REJECTED = {"status_code": 400, "message": "bad"}
ON_FILE = {"status_code": 200, "data": {"vat_invoice_id": "V9", "s_challan_number": "C9"}}


class FakeInvoice(frappe._dict):
	def db_set(self, field, value):
		self[field] = value

	def reload(self):
		pass


def invoice(**values):
	return FakeInvoice(
		{
			"name": "VI-1",
			"invoice_number": "SINV-1",
			"status": "Pending",
			"requested_payloads": "{}",
			**values,
		}
	)


class VendorCase(unittest.TestCase):
	"""A client with the database and every vendor call replaced."""

	def setUp(self):
		for name in ("db", "log_error"):
			patcher = patch.object(frappe, name, MagicMock())
			patcher.start()
			self.addCleanup(patcher.stop)
		self.client = VATSmartChallan.__new__(VATSmartChallan)
		self.client.base_url = "https://vendor.dgepay.net"
		self.client.last_http_status = None
		self.client.get_response_data = MagicMock()
		self.client._fetch_invoice_details = MagicMock()
		self.client.get_vat_invoice_details = MagicMock()

	def sync(self, doc):
		frappe.db.get_value.return_value = doc.status
		self.client.sync_vat_invoice(doc)

	def posted_sales(self):
		return [c for c in self.client.get_response_data.call_args_list if c.args[0].endswith("/record_vat")]


class TestSaleSync(VendorCase):
	def test_accepted_sale_is_synced(self):
		self.client.get_response_data.return_value = ACCEPTED
		doc = invoice()
		self.sync(doc)
		self.assertEqual((doc.status, doc.vat_invoice_id), ("Synced", "V1"))

	def test_claim_is_committed_before_the_vendor_call(self):
		self.client.get_response_data.side_effect = (
			lambda *a, **k: frappe.db.commit.assert_called_once() or ACCEPTED
		)
		self.sync(invoice())

	def test_rejected_sale_fails(self):
		self.client.get_response_data.return_value = REJECTED
		self.client._fetch_invoice_details.return_value = None
		doc = invoice()
		self.sync(doc)
		self.assertEqual(doc.status, "Failed")
		self.assertFalse(doc.vat_invoice_id)

	def test_rejection_adopts_a_sale_the_vendor_already_has(self):
		self.client.get_response_data.return_value = REJECTED
		self.client._fetch_invoice_details.return_value = ON_FILE
		doc = invoice()
		self.sync(doc)
		self.assertEqual((doc.status, doc.vat_invoice_id), ("Synced", "V9"))

	def test_retry_asks_before_sending_again(self):
		self.client._fetch_invoice_details.return_value = ON_FILE
		doc = invoice(status="Failed")
		self.sync(doc)
		self.assertEqual(self.posted_sales(), [])
		self.assertEqual(doc.status, "Synced")

	def test_retry_sends_once_when_vendor_has_no_record(self):
		self.client.last_http_status = 404
		self.client._fetch_invoice_details.side_effect = frappe.ValidationError
		self.client.get_response_data.return_value = ACCEPTED
		doc = invoice(status="Failed")
		self.sync(doc)
		self.assertEqual(len(self.posted_sales()), 1)
		self.assertEqual(doc.status, "Synced")

	def test_retry_does_not_send_on_an_unclear_answer(self):
		self.client.last_http_status = 500
		self.client._fetch_invoice_details.side_effect = frappe.ValidationError
		doc = invoice(status="Failed")
		self.sync(doc)
		self.assertEqual(self.posted_sales(), [])
		self.assertEqual(doc.status, "Failed")

	def test_invoice_not_due_is_left_alone(self):
		doc = invoice(status="Synced")
		self.sync(doc)
		self.client.get_response_data.assert_not_called()
		self.assertEqual(doc.status, "Synced")


class TestReturnSync(VendorCase):
	def line(self, name, uom="Nos"):
		return frappe._dict(item_name=name, uom=uom, qty=-1, rate=100, amount=-100, discount_amount=0)

	def test_finished_return_is_not_posted_again(self):
		doc = invoice(vat_invoice_id="V1", is_return=1, return_response="{}")
		self.sync(doc)
		self.client.get_response_data.assert_not_called()

	@patch("vat_compliance.vschallan.source_invoice", return_value=frappe._dict())
	def test_rejected_return_can_be_retried(self, _source):
		self.client.get_response_data.return_value = {"status_code": 400}
		doc = invoice(return_payload=json.dumps({"return_request_details": []}))
		self.client.sync_return_vat_invoice(doc)
		self.assertEqual(doc.status, "Failed")
		self.assertFalse(doc.return_response)

	def test_return_line_matches_vendor_line_by_item(self):
		available = [
			{"product_name": "Tea", "id": 1, "vat_percentage": 15, "service_type_id": "S"},
			{"product_name": "Rice", "id": 2, "vat_percentage": 5, "service_type_id": "R"},
		]
		result = self.client._return_line(frappe._dict(), self.line("Rice"), available)
		self.assertEqual((result["product_id"], result["vat_percentage"]), (2, 5))

	def test_repeated_item_uses_each_vendor_line_once(self):
		available = [{"product_name": "Tea", "id": 1}, {"product_name": "Tea", "id": 2}]
		ids = [
			self.client._return_line(frappe._dict(), self.line("Tea"), available)["product_id"] for _ in "ab"
		]
		self.assertEqual(ids, [1, 2])

	def test_unmatched_return_line_is_an_error(self):
		with self.assertRaises(frappe.ValidationError):
			self.client._return_line(frappe._dict(), self.line("Rice"), [{"product_name": "Tea", "id": 1}])


class TestPosHook(unittest.TestCase):
	def applies(self, branch="BR-1", disabled=0, **values):
		doc = frappe._dict({"doctype": "POS Invoice", "pos_profile": "Till", **values})
		with patch.object(frappe, "db", MagicMock()) as db:
			db.get_single_value.return_value = disabled
			db.get_value.return_value = branch
			return hook._challan_applies(doc)

	def test_applies_to_a_pos_sale(self):
		self.assertTrue(self.applies())

	def test_skips_consolidated_invoice(self):
		self.assertFalse(self.applies(is_consolidated=1))

	def test_skips_sales_invoice_not_from_pos(self):
		self.assertFalse(self.applies(doctype="Sales Invoice", is_pos=0))

	def test_skips_without_retailer_branch(self):
		self.assertFalse(self.applies(branch=None))

	def test_skips_when_vendor_disabled(self):
		self.assertFalse(self.applies(disabled=1))

	@patch.object(hook, "VATSmartChallan")
	@patch.object(hook, "enqueue")
	@patch.object(hook, "_challan_applies", return_value=True)
	def test_return_reports_after_commit_without_calling_vendor(self, _applies, enqueue, client):
		with patch.object(frappe, "db", MagicMock()) as db:
			db.get_single_value.return_value = "After Submit"
			hook.create_vat_invoice(frappe._dict(name="R-1", is_return=1))
		self.assertTrue(enqueue.call_args.kwargs["enqueue_after_commit"])
		client.assert_not_called()

	def test_background_job_paths_resolve(self):
		for path in ("sync_vat_invoice_job", "sync_return_job", "auto_sync_vat_invoices"):
			self.assertTrue(callable(frappe.get_attr(f"vat_compliance.vschallan.{path}")))


class TestVendorSafety(unittest.TestCase):
	def client(self):
		return VATSmartChallan.__new__(VATSmartChallan)

	def test_site_files_cannot_be_sent(self):
		for path in (
			"site_config.json",
			"/site_config.json",
			"/files/../../site_config.json",
			"/private/files/../../site_config.json",
			"/private/backups/x.sql.gz",
		):
			with self.subTest(path), self.assertRaises(frappe.ValidationError):
				self.client().get_absolute_file_path(path)

	def test_xml_entities_are_refused(self):
		bomb = '<!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>'
		with self.assertRaises(Exception):
			self.client()._parse_xml(bomb)

	def test_vendor_url_must_be_https_on_vendor_host(self):
		check_base_url("https://api.dgepay.net/v1")
		for url in ("http://api.dgepay.net", "https://api.dgepay.net.evil.com", "https://evil.com", "", None):
			with self.subTest(url), self.assertRaises(frappe.ValidationError):
				check_base_url(url)


class TestSyncHealth(unittest.TestCase):
	def problems(self, config):
		with patch.object(frappe, "db", MagicMock()) as db:
			db.count.return_value = 0
			db.get_single_value.return_value = config.get("sync_schedule")
			db.get_singles_dict.return_value = config
			return sync_health._problems()

	def test_unused_integration_raises_no_alert(self):
		self.assertEqual(self.problems({}), [])

	def test_disabled_integration_raises_no_alert(self):
		self.assertEqual(self.problems({"base_url": "https://a.dgepay.net", "disabled": 1}), [])

	def test_blank_schedule_alerts_when_in_use(self):
		self.assertEqual(len(self.problems({"base_url": "https://a.dgepay.net"})), 1)
