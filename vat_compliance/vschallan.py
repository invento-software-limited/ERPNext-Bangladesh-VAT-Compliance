import json
import mimetypes
import os
from datetime import datetime
from urllib.parse import urlencode

import defusedxml.ElementTree as ET
import frappe
import requests
import xmltodict
from defusedxml.common import DefusedXmlException
from frappe import _
from frappe.utils import add_days, add_to_date, cint, date_diff, flt, getdate, now_datetime, nowdate
from frappe.utils.background_jobs import enqueue
from frappe.utils.password import get_decrypted_password, set_encrypted_password
from requests.auth import HTTPBasicAuth

from vat_compliance.vat_challan.challan_lines import invoice_timestamp, line_amounts, service_fields
from vat_compliance.vat_challan.sync_health import report_sync_health
from vat_compliance.vat_challan.vendor_url import check_base_url

SYNCABLE_STATUSES = ("Pending", "Failed")
STALE_SYNC_HOURS = 1
RETURN_LOOKBACK_DAYS = 90
RETURN_DOCTYPES = {"POS Invoice": {}, "Sales Invoice": {"is_pos": 1}}
# Assumed to mean "no such invoice" on the details endpoint; to confirm with the vendor.
VENDOR_NOT_FOUND_STATUSES = (400, 404)
MAX_XML_RESPONSE_CHARS = 5_000_000


