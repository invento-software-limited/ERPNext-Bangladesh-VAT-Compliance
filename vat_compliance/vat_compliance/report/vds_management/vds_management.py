# Copyright (c) 2025, na and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.utils import flt


def execute(filters=None):
	"""Execute the report."""
	data = get_data(filters)
	columns = get_columns()
	message = get_message()
	return columns, data, message


def get_columns():
	"""Return columns for the report."""
	return [
		{"fieldname": "payment_date", "label": "Payment Date", "fieldtype": "Date", "width": 120},
		{"fieldname": "payment_month", "label": "Payment Month", "fieldtype": "Data", "width": 120},
		{
			"fieldname": "invoice_id",
			"label": "Invoice Number",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 200,
		},
		{"fieldname": "invoice_status", "label": "Invoice Status", "fieldtype": "Data", "width": 120},
		{
			"fieldname": "supplier_name",
			"label": "Supplier Name",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 150,
		},
		{"fieldname": "invoice_amount", "label": "Invoice Amount", "fieldtype": "Currency", "width": 120},
		{"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 120},
		{
			"fieldname": "payment_entry_id",
			"label": "Payment Entry",
			"fieldtype": "Link",
			"options": "Payment Entry",
			"width": 200,
		},
		{
			"fieldname": "account_credit",
			"label": "Account head",
			"fieldtype": "Link",
			"options": "Account",
			"width": 240,
		},
		{
			"fieldname": "liability_head",
			"label": "Liability head",
			"fieldtype": "Link",
			"options": "Account",
			"width": 240,
		},
		{"fieldname": "vds_amount", "label": "VDS Amount", "fieldtype": "Currency", "width": 120},
		{
			"fieldname": "section_ref",
			"label": "Section Ref",
			"fieldtype": "Link",
			"options": "Item Tax Template",
			"width": 120,
		},
		{"fieldname": "applied_rate", "label": "Applied Rate", "fieldtype": "Percent", "width": 120},
		{
			"fieldname": "fiscal_year",
			"label": "Fiscal Year",
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"width": 120,
		},
	]


def get_message():
	"""Return the report legend."""
	return """<span class="indicator red">
		DNGT : Deducted but not deposited into govt. treasury
		</span>&nbsp;&nbsp;&nbsp;&nbsp;
		<span class="indicator green">
		DDGT : Deducted and deposited into govt. treasury
		</span>"""


def _build_base_conditions():
	"""Return base SQL conditions."""
	return [
		"per.reference_doctype = 'Purchase Invoice'",
		"per.custom_vdsvcs = 'Withheld'",
		"pe.payment_type = 'Pay'",
		"pe.docstatus = 1",
	]


def _build_filter_conditions(filters):
	"""Return SQL conditions based on filters."""
	filter_conditions = []
	filter_mapping = [
		("from_date", "pe.posting_date >= %(from_date)s"),
		("to_date", "pe.posting_date <= %(to_date)s"),
		("invoice_status", "pi.status = %(invoice_status)s"),
		("supplier", "pe.party = %(supplier)s"),
		("company", "pe.company = %(company)s"),
	]

	for filter_key, condition in filter_mapping:
		if filters.get(filter_key):
			filter_conditions.append(condition)

	return filter_conditions


def _get_payment_entry_data(filters):
	"""Fetch payment entry data from the database."""
	base_conditions = _build_base_conditions()
	filter_conditions = _build_filter_conditions(filters)

	all_conditions = base_conditions + filter_conditions
	where_clause = " AND ".join(all_conditions)

	query = f"""
		SELECT
			per.reference_name as invoice_id,
			pe.posting_date as payment_date,
			pe.party as supplier_name,
			pi.status as invoice_status,
			pe.name as payment_entry_id,
			pi.grand_total as invoice_amount,
			per.allocated_amount as vds_amount,
			per.name as child_name,
			fy.name as fiscal_year
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe ON per.parent = pe.name
		INNER JOIN `tabPurchase Invoice` pi ON per.reference_name = pi.name
		LEFT JOIN `tabFiscal Year` fy ON pe.posting_date BETWEEN fy.year_start_date AND fy.year_end_date
		WHERE {where_clause}
		ORDER BY pe.posting_date DESC, pe.creation DESC
	"""

	return frappe.db.sql(query, filters, as_dict=True)


def _get_journal_entry_status(child_name):
	"""Get journal entry status for a payment entry reference."""
	if not child_name:
		return None

	je_account = frappe.db.get_all(
		"Journal Entry Account",
		filters={"reference_detail_no": ["like", f"%{child_name}%"], "custom_tax_type": "VAT"},
		fields=["parent"],
	)

	if not je_account:
		return None

	if je_account[0] and not je_account[0].get("parent"):
		return None

	je_doc = frappe.get_doc("Journal Entry", je_account[0]["parent"])

	if je_doc.docstatus == 1:
		return "DDGT"

	return None


def _get_tax_template_groups(invoice_doc, allocated_amount):
	"""Get grouped tax template details for an invoice based on allocated amount."""
	if not invoice_doc:
		return []

	groups = []

	# Calculate total net amount of taxable items
	taxable_items = [
		item
		for item in invoice_doc.items
		if item.get("item_tax_template") and flt(item.get("net_amount")) > 0
	]
	total_net_amount = sum(flt(item.get("net_amount", 0)) for item in taxable_items)

	if not total_net_amount:
		return []

	allocation_ratio = min(flt(allocated_amount) / total_net_amount, 1.0)

	for item in taxable_items:
		tax_category = item.get("item_tax_template")

		# Parse item_tax_rate
		tax_rows = json.loads(item.get("item_tax_rate", "{}"))
		if not tax_rows:
			continue

		first_key = next(iter(tax_rows))
		tax_value = tax_rows[first_key]

		if isinstance(tax_value, dict):
			tax_rate = tax_value.get("tax_rate", 0)
		else:
			tax_rate = tax_value

		account_credit = item.get("expense_account")
		liability_head = first_key
		item_net_amount = flt(item.get("net_amount", 0))

		# Calculate allocated amount for this item
		item_allocated_amount = item_net_amount * allocation_ratio

		# Calculate VDS amount
		vds_amount = item_allocated_amount * (tax_rate / 100)

		if not vds_amount:
			continue

		# Group allocation
		existing_group = next(
			(
				group
				for group in groups
				if group["account_credit"] == account_credit
				and group["liability_head"] == liability_head
				and group["section_ref"] == tax_category
				and group["applied_rate"] == tax_rate
			),
			None,
		)

		if existing_group:
			existing_group["vds_amount"] += vds_amount
			existing_group["net_amount"] += item_allocated_amount
		else:
			groups.append(
				{
					"account_credit": account_credit,
					"liability_head": liability_head,
					"vds_amount": vds_amount,
					"section_ref": tax_category,
					"applied_rate": tax_rate,
					"net_amount": item_allocated_amount,
				}
			)

	return groups


@frappe.whitelist()
def make_journal_entry(rows):
	"""Create a Journal Entry for the selected rows."""
	if isinstance(rows, str):
		rows = json.loads(rows)

	if not rows:
		frappe.throw("No rows selected")

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "VAT Payment Entry"
	je.posting_date = frappe.utils.nowdate()

	accounts = []

	for row in rows:
		accounts.append(
			{
				"account": row.get("liability_head"),
				"debit_in_account_currency": row.get("vds_amount"),
				"reference_detail_no": row.get("child_name"),
				"custom_tax_type": "VAT",
			}
		)

	je.set("accounts", accounts)
	je.insert()
	return je.name


def _process_data_row(row, invoice_docs):
	"""Process a single data row and return list of rows (parent + children)."""
	row["check"] = 0
	row["supplier_name"] = row.get("supplier_name")

	# Set status based on journal entry
	je_status = _get_journal_entry_status(row.get("child_name"))
	row["status"] = je_status if je_status else "DNGT"

	# Format payment month
	if row.get("payment_date"):
		row["payment_month"] = row["payment_date"].strftime("%b %Y")

	# Get invoice document
	inv_doc = invoice_docs.get(row["invoice_id"])
	if not inv_doc:
		return [row]

	# Get tax withholding groups
	groups = _get_tax_template_groups(inv_doc, row.get("vds_amount"))

	if not groups or len(groups) == 0:
		return []

	# Single group - update main row
	if len(groups) == 1:
		row.update(groups[0])
		return [row]

	# Multiple groups - create parent + children rows
	result_rows = []

	# Parent row with first group
	parent_row = row.copy()
	parent_row.update(groups[0])
	result_rows.append(parent_row)

	# Child rows for remaining groups
	for group in groups[1:]:
		child_row = {
			"check": 0,
			"payment_date": None,
			"payment_month": None,
			"status": "",
			"fiscal_year": None,
			"invoice_id": "",
			"invoice_status": "",
			"payment_entry_id": "",
			"invoice_amount": None,
			"vds_amount": group["vds_amount"],
			"account_credit": group["account_credit"],
			"liability_head": group["liability_head"],
			"section_ref": group["section_ref"],
			"applied_rate": group["applied_rate"],
			"net_amount": group["net_amount"],
			"child_name": row.get("child_name"),
			"supplier_name": row.get("supplier_name"),
			"indent": 1,
		}
		result_rows.append(child_row)

	return result_rows


def _filter_by_status(data, status_filter):
	"""Filter data based on status, keeping parent-child relationships."""
	if not status_filter:
		return data

	filtered_result = []
	i = 0

	while i < len(data):
		row = data[i]
		if row.get("indent", 0) == 0:
			parent_row = row
			children = []
			j = i + 1

			# Collect all child rows
			while j < len(data) and data[j].get("indent", 0) == 1:
				children.append(data[j])
				j += 1

			# Include parent and children if status matches
			if parent_row["status"] == status_filter:
				filtered_result.append(parent_row)
				filtered_result.extend(children)

			i = j
		else:
			i += 1

	return filtered_result


def get_data(filters):
	"""Fetch and process data for the report."""
	# Get base payment entry data
	base_data = _get_payment_entry_data(filters)
	if not base_data:
		return []

	# Get all invoice documents in batch
	invoice_ids = list(set(d["invoice_id"] for d in base_data))
	invoice_docs = {}

	for invoice_id in invoice_ids:
		try:
			invoice_docs[invoice_id] = frappe.get_doc("Purchase Invoice", invoice_id)
		except frappe.DoesNotExistError:
			invoice_docs[invoice_id] = None

	# Process all rows
	result_data = []
	for row in base_data:
		processed_rows = _process_data_row(row, invoice_docs)
		result_data.extend(processed_rows)

	# Apply status filter if specified
	status_filter = filters.get("status")
	if status_filter:
		result_data = _filter_by_status(result_data, status_filter)

	return result_data
