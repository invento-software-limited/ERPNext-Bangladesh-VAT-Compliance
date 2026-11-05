import frappe

from vat_compliance.access import require_company, require_report
from vat_compliance.deposits import make_deposit_entry
from vat_compliance.vat_compliance.report.sales_vat_management.sales_vat_management import (
	execute as execute_sales_vat,
)
from vat_compliance.vat_compliance.report.vds_management.vds_management import execute as execute_vds


@frappe.whitelist()
def get_vat_payment_data(from_date: str, to_date: str, company: str):
	"""What is still to deposit. A report failure surfaces as an error: an empty list here
	would read as no VAT due."""
	require_company(company)
	require_report("Sales VAT Management")
	require_report("VDS Management")

	filters = {"from_date": from_date, "to_date": to_date, "company": company}
	return _collected_sales(execute_sales_vat(filters)[1]) + _withheld_vds(execute_vds(filters)[1])


def _collected_sales(rows):
	data = []
	for row in rows:
		if row.get("status") == "Collected":
			row["party_type"] = "Customer"
			row["party_name"] = row.get("customer_name")
			row["liability_head"] = row.get("account_credit")
			row["source_report"] = "Sales VAT Management"
			data.append(row)
	return data


def _withheld_vds(rows):
	"""Every undeposited tax group. Indented rows leave the payment's details to the row above."""
	data, parent = [], {}
	for row in rows:
		parent = row if not row.get("indent") else parent
		if row.get("status") == "DNGT":
			for field in ("invoice_id", "payment_date", "payment_entry_id"):
				row[field] = row.get(field) or parent.get(field)
			row["party_type"] = "Supplier"
			row["party_name"] = row.get("supplier_name")
			row["source_report"] = "VDS Management"
			data.append(row)
	return data


@frappe.whitelist(methods=["POST"])
def make_journal_entry(rows: str | list):
	return make_deposit_entry(rows)