class VATSmartChallan:
	"""
	Service client for integrating with the VAT Smart Challan API.

	This class:
	- Reads API configuration from the "POS Vendor Configuration" doctype.
	- Manages access tokens (retrieve, cache, and refresh on expiry/401).
	- Calls API endpoints to fetch master data (zones, divisions, circles, VAT commission rates,
	  and retailer service types).
	- Persists responses into respective Frappe doctypes while preventing duplicates.
	"""

	def __init__(self):
		"""
		Initialize the client using configuration stored in POS Vendor Configuration (Single Doctype).

		Loads and validates configuration, decrypts secrets, sets up token and cache directory.

		Raises:
			frappe.ValidationError: If configuration is missing or disabled.
		"""
		config_data = frappe.db.get_singles_dict("POS Vendor Configuration")

		if not config_data:
			frappe.throw(_("No POS Vendor Configuration found"))

		if cint(config_data.get("disabled")):
			frappe.throw(_("POS Vendor Configuration is disabled"))

		self.docname = "POS Vendor Configuration"
		self.base_url = config_data.get("base_url")
		self.client_id = config_data.get("client_id")
		self.access_token = self._stored_token(config_data.get("access_token"))
		self.last_http_status = None
		self.expiry_date = config_data.get("expiry_date")
		self.company_id = config_data.get("company_id")
		# A missing secret fails at send time, where it leaves a Failed invoice to retry.
		self.client_secret = get_decrypted_password(
			"POS Vendor Configuration", self.docname, "client_secret", raise_exception=False
		)
		self.sync_schedule = config_data.get("sync_schedule")

	def _stored_token(self, value):
		"""Tokens are encrypted; a value that is not masked predates that and is still usable."""
		if value and set(value) != {"*"}:
			return value
		return get_decrypted_password(self.docname, self.docname, "access_token", raise_exception=False)

	def get_access_token(self, force_refresh=False):
		"""
		Get a valid access token, refreshing if needed.
		Handles both XML and JSON responses from the API.

		Args:
			force_refresh (bool): If True, forces a fresh token request regardless of current state.

		Returns:
			dict: {
				"access_token": str,
				"expiry_date": str | None (format: "%Y-%m-%d %H:%M:%S"),
				"company_id": str | None
			}

		Raises:
			frappe.ValidationError: If token retrieval fails or response parsing fails.
		"""
		# Return cached token if valid
		if self.access_token and not force_refresh and self.expiry_date:
			try:
				expiry_datetime = datetime.strptime(self.expiry_date, "%Y-%m-%d %H:%M:%S")
				if expiry_datetime > datetime.now():
					return {
						"access_token": self.access_token,
						"expiry_date": self.expiry_date,
						"company_id": self.company_id,
					}
			except (ValueError, TypeError):
				pass

		check_base_url(self.base_url)
		url = f"{self.base_url}/integration/vendor_authenticate"
		headers = {"Content-Type": "application/json"}

		try:
			response = requests.post(
				url, headers=headers, auth=HTTPBasicAuth(self.client_id, self.client_secret), timeout=30
			)
			response.raise_for_status()
			raw_content = response.text.strip()

			# Detect response format
			if raw_content.startswith("{") or raw_content.startswith("["):
				# JSON response
				try:
					data = json.loads(raw_content)
					self.access_token = data.get("access_token")
					self.expiry_date = data.get("expiry_time")
					self.company_id = data.get("company_id")
				except ValueError:
					frappe.log_error(raw_content, "Vendor token response")
					frappe.throw(_("Could not read the vendor's token response."))
			else:
				# XML response
				try:
					root = self._parse_xml(raw_content)
					access_token_elem = root.find(".//access_token")
					expiry_time_elem = root.find(".//expiry_time")
					company_id_elem = root.find(".//company_id")

					if access_token_elem is None:
						frappe.log_error(raw_content, "Vendor token response")
						frappe.throw(_("Could not read the vendor's token response."))

					self.access_token = access_token_elem.text
					self.expiry_date = expiry_time_elem.text if expiry_time_elem is not None else None
					self.company_id = company_id_elem.text if company_id_elem is not None else None

				except (ET.ParseError, DefusedXmlException):
					frappe.log_error(raw_content, "Vendor token response")
					frappe.throw(_("Could not read the vendor's token response."))

			# Save to Single Doc
			# set_single_value alone would bypass the Password field's encryption.
			set_encrypted_password(self.docname, self.docname, self.access_token, "access_token")
			frappe.db.set_single_value(
				"POS Vendor Configuration", "access_token", "*" * len(self.access_token or "")
			)
			frappe.db.set_single_value("POS Vendor Configuration", "expiry_date", self.expiry_date)
			frappe.db.set_single_value("POS Vendor Configuration", "company_id", self.company_id)

			return {
				"access_token": self.access_token,
				"expiry_date": self.expiry_date,
				"company_id": self.company_id,
			}

		except requests.exceptions.RequestException as e:
			frappe.log_error(str(e), "Vendor authentication failed")
			frappe.throw(_("Could not authenticate with the VAT challan vendor."))

	def get_header(self):
		"""
		Build request headers for authenticated API calls.

		Returns:
			dict: Headers including Authorization, companyID and Content-Type.
		"""
		return {
			"Authorization": f"Token {self.access_token}",
			"companyID": self.company_id,
			"Content-Type": "application/json",
		}

	def get_zone(self):
		"""
		Fetch and upsert zones from the API.

		Behavior:
			- Calls /integration/zone.
			- Refreshes token and retries on 401.
			- Uses common parser to handle XML/JSON.
			- Inserts missing records into "VC Zone" by unique zone_id.
		"""
		url = f"{self.base_url}/integration/zone"
		parsed_data = self.get_response_data(url, "GET")

		zones = []
		if isinstance(parsed_data, dict):
			data = parsed_data.get("data") or parsed_data
			zone_data = data.get("zone")
			if isinstance(zone_data, list):
				zones = zone_data
			elif isinstance(zone_data, dict):
				zones = [zone_data]

		for z in zones:
			zone_id = z.get("id")
			zone_name = z.get("name")

			if zone_id and zone_name:
				if not frappe.db.exists("VC Zone", {"zone_id": zone_id}):
					doc = frappe.get_doc({"doctype": "VC Zone", "zone_id": zone_id, "zone_name": zone_name})
					doc.insert(ignore_permissions=True)

	def get_vat_commission_rate(self):
		"""
		Fetch and upsert VAT commission rates from the API.

		Behavior:
			- Calls /integration/vat_commissionrate.
			- Uses common parser (XML/JSON).
			- Inserts missing "VC VAT Commission Rate" records by vat_commission_rate_id.
			- Links each rate to its "VC Zone" using zone_id.
		"""
		url = f"{self.base_url}/integration/vat_commissionrate"
		parsed_data = self.get_response_data(url, "GET")

		rates = []
		if isinstance(parsed_data, dict):
			data = parsed_data.get("data") or parsed_data
			rate_data = data.get("vat_commissionrate")
			if isinstance(rate_data, list):
				rates = rate_data
			elif isinstance(rate_data, dict):
				rates = [rate_data]

		for r in rates:
			rate_id = r.get("id")
			name = r.get("name")
			zone_id_elem = r.get("zone_id")

			if rate_id and name and zone_id_elem:
				if not frappe.db.exists("VC VAT Commission Rate", {"vat_commission_rate_id": rate_id}):
					zone_doc = frappe.get_value("VC Zone", {"zone_id": zone_id_elem}, "name")

					doc = frappe.get_doc(
						{
							"doctype": "VC VAT Commission Rate",
							"vat_commission_rate_id": rate_id,
							"vat_commission_rate_name": name,
							"zone": zone_doc,
						}
					)
					doc.insert(ignore_permissions=True)

	def get_division(self):
		"""
		Fetch divisions from API and save them in VC Division doctype.
		Avoid duplicates based on division ID.
		Link each division to VC Zone and VC VAT Commission Rate.
		"""
		url = f"{self.base_url}/integration/division"
		parsed_data = self.get_response_data(url, "GET")

		divisions = []
		if isinstance(parsed_data, dict):
			data = parsed_data.get("data") or parsed_data
			div_data = data.get("division")
			if isinstance(div_data, list):
				divisions = div_data
			elif isinstance(div_data, dict):
				divisions = [div_data]

		for d in divisions:
			div_id = d.get("id")
			name = d.get("name")
			zone_id = d.get("zone_id")
			vat_commissionrate_id_elem = d.get("vat_commissionrate_id")

			if div_id and name and zone_id and vat_commissionrate_id_elem:
				if not frappe.db.exists("VC Division", {"division_id": div_id}):
					zone_doc = frappe.get_value("VC Zone", {"zone_id": zone_id}, "name")
					vat_rate_doc = frappe.get_value(
						"VC VAT Commission Rate",
						{"vat_commission_rate_id": vat_commissionrate_id_elem},
						"name",
					)

					doc = frappe.get_doc(
						{
							"doctype": "VC Division",
							"division_id": div_id,
							"division_name": name,
							"zone": zone_doc,
							"vat_commission_rate": vat_rate_doc,
						}
					)
					doc.insert(ignore_permissions=True)

	def get_circle(self):
		"""
		Fetch circles from API and save them in VC Circle doctype.
		Avoid duplicates based on circle ID.
		Link each circle to VC Division, VC Zone, and VC VAT Commission Rate.
		"""
		url = f"{self.base_url}/integration/circle"
		parsed_data = self.get_response_data(url, "GET")

		circles = []
		if isinstance(parsed_data, dict):
			data = parsed_data.get("data")
			if data:
				circle_data = data.get("circle")
				if isinstance(circle_data, list):
					circles = circle_data
				elif isinstance(circle_data, dict):
					circles = [circle_data]

		for c in circles:
			circle_id = c.get("id")
			name = c.get("name")
			zone_id = c.get("zone_id")
			vat_commissionrate_id = c.get("vat_commissionrate_id")
			division_id_elem = c.get("division_id")

			if not (circle_id and name and division_id_elem):
				continue  # skip invalid record

			# Skip if already exists
			if frappe.db.exists("VC Circle", {"circle_id": circle_id}):
				continue

			division_doc = frappe.get_value("VC Division", {"division_id": division_id_elem}, "name")
			zone_doc = frappe.get_value("VC Zone", {"zone_id": zone_id}, "name")
			vat_rate_doc = frappe.get_value(
				"VC VAT Commission Rate", {"vat_commission_rate_id": vat_commissionrate_id}, "name"
			)

			doc = frappe.get_doc(
				{
					"doctype": "VC Circle",
					"circle_id": circle_id,
					"circle_name": name,
					"division": division_doc,
					"zone": zone_doc,
					"vat_commission_rate": vat_rate_doc,
				}
			)
			doc.insert(ignore_permissions=True)

	def get_service_types(self):
		"""
		Fetch Retailer Service Types from API and save them in VC Service Type doctype.
		Avoid duplicates based on service_id.
		"""
		url = f"{self.base_url}/integration/retailer_service_type"
		parsed_data = self.get_response_data(url, "GET")

		services = []
		if isinstance(parsed_data, dict):
			# Handle {"data": {"retailer_service_types": [...]}}
			data = parsed_data.get("data")
			if data:
				service_data = data.get("retailer_service_types")
				if isinstance(service_data, list):
					services = service_data
				elif isinstance(service_data, dict):
					services = [service_data]

		for service in services:
			service_id = service.get("id")
			heading_code = service.get("heading_code")
			service_code = service.get("service_code")
			service_name = service.get("service_name")
			vat_rate = service.get("vat_rate")

			if not (service_id and service_name):
				continue  # skip invalid

			# Check if service already exists
			exists = frappe.db.exists("VC Service Type", {"service_id": service_id})
			if exists:
				continue

			doc = frappe.get_doc(
				{
					"doctype": "VC Service Type",
					"service_id": service_id,
					"heading_code": heading_code,
					"service_code": service_code,
					"service_name": service_name,
					"vat_rate": vat_rate,
				}
			)
			doc.insert(ignore_permissions=True)

	def register_retailer(self, doc):
		"""
		Register a retailer via external API using RetailerRegistration doc fields.
		Handles both XML and JSON responses.
		"""
		url = f"{self.base_url}/integration/retail_registration"

		type_of_business_list = []
		if hasattr(doc, "service_types") and doc.service_types:
			for row in doc.service_types:
				if row.type_id:
					type_of_business_list.append(row.type_id)

		business_logo_url = None
		if doc.business_logo:
			business_logo_url = frappe.utils.get_url(doc.business_logo)

		# Prepare payload
		payload = {
			"owner_full_name": doc.owner_full_name,
			"owner_cc": doc.owner_cc,
			"owner_mobile": doc.owner_mobile,
			"owner_email": doc.owner_email,
			"owner_nid": doc.get_password("owner_nid", raise_exception=False),
			"business_name": doc.business_name,
			"business_address": doc.address_display,
			"business_logo": business_logo_url,
			"business_website": doc.business_website,
			"business_ecom": doc.business_ecom,
			"business_app": doc.business_app,
			"bin": doc.bin,
			"trade_license_number": doc.trade_license_number,
			"tin": doc.tin,
			"type_of_business_list": type_of_business_list,
			"zone_id": doc.zone_id,
			"vat_commissionrate_id": doc.vat_commissionrate_id,
			"division_id": doc.division_id,
			"circle_id": doc.circle_id,
		}

		try:
			parsed_data = self.get_response_data(url, "POST", payload)
			doc.db_set("server_response", json.dumps(parsed_data, indent=2))
			status_code = str(parsed_data.get("status_code"))
			success = parsed_data.get("success")
			error_msg = parsed_data.get("error")
			data_elem = parsed_data.get("data")

			if status_code == "200" and data_elem:
				message = data_elem.get("message")
				retailer_id = data_elem.get("retailer_id")
				retailer_number = data_elem.get("retailer_number")

				if retailer_id and retailer_number:
					doc.db_set("status_code", status_code)
					doc.db_set("retailer_id", retailer_id)
					frappe.msgprint(f"Retailer registered successfully: {retailer_number}")

				else:
					retailer_details = data_elem.get("retailer_details")
					if retailer_details:
						existing_id = retailer_details.get("retailer_id")
						existing_number = retailer_details.get("retailer_number")
						doc.db_set("status_code", status_code)
						doc.db_set("retailer_id", existing_id)

						frappe.msgprint(f"Retailer already exists ({message}): {existing_number}")
					else:
						frappe.throw(f"Retailer registration failed: {message or 'Unknown error'}")

			elif success == "0":
				frappe.throw(f"Retailer registration failed: {error_msg or 'Unknown error'}")

			else:
				frappe.throw(_("Unexpected response format from API"))

		except requests.exceptions.HTTPError as e:
			frappe.throw(f"HTTP Error: {e!s}")
		except requests.exceptions.RequestException as e:
			frappe.throw(f"Request Error: {e!s}")

	def retailer_branch_registration(self, doc):
		url = f"{self.base_url}/integration/retailer_branch_registration"

		payload = {
			"retailer_id": doc.retailer_id,
			"branch_name": doc.branch_name,
			"branch_address": doc.address_display,
			"branch_type": 1 if doc.branch_type == "Main Branch" else 2,
			"zone_id": doc.zone_id,
			"vat_commissionrate_id": doc.vat_commissionrate_id,
			"division_id": doc.division_id,
			"circle_id": doc.circle_id,
			"branch_phone_number": doc.branch_phone_number,
			"branch_dial_code": doc.branch_dial_code,
		}

		try:
			parsed_data = self.get_response_data(url, "POST", payload)
			doc.db_set("server_response", json.dumps(parsed_data, indent=2))
			status_code = str(parsed_data.get("status_code"))
			data_elem = parsed_data.get("data")
			success = parsed_data.get("success")
			error_msg = parsed_data.get("error")

			if status_code == "200" and data_elem:
				branch_id = data_elem.get("branch_id")
				branch_number = data_elem.get("branch_number")

				if branch_id and branch_number:
					doc.db_set("branch_id", branch_id)
					doc.db_set("branch_number", branch_number)
					frappe.msgprint(f"Retailer Branch registered successfully: {branch_number}")

			elif success == "0":
				frappe.throw(f"Retailer registration failed: {error_msg or 'Unknown error'}")

		except requests.exceptions.HTTPError as e:
			frappe.throw(f"HTTP Error: {e!s}")
		except requests.exceptions.RequestException as e:
			frappe.throw(f"Request Error: {e!s}")

	def parse_xml_to_json(self, xml_string):
		"""
		Convert XML string to JSON dict
		"""
		try:
			return xmltodict.parse(xml_string)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Failed to convert XML to JSON")
			frappe.throw(_("Failed to convert XML to JSON"))

	def detect_response_format(self, response_text: str) -> str:
		"""
		Detects if a response string is in XML or JSON format.

		Returns:
			"json" if JSON,
			"xml" if XML,
			"unknown" if neither.
		"""
		response_text = response_text.strip()

		# Try JSON
		try:
			json.loads(response_text)
			return "json"
		except (json.JSONDecodeError, TypeError):
			pass

		# Try XML
		try:
			self._parse_xml(response_text)
			return "xml"
		except (ET.ParseError, DefusedXmlException):
			pass

		return "unknown"

	def _parse_xml(self, text):
		"""Vendor XML is untrusted: defusedxml refuses entity tricks, the cap bounds memory."""
		if len(text) > MAX_XML_RESPONSE_CHARS:
			raise DefusedXmlException("Response too large")
		return ET.fromstring(text)

	def get_response_data(
		self, url: str, request_type: str, payload: dict | None = None, files: dict | None = None
	):
		"""
		Perform an authenticated HTTP request and return parsed response data.

		Behavior:
		- Sends GET or POST requests with Authorization headers.
		- Automatically refreshes the access token and retries once on HTTP 401.
		- Detects response format (XML/JSON) and returns a parsed Python dict.
		  For XML responses, the "ObjectNode" element is extracted after conversion.
		- Supports file uploads via multipart/form-data if `files` is provided.

		Args:
			url (str): The API endpoint URL.
			request_type (str): "GET" or "POST".
			payload (dict, optional): JSON-serializable body for POST requests.
			files (dict, optional): Dictionary of files for multipart upload, e.g. {"file": open("path", "rb")}.

		Returns:
			dict | list | None: Parsed response content. For XML, the value of "ObjectNode".
								For JSON, the decoded JSON structure.

		Raises:
			frappe.ValidationError: If request_type is invalid or if response format is unknown.
			requests.exceptions.RequestException: For network/HTTP errors (after retry logic).
		"""
		check_base_url(self.base_url)
		headers = self.get_header().copy()
		if request_type == "POST" and files:
			headers.pop("Content-Type", None)

		try:
			# Determine request method
			if request_type == "GET":
				response = requests.get(url, headers=headers, timeout=30)
			elif request_type == "POST":
				if files:
					response = requests.post(url, headers=headers, data=payload, files=files, timeout=30)
				else:
					response = requests.post(url, headers=headers, json=payload, timeout=30)
			else:
				frappe.throw(_("Invalid request type"))

			# Retry if unauthorized
			if response.status_code == 401:
				self.get_access_token(force_refresh=True)
				headers = self.get_header()
				if request_type == "GET":
					response = requests.get(url, headers=headers, timeout=30)
				elif request_type == "POST":
					if files:
						response = requests.post(url, headers=headers, data=payload, files=files, timeout=30)
					else:
						response = requests.post(url, headers=headers, json=payload, timeout=30)

			self.last_http_status = response.status_code
			response.raise_for_status()
			raw_content = response.text
			format_type = self.detect_response_format(raw_content)

			# Parse response
			if format_type == "xml":
				converted_data = self.parse_xml_to_json(raw_content)
				parsed_data = converted_data.get("ObjectNode", converted_data)
			elif format_type == "json":
				parsed_data = json.loads(raw_content)
			else:
				frappe.throw(_("Unknown response format from API"))

			return parsed_data

		except requests.exceptions.RequestException as e:
			frappe.log_error(str(e), "VAT challan vendor request failed")
			frappe.throw(_("The VAT challan vendor request failed."))

	def get_absolute_file_path(self, file_url: str) -> str:
		"""Path of a File's upload. Only the site's upload folders qualify, so site_config.json
		and the rest of the site folder can never be sent to the vendor."""
		relative = file_url.lstrip("/")
		for prefix, folder in (("private/files/", ("private", "files")), ("files/", ("public", "files"))):
			if relative.startswith(prefix):
				root = os.path.realpath(frappe.get_site_path(*folder))
				path = os.path.realpath(os.path.join(root, relative[len(prefix) :]))
				if path.startswith(root + os.sep) and os.path.isfile(path):
					return path
		frappe.throw(_("Invalid file path"))

	def upload_file(self, document_category_key: str, file_path: str, retailer_id: str):
		"""
		Upload a document file for a retailer to the NBR API using common response handling.

		Args:
			document_category_key (str): Document category key.
			file_path (str): Local file path to upload.
			retailer_id (str): Retailer's ID.

		Returns:
			dict: API response containing message and uploaded file URL.

		Raises:
			frappe.ValidationError: On upload failure or invalid response.
		"""
		url = f"{self.base_url}/integration/upload_file"
		absolute_file_path = self.get_absolute_file_path(file_path)

		# Determine MIME type
		mime_type, _ = mimetypes.guess_type(absolute_file_path)

		# Path is validated in get_absolute_file_path to be within site directory
		with open(absolute_file_path, "rb") as f:  # nosemgrep
			files = {
				"file": (os.path.basename(absolute_file_path), f, mime_type or "application/octet-stream"),
			}

			data = {
				"retailer_id": retailer_id,
				"document_category_key": document_category_key,
			}

			parsed_data = self.get_response_data(url, request_type="POST", payload=data, files=files)

		status_code = str(parsed_data.get("status_code") or parsed_data.get("code"))
		if status_code == "200":
			data = parsed_data.get("data", {})
			return {
				"message": data.get("message", "File uploaded successfully"),
				"file_url": data.get("upload_file_url"),
			}
		else:
			error_msg = parsed_data.get("message") or parsed_data.get("error") or "Unknown error"
			frappe.throw(f"File upload failed: {error_msg}")

	def create_vat_invoice(self, doc):
		pos_profile = frappe.get_doc("POS Profile", doc.pos_profile)

		retailer_branch_id = pos_profile.custom_retailer_branch
		retailer_branch_doc = frappe.get_doc("Retailer Branch Registration", retailer_branch_id)

		if retailer_branch_doc.disabled:
			return

		retailer_id = pos_profile.custom_retailer
		retailer_doc = frappe.get_doc("Retailer Registration", retailer_id)
		valid_service_type_ids = [d.type_id for d in retailer_doc.get("service_types")]

		customer = frappe.get_doc("Customer", doc.customer)

		buyer_info = {
			"dial_code": "+88",
			"phone": customer.mobile_no,
			"name": customer.customer_name,
			"email": customer.email_id,
		}

		vat_invoice_detail = [
			self._sale_line(doc, item, valid_service_type_ids, retailer_doc) for item in doc.items
		]

		payload = {
			"invoice_number": doc.name,
			"retailer_id": pos_profile.custom_retailer_id,
			"invoice_date": f"{doc.posting_date} {doc.posting_time}",
			"retailer_transaction_ref": doc.name,
			"customer_id": doc.customer,
			"bank_transaction_id": "",
			"branch": pos_profile.custom_retailer_branch,
			"buyer_info": json.dumps(buyer_info),
			"txn_amount": doc.total,
			"payment_method": doc.payments[0].mode_of_payment if doc.payments else "",
			"total_sd_percentage": 0.0,
			"terminal_number": "",
			"total_sd_amount": 0.0,
			"retailer_branch_id": pos_profile.custom_retailer_branch_id,
			"total_amount": doc.grand_total,
			"total_discount_amount": doc.discount_amount,
			"vat_invoice_detail": json.dumps(vat_invoice_detail),
		}

		requested_payloads = {
			"vat_invoice": {
				**payload,
				"invoice_date": invoice_timestamp(doc.posting_date, doc.posting_time),
				"buyer_info": buyer_info,
				"vat_invoice_detail": vat_invoice_detail,
			}
		}

		payload["requested_payloads"] = json.dumps(requested_payloads, indent=2)
		payload["vat_invoice_detail"] = json.dumps(vat_invoice_detail, indent=2)

		vat_invoice_doc = frappe.get_doc({"doctype": "VAT Invoice", **payload})

		vat_invoice_doc.insert(ignore_permissions=True)

		if self.sync_schedule == "After Submit":
			enqueue_sync(vat_invoice_doc.name, after_commit=True)

		return vat_invoice_doc

	def _sale_line(self, doc, item, valid_service_type_ids, retailer_doc):
		service = service_fields(item)
		if not service.service_type_id:
			frappe.throw(
				_("Item '{0}' is missing a Service Type ID. Please set it before proceeding.").format(
					item.item_name
				)
			)
		if service.service_type_id not in valid_service_type_ids:
			frappe.throw(
				_(
					"Service Type '{0}' in item '{1}' is not listed under Retailer '{2}'. Please check retailer setup."
				).format(service.service_type_name, item.item_name, retailer_doc.name)
			)

		amounts = line_amounts(doc, item, service.vat_rate, service.vat_inclusive)
		sd_percentage = flt(item.get("sd_percentage") or 0.0)
		sd_amount = amounts.total_amount * sd_percentage / 100
		return {
			"invoice_number": doc.name,
			"product_name": item.item_name,
			"quantity": amounts.qty,
			"unit_price": amounts.unit_price,
			"sd_percentage": sd_percentage,
			"sd_amount": sd_amount,
			"total_amount": amounts.total_amount + sd_amount,
			"service_type_id": service.service_type_id,
			"discount_percentage": flt(item.get("discount_percentage") or 0.0),
			"discount_amount": amounts.discount_amount,
			"total_amount_before_tax": amounts.total_amount_before_tax,
			"vat_inclusive": service.vat_inclusive,
			"vat_percentage": service.vat_rate,
			"vat_amount": amounts.vat_amount,
		}

	def sync_vat_invoice(self, doc):
		"""Bring one invoice up to date with the vendor. Runs outside any document submit,
		because it commits: the Syncing claim and the outcome must survive a later failure."""
		previous = self._claim(doc)
		if not previous:
			return

		try:
			# A Failed send may have reached the vendor before the connection dropped.
			if not self._sale_recorded(doc) and previous == "Failed":
				self._adopt_existing_sale(doc)
			if not self._sale_recorded(doc):
				self._record_sale(doc)
			if not self._sale_recorded(doc):
				doc.db_set("status", "Failed")
				return

			doc.db_set("status", "Synced")
			self.get_vat_invoice_details(doc)
			if doc.is_return and not doc.return_response:
				self.sync_return_vat_invoice(doc)
		except Exception:
			doc.db_set("status", "Failed")
			frappe.log_error(frappe.get_traceback(), "VAT Sync Error")

	def _claim(self, doc):
		"""Mark the invoice Syncing and return its previous status, or None if it is not due.
		The row lock stops two overlapping runs sending the same invoice."""
		status = frappe.db.get_value("VAT Invoice", doc.name, "status", for_update=True)
		if status not in SYNCABLE_STATUSES:
			frappe.db.rollback()
			return None
		doc.reload()
		doc.db_set("status", "Syncing")
		frappe.db.commit()
		return status

	def _sale_recorded(self, doc):
		return bool(doc.vat_invoice_id or doc.s_challan_number or doc.get_response)

	def _record_sale(self, doc):
		payload = doc.requested_payloads
		if isinstance(payload, str):
			payload = json.loads(payload)

		parsed_data = self.get_response_data(
			f"{self.base_url}/integration/record_vat", "POST", payload=payload
		)
		doc.db_set("response", json.dumps(parsed_data, indent=2))

		if str(parsed_data.get("status_code")) == "200":
			self._save_vendor_ids(doc, parsed_data.get("data") or {})
		else:
			# A rejection can also mean the vendor already holds this invoice number.
			self._adopt_existing_sale(doc)

	def _save_vendor_ids(self, doc, data):
		if data.get("vat_invoice_id"):
			doc.db_set("vat_invoice_id", data.get("vat_invoice_id"))
		if data.get("s_challan_number"):
			doc.db_set("s_challan_number", data.get("s_challan_number"))

	def _adopt_existing_sale(self, doc):
		"""Accept the vendor's record of this invoice, if it has one. An unclear answer raises,
		so the invoice stays Failed instead of risking a duplicate send."""
		parsed_data = self._lookup_invoice(doc)
		data = (parsed_data or {}).get("data") or {}
		if str((parsed_data or {}).get("status_code")) != "200":
			return
		if not (data.get("vat_invoice_id") or data.get("vat_invoice_detail_data")):
			return
		doc.db_set("get_response", json.dumps(parsed_data, indent=2))
		self._save_vendor_ids(doc, data)

	def _lookup_invoice(self, doc):
		try:
			return self._fetch_invoice_details(doc)
		except frappe.ValidationError:
			if self.last_http_status in VENDOR_NOT_FOUND_STATUSES:
				return None
			raise

	def _fetch_invoice_details(self, doc):
		query = {"invoice_number": doc.invoice_number}
		if doc.s_challan_number:
			query["smart_challan_number"] = doc.s_challan_number
		return self.get_response_data(
			f"{self.base_url}/integration/get_vat_invoice_details?{urlencode(query)}", "GET"
		)

	def download_schallan(self, doc):
		url = f"{self.base_url}/integration/download_schallan"

		try:
			payload = {"vat_invoice_id": doc.vat_invoice_id}

			parsed_data = self.get_response_data(
				url,
				request_type="POST",
				payload=payload,
			)
			if str(parsed_data.get("status_code")) == "200":
				data = parsed_data.get("data", {})
				download_url = data.get("download_url")
				return download_url

			else:
				frappe.log_error(frappe.get_traceback(), "Download Schallan Error")
				frappe.throw(_("Failed to download Schallan"))
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Download Schallan Error")
			frappe.throw(_("Failed to download Schallan"))

	def get_vat_invoice_details(self, doc):
		"""Store the vendor's copy of a recorded invoice. Failure is logged, not raised: the
		sale is already recorded, and a later return fetches the details again."""
		try:
			parsed_data = self._fetch_invoice_details(doc)
			doc.db_set("get_response", json.dumps(parsed_data, indent=2))
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Get VAT Invoice Details Error")

	def return_vat_invoice(self, invoice_doc):
		"""Prepare the return payload on the original sale's VAT Invoice, ready to sync."""
		doc = frappe.db.exists("VAT Invoice", {"invoice_number": invoice_doc.return_against})
		if not doc:
			frappe.log_error(
				f"No VAT Invoice for {invoice_doc.return_against}", "VAT Invoice not found error"
			)
			return
		doc = frappe.get_doc("VAT Invoice", doc)

		doc.db_set("is_return", 1)
		doc.db_set("return_invoice_no", invoice_doc.name)
		if doc.status == "Synced":
			doc.db_set("status", "Pending")

		try:
			doc.db_set("return_payload", json.dumps(self._return_payload(doc, invoice_doc), indent=2))
		except Exception:
			doc.db_set("status", "Failed")
			frappe.log_error(frappe.get_traceback(), "Return Invoice Payload Error")

	def _return_payload(self, doc, invoice_doc):
		available = self._vendor_lines(doc)
		details = [self._return_line(invoice_doc, item, available) for item in invoice_doc.items]

		total_vat_amount = sum(d["vat_amount"] for d in details)
		before_tax = sum(d["total_amount_before_tax"] for d in details)
		return {
			"invoice_number": doc.invoice_number,
			"request_date": invoice_timestamp(invoice_doc.posting_date, invoice_doc.posting_time),
			"total_void_amount": abs(flt(invoice_doc.grand_total)),
			"total_sd_percentage": 0,
			"total_sd_amount": 0,
			"vat_percentage": total_vat_amount / before_tax * 100 if before_tax else 0.0,
			"vat_amount": total_vat_amount,
			"return_reason": invoice_doc.remarks,
			"return_request_details": details,
		}

	def _vendor_lines(self, doc):
		details = frappe.parse_json(doc.get_response) if doc.get_response else None
		if not details:
			details = self._fetch_invoice_details(doc)
			doc.db_set("get_response", json.dumps(details, indent=2))

		lines = ((details or {}).get("data") or {}).get("vat_invoice_detail_data")
		if isinstance(lines, dict):
			lines = [lines]
		if not lines:
			frappe.throw(_("The vendor returned no lines for invoice {0}").format(doc.invoice_number))
		return list(lines)

	def _return_line(self, invoice_doc, item, available):
		"""One return line. The sale sent item_name as product_name, so match on that. A line
		is used once, because an invoice can repeat an item. No match is an error: skipping it
		would under-report the return."""
		match = next((d for d in available if d.get("product_name") == item.item_name), None)
		if not match:
			frappe.throw(_("No vendor line matches returned item {0}").format(item.item_name))
		available.remove(match)

		vat_percentage = flt(match.get("vat_percentage") or 0)
		vat_inclusive = str(match.get("vat_inclusive")).lower() == "true"
		amounts = line_amounts(invoice_doc, item, vat_percentage, vat_inclusive)
		return {
			"product_name": item.item_name,
			"unit_of_supply": item.uom,
			"quantity": amounts.qty,
			"unit_price": amounts.unit_price,
			"service_type_id": match.get("service_type_id"),
			"vat_percentage": vat_percentage,
			"vat_amount": amounts.vat_amount,
			"total_amount": amounts.total_amount,
			"vat_inclusive": vat_inclusive,
			"total_amount_before_tax": amounts.total_amount_before_tax,
			"discount_percentage": flt(match.get("discount_percentage") or 0),
			"discount_amount": amounts.discount_amount,
			"product_id": match.get("id"),
		}

	def sync_return_vat_invoice(self, doc):
		url = f"{self.base_url}/integration/return_invoice_request"
		try:
			invoice_doc = source_invoice(doc.return_invoice_no)
			if not doc.return_payload:
				self.return_vat_invoice(invoice_doc)
				doc.reload()

			payload = frappe.parse_json(doc.return_payload)
			if not payload:
				doc.db_set("status", "Failed")
				return

			parsed_data = self.get_response_data(url, request_type="POST", payload=payload)
			if self._vendor_rejected(parsed_data):
				doc.db_set("status", "Failed")
				frappe.log_error(json.dumps(parsed_data, indent=2), "Return Invoice Rejected")
				return

			# Set only now, so a rejected return never reads as accepted. return_response also
			# marks the return as done, so a rejection must not be stored there.
			doc.db_set("return_response", json.dumps(parsed_data, indent=2))
			doc.db_set("status", self._return_status(payload, invoice_doc))

		except Exception:
			doc.db_set("status", "Failed")
			frappe.log_error(frappe.get_traceback(), "Return Invoice Request Error")

	def _vendor_rejected(self, parsed_data):
		status_code = parsed_data.get("status_code")
		return str(parsed_data.get("success")) == "0" or (
			status_code is not None and str(status_code) != "200"
		)

	def _return_status(self, payload, invoice_doc):
		returned = sum(flt(d.get("quantity")) for d in payload.get("return_request_details", []))
		sold = sum(abs(flt(i.qty)) for i in invoice_doc.items)
		return "Return" if returned == sold else "Partly Return"


