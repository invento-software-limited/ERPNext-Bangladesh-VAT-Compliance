# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint
from frappe.utils.background_jobs import enqueue

from vat_compliance.vschallan import VATSmartChallan


def create_vat_invoice(doc, method=None):
	"""POS Invoice and POS Sales Invoice on_submit. Vendor calls run in a job after commit, so
	a slow or failing vendor cannot hold up or undo the sale."""
	if not _challan_applies(doc):
		return
	if not doc.is_return:
		VATSmartChallan().create_vat_invoice(doc)
	elif frappe.db.get_single_value("POS Vendor Configuration", "sync_schedule") == "After Submit":
		enqueue(
			"vat_compliance.vschallan.sync_return_job",
			invoice_name=doc.name,
			queue="long",
			enqueue_after_commit=True,
		)


def _challan_applies(doc):
	# A consolidated Sales Invoice merges POS Invoices that each have their own challan.
	if doc.get("is_consolidated") or not doc.get("pos_profile"):
		return False
	if doc.doctype == "Sales Invoice" and not doc.get("is_pos"):
		return False
	if cint(frappe.db.get_single_value("POS Vendor Configuration", "disabled")):
		return False
	return bool(frappe.db.get_value("POS Profile", doc.pos_profile, "custom_retailer_branch"))
