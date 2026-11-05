# Copyright (c) 2025, na and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _

from vat_compliance import report_kit as kit
from vat_compliance.access import require_report
from vat_compliance.vat_rates import add_invoice_vat

# Each invoice renders a PDF inside the web request, so the request size must be bounded.
MAX_BULK_INVOICES = 500


def execute(filters=None):
	if not filters:
		filters = {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data, get_meta(filters, data)


def get_columns():
	return [
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 130},
		{
			"label": _("Invoice No"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 220,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 280,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 260,
		},
		{"label": _("Total (Excl. VAT)"), "fieldname": "net_total", "fieldtype": "Currency", "width": 170},
		{
			"label": _("Total VAT"),
			"fieldname": "vat_amount",
			"fieldtype": "Currency",
			"width": 150,
		},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 170},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
		{"label": _("Download 6.3"), "fieldname": "download", "fieldtype": "Data", "width": 150},
	]


def get_data(filters):
	# Real Sales Invoice fields: the old version passed from_date/to_date as if they were
	# fields, so the report always came back empty. get_list applies the user's permissions.
	list_filters = [["docstatus", "=", 1]]
	if filters.get("status"):
		list_filters.append(["status", "=", filters.get("status")])
	if filters.get("from_date"):
		list_filters.append(["posting_date", ">=", filters.get("from_date")])
	if filters.get("to_date"):
		list_filters.append(["posting_date", "<=", filters.get("to_date")])
	for field, key in (("company", "company"), ("customer", "customer"), ("name", "sales_invoice")):
		if filters.get(key):
			list_filters.append([field, "=", filters.get(key)])

	invoices = frappe.get_list(
		"Sales Invoice",
		filters=list_filters,
		fields=[
			"name",
			"posting_date",
			"customer",
			"company",
			"net_total",
			"total_taxes_and_charges",
			"grand_total",
			"status",
			"base_net_total",
			"base_total_taxes_and_charges",
		],
		order_by="posting_date DESC",
		limit_page_length=0,
	)

	add_invoice_vat("Sales Invoice", invoices)

	# The JS formatter turns this into the print/download button.
	for inv in invoices:
		inv["download"] = inv.name

	return invoices


@frappe.whitelist()
def download_all_invoices(filters):
	"""
	Generate PDFs for all invoices and create a zip file for download
	"""
	import zipfile
	from io import BytesIO

	require_report("Mushak 6_3")
	frappe.has_permission("Sales Invoice", "print", throw=True)

	if isinstance(filters, str):
		filters = frappe.parse_json(filters)

	invoices = get_data(filters)
	if not invoices:
		frappe.throw(_("No invoices found for the selected filters"))
	if len(invoices) > MAX_BULK_INVOICES:
		frappe.throw(
			_("Select at most {0} invoices to download. Narrow the date range.").format(MAX_BULK_INVOICES)
		)

	try:
		zip_buffer = BytesIO()

		included, failed = [], []
		with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
			for invoice in invoices:
				try:
					pdf_content = frappe.get_print(
						doctype="Sales Invoice",
						name=invoice.get("name"),
						as_pdf=True,
						pdf_generator="wkhtmltopdf",
					)
					zipf.writestr(f"Mushak_6_3_{invoice['name']}.pdf", pdf_content)
					included.append(invoice["name"])
				except Exception as e:
					frappe.log_error(
						f"Error generating PDF for invoice {invoice['name']}: {e!s}",
						"Download All Invoices",
					)
					failed.append(invoice["name"])
			zipf.writestr("MANIFEST.txt", build_manifest(included, failed))

		if not included:
			frappe.throw(_("None of the {0} invoices could be generated. See Error Log.").format(len(failed)))

		zip_buffer.seek(0)

		# A partial set must be obvious before anyone opens or files it.
		prefix = "INCOMPLETE_" if failed else ""
		file_name = f"{prefix}mushak_6_3_invoices_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"

		frappe.response["filename"] = file_name
		frappe.response["filecontent"] = zip_buffer.getvalue()
		frappe.response["type"] = "download"
		frappe.response["content_type"] = "application/zip"

	except frappe.ValidationError:
		raise
	except Exception as e:
		frappe.log_error(f"Error in download_all_invoices: {e!s}", "Download All Invoices")
		frappe.throw(_("Error generating zip file: {0}").format(str(e)))


def build_manifest(included, failed):
	lines = [f"Included: {len(included)}", f"Failed: {len(failed)}", "", "Included invoices:", *included]
	if failed:
		lines += ["", "FAILED, NOT IN THIS ZIP:", *failed]
	return "\n".join(lines) + "\n"


def get_meta(filters, data):
	"""Header cards and charts, in company currency, from the same invoices as the table."""
	filters = frappe._dict(filters or {})

	def day(r):
		return r.get("posting_date")

	def vat(r):
		return r.get("base_vat_amount")

	return kit.meta(
		filters,
		invoices=len(data),
		net=kit.total(data, lambda r: r.get("base_net_total")),
		vat=kit.total(data, vat),
		statuses=kit.group(data, lambda r: r.get("status"), lambda r: r.get("base_net_total")),
		trend_count=kit.monthly(data, day, lambda r: 1, filters),
		trend_vat=kit.monthly(data, day, vat, filters),
	)
