# Copyright (c) 2025, na and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


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

	data = frappe.db.sql(
		f"""
		SELECT
			name as invoice,
			posting_date,
			supplier,
			grand_total,
			custom_mushak_63
		FROM
			`tabPurchase Invoice`
		WHERE
			docstatus = 1
			{conditions}
		ORDER BY
			posting_date DESC
	""",
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
def upload_mushak_63(invoice_id, file_url):
	if not invoice_id or not file_url:
		frappe.throw(_("Missing invoice or file"))

	frappe.db.set_value("Purchase Invoice", invoice_id, "custom_mushak_63", file_url)
	return True
