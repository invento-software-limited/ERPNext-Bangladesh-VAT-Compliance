import json
import mimetypes
import os
import xml.etree.ElementTree as ET
from datetime import datetime, time, timedelta

import frappe
import requests
import xmltodict
from frappe import _
from frappe.utils import add_days, date_diff, flt, get_url, getdate, nowdate
from frappe.utils.background_jobs import enqueue
from frappe.utils.password import get_decrypted_password
from requests.auth import HTTPBasicAuth


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
			frappe.throw("No POS Vendor Configuration found")

		if config_data.get("disabled") == "1":
			frappe.throw("POS Vendor Configuration is disabled")

		self.docname = "POS Vendor Configuration"
		self.base_url = config_data.get("base_url")
		self.client_id = config_data.get("client_id")
		self.access_token = config_data.get("access_token")
		self.expiry_date = config_data.get("expiry_date")
		self.company_id = config_data.get("company_id")
		self.client_secret = get_decrypted_password("POS Vendor Configuration", self.docname, "client_secret")
		self.sync_schedule = config_data.get("sync_schedule")

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
				except Exception as e:
					frappe.throw(f"Failed to parse JSON response: {raw_content}\nError: {e!s}")
			else:
				# XML response
				try:
					root = ET.fromstring(raw_content)
					access_token_elem = root.find(".//access_token")
					expiry_time_elem = root.find(".//expiry_time")
					company_id_elem = root.find(".//company_id")

					if access_token_elem is None:
						frappe.throw(f"No access_token found in XML response: {raw_content}")

					self.access_token = access_token_elem.text
					self.expiry_date = expiry_time_elem.text if expiry_time_elem is not None else None
					self.company_id = company_id_elem.text if company_id_elem is not None else None

				except ET.ParseError:
					frappe.throw(f"Failed to parse XML response: {raw_content}")

			# Save to Single Doc
			frappe.db.set_single_value("POS Vendor Configuration", "access_token", self.access_token)
			frappe.db.set_single_value("POS Vendor Configuration", "expiry_date", self.expiry_date)
			frappe.db.set_single_value("POS Vendor Configuration", "company_id", self.company_id)
			frappe.db.commit()

			return {
				"access_token": self.access_token,
				"expiry_date": self.expiry_date,
				"company_id": self.company_id,
			}

		except requests.exceptions.RequestException as e:
			frappe.throw(f"Failed to authenticate vendor: {e!s}")

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
					frappe.db.commit()

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
					frappe.db.commit()

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
					frappe.db.commit()

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
			frappe.db.commit()

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
			frappe.db.commit()

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
			"owner_nid": doc.owner_nid,
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
				frappe.throw("Unexpected response format from API")

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
			ET.fromstring(response_text)
			return "xml"
		except ET.ParseError:
			pass

		return "unknown"

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
				frappe.throw("Invalid request type")

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
				frappe.throw("Unknown response format from API")

			return parsed_data

		except requests.exceptions.RequestException as e:
			frappe.throw(str(e))

	def get_absolute_file_path(self, file_url: str) -> str:
		"""
		Returns the absolute filesystem path of a file stored in ERPNext,
		handling both /files (public) and /private/files (private) paths.
		"""
		file_url = file_url.lstrip("/")

		if file_url.startswith("private/files/"):
			absolute_path = frappe.get_site_path(file_url)
		elif file_url.startswith("files/"):
			absolute_path = os.path.join(frappe.get_site_path("public", "files"), file_url.split("/")[-1])
		else:
			absolute_path = frappe.get_site_path(file_url)

		if not os.path.exists(absolute_path):
			frappe.throw(f"File does not exist: {absolute_path}")

		return absolute_path

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

		# Make sure file exists
		if not os.path.exists(absolute_file_path):
			frappe.throw(f"File does not exist: {absolute_file_path}")

		# Determine MIME type
		mime_type, _ = mimetypes.guess_type(absolute_file_path)

		with open(absolute_file_path, "rb") as f:
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

		vat_invoice_detail = []
		for item in doc.items:
			service_type_id = item.get("custom_service_type_id")

			if not service_type_id:
				frappe.throw(
					_("Item '{0}' is missing a Service Type ID. Please set it before proceeding.").format(
						item.item_name
					)
				)

			if service_type_id not in valid_service_type_ids:
				frappe.throw(
					_(
						"Service Type '{0}' in item '{1}' is not listed under Retailer '{2}'. Please check retailer setup."
					).format(item.custom_service_type_name, item.item_name, retailer_doc.name)
				)

			vat_percentage = flt(item.custom_vat_rate or 0.0)
			vat_inclusive = item.custom_vat_exclusive == 0
			qty = flt(item.qty)
			rate = flt(item.rate)
			discount_percentage = flt(item.get("discount_percentage") or 0.0)
			discount_amount = flt(item.get("discount_amount") or 0.0)

			if vat_inclusive:
				total_amount = qty * rate - discount_amount
				total_amount_before_tax = total_amount / (1 + vat_percentage / 100)
				vat_amount = total_amount - total_amount_before_tax
			else:
				total_amount_before_tax = qty * rate - discount_amount
				vat_amount = total_amount_before_tax * vat_percentage / 100
				total_amount = total_amount_before_tax + vat_amount

			sd_percentage = flt(item.get("sd_percentage") or 0.0)
			sd_amount = total_amount * sd_percentage / 100

			vat_invoice_detail.append(
				{
					"invoice_number": doc.name,
					"product_name": item.item_name,
					"quantity": qty,
					"unit_price": rate,
					"sd_percentage": sd_percentage,
					"sd_amount": sd_amount,
					"total_amount": total_amount + sd_amount,
					"service_type_id": service_type_id,
					"discount_percentage": discount_percentage,
					"discount_amount": discount_amount,
					"total_amount_before_tax": total_amount_before_tax,
					"vat_inclusive": vat_inclusive,
					"vat_percentage": vat_percentage,
					"vat_amount": vat_amount,
				}
			)

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
		if isinstance(doc.posting_date, str):
			posting_date = datetime.strptime(doc.posting_date, "%Y-%m-%d").date()
		else:
			posting_date = doc.posting_date

		if isinstance(doc.posting_time, str):
			try:
				posting_time = datetime.strptime(doc.posting_time, "%H:%M:%S.%f").time()
			except ValueError:
				posting_time = datetime.strptime(doc.posting_time, "%H:%M:%S").time()
		else:
			posting_time = doc.posting_time

		posting_datetime = datetime.combine(posting_date, posting_time)
		invoice_timestamp = int(posting_datetime.timestamp())

		requested_payloads = {
			"vat_invoice": {
				**payload,
				"invoice_date": invoice_timestamp,
				"buyer_info": buyer_info,
				"vat_invoice_detail": vat_invoice_detail,
			}
		}

		payload["requested_payloads"] = json.dumps(requested_payloads, indent=2)
		payload["vat_invoice_detail"] = json.dumps(vat_invoice_detail, indent=2)

		vat_invoice_doc = frappe.get_doc({"doctype": "VAT Invoice", **payload})

		vat_invoice_doc.insert(ignore_permissions=True)

		if self.sync_schedule == "After Submit":
			self.sync_vat_invoice(vat_invoice_doc)

		return vat_invoice_doc

	def sync_vat_invoice(self, doc):
		doc.db_set("status", "Syncing")

		url = f"{self.base_url}/integration/record_vat"

		try:
			payload = doc.requested_payloads
			if isinstance(payload, str):
				payload = json.loads(payload)

			parsed_data = self.get_response_data(
				url,
				request_type="POST",
				payload=payload,
			)

			response = parsed_data
			if not isinstance(parsed_data, str):
				response = json.dumps(parsed_data, indent=2)

			if str(parsed_data.get("status_code")) == "200":
				data = parsed_data.get("data", {})
				vat_invoice_id = data.get("vat_invoice_id")
				s_challan_number = data.get("s_challan_number")

				if vat_invoice_id:
					doc.db_set("vat_invoice_id", vat_invoice_id)
				if s_challan_number:
					doc.db_set("s_challan_number", s_challan_number)

				doc.db_set("response", response)
				doc.db_set("status", "Synced")

				self.get_vat_invoice_details(doc)
				if doc.is_return and not doc.return_response:
					self.sync_return_vat_invoice(doc)
			elif str(parsed_data.get("success")) == "0":
				self.get_vat_invoice_details(doc)
				if doc.is_return:
					self.sync_return_vat_invoice(doc)
			else:
				doc.db_set("status", "Failed")

		except Exception:
			doc.db_set("status", "Failed")
			frappe.log_error(frappe.get_traceback(), "VAT Sync Error")

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
				frappe.throw("Failed to download Schallan")
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Download Schallan Error")
			frappe.throw("Failed to download Schallan")

	def get_vat_invoice_details(self, doc):
		url = f"{self.base_url}/integration/get_vat_invoice_details?invoice_number={doc.invoice_number}&smart_challan_number={doc.s_challan_number}"
		try:
			if doc.status == "Pending" or doc.status == "Failed":
				self.sync_vat_invoice(doc)

			parsed_data = self.get_response_data(
				url,
				request_type="GET",
			)
			response = parsed_data
			if not isinstance(parsed_data, str):
				response = json.dumps(parsed_data, indent=2)

			doc.db_set("get_response", response)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Get VAT Invoice Details Error")
		pass

	def return_vat_invoice(self, pos_invoice_doc):
		try:
			doc = frappe.get_doc("VAT Invoice", {"invoice_number": pos_invoice_doc.return_against})
		except Exception:
			frappe.log_error(frappe.get_traceback(), "VAT Invoice not found error")
			return

		doc.db_set("is_return", 1)
		doc.db_set("return_invoice_no", pos_invoice_doc.name)
		if doc.status == "Synced":
			doc.db_set("status", "Pending")

		vat_invoice_details = frappe.parse_json(doc.get_response)
		if not vat_invoice_details:
			self.get_vat_invoice_details(doc)
			vat_invoice_details = frappe.parse_json(doc.get_response)
		vat_data = vat_invoice_details.get("data", {})

		vat_invoice_detail_data = vat_data.get("vat_invoice_detail_data")
		if isinstance(vat_invoice_detail_data, dict):
			vat_invoice_detail_data = [vat_invoice_detail_data]  # normalize

		return_request_details = []
		total_vat_amount = 0.0
		total_vat_percentage = 0.0

		try:
			for item in pos_invoice_doc.items:
				matching_vat_detail = next(
					(d for d in vat_invoice_detail_data if d.get("product_name") == item.item_code), None
				)

				if not matching_vat_detail:
					continue

				qty = abs(flt(item.qty))
				rate = flt(item.rate)
				discount_percentage = flt(matching_vat_detail.get("discount_percentage") or 0)
				discount_amount = qty * discount_percentage / 100

				vat_percentage = flt(matching_vat_detail.get("vat_percentage") or 0)
				vat_inclusive = str(matching_vat_detail.get("vat_inclusive")).lower() == "true"

				if vat_inclusive:
					total_amount = abs(flt(item.amount)) - discount_amount
					total_amount_before_tax = total_amount / (1 + vat_percentage / 100)
					vat_amount = total_amount - total_amount_before_tax
				else:
					total_amount_before_tax = abs(flt(item.amount)) - discount_amount
					vat_amount = total_amount_before_tax * vat_percentage / 100
					total_amount = total_amount_before_tax + vat_amount

				total_vat_amount += vat_amount

				merged = {
					"product_name": item.item_code,
					"unit_of_supply": item.uom,
					"quantity": qty,
					"unit_price": rate,
					"service_type_id": item.custom_service_type_id,
					"vat_percentage": vat_percentage,
					"vat_amount": vat_amount,
					"total_amount": total_amount,
					"vat_inclusive": vat_inclusive,
					"total_amount_before_tax": total_amount_before_tax,
					"discount_percentage": discount_percentage,
					"discount_amount": discount_amount,
					"product_id": matching_vat_detail.get("id"),
				}

				return_request_details.append(merged)

			total_amount_before_tax_sum = sum(d["total_amount_before_tax"] for d in return_request_details)
			if total_amount_before_tax_sum:
				total_vat_percentage = (total_vat_amount / total_amount_before_tax_sum) * 100

			if isinstance(pos_invoice_doc.posting_date, str):
				posting_date = datetime.strptime(pos_invoice_doc.posting_date, "%Y-%m-%d").date()
			else:
				posting_date = pos_invoice_doc.posting_date

			posting_time = pos_invoice_doc.posting_time
			if isinstance(posting_time, str):
				try:
					posting_time = datetime.strptime(posting_time, "%H:%M:%S.%f").time()
				except ValueError:
					posting_time = datetime.strptime(posting_time, "%H:%M:%S").time()
			elif isinstance(posting_time, timedelta):
				total_seconds = int(posting_time.total_seconds())
				hours = total_seconds // 3600
				minutes = (total_seconds % 3600) // 60
				seconds = total_seconds % 60
				posting_time = time(hour=hours, minute=minutes, second=seconds)
			elif isinstance(posting_time, datetime):
				posting_time = posting_time.time()

			posting_datetime = datetime.combine(posting_date, posting_time)
			invoice_timestamp = int(posting_datetime.timestamp())

			payload = {
				"invoice_number": doc.invoice_number,
				"request_date": invoice_timestamp,
				"total_void_amount": abs(flt(pos_invoice_doc.grand_total)),
				"total_sd_percentage": 0,
				"total_sd_amount": 0,
				"vat_percentage": total_vat_percentage,
				"vat_amount": total_vat_amount,
				"return_reason": pos_invoice_doc.remarks,
				"return_request_details": return_request_details,
			}

			doc.db_set("return_payload", json.dumps(payload, indent=2))

		except Exception:
			frappe.log_error(frappe.get_traceback(), "Return Invoice Payload Error")

	def sync_return_vat_invoice(self, doc):
		url = f"{self.base_url}/integration/return_invoice_request"
		try:
			pos_invoice_doc = None

			if not doc.return_payload:
				pos_invoice_doc = frappe.get_doc("POS Invoice", doc.return_invoice_no)
				self.return_vat_invoice(pos_invoice_doc)

			payload = doc.return_payload
			if isinstance(payload, str):
				payload = frappe.parse_json(payload)

			if not pos_invoice_doc:
				pos_invoice_doc = frappe.get_doc("POS Invoice", doc.return_invoice_no)

			return_qty_sum = sum(d.get("quantity", 0) for d in payload.get("return_request_details", []))
			pos_qty_sum = sum(abs(flt(i.qty)) for i in pos_invoice_doc.items)

			if return_qty_sum == pos_qty_sum:
				doc.db_set("status", "Return")
			else:
				doc.db_set("status", "Partly Return")

			parsed_data = self.get_response_data(
				url,
				request_type="POST",
				payload=payload,
			)

			response = parsed_data
			if not isinstance(parsed_data, str):
				response = json.dumps(parsed_data, indent=2)
			if parsed_data.get("success") == "0" and parsed_data.get("error") == "Bad request":
				doc.db_set("status", "Failed")

			doc.db_set("return_response", response)

		except Exception:
			doc.db_set("status", "Failed")
			frappe.log_error(frappe.get_traceback(), "Return Invoice Request Error")


