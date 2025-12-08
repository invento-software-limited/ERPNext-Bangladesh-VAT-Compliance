import frappe

from vat_compliance.vschallan import VATSmartChallan


def create_vat_invoice(doc, method=None):
	vschallan = VATSmartChallan()
	if not doc.status == "Return":
		vschallan.create_vat_invoice(doc)
	else:
		config = frappe.get_single("POS Vendor Configuration")
		schedule = config.sync_schedule
		if schedule == "After Submit":
			vschallan.return_vat_invoice(doc)
			vat_invoice = frappe.get_doc("VAT Invoice", {"return_invoice_no": doc.name})
			vat_invoice.sync_vat_invoice()
