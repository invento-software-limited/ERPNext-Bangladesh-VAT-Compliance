# Copyright (c) 2025, na and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from vat_compliance import report_kit as kit


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data, get_meta(filters, data)


def get_columns():
	return [
		{"fieldname": "posting_date", "label": _("Date"), "fieldtype": "Date", "width": 150},
		{
			"fieldname": "invoice",
			"label": _("Purchase Invoice"),
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 250,
		},
		{
			"fieldname": "supplier",
			"label": _("Supplier"),
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 220,
		},
		{"fieldname": "grand_total", "label": _("Grand Total"), "fieldtype": "Currency", "width": 150},
		{"fieldname": "custom_mushak_63", "label": _("Mushak 6.3"), "fieldtype": "Data", "width": 180},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120},
		{"fieldname": "action", "label": _("Action"), "fieldtype": "Data", "width": 150},
	]


def get_data(filters):
	conditions = get_conditions(filters)

	query = """
		SELECT
			name as invoice,
			posting_date,
			supplier,
			grand_total,
			base_grand_total,
			custom_mushak_63
		FROM
			`tabPurchase Invoice`
		WHERE
			docstatus = 1
			{conditions}
		ORDER BY
			posting_date DESC
	"""

	data = frappe.db.sql(
		query.replace("{conditions}", conditions),
		filters,
		as_dict=1,
	)

	for row in data:
		if row.get("custom_mushak_63"):
			row["status"] = "Collected"
		else:
			row["status"] = "Not Collected"

	return data


def get_conditions(filters):
	conditions = []

	if filters.get("from_date"):
		conditions.append("posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("posting_date <= %(to_date)s")
	if filters.get("supplier"):
		conditions.append("supplier = %(supplier)s")
	if filters.get("company"):
		conditions.append("company = %(company)s")

	# Status filter is handled in python because it depends on a custom field check which is easier/cleaner there or we can do it in SQL.
	# Let's do it in SQL for efficiency if possible, but custom_mushak_63 is a field so:
	if filters.get("status"):
		if filters.get("status") == "Collected":
			conditions.append("custom_mushak_63 IS NOT NULL AND custom_mushak_63 != ''")
		elif filters.get("status") == "Not Collected":
			conditions.append("(custom_mushak_63 IS NULL OR custom_mushak_63 = '')")

	return "AND " + " AND ".join(conditions) if conditions else ""


@frappe.whitelist()
def upload_mushak_63(invoice_id: str, file_url: str):
	if not invoice_id or not file_url:
		frappe.throw(_("Missing invoice or file"))

	frappe.db.set_value("Purchase Invoice", invoice_id, "custom_mushak_63", file_url)
	return True


def get_meta(filters, data):
	"""Header cards and charts, in company currency, from the same bills as the table."""
	filters = frappe._dict(filters or {})
	value = lambda r: r.get("base_grand_total")
	collected = [r for r in data if r.get("status") == "Collected"]
	pending = [r for r in data if r.get("status") != "Collected"]
	return kit.meta(
		filters,
		bills=len(data),
		value=kit.total(data, value),
		collected=len(collected),
		collected_value=kit.total(collected, value),
		pending=len(pending),
		pending_value=kit.total(pending, value),
		pending_suppliers=kit.group(pending, lambda r: r.get("supplier"), value, limit=6),
		trend_count=kit.monthly(data, lambda r: r.get("posting_date"), lambda r: 1, filters),
	)
