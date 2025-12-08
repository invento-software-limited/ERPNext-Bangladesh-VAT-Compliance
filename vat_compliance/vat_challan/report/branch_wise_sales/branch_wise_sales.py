# Copyright (c) 2025, Invento Software Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	summary = get_report_summary(filters)
	chart = get_branch_wise_chart(filters)
	return columns, data, None, chart, summary


def get_report_summary(filters):
	filters = frappe._dict(filters or {})

	# remove non-doctype fields
	valid_filters = {}

	if filters.get("branch"):
		valid_filters["branch"] = filters.branch
	if filters.get("status"):
		valid_filters["status"] = filters.status

	if filters.get("from_date") and filters.get("to_date"):
		valid_filters["invoice_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		valid_filters["invoice_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		valid_filters["invoice_date"] = ["<=", filters.to_date]

	# Counts
	total_invoices = frappe.db.count("VAT Invoice", valid_filters)
	pending_invoices = frappe.db.count("VAT Invoice", {**valid_filters, "status": "Pending"})
	synced_invoices = frappe.db.count("VAT Invoice", {**valid_filters, "status": "Synced"})
	failed_invoices = frappe.db.count("VAT Invoice", {**valid_filters, "status": "Failed"})

	# Extra metric (non-currency) - unique customers
	unique_customers = frappe.get_all(
		"VAT Invoice", filters=valid_filters, distinct=True, pluck="customer_id"
	)
	unique_customers_count = len(unique_customers)

	# Aggregates (SUM)
	totals = frappe.db.get_value(
		"VAT Invoice",
		valid_filters,
		[
			"sum(txn_amount) as total_txn_amount",
			"sum(total_amount) as total_sales",
			"sum(total_sd_amount) as total_vat_amount",
			"sum(total_discount_amount) as total_discount_amount",
		],
		as_dict=True,
	)

	return [
		{"value": total_invoices, "label": _("Total Invoices"), "datatype": "Int", "indicator": "blue"},
		{"value": pending_invoices, "label": _("Pending"), "datatype": "Int", "indicator": "orange"},
		{"value": synced_invoices, "label": _("Synced"), "datatype": "Int", "indicator": "green"},
		{"value": failed_invoices, "label": _("Failed"), "datatype": "Int", "indicator": "red"},
		{
			"value": unique_customers_count,
			"label": _("Unique Customers"),
			"datatype": "Int",
			"indicator": "purple",
		},
		{
			"value": totals.total_txn_amount or 0,
			"label": _("Transaction Amount"),
			"datatype": "Currency",
			"indicator": "blue",
		},
		{
			"value": totals.total_sales or 0,
			"label": _("Total Sales"),
			"datatype": "Currency",
			"indicator": "green",
		},
		{
			"value": totals.total_vat_amount or 0,
			"label": _("Total VAT Amount"),
			"datatype": "Currency",
			"indicator": "orange",
		},
		{
			"value": totals.total_discount_amount or 0,
			"label": _("Total Discount"),
			"datatype": "Currency",
			"indicator": "red",
		},
	]


def get_branch_wise_chart(filters):
	filters = frappe._dict(filters or {})
	conditions = ["1=1"]

	if filters.get("from_date"):
		conditions.append(f"invoice_date >= '{filters.from_date}'")
	if filters.get("to_date"):
		conditions.append(f"invoice_date <= '{filters.to_date}'")
	if filters.get("status"):
		conditions.append(f"status = '{filters.status}'")

	where_clause = " AND ".join(conditions)

	# Get transaction amount per branch
	sales_data = frappe.db.sql(
		f"""
        SELECT branch, SUM(txn_amount) as total_txn
        FROM `tabVAT Invoice`
        WHERE {where_clause}
        GROUP BY branch
        ORDER BY total_txn DESC
    """,
		as_list=True,
	)

	labels = [row[0] or "Unknown" for row in sales_data]
	values = [row[1] or 0 for row in sales_data]

	return {
		"data": {"labels": labels, "datasets": [{"name": "Transaction Amount", "values": values}]},
		"type": "bar",
		"height": 300,
	}


def get_sales_trends_chart(filters):
	filters = frappe._dict(filters or {})

	# Remove non-doctype fields
	valid_filters = {}
	if filters.get("from_date") and filters.get("to_date"):
		valid_filters["invoice_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		valid_filters["invoice_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		valid_filters["invoice_date"] = ["<=", filters.to_date]

	# Get sales per day
	sales_data = frappe.get_all(
		"VAT Invoice",
		filters=valid_filters,
		fields=["invoice_date", "sum(total_amount) as total_sales"],
		group_by="DATE(invoice_date)",
		order_by="invoice_date asc",
		as_list=True,
	)

	# Format for chart
	labels = [str(row[0].date()) if hasattr(row[0], "date") else str(row[0]) for row in sales_data]
	values = [row[1] or 0 for row in sales_data]

	return {
		"data": {"labels": labels, "datasets": [{"name": "Sales", "values": values}]},
		"type": "line",  # Line chart
		"height": 300,
	}


def get_columns():
	return [
		{
			"fieldname": "name",
			"label": _("VAT Invoice Number"),
			"fieldtype": "Link",
			"options": "VAT Invoice",
			"width": 150,
		},
		{"fieldname": "invoice_number", "label": _("Invoice Number"), "fieldtype": "Data", "width": 120},
		{"fieldname": "invoice_date", "label": _("Invoice Date"), "fieldtype": "Datetime", "width": 130},
		{
			"fieldname": "branch",
			"label": _("Branch"),
			"fieldtype": "Link",
			"options": "Retailer Branch Registration",
			"width": 120,
		},  # 👈 Added Branch
		{"fieldname": "customer_id", "label": _("Customer ID"), "fieldtype": "Data", "width": 120},
		{"fieldname": "retailer_id", "label": _("Retailer ID"), "fieldtype": "Data", "width": 120},
		{"fieldname": "txn_amount", "label": _("Transaction Amount"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "total_sd_percentage", "label": _("SD %"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "total_sd_amount", "label": _("SD Amount"), "fieldtype": "Currency", "width": 120},
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
		{"fieldname": "payment_method", "label": _("Payment Method"), "fieldtype": "Data", "width": 120},
		{"fieldname": "order_id", "label": _("Order ID"), "fieldtype": "Data", "width": 120},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	filters = frappe._dict(filters or {})
	filter_conditions = {}

	if filters.get("invoice_number"):
		filter_conditions["invoice_number"] = ["like", f"%{filters.invoice_number}%"]
	if filters.get("order_id"):
		filter_conditions["order_id"] = ["like", f"%{filters.order_id}%"]
	if filters.get("status"):
		filter_conditions["status"] = filters.status
	if filters.get("branch"):
		filter_conditions["branch"] = filters.branch
	if filters.get("from_date") and filters.get("to_date"):
		filter_conditions["invoice_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		filter_conditions["invoice_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		filter_conditions["invoice_date"] = ["<=", filters.to_date]

	data = frappe.get_all(
		"VAT Invoice",
		fields=[
			"name",
			"invoice_number",
			"invoice_date",
			"branch",  # 👈 Added Branch
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
		],
		filters=filter_conditions,
		order_by="creation desc",
	)
	return data
