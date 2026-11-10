import re

import frappe
import requests
from frappe import _
from frappe.rate_limiter import rate_limit

from vat_compliance.hook_functions.party_verification import remember_check

BASE_URL = "https://www.achallan.gov.bd/acs/v2"
# Protects the government service from one user or a loop; the buttons are clicked by hand.
VALIDATION_LIMIT_PER_MINUTE = 30


def _require_party_write():
	if not (frappe.has_permission("Customer", "write") or frappe.has_permission("Supplier", "write")):
		frappe.throw(_("You do not have access to verify BIN or TIN."), frappe.PermissionError)


def _get_acs_session():
	"""
	Helper to get a session with CSRF token and cookies from achallan.gov.bd
	"""

	csrf_url = f"{BASE_URL}/general/challan-payment?id=2"

	session = requests.Session()
	session.headers.update(
		{
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
		}
	)
	settings = frappe.get_single("Compliance Settings")
	if getattr(settings, "enable_proxy", None):
		proxy = getattr(settings, "upstream_proxy", None)
		if proxy:
			session.proxies = {
				"http": proxy,
				"https": proxy,
			}

	timeout = getattr(settings, "request_timeout", 30) or 30
	response = session.get(csrf_url, timeout=timeout)
	response.raise_for_status()

	html_content = response.text
	match = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', html_content)

	if not match:
		frappe.throw(_("Failed to retrieve CSRF token from external service."))

	csrf_token = match.group(1)
	session.headers.update({"X-Xsrf-Token": csrf_token})

	return session


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=VALIDATION_LIMIT_PER_MINUTE, seconds=60)
def validate_bin(bin_no: str):
	"""
	Validate BIN number using the external API from achallan.gov.bd.
	"""
	_require_party_write()
	validate_url = f"{BASE_URL}/api/remote/binValidate"

	try:
		session = _get_acs_session()
		settings = frappe.get_single("Compliance Settings")
		timeout = getattr(settings, "request_timeout", 30) or 30

		params = {"binNo": bin_no}

		api_response = session.get(validate_url, params=params, timeout=timeout)
		api_response.raise_for_status()

		result = api_response.json()
		remember_check("bin", bin_no, result)
		return result

	except requests.exceptions.RequestException as e:
		frappe.log_error(f"BIN Validation Error: {e!s}", frappe.get_traceback())
		frappe.throw(f"Error connecting to validation service: {e!s}")
	except Exception as e:
		frappe.log_error(f"BIN Validation Error: {e!s}", frappe.get_traceback())
		frappe.throw(f"An unexpected error occurred: {e!s}")


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=VALIDATION_LIMIT_PER_MINUTE, seconds=60)
def validate_tin(tin_no: str):
	"""
	Validate TIN number using the external API from achallan.gov.bd.
	"""
	_require_party_write()
	validate_url = f"{BASE_URL}/api/remote/tinValidate"

	try:
		session = _get_acs_session()
		settings = frappe.get_single("Compliance Settings")
		timeout = getattr(settings, "request_timeout", 30) or 30

		params = {"tinNo": tin_no}

		api_response = session.get(validate_url, params=params, timeout=timeout)
		api_response.raise_for_status()

		result = api_response.json()
		remember_check("tin", tin_no, result)
		return result

	except requests.exceptions.RequestException as e:
		frappe.log_error(f"TIN Validation Error: {e!s}", frappe.get_traceback())
		frappe.throw(f"Error connecting to validation service: {e!s}")
	except Exception as e:
		frappe.log_error(f"TIN Validation Error: {e!s}", frappe.get_traceback())
		frappe.throw(f"An unexpected error occurred: {e!s}")
