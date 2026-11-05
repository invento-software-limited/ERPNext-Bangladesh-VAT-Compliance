# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""What one invoice line reports to the VAT challan API, for sales and returns alike."""

from datetime import datetime
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import cint, flt, get_time, getdate
from frappe.utils.data import get_system_timezone


def line_amounts(doc, item, vat_percentage, vat_inclusive):
	"""Amounts for a line, positive even on a return.

	ERPNext's `rate` and `amount` are already net of the line discount, so it is not deducted
	again. `net_amount` is not used: it excludes VAT when the ERPNext tax is inclusive, and
	the VAT here is worked out from the service type's rate.
	"""
	qty = abs(flt(item.qty))
	unit_discount = abs(flt(item.get("discount_amount")))
	amount = abs(flt(item.get("amount"))) or qty * abs(flt(item.rate))
	invoice_discount = _invoice_discount_share(doc, amount)
	payable = amount - invoice_discount

	if vat_inclusive:
		before_tax = payable / (1 + vat_percentage / 100)
		vat_amount = payable - before_tax
		total = payable
	else:
		before_tax = payable
		vat_amount = before_tax * vat_percentage / 100
		total = before_tax + vat_amount

	return frappe._dict(
		qty=qty,
		unit_price=abs(flt(item.rate)) + unit_discount,
		discount_amount=unit_discount * qty + invoice_discount,
		total_amount_before_tax=before_tax,
		vat_amount=vat_amount,
		total_amount=total,
	)


def service_fields(item):
	"""Service type, VAT rate and pricing basis of a line. POS Invoice lines carry these as
	custom fields; Sales Invoice lines do not, so they come from the Item."""
	if item.get("custom_service_type_id"):
		return frappe._dict(
			service_type_id=item.custom_service_type_id,
			service_type_name=item.get("custom_service_type_name"),
			vat_rate=flt(item.get("custom_vat_rate")),
			vat_inclusive=not cint(item.get("custom_vat_exclusive")),
		)

	master = frappe.db.get_value(
		"Item", item.item_code, ["custom_service_type", "custom_vat_exclusive"], as_dict=True
	) or frappe._dict()
	service = frappe._dict()
	if master.custom_service_type:
		service = frappe.db.get_value(
			"VC Service Type",
			master.custom_service_type,
			["service_id", "service_name", "vat_rate"],
			as_dict=True,
		) or frappe._dict()
	return frappe._dict(
		service_type_id=service.service_id,
		service_type_name=service.service_name,
		vat_rate=flt(service.vat_rate),
		vat_inclusive=not cint(master.custom_vat_exclusive),
	)


def invoice_timestamp(posting_date, posting_time):
	"""Epoch for a posting in the site's time zone. The container's clock may be on UTC, so
	a naive `.timestamp()` would shift every invoice by the offset."""
	moment = datetime.combine(getdate(posting_date), get_time(posting_time))
	return int(moment.replace(tzinfo=ZoneInfo(get_system_timezone())).timestamp())


def _invoice_discount_share(doc, amount):
	total = abs(flt(doc.get("total")))
	return abs(flt(doc.get("discount_amount"))) * amount / total if total else 0.0
