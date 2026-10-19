# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""Helpers the VAT reports use to build their header `meta` (the third value
`execute()` returns, read by public/js/vat_report/kit.js).

Every figure is summed from the same rows the report returns to its table, so a
card can never disagree with the grid below it.
"""

from collections import OrderedDict

import frappe
from frappe.utils import cint, flt, getdate

from vat_compliance.dashboard import period as periods


def meta(filters, **sections):
	"""The header payload: currency, the period the filters cover, plus report sections."""
	company = (filters or {}).get("company") or frappe.defaults.get_user_default("Company")
	currency = frappe.get_cached_value("Company", company, "default_currency") if company else None
	symbol, on_right = (frappe.get_cached_value("Currency", currency, ["symbol", "symbol_on_right"]) if currency else None) or ("", 0)
	return {
		"vat_header": 1,
		"currency": {"code": currency, "symbol": symbol or currency or "", "on_right": cint(on_right)},
		"period": {"from_date": (filters or {}).get("from_date"), "to_date": (filters or {}).get("to_date")},
		**sections,
	}


def monthly(rows, date_of, value_of, filters):
	"""Rows bucketed over the filter window: weekly up to ~3 months, monthly beyond.
	Returns {labels, values, starts, ends}; starts/ends let a bar set the date filters."""
	dates = [getdate(date_of(r)) for r in rows if date_of(r)]
	start = getdate(filters.get("from_date") or (min(dates) if dates else None))
	end = getdate(filters.get("to_date") or (max(dates) if dates else None))
	if not start or not end or start > end:
		return {"labels": [], "values": [], "starts": [], "ends": []}
	marks = periods.buckets(start, end)
	values = [0.0] * len(marks)
	for r in rows:
		d = date_of(r)
		if not d:
			continue
		d = getdate(d)
		for i, (lo, hi, _label) in enumerate(marks):
			if lo <= d <= hi:
				values[i] += flt(value_of(r))
				break
	return {"labels": [m[2] for m in marks], "values": values,
		"starts": [str(m[0]) for m in marks], "ends": [str(m[1]) for m in marks]}


def group(rows, key_of, value_of, limit=None):
	"""[{key, value, count}] by key, largest value first."""
	out = OrderedDict()
	for r in rows:
		key = key_of(r)
		if key in (None, ""):
			continue
		g = out.setdefault(key, {"key": key, "value": 0.0, "count": 0})
		g["value"] += flt(value_of(r))
		g["count"] += 1
	ranked = sorted(out.values(), key=lambda g: -g["value"])
	return ranked[:limit] if limit else ranked


def total(rows, value_of):
	return sum(flt(value_of(r)) for r in rows)


def pct(part, whole):
	return flt(part) / flt(whole) * 100 if flt(whole) else 0
