# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""Vendor credentials go to base_url, so it must be HTTPS on a known vendor host."""

from urllib.parse import urlparse

import frappe
from frappe import _

VENDOR_HOST_SUFFIX = ".dgepay.net"


def check_base_url(base_url):
	parsed = urlparse(base_url or "")
	if parsed.scheme != "https" or not _is_allowed_host(parsed.hostname or ""):
		frappe.throw(_("The vendor Base URL must be HTTPS on an approved vendor host."))


def _is_allowed_host(host):
	# A new vendor host can be approved per site, without a code change.
	extra = frappe.conf.get("vat_challan_allowed_hosts") or []
	return host.endswith(VENDOR_HOST_SUFFIX) or host in extra
