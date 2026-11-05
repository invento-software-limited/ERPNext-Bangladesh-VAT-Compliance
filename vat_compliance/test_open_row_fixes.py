# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

import unittest
from unittest.mock import patch

import frappe

from vat_compliance import deposits, vat_rates
from vat_compliance.dashboard import vat_status
from vat_compliance.hook_functions import party_verification as party
from vat_compliance.vat_compliance.page.vat_payment import vat_payment
from vat_compliance.vat_compliance.report.mushak_6_3.mushak_6_3 import build_manifest
from vat_compliance.vat_compliance.report.vds_management import vds_management as vds

D = frappe._dict
VAT, OTHER = "VAT - T", "Other - T"


def group(rate):
	return {"account_credit": "Exp", "liability_head": VAT, "section_ref": f"T{rate}", "applied_rate": rate}


def state(docstatus, parent="JE-1"):
	return D(docstatus=docstatus, parent=parent)


class TestGroupStatus(unittest.TestCase):
	"""FM-20 and FM-23."""

	def test_paying_one_group_leaves_the_other_unpaid(self):
		groups = [group(15), group(5)]
		paid = {deposits.group_key("REF", groups[1]): state(1)}
		with patch.object(deposits, "journal_states", return_value=paid):
			deposits.mark_vds_groups("REF", groups)
		self.assertEqual([g["status"] for g in groups], ["DNGT", "DDGT"])

	def test_old_entry_covers_only_the_first_group(self):
		groups = [group(15), group(5)]
		with patch.object(deposits, "journal_states", return_value={"REF": state(1)}):
			deposits.mark_vds_groups("REF", groups)
		self.assertEqual([g["status"] for g in groups], ["DDGT", "DNGT"])

	def test_draft_entry_is_not_a_deposit(self):
		groups = [group(15)]
		with patch.object(
			deposits, "journal_states", return_value={deposits.group_key("REF", groups[0]): state(0)}
		):
			deposits.mark_vds_groups("REF", groups)
		self.assertEqual(groups[0]["status"], "DNGT")

	def test_sales_payment_needs_every_account_deposited(self):
		heads = {VAT: 1, OTHER: 1}
		one = {deposits.line_key("REF", VAT): state(1)}
		with patch.object(deposits, "journal_states", return_value=one):
			self.assertFalse(deposits.sales_deposited("REF", heads))
		both = {deposits.line_key("REF", h): state(1) for h in heads}
		with patch.object(deposits, "journal_states", return_value=both):
			self.assertTrue(deposits.sales_deposited("REF", heads))

	def test_child_group_reaches_the_page_with_its_payment_details(self):
		rows = [
			D(
				status="DDGT",
				invoice_id="PI-1",
				payment_date="2026-01-01",
				payment_entry_id="PE-1",
				vds_amount=15,
			),
			D(status="DNGT", indent=1, invoice_id="", payment_entry_id="", vds_amount=5, supplier_name="S"),
		]
		data = vat_payment._withheld_vds(rows)
		self.assertEqual(len(data), 1)
		self.assertEqual(
			(data[0].invoice_id, data[0].payment_entry_id, data[0].party_name), ("PI-1", "PE-1", "S")
		)

	def test_multi_rate_payment_splits_into_rows_with_their_own_status(self):
		invoice = D(
			company="T",
			grand_total=120,
			items=[
				D(
					net_amount=100,
					expense_account="Exp",
					item_tax_template="T15",
					item_tax_rate=frappe.as_json({VAT: 15}),
				),
				D(
					net_amount=100,
					expense_account="Exp",
					item_tax_template="T5",
					item_tax_rate=frappe.as_json({VAT: 5}),
				),
			],
		)
		row = D(invoice_id="PI-1", child_name="REF", vds_amount=120, supplier_name="S")
		second = deposits.vds_groups(invoice, 120)[1]
		paid = {deposits.group_key("REF", second): state(1)}
		with patch.object(deposits, "journal_states", return_value=paid):
			rows = vds._process_data_row(row, {"PI-1": invoice})
		self.assertEqual(
			[(r.get("indent", 0), r["status"], r["vds_amount"]) for r in rows],
			[(0, "DNGT", 15), (1, "DDGT", 5)],
		)
		self.assertEqual(rows[1]["deposit_key"], deposits.group_key("REF", second))

	def test_status_filter_keeps_a_payment_with_a_matching_group(self):
		rows = [D(status="DDGT", indent=0), D(status="DNGT", indent=1)]
		self.assertEqual(len(vds._filter_by_status(rows, "DNGT")), 2)
		self.assertEqual(vds._filter_by_status(rows, "Other"), [])


