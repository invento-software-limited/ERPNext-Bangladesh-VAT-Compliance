import frappe
import json
from frappe.utils import flt
from vat_compliance.vat_compliance.report.sales_vat_management.sales_vat_management import execute as execute_sales_vat
from vat_compliance.vat_compliance.report.vds_management.vds_management import execute as execute_vds

@frappe.whitelist()
def get_vat_payment_data(from_date, to_date, company):
	filters = {
		"from_date": from_date,
		"to_date": to_date,
		"company": company
	}
	
	data = []

	# Fetch Sales VAT data
	try:
		_, sales_data, _ = execute_sales_vat(filters)
		for row in sales_data:
			if row.get("status") == "Collected":
				row["party_type"] = "Customer"
				row["party_name"] = row.get("customer_name")
				row["liability_head"] = row.get("account_credit")
				row["source_report"] = "Sales VAT Management"
				data.append(row)
	except Exception as e:
		frappe.log_error(f"Error fetching Sales VAT data: {str(e)}")

	# Fetch VDS data
	try:
		_, vds_data, _ = execute_vds(filters)
		for row in vds_data:
			if row.get("status") == "DNGT":
				row["party_type"] = "Supplier"
				row["party_name"] = row.get("supplier_name")
				row["source_report"] = "VDS Management"
				data.append(row)
	except Exception as e:
		frappe.log_error(f"Error fetching VDS data: {str(e)}")
	
	return data

@frappe.whitelist()
def make_journal_entry(rows):
	if isinstance(rows, str):
		rows = json.loads(rows)
		
	if not rows:
		frappe.throw("No rows selected")

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "VAT Payment Entry"
	je.posting_date = frappe.utils.nowdate()
	
	accounts = []
	for row in rows:
		liability_head = row.get("liability_head")
		if not liability_head:
			frappe.throw(f"Account head missing for row {row.get('invoice_id')}")
			
		# Handle comma-separated accounts from Sales VAT Management
		if "," in liability_head:
			# If multiple accounts, we can't easily determine the split of vds_amount without recalculating.
			# For now, we'll throw an error or just take the first one?
			# Throwing an error is safer.
			frappe.throw(f"Multiple account heads found for {row.get('invoice_id')}: {liability_head}. Please handle manually.")

		accounts.append({
			"account": liability_head,
			"debit_in_account_currency": row.get("vds_amount"),
			"reference_detail_no": row.get("child_name"),
			"custom_tax_type": "VAT",
		})
		
	je.set("accounts", accounts)
	je.insert()
	return je.name