def enqueue_sync(invoice_name, after_commit=False):
	enqueue(
		"vat_compliance.vschallan.sync_vat_invoice_job",
		invoice_name=invoice_name,
		queue="long",
		job_id=f"vat_sync_{invoice_name}",
		deduplicate=True,
		enqueue_after_commit=after_commit,
	)


def source_invoice(name):
	"""The POS sale behind a VAT Invoice; POS can create either doctype."""
	for doctype in RETURN_DOCTYPES:
		if frappe.db.exists(doctype, name):
			return frappe.get_doc(doctype, name)
	frappe.throw(_("Invoice {0} not found").format(name))


@frappe.whitelist(methods=["POST"])
def auto_sync_vat_invoices():
	frappe.has_permission("VAT Invoice", "write", throw=True)
	try:
		if _sync_is_due():
			_fail_stale_syncing()
			_prepare_returns()
			_enqueue_due_invoices()
			frappe.db.set_single_value("POS Vendor Configuration", "last_sync_date", getdate(nowdate()))
	finally:
		report_sync_health()


def _sync_is_due():
	config = frappe.get_single("POS Vendor Configuration")
	if cint(config.disabled):
		return False
	days_between = {"Daily": 0, "After Submit": 0, "Weekly": 7, "Monthly": 30, "Quarterly": 90}.get(
		config.sync_schedule
	)
	if days_between is None:
		return False
	if not days_between or not config.last_sync_date:
		return True
	return date_diff(nowdate(), config.last_sync_date) >= days_between


