# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""VAT deposits into the treasury: what each payment owes, per tax group, and whether a
Journal Entry has paid it.

Each owed line has its own key, stored in the Journal Entry row's reference_detail_no, so one
tax group can be deposited without marking the others. Entries made before keys existed hold
the bare Payment Entry Reference name; those covered only a VDS payment's first group, or all
of a sales payment.

Amounts and accounts are always rebuilt here from the invoice. Rows from the browser only say
which lines were selected.
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from vat_compliance.access import require_company, require_doc
from vat_compliance.vat_rates import is_taxable_line, line_net, line_vat, payment_ratio

SUBMITTED = 1
# Invoice type -> (payment type, VDS/VCS marking) that leaves VAT to deposit.
ELIGIBLE = {"Purchase Invoice": ("Pay", "Withheld"), "Sales Invoice": ("Receive", "Collected")}


def make_deposit_entry(rows):
	return DepositEntry(rows).create()


class DepositEntry:
	"""Draft Journal Entry for selected lines. The user adds the bank line in the form."""

	def __init__(self, rows):
		self.rows = json.loads(rows) if isinstance(rows, str) else rows

	def create(self):
		frappe.has_permission("Journal Entry", "create", throw=True)
		frappe.has_permission("Payment Entry", "read", throw=True)
		if not self.rows:
			frappe.throw(_("No rows selected"))
		companies, accounts = set(), []
		for reference, key in sorted(
			{(r.get("child_name"), r.get("deposit_key")) for r in self.rows}, key=str
		):
			ref = _payment_reference(reference)
			companies.add(ref.company)
			accounts.extend(_journal_rows(_selected_lines(ref, key)))
		if len(companies) > 1:
			frappe.throw(_("Select rows from one company at a time."))
		if not accounts:
			frappe.throw(_("The selected rows have no VAT to deposit."))
		return self._insert(companies.pop(), accounts)

	def _insert(self, company, accounts):
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "VAT Payment Entry"
		je.company = company
		je.posting_date = nowdate()
		je.set("accounts", accounts)
		je.insert()
		return je.name


def _payment_reference(name):
	"""The payment row behind a selected line, locked so two clicks cannot both deposit it."""
	fields = ["name", "parent", "reference_doctype", "reference_name", "allocated_amount", "custom_vdsvcs"]
	ref = (
		frappe.db.get_value("Payment Entry Reference", name, fields, as_dict=True, for_update=True)
		if name
		else None
	)
	rule = ELIGIBLE.get(ref.reference_doctype) if ref else None
	if not rule or ref.custom_vdsvcs != rule[1]:
		frappe.throw(_("A selected row has no VAT to deposit. Refresh and try again."))
	require_doc("Payment Entry", ref.parent)
	entry = frappe.db.get_value(
		"Payment Entry", ref.parent, ["company", "docstatus", "payment_type"], as_dict=True
	)
	if entry.docstatus != SUBMITTED or entry.payment_type != rule[0]:
		frappe.throw(_("Payment Entry {0} is not a submitted payment.").format(ref.parent))
	require_company(entry.company)
	ref.company = entry.company
	return ref


def _selected_lines(ref, key):
	lines = payment_lines(ref)
	if key and key != ref.name:
		lines = [line for line in lines if line.key == key]
		if not lines:
			frappe.throw(
				_("{0} has changed since this list loaded. Refresh and try again.").format(ref.reference_name)
			)
	_refuse_repeats(ref, lines)
	return lines


def payment_lines(ref):
	"""Every line this payment owes: a VDS payment per tax group, a sales payment per VAT account."""
	invoice = frappe.get_doc(ref.reference_doctype, ref.reference_name)
	if ref.reference_doctype == "Purchase Invoice":
		groups = vds_groups(invoice, ref.allocated_amount)
		return [
			frappe._dict(
				key=group_key(ref.name, g), account=g["liability_head"], amount=g["vds_amount"], first=not i
			)
			for i, g in enumerate(groups)
		]
	ratio = payment_ratio(invoice, ref.allocated_amount)
	return [
		frappe._dict(key=line_key(ref.name, head), account=head, amount=vat * ratio, first=True)
		for head, vat in sales_head_vat(invoice).items()
	]


