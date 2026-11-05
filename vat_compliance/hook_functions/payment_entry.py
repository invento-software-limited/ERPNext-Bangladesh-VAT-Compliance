import json

import frappe
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry
from frappe.utils import flt

from vat_compliance.vat_rates import is_taxable_line, line_tax_map, payment_ratio


def get_cost_center(doc):
	"""
	Get the cost center from a document.
	It first checks for a 'cost_center' field in the document itself.
	If not found, it checks the first item in the 'items' table.
	"""
	cost_center = doc.get("cost_center")
	if not cost_center and doc.get("items"):
		cost_center = doc.items[0].get("cost_center")
	return cost_center


@frappe.whitelist()
def calculate_tax_rows(doc: dict | str) -> list:
	"""VDS deduction rows for a draft Payment Entry, for the form to show before saving."""
	frappe.has_permission("Payment Entry", "write", throw=True)
	if isinstance(doc, str):
		try:
			doc = json.loads(doc)
		except json.JSONDecodeError:
			return []
	if doc.get("doctype") != "Payment Entry":
		frappe.throw(frappe._("Expected a Payment Entry"))
	return get_vds_rows(frappe.get_doc(doc), check_read=True)


def sync_vds_deductions(doc, method=None):
	"""Payment Entry before_validate: VDS rows always follow the current allocations. Other
	deductions, such as write-offs, have no reference and are kept."""
	if not doc.docstatus.is_draft():
		return
	deductions = doc.get("deductions") or []
	kept = [d for d in deductions if not d.get("custom_reference_doctype")]
	rows = get_vds_rows(doc)
	if not rows and len(kept) == len(deductions):
		return
	doc.set("deductions", kept)
	for row in rows:
		doc.append("deductions", row)


def get_vds_rows(doc, check_read=False) -> list:
	"""One row per taxable line and tax account of each invoice marked Withheld."""
	deductions = []
	for ref in doc.get("references") or []:
		if ref.reference_doctype not in ("Sales Invoice", "Purchase Invoice"):
			continue
		if ref.get("custom_vdsvcs") != "Withheld":
			continue
		try:
			inv_doc = frappe.get_doc(ref.reference_doctype, ref.reference_name)
		except frappe.DoesNotExistError:
			continue
		if check_read:
			inv_doc.check_permission("read")
		deductions.extend(_invoice_vds_rows(doc, ref, inv_doc))
	return deductions


def _invoice_vds_rows(doc, ref, inv_doc):
	cost_center = get_cost_center(inv_doc) or frappe.get_value("Company", doc.company, "cost_center")
	allocation_ratio = payment_ratio(inv_doc, ref.allocated_amount)
	rows = []
	for item in inv_doc.get("items", []):
		if flt(item.get("net_amount")) <= 0 or not is_taxable_line(item, inv_doc.company):
			continue
		allocated_amount = flt(item.get("net_amount")) * allocation_ratio
		for account, rate in line_tax_map(item, inv_doc.company).items():
			vat_amount = allocated_amount * flt(rate) / 100
			rows.append(
				{
					"custom_reference_doctype": inv_doc.doctype,
					"custom_reference_name": inv_doc.name,
					"account": account,
					"cost_center": cost_center,
					"amount": vat_amount if doc.payment_type == "Receive" else -vat_amount,
					"custom_item_code": item.get("item_code"),
					"custom_item_name": item.get("item_name"),
					"custom_allocated_amount": allocated_amount,
				}
			)
	return rows


class CustomPaymentEntry(PaymentEntry):
	def __init__(self, *args, **kwargs):
		"""
		Initialize the custom Payment Entry by delegating to the base class.
		"""
		super().__init__(*args, **kwargs)

	@frappe.whitelist()
	def allocate_amount_to_references(
		self, paid_amount: float, paid_amount_change: bool, allocate_payment_amount: bool
	):
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
