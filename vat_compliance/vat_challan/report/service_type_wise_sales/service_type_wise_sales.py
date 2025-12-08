# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils.data import flt


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	summary = get_report_summary(data)
	service_chart = get_service_type_chart(data)
	return columns, data, None, service_chart, summary


def get_columns():
	return [
		{"fieldname": "name", "label": _("VAT Invoice Number"), "fieldtype": "Data", "width": 150},
		{"fieldname": "invoice_number", "label": _("Invoice Number"), "fieldtype": "Data", "width": 120},
		{"fieldname": "invoice_date", "label": _("Invoice Date"), "fieldtype": "Datetime", "width": 130},
		{"fieldname": "branch", "label": _("Branch"), "fieldtype": "Data", "width": 120},
		{"fieldname": "customer_id", "label": _("Customer ID"), "fieldtype": "Data", "width": 120},
		{"fieldname": "txn_amount", "label": _("Transaction Amount"), "fieldtype": "Currency", "width": 130},
		{
			"fieldname": "total_discount_amount",
			"label": _("Discount Amount"),
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"fieldname": "total_service_charges_amount",
			"label": _("Service Charges"),
			"fieldtype": "Currency",
			"width": 130,
		},
		{"fieldname": "total_amount", "label": _("Total Amount"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 100},
		{"fieldname": "service_type", "label": _("Service Type"), "fieldtype": "Data", "width": 120},
	]


def get_data(filters=None):
	conditions = {}

	if filters:
		if filters.get("from_date") and filters.get("to_date"):
			conditions["invoice_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
		elif filters.get("from_date"):
			conditions["invoice_date"] = [">=", filters.get("from_date")]
		elif filters.get("to_date"):
			conditions["invoice_date"] = ["<=", filters.get("to_date")]

		if filters.get("status"):
			conditions["status"] = filters.get("status")

	invoices = frappe.get_all(
		"VAT Invoice",
		filters=conditions,
		fields=[
			"name",
			"invoice_number",
			"invoice_date",
			"branch",
			"customer_id",
			"retailer_id",
			"txn_amount",
			"total_sd_percentage",
			"total_sd_amount",
			"total_discount_amount",
			"total_service_charges_amount",
			"total_amount",
			"payment_method",
			"order_id",
			"status",
			"requested_payloads",
		],
		order_by="invoice_date desc",
	)

	filtered_invoices = []
	service_type_filter = filters.get("service_type") if filters else None

	for inv in invoices:
		payload = inv.get("requested_payloads")
		service_names = []
		service_match = False

		if payload:
			try:
				payload_dict = json.loads(payload)
				vat_invoice = payload_dict.get("vat_invoice", {})
				for item in vat_invoice.get("vat_invoice_detail", []):
					st_id = item.get("service_type_id")
					if st_id:
						st_doc = frappe.get_value("VC Service Type", {"service_id": st_id}, "service_name")
						if st_doc:
							service_names.append(st_doc)
							# Match service type filter if applied
							if service_type_filter and st_doc == frappe.get_value(
								"VC Service Type", service_type_filter, "service_name"
							):
								service_match = True
			except Exception:
				service_names.append("Unknown")

		inv["service_type"] = ", ".join(service_names) if service_names else "Unknown"

		# Include invoice only if matches service filter (or no filter)
		if not service_type_filter or service_match:
			filtered_invoices.append(inv)

	return filtered_invoices


def get_report_summary(data):
	total_invoices = len(data)
	pending = len([d for d in data if d["status"] == "Pending"])
	synced = len([d for d in data if d["status"] == "Synced"])
	failed = len([d for d in data if d["status"] == "Failed"])
	total_txn = sum(flt(d["txn_amount"]) for d in data)
	total_sales = sum(flt(d["total_amount"]) for d in data)
	total_vat = sum(flt(d["total_amount"]) - flt(d["txn_amount"]) for d in data)
	total_discount = sum(flt(d["total_discount_amount"]) for d in data)
	unique_customers = len(set(d["customer_id"] for d in data))

	return [
		{"value": total_invoices, "label": _("Total Invoices"), "datatype": "Int", "indicator": "blue"},
		{"value": pending, "label": _("Pending"), "datatype": "Int", "indicator": "orange"},
		{"value": synced, "label": _("Synced"), "datatype": "Int", "indicator": "green"},
		{"value": failed, "label": _("Failed"), "datatype": "Int", "indicator": "red"},
		{"value": total_txn, "label": _("Transaction Amount"), "datatype": "Currency", "indicator": "blue"},
		{"value": total_sales, "label": _("Total Sales"), "datatype": "Currency", "indicator": "green"},
		{"value": total_vat, "label": _("Total VAT Amount"), "datatype": "Currency", "indicator": "orange"},
		{"value": total_discount, "label": _("Total Discount"), "datatype": "Currency", "indicator": "red"},
		{"value": unique_customers, "label": _("Unique Customers"), "datatype": "Int", "indicator": "purple"},
	]


def get_service_type_chart(data):
	service_totals = {}
	for d in data:
		stype = d["service_type"] or "Unknown"
		service_totals[stype] = service_totals.get(stype, 0) + flt(d.get("txn_amount") or 0)

	labels = list(service_totals.keys())
	values = list(service_totals.values())

	return {
		"data": {"labels": labels, "datasets": [{"name": "Transaction Amount", "values": values}]},
		"type": "bar",
		"height": 300,
	}
