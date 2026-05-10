# Copyright (c) 2025, na and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
		{
			"label": _("Opening Balance Qty"),
			"fieldname": "opening_balance_qty",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": _("Opening Balance Value"),
			"fieldname": "opening_balance_value",
			"fieldtype": "Currency",
			"width": 180,
		},
		{"label": _("Production Qty"), "fieldname": "production_qty", "fieldtype": "Float", "width": 120},
		{
			"label": _("Production Value"),
			"fieldname": "production_value",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("Total Produced Qty"),
			"fieldname": "total_produced_qty",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Total Produced Value"),
			"fieldname": "total_produced_value",
			"fieldtype": "Currency",
			"width": 150,
		},
		{"label": _("Buyer Name"), "fieldname": "buyer_name", "fieldtype": "Data", "width": 150},
		{"label": _("Buyer Address"), "fieldname": "buyer_address", "fieldtype": "Data", "width": 200},
		{"label": _("BIN/NID"), "fieldname": "buyer_id", "fieldtype": "Data", "width": 120},
		{
			"label": _("Challan No"),
			"fieldname": "challan_no",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 200,
		},
		{"label": _("Challan Date"), "fieldname": "challan_date", "fieldtype": "Date", "width": 120},
		{"label": _("Item Description"), "fieldname": "item_description", "fieldtype": "Data", "width": 150},
		{"label": _("Quantity"), "fieldname": "qty", "fieldtype": "Float", "width": 120},
		{"label": _("Taxable Value"), "fieldname": "taxable_value", "fieldtype": "Currency", "width": 150},
		{
			"label": _("Supplementary Duty"),
			"fieldname": "supplementary_duty",
			"fieldtype": "Currency",
			"width": 180,
		},
		{"label": _("VAT"), "fieldname": "vat_amount", "fieldtype": "Currency", "width": 100},
		{
			"label": _("Closing Balance Qty"),
			"fieldname": "closing_balance_qty",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": _("Closing Balance Value"),
			"fieldname": "closing_balance_value",
			"fieldtype": "Currency",
			"width": 180,
		},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 150},
		{"label": _("Item Type"), "fieldname": "item_type", "fieldtype": "Data", "width": 100},
		# Added to distinguish item types
	]


