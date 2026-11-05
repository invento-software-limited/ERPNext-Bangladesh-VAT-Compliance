# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""Encrypt the vendor token and owner NIDs stored in plain text by earlier versions."""

import frappe
from frappe.utils.password import set_encrypted_password


def execute():
	_encrypt_vendor_token()
	_encrypt_owner_nids()


def _encrypt_vendor_token():
	doctype = "POS Vendor Configuration"
	token = frappe.db.get_single_value(doctype, "access_token")
	if token and set(token) != {"*"}:
		set_encrypted_password(doctype, doctype, token, "access_token")
		frappe.db.set_single_value(doctype, "access_token", "*" * len(token))


def _encrypt_owner_nids():
	doctype = "Retailer Registration"
	for row in frappe.get_all(doctype, filters={"owner_nid": ["is", "set"]}, fields=["name", "owner_nid"]):
		if set(row.owner_nid) != {"*"}:
			set_encrypted_password(doctype, row.name, row.owner_nid, "owner_nid")
			frappe.db.set_value(
				doctype, row.name, "owner_nid", "*" * len(row.owner_nid), update_modified=False
			)