def _fail_stale_syncing():
	"""A worker killed mid-send leaves Syncing behind. Failed gets retried, and a retry asks
	the vendor first, so this cannot cause a duplicate."""
	cutoff = add_to_date(now_datetime(), hours=-STALE_SYNC_HOURS)
	for name in frappe.get_all(
		"VAT Invoice", filters={"status": "Syncing", "modified": ["<", cutoff]}, pluck="name"
	):
		frappe.db.set_value("VAT Invoice", name, "status", "Failed")


def _prepare_returns():
	cutoff = add_days(nowdate(), -RETURN_LOOKBACK_DAYS)
	schedule_filters = {"is_return": 1, "docstatus": 1, "posting_date": [">=", cutoff]}
	vschallan = VATSmartChallan()
	for doctype, extra in RETURN_DOCTYPES.items():
		for name in frappe.get_all(doctype, filters={**schedule_filters, **extra}, pluck="name"):
			_prepare_return(vschallan, doctype, name)


def _prepare_return(vschallan, doctype, name):
	if frappe.db.exists("VAT Invoice", {"return_invoice_no": name}):
		return
	try:
		invoice_doc = frappe.get_doc(doctype, name)
		if frappe.db.exists("VAT Invoice", {"invoice_number": invoice_doc.return_against}):
			vschallan.return_vat_invoice(invoice_doc)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Return VAT Invoice failed for {name}")


def _enqueue_due_invoices():
	for name in frappe.get_all(
		"VAT Invoice", filters={"status": ["in", list(SYNCABLE_STATUSES)]}, pluck="name"
	):
		enqueue_sync(name)


def sync_vat_invoice_job(invoice_name):
	doc = frappe.get_doc("VAT Invoice", invoice_name)
	try:
		doc.sync_vat_invoice()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "VAT Sync Error")


def sync_return_job(invoice_name):
	"""Report a POS return. Runs after the return commits, so a vendor problem cannot stop the
	refund at the till; a failure stays on the VAT Invoice for the daily retry."""
	try:
		VATSmartChallan().return_vat_invoice(source_invoice(invoice_name))
		name = frappe.db.exists("VAT Invoice", {"return_invoice_no": invoice_name})
		if name:
			frappe.get_doc("VAT Invoice", name).sync_vat_invoice()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Return VAT Invoice Error")