@frappe.whitelist()
def auto_sync_vat_invoices():
	config = frappe.get_single("POS Vendor Configuration")
	schedule = config.sync_schedule

	last_sync = frappe.db.get_single_value("POS Vendor Configuration", "last_sync_date")
	last_sync_date = getdate(last_sync) if last_sync else None

	today = getdate(nowdate())
	should_run = False

	if schedule == "Daily":
		should_run = True
	elif schedule == "Weekly":
		should_run = not last_sync or date_diff(today, getdate(last_sync)) >= 7
	elif schedule == "Monthly":
		should_run = not last_sync or date_diff(today, getdate(last_sync)) >= 30
	elif schedule == "Quarterly":
		should_run = not last_sync or date_diff(today, getdate(last_sync)) >= 90
	elif schedule == "After Submit":
		should_run = True

	if not should_run:
		return

	filters = {"status": "Return"}
	if last_sync_date:
		filters["posting_date"] = [">=", last_sync_date]

	vschallan = VATSmartChallan()

	pos_invoices = frappe.get_all("POS Invoice", filters=filters, fields=["name"])

	for pos_inv in pos_invoices:
		vat_exists = frappe.db.exists("VAT Invoice", {"return_invoice_no": pos_inv.name})
		if vat_exists:
			continue

		try:
			pos_invoice_doc = frappe.get_doc("POS Invoice", pos_inv.name)
			vschallan.return_vat_invoice(pos_invoice_doc)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Return VAT Invoice failed for {pos_inv.name}")

	invoices = frappe.get_all(
		"VAT Invoice", filters={"status": ["in", ["Pending", "Failed"]]}, fields=["name"]
	)

	for inv in invoices:
		enqueue(
			"vschallan.vschallan.sync_vat_invoice_job",
			invoice_name=inv.name,
			queue="long",
		)

	frappe.db.set_value("POS Vendor Configuration", None, "last_sync_date", today)
	frappe.db.commit()


def sync_vat_invoice_job(invoice_name):
	doc = frappe.get_doc("VAT Invoice", invoice_name)
	try:
		doc.sync_vat_invoice()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "VAT Sync Error")
