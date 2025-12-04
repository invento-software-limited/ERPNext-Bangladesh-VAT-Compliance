# Copyright (c) 2025, na and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.utils import flt


def execute(filters=None):
	if not filters:
		filters = {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	return [
		{"label": "Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
		{
			"label": "Opening Balance Qty",
			"fieldname": "opening_balance_qty",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": "Opening Balance Value",
			"fieldname": "opening_balance_value",
			"fieldtype": "Currency",
			"width": 180,
		},
		{
			"label": "Invoice No",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 200,
		},
		{"label": "Challan Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
		{"label": "Supplier Name", "fieldname": "supplier_name", "fieldtype": "Data", "width": 150},
		{
			"label": "Supplier Address",
			"fieldname": "supplier_address_display",
			"fieldtype": "Data",
			"width": 200,
		},
		{"label": "BIN/NID", "fieldname": "supplier_bin_no", "fieldtype": "Data", "width": 120},
		{
			"label": "Description",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{"label": "Quantity", "fieldname": "qty", "fieldtype": "Float", "width": 120},
		{"label": "Value (Excl. Tax)", "fieldname": "base_net_amount", "fieldtype": "Currency", "width": 150},
		{
			"label": "Supplementary Duty",
			"fieldname": "supplementary_duty",
			"fieldtype": "Currency",
			"width": 180,
		},
		{"label": "VAT", "fieldname": "vat_amount", "fieldtype": "Currency", "width": 100},
		{"label": "Total Quantity", "fieldname": "total_qty", "fieldtype": "Float", "width": 120},
		{"label": "Total (Incl. Tax)", "fieldname": "total_amount", "fieldtype": "Currency", "width": 150},
		{
			"label": "Stock Consumption Quantity",
			"fieldname": "stock_consumption_qty",
			"fieldtype": "Float",
			"width": 220,
		},
		{
			"label": "Stock Consumption Value",
			"fieldname": "stock_consumption_value",
			"fieldtype": "Currency",
			"width": 220,
		},
		{
			"label": "Closing Balance Qty",
			"fieldname": "closing_balance_qty",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": "Closing Balance Value",
			"fieldname": "closing_balance_value",
			"fieldtype": "Currency",
			"width": 180,
		},
		{"label": "Remarks", "fieldname": "remarks", "fieldtype": "Data", "width": 120},
		{"label": "Item Type", "fieldname": "item_type", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	conditions = get_conditions(filters)

	invoices = frappe.db.sql(
		f"""
        SELECT
            pii.parent AS name,
            pi.posting_date,
            pi.supplier,
            pi.currency,
            pi.supplier_name,
            pi.billing_address as supplier_address,
            pi.remarks,
            pii.item_code,
            pii.item_name,
            pii.qty,
            pii.rate,
            pii.amount,
            pii.net_amount,
            pii.base_net_amount,
            pii.item_tax_template,
            pii.item_tax_rate,
            it.is_stock_item,
            it.stock_uom
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
        INNER JOIN `tabItem` it ON pii.item_code = it.name
        WHERE {conditions} AND pi.docstatus = 1
        ORDER BY pi.posting_date ASC, pi.name ASC
    """,
		filters,
		as_dict=True,
	)

	supplier_cache = {}
	address_cache = {}
	data = []

	opening_balances = get_opening_balances(filters)

	for i, row in enumerate(invoices, start=1):
		item_code = row.get("item_code")
		is_stock_item = row.get("is_stock_item", 0)

		if is_stock_item:
			opening_balance_qty = opening_balances.get(item_code, {}).get("qty", 0)
			opening_balance_value = opening_balances.get(item_code, {}).get("value", 0)

			purchase_qty = row.get("qty", 0)
			purchase_value = row.get("base_net_amount", 0) or row.get("net_amount", 0)

			production_consumption_qty = get_stock_consumption(item_code, filters)
			production_consumption_value = get_stock_consumption_value(item_code, filters)

			closing_balance_qty = opening_balance_qty + purchase_qty - production_consumption_qty
			closing_balance_value = opening_balance_value + purchase_value - production_consumption_value

			item_type = "Stock Item"
		else:
			opening_balance_qty = 0
			opening_balance_value = 0

			purchase_qty = row.get("qty", 0)
			purchase_value = row.get("base_net_amount", 0) or row.get("net_amount", 0)

			production_consumption_qty = row.get("qty", 0)
			production_consumption_value = row.get("base_net_amount", 0) or row.get("net_amount", 0)

			closing_balance_qty = 0
			closing_balance_value = 0

			item_type = "Service Item"

		tax_rows = json.loads(row.get("item_tax_rate", "{}"))

		if tax_rows:
			first_key = next(iter(tax_rows))
			tax_value = tax_rows[first_key]
			if isinstance(tax_value, dict):
				tax_rate = tax_value.get("tax_rate", 0)
			else:
				tax_rate = tax_value
		else:
			tax_rate = 0

		vat_amount = row.get("net_amount", 0) * (tax_rate / 100)

		# Get supplier BIN/NID
		supplier = row.get("supplier")
		if supplier and supplier not in supplier_cache:
			supplier_cache[supplier] = frappe.db.get_value("Supplier", supplier, "custom_bin_no")
		row["supplier_bin_no"] = supplier_cache.get(supplier)

		address_name = row.get("supplier_address")
		supplier_address_display = ""
		if address_name:
			if address_name not in address_cache:
				address_doc = frappe.db.get_value(
					"Address",
					address_name,
					["address_line1", "address_line2", "city", "state", "country", "pincode"],
					as_dict=True,
				)
				if address_doc:
					address_display = ", ".join(
						filter(
							None,
							[
								address_doc.address_line1,
								address_doc.address_line2,
								address_doc.city,
								address_doc.state,
								address_doc.country,
								address_doc.pincode,
							],
						)
					)
					address_cache[address_name] = address_display
			supplier_address_display = address_cache.get(address_name, "")

		data_row = {
			"sl_no": i,
			"posting_date": row.get("posting_date"),
			"opening_balance_qty": opening_balance_qty,
			"opening_balance_value": opening_balance_value,
			"name": row.get("name"),
			"supplier_name": row.get("supplier_name"),
			"supplier_address_display": supplier_address_display,
			"supplier_bin_no": row.get("supplier_bin_no"),
			"item_code": row.get("item_name") or row.get("item_code"),
			"qty": row.get("qty"),
			"base_net_amount": row.get("base_net_amount") or row.get("net_amount", 0),
			"supplementary_duty": 0,
			"vat_amount": vat_amount,
			"total_qty": row.get("qty"),
			"total_amount": row.get("amount") + vat_amount,
			"stock_consumption_qty": production_consumption_qty,
			"stock_consumption_value": production_consumption_value,
			"closing_balance_qty": closing_balance_qty,
			"closing_balance_value": closing_balance_value,
			"remarks": row.get("remarks") or "",
			"item_type": item_type,
		}

		data.append(data_row)

	return data


def get_conditions(filters):
	conditions = "1=1"
	if filters.get("from_date"):
		conditions += " AND pi.posting_date >= %(from_date)s"
	if filters.get("to_date"):
		conditions += " AND pi.posting_date <= %(to_date)s"
	if filters.get("company"):
		conditions += " AND pi.company = %(company)s"
	if filters.get("supplier"):
		conditions += " AND pi.supplier = %(supplier)s"
	if filters.get("item_type"):
		if filters.get("item_type") == "Stock Item":
			conditions += " AND it.is_stock_item = 1"
		elif filters.get("item_type") == "Service Item":
			conditions += " AND it.is_stock_item = 0"
	return conditions


def get_opening_balances(filters):
	"""Get opening balances for stock items as of from_date"""
	opening_balances = {}

	if not filters.get("from_date") or not filters.get("company"):
		return opening_balances

	sle_data = frappe.db.sql(
		"""
							 SELECT item_code,
									SUM(actual_qty) as qty,
									SUM(stock_value_difference) as value
							 FROM `tabStock Ledger Entry`
							 WHERE posting_date
								 < %(from_date)s
							   AND company = %(company)s
							   AND is_cancelled = 0
							 GROUP BY item_code
							 """,
		filters,
		as_dict=True,
	)

	for entry in sle_data:
		opening_balances[entry.item_code] = {"qty": entry.qty, "value": entry.value}

	return opening_balances


def get_stock_consumption(item_code, filters):
	"""Get stock consumption quantity for production within date range"""
	consumption_qty = frappe.db.sql(
		"""
									SELECT SUM(sed.qty) as total_qty
									FROM `tabStock Entry Detail` sed
											 INNER JOIN `tabStock Entry` se ON sed.parent = se.name
									WHERE sed.item_code = %s
									  AND se.posting_date BETWEEN %s AND %s
									  AND se.docstatus = 1
									  AND se.purpose = 'Manufacture'
									  AND sed.s_warehouse IS NOT NULL
									  AND sed.t_warehouse IS NULL
									""",
		(item_code, filters.get("from_date"), filters.get("to_date")),
	)

	return flt(consumption_qty[0][0]) if consumption_qty else 0


def get_stock_consumption_value(item_code, filters):
	"""Get stock consumption value for production within date range"""
	consumption_value = frappe.db.sql(
		"""
									  SELECT SUM(sed.amount) as total_value
									  FROM `tabStock Entry Detail` sed
											   INNER JOIN `tabStock Entry` se ON sed.parent = se.name
									  WHERE sed.item_code = %s
										AND se.posting_date BETWEEN %s AND %s
										AND se.docstatus = 1
										AND se.purpose = 'Manufacture'
										AND sed.s_warehouse IS NOT NULL
										AND sed.t_warehouse IS NULL
									  """,
		(item_code, filters.get("from_date"), filters.get("to_date")),
	)

	return flt(consumption_value[0][0]) if consumption_value else 0
