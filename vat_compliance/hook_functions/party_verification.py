# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""A party is Verified only by a real BIN/TIN check. The buttons set the status from the browser,
so the server accepts it only after the check succeeded here, and drops it when the number changes."""

import frappe
from frappe import _

VERIFIED = "Verified"
NOT_VERIFIED = "Not Verified"
PROOF_SECONDS = 60 * 60
CHECKS = {
	"Customer": (
		("bin", "custom_binvat_registration_no", "custom_bin_verification_status"),
		("tin", "custom_tin_no", "custom_tin_verification_status"),
	),
	"Supplier": (
		("bin", "custom_bin_no", "custom_bin_verification_status"),
		("tin", "custom_tin_no", "custom_tin_verification_status"),
	),
}


def remember_check(kind, number, response):
	"""Called with the government service's answer."""
	if str((response or {}).get("responseCode")) == "0":
		frappe.cache.set_value(_proof_key(kind, number), 1, expires_in_sec=PROOF_SECONDS)


def validate_verification(doc, method=None):
	"""Customer and Supplier validate."""
	before = doc.get_doc_before_save()
	for kind, number_field, status_field in CHECKS[doc.doctype]:
		if doc.get(status_field) != VERIFIED or _still_valid(doc, before, number_field, status_field):
			continue
		if not (doc.get(number_field) and frappe.cache.get_value(_proof_key(kind, doc.get(number_field)))):
			doc.set(status_field, NOT_VERIFIED)
			frappe.msgprint(
				_("{0} was set to Not Verified. Use its Verify button.").format(kind.upper()),
				indicator="orange",
				alert=True,
			)


def _still_valid(doc, before, number_field, status_field):
	return (
		bool(before)
		and before.get(status_field) == VERIFIED
		and before.get(number_field) == doc.get(number_field)
	)


def _proof_key(kind, number):
	return f"vat_compliance:{kind}_verified:{number}"
