# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

from vat_compliance.access import require_readable_file


def validate_mushak_63(doc, method=None):
	"""Attach fields are not sanitized on save, and this one can change on a submitted invoice.
	Only a real file is accepted, so it cannot carry script into the Supplier Mushak 6.3 report."""
	if doc.get("custom_mushak_63") and doc.has_value_changed("custom_mushak_63"):
		require_readable_file(doc.custom_mushak_63)
