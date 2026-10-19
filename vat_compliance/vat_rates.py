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
