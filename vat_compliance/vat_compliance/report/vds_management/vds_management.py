# Copyright (c) 2025, na and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from vat_compliance import report_kit as kit
from vat_compliance.access import scope_report_to_company
from vat_compliance.deposits import make_deposit_entry, mark_vds_groups
from vat_compliance.deposits import vds_groups as _get_tax_template_groups


def execute(filters=None):
	"""Execute the report."""
	scope_report_to_company(filters)
	data = get_data(filters)
	columns = get_columns()
	return columns, data, get_meta(filters, data)


def get_columns():
	"""Return columns for the report."""
	return [
		{"fieldname": "payment_date", "label": _("Payment Date"), "fieldtype": "Date", "width": 120},
		{"fieldname": "payment_month", "label": _("Payment Month"), "fieldtype": "Data", "width": 120},
		{
			"fieldname": "invoice_id",
			"label": _("Invoice Number"),
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 200,
		},
		{"fieldname": "invoice_status", "label": _("Invoice Status"), "fieldtype": "Data", "width": 120},
		{
			"fieldname": "supplier_name",
			"label": _("Supplier Name"),
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 150,
		},
		{"fieldname": "invoice_amount", "label": _("Invoice Amount"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120},
		{
			"fieldname": "payment_entry_id",
			"label": _("Payment Entry"),
			"fieldtype": "Link",
			"options": "Payment Entry",
			"width": 200,
		},
		{
			"fieldname": "account_credit",
			"label": _("Account head"),
			"fieldtype": "Link",
			"options": "Account",
			"width": 240,
		},
		{
			"fieldname": "liability_head",
			"label": _("Liability head"),
			"fieldtype": "Link",
			"options": "Account",
			"width": 240,
		},
		{"fieldname": "vds_amount", "label": _("VDS Amount"), "fieldtype": "Currency", "width": 120},
		{
			"fieldname": "section_ref",
			"label": _("Section Ref"),
			"fieldtype": "Link",
			"options": "Item Tax Template",
			"width": 120,
		},
		{"fieldname": "applied_rate", "label": _("Applied Rate"), "fieldtype": "Percent", "width": 120},
		{
			"fieldname": "fiscal_year",
			"label": _("Fiscal Year"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"width": 120,
		},
	]


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

	query = """
		SELECT
			per.reference_name as invoice_id,
			pe.posting_date as payment_date,
			pe.party as supplier_name,
			pi.status as invoice_status,
			pe.name as payment_entry_id,
			pi.base_grand_total as invoice_amount,
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

	return frappe.db.sql(query.replace("{where_clause}", where_clause), filters, as_dict=True)


@frappe.whitelist(methods=["POST"])
def make_journal_entry(rows: str | list):
	"""Create a draft Journal Entry for the selected rows."""
	return make_deposit_entry(rows)


def _process_data_row(row, invoice_docs):
	"""Process a single data row and return list of rows (parent + children)."""
	row["check"] = 0
	row["supplier_name"] = row.get("supplier_name")

	row["status"] = "DNGT"

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
	mark_vds_groups(row.get("child_name"), groups)

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
			"status": group["status"],
			"deposit_key": group["deposit_key"],
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

			# Each tax group has its own status; keep a payment if any group matches.
			if status_filter in (r["status"] for r in (parent_row, *children)):
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


def get_meta(filters, data):
	"""Header cards and charts. Indented rows split one payment across tax groups; they
	have their own amount and status but take the date and supplier of the row above."""
	filters = frappe._dict(filters or {})
	rows, parent = [], {}
	for r in data:
		if not r.get("indent"):
			parent = r
		rows.append(
			{
				"date": parent.get("payment_date"),
				"supplier": parent.get("supplier_name"),
				"status": r.get("status") or parent.get("status"),
				"amount": flt(r.get("vds_amount")),
			}
		)

	def amount(r):
		return r["amount"]

	deposited = [r for r in rows if r["status"] == "DDGT"]
	return kit.meta(
		filters,
		deducted=kit.total(rows, amount),
		payments=len(
			{r.get("payment_entry_id") for r in data if not r.get("indent") and r.get("payment_entry_id")}
		),
		pending=kit.total([r for r in rows if r["status"] == "DNGT"], amount),
		pending_count=len([r for r in rows if r["status"] == "DNGT"]),
		deposited=kit.total(deposited, amount),
		deposited_count=len(deposited),
		suppliers=kit.group(rows, lambda r: r["supplier"], amount),
		trend=kit.monthly(rows, lambda r: r["date"], amount, filters),
		trend_deposited=kit.monthly(deposited, lambda r: r["date"], amount, filters),
	)
