# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""Data for the VAT page dashboard (/app/vat-dashboard), in company currency.

Amounts come from postings on the VAT account(s) (see vat_ledger); treasury status
follows the app's own report rules (see vat_status). "Period" figures follow the
selected window; the VAT balance is as of today.
"""

import frappe
from frappe import _
from frappe.core.doctype.user_permission.user_permission import get_user_permissions
from frappe.utils import cint, flt, getdate, today

from vat_compliance.dashboard import period as periods
from vat_compliance.dashboard import vat_ledger as ledger
from vat_compliance.dashboard.vat_status import treasury_status

MAX_PAGE = 100
PARTY = {"Sales Invoice": ("customer", "customer_name"), "Purchase Invoice": ("supplier", "supplier_name")}


@frappe.whitelist()
def get_dashboard_data(company=None, period="tm", from_date=None, to_date=None, start=0, page_length=20):
	frappe.has_permission("GL Entry", "read", throw=True)
	company = _validate_company(company)
	start, page_length = max(cint(start), 0), min(max(cint(page_length), 1), MAX_PAGE)
	return VATDashboard(company, period, from_date, to_date).build(start, page_length)


def _validate_company(company):
	allowed = _allowed_companies()
	company = company or frappe.defaults.get_user_default("Company") or (allowed[0] if allowed else None)
	if not company or company not in allowed:
		frappe.throw(_("You do not have access to company {0}").format(company or ""), frappe.PermissionError)
	return company


def _allowed_companies():
	names = frappe.get_all("Company", pluck="name", order_by="name asc")
	restricted = get_user_permissions().get("Company")
	if restricted:
		allowed = {p.get("doc") for p in restricted}
		names = [n for n in names if n in allowed]
	return names


class VATDashboard:
	def __init__(self, company, period, from_date, to_date):
		self.company, self.period = company, period
		self.today = getdate(today())
		self.start, self.end, self.label = periods.resolve(period, from_date, to_date, self.today, company)
		self.accounts = ledger.vat_accounts(company)
		self.rows = ledger.gl_rows(company, self.accounts, max(self.end, self.today))
		self.in_period = [r for r in self.rows if self.start <= r.posting_date <= self.end]
		self.docs = self._documents()

	def build(self, start, page_length):
		currency = frappe.get_cached_value("Company", self.company, "default_currency")
		symbol, on_right = frappe.get_cached_value("Currency", currency, ["symbol", "symbol_on_right"]) or ("", 0)
		now, prior = ledger.totals(self.in_period), ledger.totals(self.rows, *periods.previous(self.start, self.end))
		return {
			"company": self.company, "companies": _allowed_companies(), "currency": currency,
			"currency_symbol": symbol or currency, "currency_symbol_on_right": cint(on_right),
			"accounts": self.accounts, "today": self.today, "period": self.period,
			"period_start": self.start, "period_end": self.end, "period_label": self.label,
			"totals": {**now, "net": now["output"] - now["input"]},
			"prior": {**prior, "net": prior["output"] - prior["input"]},
			"balance": ledger.balance(self.rows, self.today),
			"balance_at_start": ledger.balance(self.rows, periods.previous(self.start, self.start)[1]),
			"series": self._series(),
			"counts": {s: len({r.voucher_no for r in self.in_period if r.source == s}) for s in ledger.SOURCES},
			"status": treasury_status(self.company, self.start, self.end),
			"top_customers": self._top("Sales Invoice"),
			"top_suppliers": self._top("Purchase Invoice"),
			"no_template": self._no_template_count(),
			"worklist": self._worklist(start, page_length),
			"can_read": {dt: frappe.has_permission(dt, "read") for dt in ("Sales Invoice", "Purchase Invoice", "Journal Entry")},
		}

	def _series(self):
		marks = periods.buckets(self.start, self.end)
		by = lambda source: [ledger.totals(self.rows, lo, hi)[source] for lo, hi, __ in marks]
		output, inp = by("output"), by("input")
		return {"labels": [m[2] for m in marks], "output": output, "input": inp,
			"net": [o - i for o, i in zip(output, inp)],
			"balance": [ledger.balance(self.rows, hi) for __, hi, __ in marks]}

	def _documents(self):
		"""Invoice headers behind the period's VAT postings, read with the user's permissions."""
		vat = {}
		for r in self.in_period:
			key = (r.voucher_type, r.voucher_no)
			entry = vat.setdefault(key, {"doctype": r.voucher_type, "name": r.voucher_no, "date": r.posting_date,
				"source": r.source, "vat": 0.0})
			entry["vat"] += ledger.amount(r)
		for doctype, (party, party_name) in PARTY.items():
			names = [k[1] for k in vat if k[0] == doctype]
			if not names or not frappe.has_permission(doctype, "read"):
				continue
			heads = frappe.get_list(doctype, filters={"name": ["in", names]}, limit_page_length=0,
				fields=["name", party, party_name, "base_net_total", "is_return", "status"])
			templated = set(frappe.get_all(f"{doctype} Item", filters={"parent": ["in", [h.name for h in heads]],
				"item_tax_template": ["is", "set"]}, pluck="parent"))
			for h in heads:
				vat[(doctype, h.name)].update({"party": h.get(party), "party_name": h.get(party_name) or h.get(party),
					"net": flt(h.base_net_total), "is_return": h.is_return, "status": h.status,
					"has_template": h.name in templated})
		return sorted(vat.values(), key=lambda d: (str(d["date"]), d["name"]), reverse=True)

	def _top(self, doctype):
		groups = {}
		for d in self.docs:
			if d["doctype"] != doctype or not d.get("party"):
				continue
			g = groups.setdefault(d["party"], {"party": d["party"], "name": d["party_name"], "vat": 0.0, "count": 0, "names": []})
			g["vat"] += d["vat"]
			g["count"] += 1
			g["names"].append(d["name"])
		rows = sorted(groups.values(), key=lambda g: -g["vat"])[:5]
		total = sum(g["vat"] for g in groups.values())
		for r in rows:
			r["pct"] = r["vat"] / total * 100 if total else 0
		return rows

	def _no_template_count(self):
		return len([d for d in self.docs if d["doctype"] in PARTY and d.get("party") and not d.get("has_template")])

	def _worklist(self, start, page_length):
		rows = self.docs[start:start + page_length]
		return {"rows": rows, "total": len(self.docs), "start": start, "page_length": page_length}
