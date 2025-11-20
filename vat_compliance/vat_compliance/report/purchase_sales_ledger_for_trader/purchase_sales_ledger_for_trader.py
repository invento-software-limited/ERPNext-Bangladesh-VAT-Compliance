# Copyright (c) 2025, na and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
		{"label": _("Opening Balance Qty"), "fieldname": "opening_balance_qty",
		 "fieldtype": "Float", "width": 120},
		{"label": _("Opening Balance Value"), "fieldname": "opening_balance_value",
		 "fieldtype": "Currency", "width": 140},
		{"label": _("Purchase Qty"), "fieldname": "purchase_qty", "fieldtype": "Float",
		 "width": 110},
		{"label": _("Purchase Value"), "fieldname": "purchase_value", "fieldtype": "Currency",
		 "width": 130},
		{"label": _("Total Stock Qty"), "fieldname": "total_stock_qty", "fieldtype": "Float",
		 "width": 120},
		{"label": _("Total Stock Value"), "fieldname": "total_stock_value",
		 "fieldtype": "Currency", "width": 140},
		{"label": _("Seller Name"), "fieldname": "seller_name", "fieldtype": "Data", "width": 150},
		{"label": _("Seller Address"), "fieldname": "seller_address", "fieldtype": "Data",
		 "width": 200},
		{"label": _("Seller Registration/NID"), "fieldname": "seller_id", "fieldtype": "Data",
		 "width": 130},
		{"label": _("Purchase Challan No"), "fieldname": "purchase_challan_no",
		 "fieldtype": "Data", "width": 120},
		{"label": _("Purchase Challan Date"), "fieldname": "purchase_challan_date",
		 "fieldtype": "Date", "width": 100},
		{"label": _("Goods Description"), "fieldname": "item_description", "fieldtype": "Data",
		 "width": 160},
		{"label": _("Quantity Sold/Supplied"), "fieldname": "qty", "fieldtype": "Float",
		 "width": 110},
		{"label": _("Taxable Value"), "fieldname": "taxable_value", "fieldtype": "Currency",
		 "width": 120},
		{"label": _("Supplementary Duty"), "fieldname": "supplementary_duty",
		 "fieldtype": "Currency", "width": 130},
		{"label": _("VAT"), "fieldname": "vat_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Purchaser Name"), "fieldname": "purchaser_name", "fieldtype": "Data",
		 "width": 150},
		{"label": _("Purchaser Address"), "fieldname": "purchaser_address", "fieldtype": "Data",
		 "width": 200},
		{"label": _("Purchaser Registration/NID"), "fieldname": "purchaser_id",
		 "fieldtype": "Data", "width": 140},
		{"label": _("Sales Invoice No"), "fieldname": "sales_invoice_no", "fieldtype": "Link",
		 "options": "Sales Invoice", "width": 120},
		{"label": _("Sales Invoice Date"), "fieldname": "sales_invoice_date", "fieldtype": "Date",
		 "width": 100},
		{"label": _("Closing Balance Qty"), "fieldname": "closing_balance_qty",
		 "fieldtype": "Float", "width": 130},
		{"label": _("Closing Balance Value"), "fieldname": "closing_balance_value",
		 "fieldtype": "Currency", "width": 140},
		{"label": _("Comments"), "fieldname": "remarks", "fieldtype": "Data", "width": 130},
		{"label": _("Item Type"), "fieldname": "item_type", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	data = []

	# Get purchase data with item type information
	purchase_data = get_purchase_data(filters)

	# Get sales data with item type information
	sales_data = get_sales_data(filters)

	# Combine and process data with stock calculations
	data = combine_purchase_sales_data(purchase_data, sales_data, filters)

	return data


def get_purchase_data(filters):
	conditions = get_purchase_conditions(filters)

	purchase_invoices = frappe.db.sql(f"""
		SELECT
			pi.name as purchase_invoice_no,
			pi.posting_date,
			pi.supplier as seller_name,
			pi.supplier_name,
			pi.supplier_address,
			pi.tax_id as seller_id,
			pi.remarks,
			pi.company,
			pii.item_code,
			pii.item_name as item_description,
			pii.qty as purchase_qty,
			pii.rate,
			pii.amount as purchase_value,
			pii.net_amount as taxable_value,
			pii.item_tax_template,
			pi.name as purchase_challan_no,
			pi.posting_date as purchase_challan_date,
			it.is_stock_item,
			it.stock_uom
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
		INNER JOIN `tabItem` it ON pii.item_code = it.name
		WHERE pi.docstatus = 1 {conditions}
		ORDER BY pi.posting_date, pi.name
	""", filters, as_dict=1)

	# Calculate taxes for each purchase item
	for invoice in purchase_invoices:
		invoice.vat_amount = calculate_purchase_vat(
			invoice.item_tax_template,
			invoice.taxable_value,
			invoice.company
		)
		invoice.supplementary_duty = calculate_supplementary_duty(
			invoice.item_tax_template,
			invoice.taxable_value,
			invoice.company
		)

		# Get formatted address
		invoice.seller_address = get_address_display(invoice.supplier_address)

		# Set item type
		invoice.item_type = "Stock Item" if invoice.is_stock_item else "Service Item"

	return purchase_invoices


def get_sales_data(filters):
	conditions = get_sales_conditions(filters)

	sales_invoices = frappe.db.sql(f"""
		SELECT
			si.name as sales_invoice_no,
			si.posting_date as sales_invoice_date,
			si.customer as purchaser_name,
			si.customer_name,
			si.customer_address,
			si.tax_id as purchaser_id,
			si.remarks,
			si.company,
			sii.item_code,
			sii.item_name as item_description,
			sii.qty,
			sii.rate,
			sii.amount as taxable_value,
			sii.net_amount,
			sii.item_tax_template,
			it.is_stock_item,
			it.stock_uom
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
		INNER JOIN `tabItem` it ON sii.item_code = it.name
		WHERE si.docstatus = 1 {conditions}
		ORDER BY si.posting_date, si.name
	""", filters, as_dict=1)

	# Calculate taxes for each sales item
	for invoice in sales_invoices:
		invoice.vat_amount = calculate_sales_vat(
			invoice.item_tax_template,
			invoice.taxable_value,
			invoice.company
		)
		invoice.supplementary_duty = calculate_supplementary_duty(
			invoice.item_tax_template,
			invoice.taxable_value,
			invoice.company
		)

		# Get formatted address
		invoice.purchaser_address = get_address_display(invoice.customer_address)

		# Set item type
		invoice.item_type = "Stock Item" if invoice.is_stock_item else "Service Item"

	return sales_invoices


def combine_purchase_sales_data(purchase_data, sales_data, filters):
	combined_data = []
	sl_no = 1

	# Get opening balances for all items
	opening_balances = get_opening_balances(filters)

	# Track running balances by item
	item_balances = {}

	# Initialize item balances from opening balances
	for item_code, balance in opening_balances.items():
		item_balances[item_code] = {
			'qty': balance.get('qty', 0),
			'value': balance.get('value', 0)
		}

	# Process purchase transactions first
	for purchase in purchase_data:
		item_code = purchase.item_code
		is_stock_item = purchase.is_stock_item

		if is_stock_item:
			# Stock item calculations
			opening_balance_qty = opening_balances.get(item_code, {}).get('qty', 0)
			opening_balance_value = opening_balances.get(item_code, {}).get('value', 0)

			# Update running balance for the item
			if item_code not in item_balances:
				item_balances[item_code] = {'qty': 0, 'value': 0}

			current_balance = item_balances[item_code]

			# Total stock after this purchase
			total_stock_qty = current_balance['qty'] + purchase.purchase_qty
			total_stock_value = current_balance['value'] + purchase.purchase_value

			# Update running balance
			item_balances[item_code]['qty'] = total_stock_qty
			item_balances[item_code]['value'] = total_stock_value

			# Closing balance (same as total stock after purchase)
			closing_balance_qty = total_stock_qty
			closing_balance_value = total_stock_value
		else:
			# Service item calculations (original logic)
			opening_balance_qty = 0
			opening_balance_value = 0
			total_stock_qty = 0
			total_stock_value = 0
			closing_balance_qty = 0
			closing_balance_value = 0

		row = {
			"sl_no": sl_no,
			"posting_date": purchase.posting_date,
			"opening_balance_qty": opening_balance_qty,
			"opening_balance_value": opening_balance_value,
			"purchase_qty": purchase.purchase_qty,
			"purchase_value": purchase.purchase_value,
			"total_stock_qty": total_stock_qty,
			"total_stock_value": total_stock_value,
			"seller_name": purchase.seller_name,
			"seller_address": purchase.seller_address,
			"seller_id": purchase.seller_id,
			"purchase_challan_no": purchase.purchase_challan_no,
			"purchase_challan_date": purchase.purchase_challan_date,
			"item_description": purchase.item_description,
			"qty": 0,  # No sales in purchase rows
			"taxable_value": purchase.taxable_value,
			"supplementary_duty": purchase.supplementary_duty,
			"vat_amount": purchase.vat_amount,
			"purchaser_name": "",
			"purchaser_address": "",
			"purchaser_id": "",
			"sales_invoice_no": "",
			"sales_invoice_date": None,
			"closing_balance_qty": closing_balance_qty,
			"closing_balance_value": closing_balance_value,
			"remarks": purchase.remarks,
			"item_type": purchase.item_type,
			"currency": frappe.get_cached_value('Company', filters.get('company'),
												'default_currency')
		}

		combined_data.append(row)
		sl_no += 1

	# Process sales transactions
	for sales in sales_data:
		item_code = sales.item_code
		is_stock_item = sales.is_stock_item

		if is_stock_item:
			# Stock item calculations
			if item_code in item_balances:
				current_balance = item_balances[item_code]
				opening_balance_qty = current_balance['qty']
				opening_balance_value = current_balance['value']
			else:
				opening_balance_qty = opening_balances.get(item_code, {}).get('qty', 0)
				opening_balance_value = opening_balances.get(item_code, {}).get('value', 0)

			# Total stock before sales (same as opening for this transaction)
			total_stock_qty = opening_balance_qty
			total_stock_value = opening_balance_value

			# Calculate closing balance after sales
			closing_balance_qty = opening_balance_qty - sales.qty
			closing_balance_value = opening_balance_value - sales.taxable_value

			# Update running balance
			if item_code not in item_balances:
				item_balances[item_code] = {'qty': 0, 'value': 0}

			item_balances[item_code]['qty'] = closing_balance_qty
			item_balances[item_code]['value'] = closing_balance_value
		else:
			# Service item calculations (original logic)
			opening_balance_qty = 0
			opening_balance_value = 0
			total_stock_qty = 0
			total_stock_value = 0
			closing_balance_qty = 0
			closing_balance_value = 0

		row = {
			"sl_no": sl_no,
			"posting_date": sales.sales_invoice_date,
			"opening_balance_qty": opening_balance_qty,
			"opening_balance_value": opening_balance_value,
			"purchase_qty": 0,  # No purchase in sales rows
			"purchase_value": 0,
			"total_stock_qty": total_stock_qty,
			"total_stock_value": total_stock_value,
			"seller_name": "",
			"seller_address": "",
			"seller_id": "",
			"purchase_challan_no": "",
			"purchase_challan_date": None,
			"item_description": sales.item_description,
			"qty": sales.qty,
			"taxable_value": sales.taxable_value,
			"supplementary_duty": sales.supplementary_duty,
			"vat_amount": sales.vat_amount,
			"purchaser_name": sales.purchaser_name,
			"purchaser_address": sales.purchaser_address,
			"purchaser_id": sales.purchaser_id,
			"sales_invoice_no": sales.sales_invoice_no,
			"sales_invoice_date": sales.sales_invoice_date,
			"closing_balance_qty": closing_balance_qty,
			"closing_balance_value": closing_balance_value,
			"remarks": sales.remarks,
			"item_type": sales.item_type,
			"currency": frappe.get_cached_value('Company', filters.get('company'),
												'default_currency')
		}

		combined_data.append(row)
		sl_no += 1

	# Sort by date for final output
	combined_data.sort(key=lambda x: x['posting_date'])

	# Reassign serial numbers after sorting
	for i, row in enumerate(combined_data, 1):
		row['sl_no'] = i

	return combined_data


def get_opening_balances(filters):
	"""Get opening balances for stock items as of from_date"""
	opening_balances = {}

	if not filters.get("from_date") or not filters.get("company"):
		return opening_balances

	# Get stock ledger entries for opening balance
	sle_data = frappe.db.sql("""
							 SELECT item_code,
									SUM(actual_qty) as qty,
									SUM(stock_value_difference) as value
							 FROM `tabStock Ledger Entry`
							 WHERE posting_date
								 < %(from_date)s
							   AND company = %(company)s
							   AND is_cancelled = 0
							 GROUP BY item_code
							 """, filters, as_dict=True)

	for entry in sle_data:
		opening_balances[entry.item_code] = {
			'qty': entry.qty,
			'value': entry.value
		}

	return opening_balances


def get_purchase_conditions(filters):
	conditions = ""
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


def get_sales_conditions(filters):
	conditions = ""
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


def calculate_purchase_vat(item_tax_template, taxable_value, company):
	"""Calculate VAT for purchase items"""
	if not item_tax_template or not taxable_value:
		return 0

	try:
		tax_rate = frappe.db.sql("""
								 SELECT tax_rate
								 FROM `tabItem Tax Template Detail`
								 WHERE parent = %s
								   AND parenttype = 'Item Tax Template'
								 """, item_tax_template)

		if tax_rate and tax_rate[0][0]:
			return taxable_value * (tax_rate[0][0] / 100)
	except:
		pass

	return 0


def calculate_sales_vat(item_tax_template, taxable_value, company):
	"""Calculate VAT for sales items"""
	return calculate_purchase_vat(item_tax_template, taxable_value, company)


def calculate_supplementary_duty(item_tax_template, taxable_value, company):
	"""Calculate supplementary duty if applicable"""
	# Implement based on your tax configuration
	return 0


def get_address_display(address_name):
	"""Get formatted address display"""
	if not address_name:
		return ""

	try:
		address = frappe.get_doc("Address", address_name)
		return address.get_display()
	except:
		return ""
