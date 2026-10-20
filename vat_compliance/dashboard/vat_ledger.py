# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""VAT as posted to the ledger: which accounts count as VAT, and what each posting is.

Every GL row on a VAT account falls in exactly one source, so
balance = opening + output − input − deposits + adjustments, always.
"""

import frappe
from frappe.utils import flt, getdate

from vat_compliance.vat_rates import vat_accounts  # noqa: F401  the same accounts the VAT reports use

SOURCES = ("output", "input", "deposit", "opening", "adjustment")
OUTPUT_VOUCHERS = ("Sales Invoice", "POS Invoice")


def gl_rows(company, accounts, upto):
	"""Non-cancelled VAT postings up to `upto`, through the permission-aware list API."""
	if not accounts:
		return []
	rows = frappe.get_list("GL Entry", filters={"company": company, "account": ["in", accounts], "is_cancelled": 0,
		"posting_date": ["<=", upto]}, fields=["posting_date", "voucher_type", "voucher_no", "debit", "credit"],
		order_by="posting_date asc, creation asc", limit_page_length=0)
	je_types = _journal_types({r.voucher_no for r in rows if r.voucher_type == "Journal Entry"})
	for r in rows:
		r.posting_date = getdate(r.posting_date)
		r.source = _source(r, je_types.get(r.voucher_no))
		r.liability = flt(r.credit) - flt(r.debit)  # + raises what is owed to the treasury
	return rows


def _journal_types(names):
	if not names or not frappe.has_permission("Journal Entry", "read"):
		return {}
	return dict(frappe.get_list("Journal Entry", filters={"name": ["in", list(names)]},
		fields=["name", "voucher_type"], as_list=True, limit_page_length=0))


def _source(row, je_type):
	if row.voucher_type in OUTPUT_VOUCHERS:
		return "output"
	if row.voucher_type == "Purchase Invoice":
		return "input"
	if je_type == "VAT Payment Entry":
		return "deposit"
	if je_type == "Opening Entry":
		return "opening"
	return "adjustment"


def amount(row):
	"""The row's size in its source's own direction (input and deposits count as debits)."""
	return -row.liability if row.source in ("input", "deposit") else row.liability


def totals(rows, start=None, end=None):
	out = dict.fromkeys(SOURCES, 0.0)
	for r in rows:
		if (start is None or r.posting_date >= start) and (end is None or r.posting_date <= end):
			out[r.source] += amount(r)
	return out


def balance(rows, upto):
	return sum(r.liability for r in rows if r.posting_date <= getdate(upto))