class TestDepositEntry(unittest.TestCase):
	"""FM-57 and the make_journal_entry finding: browser values are ignored."""

	def setUp(self):
		self.ref = D(name="REF", reference_name="PI-1", company="Co")
		self.lines = [
			D(key="REF:a", account=VAT, amount=15.0, first=True),
			D(key="REF:b", account=OTHER, amount=5.0, first=False),
		]
		patcher = patch.object(deposits, "payment_lines", return_value=self.lines)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_amount_and_account_come_from_the_invoice(self):
		with patch.object(deposits, "journal_states", return_value={}):
			rows = deposits._journal_rows(deposits._selected_lines(self.ref, "REF:a"))
		self.assertEqual(
			rows,
			[
				{
					"account": VAT,
					"debit_in_account_currency": 15.0,
					"reference_detail_no": "REF:a",
					"custom_tax_type": "VAT",
				}
			],
		)

	def test_unknown_line_is_refused(self):
		with (
			patch.object(deposits, "journal_states", return_value={}),
			self.assertRaises(frappe.ValidationError),
		):
			deposits._selected_lines(self.ref, "REF:forged")

	def test_line_in_a_draft_entry_is_refused(self):
		with (
			patch.object(deposits, "journal_states", return_value={"REF:a": state(0)}),
			self.assertRaises(frappe.ValidationError),
		):
			deposits._selected_lines(self.ref, "REF:a")

	def test_old_entry_blocks_only_the_first_line(self):
		with patch.object(deposits, "journal_states", return_value={"REF": state(1)}):
			self.assertEqual(len(deposits._selected_lines(self.ref, "REF:b")), 1)
			with self.assertRaises(frappe.ValidationError):
				deposits._selected_lines(self.ref, "REF:a")

	def test_rows_from_two_companies_are_refused(self):
		refs = {"A": D(self.ref, company="One"), "B": D(self.ref, company="Two")}
		with (
			patch.object(frappe, "has_permission", return_value=True),
			patch.object(deposits, "_payment_reference", side_effect=refs.get),
			patch.object(deposits, "journal_states", return_value={}),
			self.assertRaises(frappe.ValidationError),
		):
			deposits.make_deposit_entry([{"child_name": "A"}, {"child_name": "B"}])

	def test_credit_note_line_is_a_credit(self):
		rows = deposits._journal_rows([D(key="k", account=VAT, amount=-5.0)])
		self.assertEqual(rows[0]["credit_in_account_currency"], 5.0)


class TestCompanyCurrency(unittest.TestCase):
	"""FM-66."""

	def test_line_net_prefers_company_currency(self):
		self.assertEqual(vat_rates.line_net({"net_amount": 100, "base_net_amount": 12000}), 12000)
		self.assertEqual(vat_rates.line_net({"net_amount": 100}), 100)

	def test_ratio_uses_company_total_when_the_party_account_is_in_company_currency(self):
		invoice = D(currency="USD", party_account_currency="BDT", grand_total=100, base_grand_total=12000)
		self.assertAlmostEqual(vat_rates.payment_ratio(invoice, 6000), 0.5)

	def test_ratio_uses_invoice_total_when_the_party_pays_in_that_currency(self):
		invoice = D(currency="USD", party_account_currency="USD", grand_total=100, base_grand_total=12000)
		self.assertAlmostEqual(vat_rates.payment_ratio(invoice, 50), 0.5)


class TestStoredRates(unittest.TestCase):
	"""FM-44."""

	def test_saved_rate_wins_over_the_current_template(self):
		with patch.object(frappe.db, "get_value") as template:
			self.assertEqual(vat_rates.stored_rate("T15", frappe.as_json({VAT: 15}), "T"), 15)
		template.assert_not_called()


