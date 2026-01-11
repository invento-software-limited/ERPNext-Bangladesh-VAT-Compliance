import frappe
from frappe import _


def validate_vat_rate(doc, method):
	"""
	Validate that the VAT rate in the linked Service Type matches the tax rate in Item Tax Templates.
	"""
	if not doc.get("custom_service_type"):
		return

	vat_rate_service = frappe.get_value("VC Service Type", doc.custom_service_type, "vat_rate")

	if vat_rate_service is None:
		return

	if not doc.get("taxes"):
		return

	for row in doc.taxes:
		if row.item_tax_template:
			template_doc = frappe.get_doc("Item Tax Template", row.item_tax_template)

			match_found = False
			if template_doc.taxes:
				for tax_row in template_doc.taxes:
					if tax_row.tax_rate == vat_rate_service:
						match_found = True
						break

			if not match_found:
				frappe.throw(
					_(
						"VAT Rate Mismatch: The selected Service Type '{0}' has a VAT rate of {1}%, but the Item Tax Template '{2}' does not contain this rate."
					).format(doc.custom_service_type, vat_rate_service, row.item_tax_template)
				)
