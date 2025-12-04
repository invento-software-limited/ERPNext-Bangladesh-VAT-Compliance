# Copyright (c) 2025, na and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _


def execute(filters=None):
	if not filters:
		filters = {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	return [
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
		{
			"label": _("Invoice No"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 200,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 180,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 150,
		},
		{"label": _("Total (Excl. VAT)"), "fieldname": "net_total", "fieldtype": "Currency", "width": 130},
		{
			"label": _("Total VAT"),
			"fieldname": "total_taxes_and_charges",
			"fieldtype": "Currency",
			"width": 120,
		},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 130},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Download 6.3"), "fieldname": "download", "fieldtype": "Data", "width": 130},
	]


def get_data(filters):
	conditions = []
	values = {}

	if filters.get("from_date"):
		conditions.append("posting_date >= %(from_date)s")
		values["from_date"] = filters.get("from_date")

	if filters.get("to_date"):
		conditions.append("posting_date <= %(to_date)s")
		values["to_date"] = filters.get("to_date")

	if filters.get("company"):
		conditions.append("company = %(company)s")
		values["company"] = filters.get("company")

	if filters.get("customer"):
		conditions.append("customer = %(customer)s")
		values["customer"] = filters.get("customer")

	if filters.get("sales_invoice"):
		conditions.append("name = %(sales_invoice)s")
		values["sales_invoice"] = filters.get("sales_invoice")

	if filters.get("status"):
		conditions.append("status = %(status)s")
		values["status"] = filters.get("status")
	else:
		conditions.append("docstatus = 1")

	where_clause = " AND ".join(conditions)

	query = f"""
        SELECT
            name,
            posting_date,
            customer,
            company,
            net_total,
            total_taxes_and_charges,
            grand_total,
            status
        FROM `tabSales Invoice`
        WHERE {where_clause}
        ORDER BY posting_date DESC
    """

	invoices = frappe.db.sql(query, values, as_dict=True)

	for inv in invoices:
		inv["download"] = (
			f"<a class='btn btn-xs btn-success' "
			f"href='/printview?doctype=Sales%20Invoice&name={inv.name}"
			f"&trigger_print=1' target='_blank'>"
			f"<i class='fa fa-download'></i></a>"
		)

	return invoices


@frappe.whitelist()
def download_all_invoices(filters):
	"""
	Generate PDFs for all invoices and create a zip file for download
	"""
	import zipfile
	from io import BytesIO

	if isinstance(filters, str):
		filters = frappe.parse_json(filters)

	invoices = get_data(filters)
	if not invoices:
		frappe.throw(_("No invoices found for the selected filters"))

	try:
		zip_buffer = BytesIO()

		with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
			for invoice in invoices:
				try:
					pdf_content = frappe.get_print(
						doctype="Sales Invoice",
						name=invoice.get("name"),
						as_pdf=True,
						pdf_generator="wkhtmltopdf",
					)
					filename = f"Mushak_6_3_{invoice['name']}.pdf"
					zipf.writestr(filename, pdf_content)

				except Exception as e:
					frappe.log_error(
						f"Error generating PDF for invoice {invoice['name']}: {e!s}",
						"Download All Invoices",
					)
					continue

		zip_buffer.seek(0)

		file_name = f"mushak_6_3_invoices_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"

		frappe.response["filename"] = file_name
		frappe.response["filecontent"] = zip_buffer.getvalue()
		frappe.response["type"] = "download"
		frappe.response["content_type"] = "application/zip"

	except Exception as e:
		frappe.log_error(f"Error in download_all_invoices: {e!s}", "Download All Invoices")
		frappe.throw(_("Error generating zip file: {0}").format(str(e)))