def get_data(filters):
	conditions = get_conditions(filters)

	query = """
		SELECT
			sii.parent AS name,
			si.posting_date,
			si.customer,
			si.currency,
			si.customer_name as buyer_name,
			si.customer_address,
			si.tax_id as buyer_id,
			si.remarks,
			sii.item_code,
			sii.item_name,
			sii.qty,
			sii.rate,
			sii.amount,
			sii.net_amount,
			sii.item_tax_template,
			si.name as challan_no,
			si.posting_date as challan_date,
			it.is_stock_item,
			it.stock_uom
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
		INNER JOIN `tabItem` it ON sii.item_code = it.name
		WHERE {conditions} AND si.docstatus = 1
		ORDER BY si.posting_date ASC, si.name ASC
	"""

	invoices = frappe.db.sql(
		query.replace("{conditions}", conditions),
		filters,
		as_dict=True,
	)

	customer_cache = {}
	address_cache = {}

	data = []

	# Get opening balances for stock items
	opening_balances = get_opening_balances(filters)

	for i, row in enumerate(invoices, start=1):
		item_code = row.get("item_code")
		is_stock_item = row.get("is_stock_item", 0)

		if is_stock_item:
			# Stock item calculations
			opening_balance_qty = opening_balances.get(item_code, {}).get("qty", 0)
			opening_balance_value = opening_balances.get(item_code, {}).get("value", 0)

			# Production quantity (for stock items, this would come from production records)
			production_qty = get_production_qty(item_code, filters)
			production_value = get_production_value(item_code, filters)

			# Total produced (cumulative)
			total_produced_qty = production_qty
			total_produced_value = production_value

			# Closing balance for stock items
			closing_balance_qty = opening_balance_qty + production_qty - row.get("qty", 0)
			closing_balance_value = opening_balance_value + production_value - row.get("amount", 0)

			item_type = "Stock Item"
		else:
			# Service item calculations (as per your current logic)
			opening_balance_qty = 0
			opening_balance_value = 0

			production_qty = row.get("qty", 0)
			production_value = row.get("amount", 0)

			total_produced_qty = production_qty
			total_produced_value = production_value

			closing_balance_qty = 0
			closing_balance_value = 0

			item_type = "Service Item"

		# Calculate VAT amount
		vat_amount = calculate_vat_amount(
			row.get("item_tax_template"), row.get("net_amount"), filters.get("company")
		)

		# Get customer BIN/NID
		customer = row.get("customer")
		if customer and customer not in customer_cache:
			customer_cache[customer] = frappe.db.get_value(
				"Customer", customer, "custom_binvat_registration_no"
			)
		row["buyer_id"] = customer_cache.get(customer) or row.get("buyer_id")

		# Get formatted address
		buyer_address = get_formatted_address(row.get("customer_address"), address_cache)

		# Prepare data row
		data_row = {
			"sl_no": i,
			"posting_date": row.get("posting_date"),
			"opening_balance_qty": opening_balance_qty,
			"opening_balance_value": opening_balance_value,
			"production_qty": production_qty,
			"production_value": production_value,
			"total_produced_qty": total_produced_qty,
			"total_produced_value": total_produced_value,
			"buyer_name": row.get("buyer_name"),
			"buyer_address": buyer_address,
			"buyer_id": row.get("buyer_id"),
			"challan_no": row.get("challan_no"),
			"challan_date": row.get("challan_date"),
			"item_description": row.get("item_name"),
			"qty": row.get("qty"),
			"taxable_value": row.get("amount"),
			"supplementary_duty": 0,
			"vat_amount": vat_amount,
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
		conditions += " AND si.posting_date >= %(from_date)s"
	if filters.get("to_date"):
		conditions += " AND si.posting_date <= %(to_date)s"
	if filters.get("company"):
		conditions += " AND si.company = %(company)s"
	if filters.get("customer"):
		conditions += " AND si.customer = %(customer)s"
	if filters.get("item_type"):
		if filters.get("item_type") == "Stock Item":
			conditions += " AND it.is_stock_item = 1"
		elif filters.get("item_type") == "Service Item":
			conditions += " AND it.is_stock_item = 0"
	return conditions


def get_opening_balances(filters):
	"""Get opening balances for stock items as of from_date"""
	opening_balances = {}

	if not filters.get("from_date"):
		return opening_balances

	# Get stock ledger entries for opening balance
	sle_data = frappe.db.sql(
		"""
							 SELECT item_code,
									SUM(actual_qty) as qty,
									SUM(stock_value_difference) as value
							 FROM `tabStock Ledger Entry`
							 WHERE posting_date
								 < %(from_date)s
							   AND company = %(company)s
							 GROUP BY item_code
							 """,
		filters,
		as_dict=True,
	)

	for entry in sle_data:
		opening_balances[entry.item_code] = {"qty": entry.qty, "value": entry.value}

	return opening_balances


def get_production_qty(item_code, filters):
	"""Get production quantity for stock items within date range"""
	production_qty = frappe.db.sql(
		"""
								   SELECT SUM(sed.qty) as total_qty
								   FROM `tabStock Entry Detail` sed
											INNER JOIN `tabStock Entry` se ON sed.parent = se.name
								   WHERE sed.item_code = %s
									 AND se.posting_date BETWEEN %s AND %s
									 AND se.docstatus = 1
									 AND sed.s_warehouse IS NULL
								   """,
		(item_code, filters.get("from_date"), filters.get("to_date")),
	)

	return flt(production_qty[0][0]) if production_qty else 0


def get_production_value(item_code, filters):
	"""Get production value for stock items within date range"""
	production_value = frappe.db.sql(
		"""
									 SELECT SUM(sed.amount) as total_value
									 FROM `tabStock Entry Detail` sed
											  INNER JOIN `tabStock Entry` se ON sed.parent = se.name
									 WHERE sed.item_code = %s
									   AND se.posting_date BETWEEN %s AND %s
									   AND se.docstatus = 1
									   AND sed.s_warehouse IS NULL
									 """,
		(item_code, filters.get("from_date"), filters.get("to_date")),
	)

	return flt(production_value[0][0]) if production_value else 0


def get_formatted_address(address_name, address_cache):
	"""Get formatted address from address name"""
	if not address_name:
		return ""

	if address_name not in address_cache:
		address_doc = frappe.db.get_value(
			"Address",
			address_name,
			["address_line1", "address_line2", "city", "state", "country", "pincode"],
			as_dict=True,
		)
		if address_doc:
			address_display = ", ".join(
				[
					line.strip()
					for line in [
						address_doc.address_line1,
						address_doc.address_line2,
						address_doc.city,
						address_doc.state,
						address_doc.country,
						address_doc.pincode,
					]
					if line and line.strip()
				]
			)
			address_cache[address_name] = address_display
	return address_cache.get(address_name, "")


def calculate_vat_amount(item_tax_template, net_amount, company):
	"""Calculate VAT amount based on item tax template"""
	if not item_tax_template or not net_amount:
		return 0

	try:
		tax_rate = frappe.db.sql(
			"""
								 SELECT tax_rate
								 FROM `tabItem Tax Template Detail`
								 WHERE parent = %s
								   AND parenttype = 'Item Tax Template' LIMIT 1
								 """,
			item_tax_template,
		)

		if tax_rate and tax_rate[0][0]:
			return net_amount * (tax_rate[0][0] / 100)

	except Exception:
		frappe.log_error(frappe.get_traceback(), "VAT Calculation Error")

	return 0
