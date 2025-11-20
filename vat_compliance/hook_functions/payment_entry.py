import json
import frappe
from frappe.utils import flt
from erpnext.accounts.doctype.tax_withholding_category.tax_withholding_category import \
	get_cost_center
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry


@frappe.whitelist()
def calculate_tax_rows(doc: dict | str) -> list:
	"""
	Calculate tax rows for a payment entry.

	This function takes a payment entry as input and returns a list of
	tax rows. The tax rows are calculated based on the references
	of the payment entry, which are sales invoices or purchase invoices.
	The allocation ratio is calculated as the minimum of the allocated
	amount divided by the total net amount of the references.

	The tax rows are calculated for each taxable item of the
	references. The tax amount is calculated as the allocated amount
	multiplied by the tax rate.

	The function returns a list of dictionaries, where each
	dictionary contains the following keys:

	- custom_reference_doctype: the doctype of the reference
	- custom_reference_name: the name of the reference
	- account: the account of the tax row
	- cost_center: the cost center of the tax row
	- amount: the amount of the tax row
	- custom_item_code: the item code of the tax row
	- custom_item_name: the item name of the tax row
	- custom_allocated_amount: the allocated amount of the tax row

	:param doc: dict | str
		The payment entry as a dictionary or a string in JSON format.
	:return list
		A list of dictionaries, where each dictionary contains the tax rows.
	"""
	if isinstance(doc, str):
		try:
			doc = frappe.get_doc(json.loads(doc))
		except (json.JSONDecodeError, frappe.DoesNotExistError):
			return []

	references = doc.get("references", [])
	deductions = []

	for ref in references:
		if ref.reference_doctype not in ["Sales Invoice", "Purchase Invoice"]:
			continue
		invoice_name = ref.reference_name
		vds = ref.get("custom_vdsvcs")
		if not vds == 'Withheld':
			continue
		try:
			inv_doc = frappe.get_doc(ref.reference_doctype, invoice_name)
		except frappe.DoesNotExistError:
			continue

		cost_center = get_cost_center(inv_doc)
		items = inv_doc.get("items", [])

		taxable_items = [
			item for item in items
			if item.get('item_tax_template') and flt(item.get('net_amount')) > 0
		]
		total_net_amount = sum(flt(item.get('net_amount', 0)) for item in taxable_items)

		if not total_net_amount:
			continue

		allocation_ratio = min(flt(ref.allocated_amount) / total_net_amount, 1.0)

		for item in taxable_items:
			item_net_amount = flt(item.get('net_amount'))
			allocated_amount = item_net_amount * allocation_ratio
			item_tax_map = json.loads(item.get('item_tax_rate', '{}'))

			for account, rate in item_tax_map.items():
				vat_rate = flt(rate) / 100
				vat_amount = allocated_amount * vat_rate

				deductions.append({
					'custom_reference_doctype': inv_doc.doctype,
					'custom_reference_name': inv_doc.name,
					'account': account,
					'cost_center': cost_center,
					'amount': vat_amount if doc.payment_type == 'Receive' else -vat_amount,
					'custom_item_code': item.get('item_code'),
					'custom_item_name': item.get('item_name'),
					'custom_allocated_amount': allocated_amount
				})

	return deductions


class CustomPaymentEntry(PaymentEntry):
	def __init__(self, *args, **kwargs):
		"""
		Initialize the custom Payment Entry by delegating to the base class.
		"""
		super().__init__(*args, **kwargs)

	@frappe.whitelist()
	def allocate_amount_to_references(self, paid_amount, paid_amount_change,
									  allocate_payment_amount):
		"""
		Allocate amounts to references based on paid amount and outstanding values.

		Parameters:
		- paid_amount (float): Paid/received amount.
		- paid_amount_change (int | bool): Indicator whether paid amount was changed.
		- allocate_payment_amount (int | bool): Whether to perform allocation.

		Returns:
		- None
		"""
		return
