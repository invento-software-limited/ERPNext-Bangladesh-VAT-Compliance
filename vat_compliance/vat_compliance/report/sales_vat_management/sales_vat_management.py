# Copyright (c) 2025, na and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	message = get_message()
	return columns, data, message


def get_message():
	return """<span class="indicator blue">
        IPNR : Invoiced (Payment Not Received)
        </span> &nbsp;&nbsp;&nbsp;
        <span class="indicator orange">
        Collected
        </span>
        &nbsp;&nbsp;&nbsp;
        <span class="indicator green">
        CDGT : Collected And Deposited Into Gov't Treasury
        </span>
        &nbsp;&nbsp;&nbsp
        <span class="indicator green">
        DVCR : Deducted (VDS Certificate received)
        </span>
        &nbsp;&nbsp;&nbsp;
        <span class="indicator red">
        DVCNR : Deducted  (VDS Certificate Not received)
        </span>"""


def get_columns():
	return [
		{"fieldname": "payment_date", "label": _("Payment Date"), "fieldtype": "Date", "width": 120},
		{
			"fieldname": "invoice_id",
			"label": _("Invoice Number"),
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 200,
		},
		{"fieldname": "invoice_status", "label": _("Invoice Status"), "fieldtype": "Data", "width": 120},
		{"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data", "width": 150},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120},
		{
			"fieldname": "account_credit",
			"label": _("Account head"),
			"fieldtype": "Link",
			"options": "Account",
			"width": 240,
		},
		{
			"fieldname": "payment_entry_id",
			"label": _("Payment Entry"),
			"fieldtype": "Link",
			"options": "Payment Entry",
			"width": 200,
		},
		{"fieldname": "invoice_amount", "label": _("Invoice Amount"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "vds_amount", "label": _("VAT on Sales Amount"), "fieldtype": "Currency", "width": 120},
		{
			"fieldname": "fiscal_year",
			"label": _("Fiscal Year"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"width": 120,
		},
	]


def _build_filter_conditions(base_conditions, filter_mapping, filters):
	"""Build filter conditions dynamically"""
	conditions = base_conditions.copy()

	for filter_key, condition_template in filter_mapping:
		if filters.get(filter_key):
			conditions.append(condition_template)

	return conditions


def _get_payment_data(filters):
	"""Get data for invoices with payments"""
	base_conditions = [
		"per.reference_doctype = 'Sales Invoice'",
		"per.custom_vdsvcs IN ('Collected', 'Withheld')",
		"pe.payment_type = 'Receive'",
		"pe.docstatus = 1",
	]

	filter_mapping = [
		("from_date", "pe.posting_date >= %(from_date)s"),
		("to_date", "pe.posting_date <= %(to_date)s"),
		("invoice_status", "si.status = %(invoice_status)s"),
		("customer", "pe.party = %(customer)s"),
		("company", "pe.company = %(company)s"),
		("sales_invoice", "si.name = %(sales_invoice)s"),
		("payment_entry", "pe.name = %(payment_entry)s"),
	]

	conditions = _build_filter_conditions(base_conditions, filter_mapping, filters)
	where_clause = " AND ".join(conditions)

	query = """
        SELECT
            per.reference_name as invoice_id,
            pe.posting_date as payment_date,
            pe.party_name as customer_name,
            si.status as invoice_status,
            pe.name as payment_entry_id,
            si.grand_total as invoice_amount,
            0 as vds_amount,
            per.custom_vdsvcs as vds,
            per.name as child_name,
            fy.name as fiscal_year
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe ON per.parent = pe.name
        INNER JOIN `tabSales Invoice` si ON per.reference_name = si.name
        LEFT JOIN `tabFiscal Year` fy ON pe.posting_date BETWEEN fy.year_start_date AND fy.year_end_date
        WHERE {where_clause}
        ORDER BY pe.posting_date DESC
    """

	return frappe.db.sql(query.replace("{where_clause}", where_clause), filters, as_dict=True)


def _get_no_payment_data(filters):
	"""Get data for invoices without payments"""
	base_conditions = ["si.docstatus = 1", "si.status != 'Paid'"]

	filter_mapping = [
		("from_date", "si.posting_date >= %(from_date)s"),
		("to_date", "si.posting_date <= %(to_date)s"),
		("invoice_status", "si.status = %(invoice_status)s"),
		("customer", "si.customer = %(customer)s"),
		("company", "si.company = %(company)s"),
		("sales_invoice", "si.name = %(sales_invoice)s"),
	]

	conditions = _build_filter_conditions(base_conditions, filter_mapping, filters)
	where_clause = " AND ".join(conditions)

	query = """
        SELECT
            si.name as invoice_id,
            si.posting_date as payment_date,
            si.customer_name as customer_name,
            si.status as invoice_status,
            NULL as payment_entry_id,
            si.grand_total as invoice_amount,
            NULL as vds_amount,
            NULL as vds,
            NULL as child_name,
            fy.name as fiscal_year
        FROM `tabSales Invoice` si
        LEFT JOIN `tabPayment Entry Reference` per ON per.reference_name = si.name
        LEFT JOIN `tabPayment Entry` pe ON per.parent = pe.name
            AND pe.docstatus = 1
            AND pe.payment_type = 'Receive'
        LEFT JOIN `tabFiscal Year` fy ON si.posting_date BETWEEN fy.year_start_date AND fy.year_end_date
        WHERE {where_clause} AND pe.name IS NULL
        ORDER BY si.posting_date DESC
    """

	return frappe.db.sql(query.replace("{where_clause}", where_clause), filters, as_dict=True)


def _get_attachments_map(payment_entry_ids):
	"""Get attachments map for payment entries"""
	if not payment_entry_ids:
		return {}

	placeholders = ",".join(["%s"] * len(payment_entry_ids))
	query = """
        SELECT parent, document_type, file, inv_numbers
        FROM `tabDocument Attachment`
        WHERE parent IN ({placeholders})
            AND document_type = 'Challan'
            AND tax_type = 'VAT'
            AND file IS NOT NULL
    """

	attachments = frappe.db.sql(
		query.replace("{placeholders}", placeholders),
		payment_entry_ids,
		as_dict=True,
	)

	attachments_map = {}
	for att in attachments:
		if att.parent not in attachments_map:
			attachments_map[att.parent] = []
		attachments_map[att.parent].append(att)

	return attachments_map


def _calculate_vat_amount_and_accounts(inv_doc, row_data):
	"""Calculate VAT amount and get account heads for an invoice"""
	account_heads = set()
	vat_amount = 0

	for item in inv_doc.items:
		if not item.item_tax_template:
			continue

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

		if tax_rate > 0:
			account_heads.add(first_key)

			if row_data.get("payment_entry_id"):
				if row_data.get("vds") == "Collected":
					row_data["status"] = "Collected"
					je_status = _get_journal_entry_status(row_data.get("child_name"))
					if je_status:
						row_data["status"] = je_status

				vat_amount += flt(item.get("net_amount", 0.0)) * (tax_rate / 100)
			else:
				vat_amount += flt(item.get("net_amount", 0.0)) * (tax_rate / 100)

	return account_heads, vat_amount


def _process_invoice_status(row_data, attachments_map):
	"""Process and set invoice status based on attachments"""
	row_data["check"] = 0
	row_data["status"] = "IPNR"

	if row_data["payment_entry_id"]:
		row_data["status"] = "DVCNR"

		# Check if VDS certificate is received
		attachments = attachments_map.get(row_data["payment_entry_id"], [])
		for att in attachments:
			if att.get("inv_numbers"):
				inv_list = [inv.strip() for inv in att["inv_numbers"].split(",")]
				if row_data["invoice_id"] in inv_list:
					row_data["status"] = "DVCR"
					break

	return row_data


def get_data(filters):
	# Get payment data and no-payment data
	payment_data = _get_payment_data(filters)
	no_payment_data = _get_no_payment_data(filters)

	# Combine and sort data
	all_data = payment_data + no_payment_data
	all_data.sort(key=lambda d: d["payment_date"] or d["invoice_amount"], reverse=True)

	if not all_data:
		return []

	# Pre-fetch invoice documents and attachments
	invoice_ids = list(set(d["invoice_id"] for d in all_data))
	payment_entry_ids = list(set(d["payment_entry_id"] for d in all_data if d["payment_entry_id"]))

	# Get invoice documents in bulk
	invoice_docs = {}
	for invoice_id in invoice_ids:
		try:
			invoice_docs[invoice_id] = frappe.get_doc("Sales Invoice", invoice_id)
		except frappe.DoesNotExistError:
			invoice_docs[invoice_id] = None

	# Get attachments map
	attachments_map = _get_attachments_map(payment_entry_ids)

	# Process each row
	result_data = []
	for row in all_data:
		# Process status
		row = _process_invoice_status(row, attachments_map)

		# Get invoice document and calculate VAT/accounts
		inv_doc = invoice_docs.get(row["invoice_id"])
		if not inv_doc:
			continue

		account_heads, vat_amount = _calculate_vat_amount_and_accounts(inv_doc, row)

		if filters.get("status"):
			if row["status"] not in filters.get("status"):
				continue

		# Set VAT amount if calculated
		if vat_amount > 0:
			row["vds_amount"] = vat_amount

		# Set account credit
		if account_heads:
			row["account_credit"] = (
				next(iter(account_heads)) if len(account_heads) == 1 else ", ".join(account_heads)
			)
			result_data.append(row)

	return result_data


@frappe.whitelist()
def upload_challan(rows, challan_data):
	"""Upload challan for selected rows"""
	if isinstance(rows, str):
		rows = json.loads(rows)

	if isinstance(challan_data, str):
		challan_data = json.loads(challan_data)

	if not rows:
		frappe.throw("No rows selected")

	# Group by payment entry
	pe_map = {}
	for row in rows:
		pe_id = row.get("payment_entry_id")
		if not pe_id:
			continue

		if pe_id not in pe_map:
			pe_map[pe_id] = []
		pe_map[pe_id].append(row.get("invoice_id"))

	# Create attachments
	for pe_id, invoice_ids in pe_map.items():
		doc = frappe.get_doc(
			{
				"doctype": "Document Attachment",
				"parent": pe_id,
				"parenttype": "Payment Entry",
				"parentfield": "custom_documents",
				"document_type": "Challan",
				"tax_type": "VAT",
				"inv_numbers": ", ".join(invoice_ids),
				"challan_no": challan_data.get("challan_no"),
				"challan_date": challan_data.get("challan_date"),
				"challan_amount": challan_data.get("challan_amount"),
				"branch_and_bank_name": challan_data.get("branch_and_bank_name"),
				"file": challan_data.get("file"),
				"remarks": challan_data.get("remarks"),
			}
		)
		doc.insert(ignore_permissions=True)

	return True


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
		return "CDGT"

	return None
