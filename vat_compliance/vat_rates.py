# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""One rule for "what VAT does this invoice line carry?", shared by the VAT reports
and the payment VDS calculation.

A line with an Item Tax Template keeps its long-standing reading: the first entry of
its `item_tax_rate`. A line without one still has `item_tax_rate` filled by ERPNext
from the invoice's tax table, e.g. {"VAT - ISL": 15.0}; for those, only entries on a
VAT account count, so another tax on the same line is never mistaken for VAT.
"""

import json

import frappe
from frappe.utils import flt


def vat_accounts(company):
	"""Compliance Settings' default VAT account when it belongs to the company, otherwise
	the company's non-group Tax accounts whose name says VAT. Cached per request."""
	cache = getattr(frappe.local, "vat_compliance_vat_accounts", None)
	if cache is None:
		cache = frappe.local.vat_compliance_vat_accounts = {}
	if company not in cache:
		cache[company] = _resolve_vat_accounts(company)
	return cache[company]


def _resolve_vat_accounts(company):
	default = frappe.db.get_single_value("Compliance Settings", "default_account")
	if default and (not company or frappe.db.get_value("Account", default, "company") == company):
		return [default]
	filters = {"account_type": "Tax", "is_group": 0, "account_name": ["like", "%VAT%"]}
	if company:
		filters["company"] = company
	return frappe.get_all("Account", filters=filters, pluck="name", order_by="name asc")


def parse_item_tax_rate(raw):
	"""`item_tax_rate` JSON as {account: rate}; a value may be a number or {"tax_rate": n}."""
	if isinstance(raw, dict):
		rows = raw
	else:
		try:
			rows = json.loads(raw or "{}")
		except (TypeError, ValueError):
			return {}
	out = {}
	for account, value in (rows or {}).items():
		out[account] = flt(value.get("tax_rate", 0) if isinstance(value, dict) else value)
	return out


def line_vat(item, company):
	"""(account, rate %) of VAT on one invoice line, or (None, 0) when it carries none."""
	rates = parse_item_tax_rate(item.get("item_tax_rate"))
	if item.get("item_tax_template"):
		if not rates:
			return None, 0
		account = next(iter(rates))
		return account, rates[account]
	return fallback_vat(rates, company)


def payment_ratio(invoice, allocated):
	"""Share of an invoice a payment covers. Allocations are VAT-inclusive, so the base is the
	gross total: half of a 115 invoice is 57.50, which carries half the VAT."""
	total = abs(flt(_payable_total(invoice)))
	return min(abs(flt(allocated)) / total, 1.0) if total else 0.0


def _payable_total(invoice):
	# Allocations are in the party account's currency, which can differ from the invoice's.
	party, currency = invoice.get("party_account_currency"), invoice.get("currency")
	if party and currency and party != currency:
		return invoice.get("base_rounded_total") or invoice.get("base_grand_total")
	return invoice.get("rounded_total") or invoice.get("grand_total")


def line_net(item):
	"""A line's net amount in company currency, which is what VAT is reported in."""
	base = item.get("base_net_amount")
	return flt(base if base is not None else item.get("net_amount"))


def stored_rate(item_tax_template, item_tax_rate, company):
	"""VAT % saved on the invoice line, so later template edits cannot change past periods.
	Only a template line saved without rates falls back to its template."""
	rate = line_vat(frappe._dict(item_tax_template=item_tax_template, item_tax_rate=item_tax_rate), company)[
		1
	]
	if item_tax_template and not parse_item_tax_rate(item_tax_rate):
		return flt(
			frappe.db.get_value(
				"Item Tax Template Detail", {"parent": item_tax_template}, "tax_rate", order_by="idx asc"
			)
		)
	return rate


def add_invoice_vat(doctype, rows, name_field="name"):
	"""Set vat_amount and base_vat_amount on invoice rows from VAT accounts only, so freight or
	AIT in the tax table is not shown as VAT. A company with no known VAT account keeps the
	invoice's tax total."""
	totals = _vat_by_invoice(doctype, [r.get(name_field) for r in rows])
	for row in rows:
		if vat_accounts(row.get("company")):
			vat, base = _sum_vat(totals.get(row.get(name_field), []), row.get("company"))
		else:
			vat, base = flt(row.get("total_taxes_and_charges")), flt(row.get("base_total_taxes_and_charges"))
		row["vat_amount"], row["base_vat_amount"] = vat, base


def _vat_by_invoice(doctype, names):
	table = {"Sales Invoice": "Sales Taxes and Charges", "Purchase Invoice": "Purchase Taxes and Charges"}[
		doctype
	]
	fields = [
		"parent",
		"account_head",
		"tax_amount_after_discount_amount",
		"base_tax_amount_after_discount_amount",
	]
	if doctype == "Purchase Invoice":
		fields.append("add_deduct_tax")
	rows = (
		frappe.get_all(table, filters={"parent": ["in", names], "parenttype": doctype}, fields=fields)
		if names
		else []
	)
	grouped = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row)
	return grouped


def _sum_vat(taxes, company):
	accounts = vat_accounts(company)
	vat = base = 0.0
	for tax in taxes:
		if tax.account_head in accounts:
			sign = -1 if tax.get("add_deduct_tax") == "Deduct" else 1
			vat += sign * flt(tax.tax_amount_after_discount_amount)
			base += sign * flt(tax.base_tax_amount_after_discount_amount)
	return vat, base


def fallback_vat(rates, company):
	"""VAT on a line without a template: its rate on the first VAT account that has one."""
	rates = parse_item_tax_rate(rates)
	for account in vat_accounts(company):
		if rates.get(account):
			return account, rates[account]
	return None, 0


def line_tax_map(item, company):
	"""Every {account: rate} a line is taxed at, for the payment VDS split. Template lines
	keep all their entries, as before; lines without a template contribute VAT only."""
	if item.get("item_tax_template"):
		return parse_item_tax_rate(item.get("item_tax_rate"))
	account, rate = line_vat(item, company)
	return {account: rate} if account else {}


def is_taxable_line(item, company):
	"""Lines that share a payment's VDS allocation: every template line (as before, even
	at 0%), plus lines without a template that carry VAT through the tax table."""
	return bool(item.get("item_tax_template")) or bool(line_vat(item, company)[1])
