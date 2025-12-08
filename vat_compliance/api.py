import re

import frappe
import requests


def _get_acs_session():
	"""
	Helper to get a session with CSRF token and cookies from achallan.gov.bd
	"""
	base_url = "https://www.achallan.gov.bd/acs/v2"
	csrf_url = f"{base_url}/general/challan-payment?id=2"

	session = requests.Session()
	session.headers.update(
		{
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
		}
	)

	proxy = "socks5://115.127.110.98:1080"
	session.proxies = {
		"http": proxy,
		"https": proxy,
	}

	response = session.get(csrf_url, timeout=30)
	response.raise_for_status()

	html_content = response.text
	match = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', html_content)

	if not match:
		frappe.throw("Failed to retrieve CSRF token from external service.")

	csrf_token = match.group(1)
	session.headers.update({"X-Xsrf-Token": csrf_token})

	return session


@frappe.whitelist()
def validate_bin(bin_no):
	"""
	Validate BIN number using the external API from achallan.gov.bd.
	"""
	validate_url = "https://www.achallan.gov.bd/acs/v2/api/remote/binValidate"

	try:
		session = _get_acs_session()

		params = {"binNo": bin_no}

		api_response = session.get(validate_url, params=params, timeout=10)
		api_response.raise_for_status()

		return api_response.json()

	except requests.exceptions.RequestException as e:
		frappe.log_error(f"BIN Validation Error: {e!s}", frappe.get_traceback())
		frappe.throw(f"Error connecting to validation service: {e!s}")
	except Exception as e:
		frappe.log_error(f"BIN Validation Error: {e!s}", frappe.get_traceback())
		frappe.throw(f"An unexpected error occurred: {e!s}")


@frappe.whitelist()
def validate_tin(tin_no):
	"""
	Validate TIN number using the external API from achallan.gov.bd.
	"""
	validate_url = "https://www.achallan.gov.bd/acs/v2/api/remote/tinValidate"

	try:
		session = _get_acs_session()

		params = {"tinNo": tin_no}

		api_response = session.get(validate_url, params=params, timeout=10)
		api_response.raise_for_status()

		return api_response.json()

	except requests.exceptions.RequestException as e:
		frappe.log_error(f"TIN Validation Error: {e!s}", frappe.get_traceback())
		frappe.throw(f"Error connecting to validation service: {e!s}")
	except Exception as e:
		frappe.log_error(f"TIN Validation Error: {e!s}", frappe.get_traceback())
		frappe.throw(f"An unexpected error occurred: {e!s}")