def _refuse_repeats(ref, lines):
	states = journal_states([line.key for line in lines] + [ref.name])
	for line in lines:
		state = states.get(line.key) or (states.get(ref.name) if line.first else None)
		if state:
			frappe.throw(_("{0} is already in Journal Entry {1}.").format(ref.reference_name, state.parent))


def _journal_rows(lines):
	rows = []
	for line in lines:
		amount = flt(line.amount, 2)
		if amount:
			side = "debit_in_account_currency" if amount > 0 else "credit_in_account_currency"
			rows.append(
				{
					"account": line.account,
					side: abs(amount),
					"reference_detail_no": line.key,
					"custom_tax_type": "VAT",
				}
			)
	return rows


def line_key(reference, *parts):
	digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:10]
	return f"{reference}:{digest}"


def group_key(reference, group):
	return line_key(
		reference,
		group["account_credit"],
		group["liability_head"],
		group["section_ref"],
		group["applied_rate"],
	)


def journal_states(keys):
	"""{key: {docstatus, parent}} for non-cancelled entries; a submitted entry wins over a draft."""
	rows = frappe.get_all(
		"Journal Entry Account",
		filters={"reference_detail_no": ["in", list(keys)], "custom_tax_type": "VAT", "docstatus": ["<", 2]},
		fields=["reference_detail_no", "docstatus", "parent"],
	)
	states = {}
	for row in sorted(rows, key=lambda r: r.docstatus):
		states[row.reference_detail_no] = row
	return states


def mark_vds_groups(reference, groups):
	"""Give each tax group its key and its own deposit status."""
	keys = [group_key(reference, g) for g in groups]
	states = journal_states([*keys, reference])
	for i, group in enumerate(groups):
		state = states.get(keys[i]) or (states.get(reference) if not i else None)
		group["deposit_key"] = keys[i]
		group["status"] = "DDGT" if state and state.docstatus == SUBMITTED else "DNGT"
	return groups


def sales_deposited(reference, heads):
	"""True once every VAT account of a sales payment is in a submitted entry."""
	if not reference or not heads:
		return False
	keys = [line_key(reference, head) for head in heads]
	states = journal_states([*keys, reference])

	def submitted(key):
		return key in states and states[key].docstatus == SUBMITTED

	return submitted(reference) or all(submitted(key) for key in keys)


def sales_head_vat(invoice):
	"""{VAT account: VAT} for the whole invoice, in company currency."""
	heads = {}
	for item in invoice.items:
		account, rate = line_vat(item, invoice.company)
		if account and rate > 0:
			heads[account] = heads.get(account, 0) + line_net(item) * rate / 100
	return heads


def vds_groups(invoice, allocated):
	"""What a payment withheld, grouped by expense account, VAT account, template and rate."""
	if not invoice:
		return []
	ratio = payment_ratio(invoice, allocated)
	groups = {}
	for item in invoice.items:
		if not is_taxable_line(item, invoice.company) or flt(line_net(item)) <= 0:
			continue
		account, rate = line_vat(item, invoice.company)
		amount = line_net(item) * ratio
		vds_amount = amount * rate / 100
		if not account or not vds_amount:
			continue
		key = (item.get("expense_account"), account, item.get("item_tax_template"), rate)
		group = groups.setdefault(
			key,
			{
				"account_credit": key[0],
				"liability_head": account,
				"section_ref": key[2],
				"applied_rate": rate,
				"vds_amount": 0,
				"net_amount": 0,
			},
		)
		group["vds_amount"] += vds_amount
		group["net_amount"] += amount
	return list(groups.values())