class TestInvoiceVat(unittest.TestCase):
	"""FM-31."""

	def run_with(self, accounts, taxes, **row):
		row = D(name="I-1", company="T", **row)
		with (
			patch.object(vat_rates, "vat_accounts", return_value=accounts),
			patch.object(vat_rates.frappe, "get_all", return_value=taxes),
		):
			vat_rates.add_invoice_vat("Purchase Invoice", [row])
		return row

	def tax(self, account, amount, kind="Add"):
		return D(
			parent="I-1",
			account_head=account,
			tax_amount_after_discount_amount=amount,
			base_tax_amount_after_discount_amount=amount * 2,
			add_deduct_tax=kind,
		)

	def test_freight_is_not_vat(self):
		row = self.run_with([VAT], [self.tax(VAT, 15), self.tax(OTHER, 50)], total_taxes_and_charges=65)
		self.assertEqual((row.vat_amount, row.base_vat_amount), (15, 30))

	def test_deducted_vat_reduces_the_total(self):
		self.assertEqual(self.run_with([VAT], [self.tax(VAT, 15), self.tax(VAT, 5, "Deduct")]).vat_amount, 10)

	def test_company_without_a_vat_account_keeps_the_tax_total(self):
		row = self.run_with([], [], total_taxes_and_charges=65, base_total_taxes_and_charges=130)
		self.assertEqual((row.vat_amount, row.base_vat_amount), (65, 130))


class TestFailedReport(unittest.TestCase):
	"""FM-69."""

	def test_failed_report_is_not_zero(self):
		failed = []
		with (
			patch.object(vat_status, "_execute", return_value=lambda f: 1 / 0),
			patch.object(vat_status.frappe, "log_error"),
		):
			self.assertIsNone(vat_status._by_status("R", {}, ("DNGT",), failed))
		self.assertEqual(failed, ["R"])

	def test_child_group_counts_under_its_own_status(self):
		rows = [D(status="DDGT", vds_amount=15), D(status="DNGT", indent=1, vds_amount=5)]
		with patch.object(vat_status, "_execute", return_value=lambda f: ([], rows)):
			out = vat_status._by_status("R", {}, ("DNGT", "DDGT"), [])
		self.assertEqual(out, {"DDGT": {"count": 1, "amount": 15}, "DNGT": {"count": 1, "amount": 5}})


class TestPartyVerification(unittest.TestCase):
	"""FM-30."""

	def customer(self, before=None, **values):
		doc = frappe.get_doc({"doctype": "Customer", "custom_binvat_registration_no": "111", **values})
		doc.get_doc_before_save = lambda: before
		return doc

	def validate(self, doc):
		with patch.object(party.frappe, "msgprint"):
			party.validate_verification(doc)
		return doc.custom_bin_verification_status

	def setUp(self):
		frappe.cache.delete_value(party._proof_key("bin", "111"))
		self.addCleanup(frappe.cache.delete_value, party._proof_key("bin", "111"))

	def test_status_set_by_hand_is_dropped(self):
		self.assertEqual(
			self.validate(self.customer(custom_bin_verification_status="Verified")), "Not Verified"
		)

	def test_status_after_a_real_check_is_kept(self):
		party.remember_check("bin", "111", {"responseCode": "0"})
		self.assertEqual(self.validate(self.customer(custom_bin_verification_status="Verified")), "Verified")

	def test_failed_check_is_not_proof(self):
		party.remember_check("bin", "111", {"responseCode": "1"})
		self.assertEqual(
			self.validate(self.customer(custom_bin_verification_status="Verified")), "Not Verified"
		)

	def test_changing_the_number_drops_the_status(self):
		before = D(custom_binvat_registration_no="999", custom_bin_verification_status="Verified")
		self.assertEqual(
			self.validate(self.customer(before, custom_bin_verification_status="Verified")), "Not Verified"
		)

	def test_unchanged_verified_party_saves_as_is(self):
		before = D(custom_binvat_registration_no="111", custom_bin_verification_status="Verified")
		self.assertEqual(
			self.validate(self.customer(before, custom_bin_verification_status="Verified")), "Verified"
		)


class TestManifest(unittest.TestCase):
	"""FM-58."""

	def test_failed_invoices_are_named(self):
		text = build_manifest(["A"], ["B"])
		self.assertIn("Failed: 1", text)
		self.assertIn("FAILED, NOT IN THIS ZIP:\nB", text)

	def test_complete_set_has_no_failed_section(self):
		self.assertNotIn("FAILED", build_manifest(["A"], []))
