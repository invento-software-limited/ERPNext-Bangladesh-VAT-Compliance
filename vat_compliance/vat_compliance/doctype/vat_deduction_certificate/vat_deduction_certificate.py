# Copyright (c) 2025, na and contributors
# For license information, please see license.txt

import json
from bs4 import BeautifulSoup
from datetime import timedelta
import frappe
from frappe import _
from frappe.utils import getdate
from frappe.utils.print_format import download_pdf
from frappe.model.document import Document
from frappe.contacts.doctype.address.address import get_company_address
from vat_compliance.vat_compliance.report.vds_management.vds_management import get_data


class VATDeductionCertificate(Document):
	def validate(self):
		self.check_date_range_conflicts()
		self.validate_return_date()

	def validate_return_date(self):
		if self.certificate_type == "Related To VAT Return":
			if not self.return_submission_date:
				frappe.throw(_("Please enter Return Submission Date"))

			posting_date = getdate(self.posting_date)
			return_date = getdate(self.return_submission_date)

			if posting_date > return_date + timedelta(days=3):
				frappe.throw(_("Posting Date must be within 3 days of Return Submission Date"))

			if posting_date < return_date:
				frappe.throw(_("Posting Date cannot be before Return Submission Date"))

	def check_date_range_conflicts(self):
		"""
		Check if from_date/to_date for the same vendor and company
		overlaps with existing VAT Deduction Certificates.
		"""
		if not self.from_date or not self.to_date or not self.vendor or not self.company:
			return

		conflict = frappe.db.sql("""
								 SELECT name, from_date, to_date
								 FROM `tabVAT Deduction Certificate`
								 WHERE name != %(name)s
								   AND vendor = %(vendor)s
								   AND company = %(company)s
								   AND (
									 (%(from_date)s BETWEEN from_date
								   AND to_date)
									OR
									 (%(to_date)s BETWEEN from_date
								   AND to_date)
									OR
									 (from_date BETWEEN %(from_date)s
								   AND %(to_date)s)
									OR
									 (to_date BETWEEN %(from_date)s
								   AND %(to_date)s)
									 )
									 LIMIT 1
								 """, {
									 "name": self.name or "",
									 "vendor": self.vendor,
									 "company": self.company,
									 "from_date": self.from_date,
									 "to_date": self.to_date
								 }, as_dict=True)

		if conflict:
			link = f"/app/vat-deduction-certificate/{conflict[0].name}"
			frappe.throw(_(
				f"Date range conflicts with existing VAT Deduction Certificate "
				f"<a href='{link}' target='_blank'>{conflict[0].name}</a> "
				f"({conflict[0].from_date} to {conflict[0].to_date})"
			))

	def update_references_and_context(self):
		data = self.get_vds_withheld_data()
		context = self.prepare_context(data)

		self.db_set('context', json.dumps(context))
		self.prepare_references(data)

		print_html = self.get_print_html()
		self.db_set('certificate_html', print_html)
		frappe.db.commit()

	def prepare_references(self, data):
		"""
		Populate the references child table with payment_entry and purchase_invoice,
		skipping duplicates where both fields match an existing row, using db_set
		"""
		frappe.db.sql("""
					  DELETE
					  FROM `tabVAT Deduction Certificate References`
					  WHERE parent = %s
					  """, (self.name,))

		existing_rows = set()

		for row in data:
			pe = row.get("payment_entry_id")
			pi = row.get("invoice_id")
			key = (pe, pi)

			if key in existing_rows:
				continue

			frappe.get_doc({
				"doctype": "VAT Deduction Certificate References",
				"parent": self.name,
				"parentfield": "references",
				"parenttype": self.doctype,
				"payment_entry": pe,
				"purchase_invoice": pi
			}).insert(ignore_permissions=True)

			existing_rows.add(key)

	def prepare_context(self, data):
		withheld_data = []

		supplier = frappe.get_doc("Supplier", self.vendor)
		for index, row in enumerate(data):
			invoice = frappe.get_doc("Purchase Invoice", row.get("invoice_id"))

			withheld_data.append({
				'sl_no': index + 1,
				'supplier_name': row.get('vendor_name'),
				'supplier_bin': supplier.get("custom_bin_no"),
				'inv_number': row.get('invoice_id'),
				'inv_posting_date': invoice.get("posting_date").strftime(
					"%Y-%m-%d") if invoice.get("posting_date") else None,
				'total_value_of_supply': row.get('invoice_amount'),
				'amount_of_vat': invoice.get("total_taxes_and_charges"),
				'amount_of_vat_withheld': row.get('vds_amount'),
			})

		company = frappe.get_doc("Company", self.company)

		address_obj = get_company_address(self.company)

		if address_obj and address_obj.company_address_display:
			address = ", ".join(
				[line.strip() for line in address_obj.company_address_display.split("<br>") if
				 line.strip()])
		else:
			address = ""

		context = {
			'name_of_withholding_entity': self.company,
			'address_of_withholding_entity': address,
			'bin_of_withholding_entity': company.get("custom_bin_no"),
			'certificate_no': self.name,
			'date_of_issue': self.posting_date.strftime("%Y-%m-%d") if self.posting_date else None,
			'withheld_data': withheld_data
		}

		return context

	def get_vds_withheld_data(self):
		"""Get withheld VAT Deduction Certificate data"""
		filters = {
			"from_date": self.from_date,
			"to_date": self.to_date,
			"status": "DDGT",
			"company": self.company,
			"vendor": self.vendor
		}
		return get_data(filters)

	def get_print_html(self):
		"""
		Generate HTML using the 'Mushak 6.6' Print Format
		Returns only the content inside <body>...</body>
		"""

		full_html = frappe.get_print(
			doctype=self.doctype,
			name=self.name,
			doc=self,
		)

		soup = BeautifulSoup(full_html, "html.parser")
		wht_div = soup.find("div", class_="wht-print")
		body_content = wht_div.decode_contents() if wht_div else full_html
		return body_content


@frappe.whitelist()
def generate_mushak_6_6(name):
	vat_deduction_certificate = frappe.get_doc("VAT Deduction Certificate", name)
	vat_deduction_certificate.update_references_and_context()
	return vat_deduction_certificate


def parse_context(json_str):
	"""Convert JSON string to Python dict"""
	if not json_str:
		return {}
	try:
		return json.loads(json_str)
	except Exception:
		return {}
