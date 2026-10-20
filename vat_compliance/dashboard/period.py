# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""Tax-period presets for the VAT dashboard. VAT is returned monthly (Mushak 9.1),
so the presets are calendar months and the company's fiscal year."""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, date_diff, get_first_day, get_last_day, getdate

LABELS = {"tm": "This month", "lm": "Last month", "fy": "This fiscal year", "1y": "Last 12 months"}
MAX_CUSTOM_DAYS = 366 * 3


def resolve(period, from_date=None, to_date=None, today=None, company=None):
	"""Inclusive (start, end, label); `end` never runs past today."""
	today = getdate(today)
	if period == "custom":
		if not from_date or not to_date:
			frappe.throw(_("Choose both a From and a To date."))
		start, end = getdate(from_date), getdate(to_date)
		if start > end:
			frappe.throw(_("From date must be on or before To date."))
		if date_diff(end, start) > MAX_CUSTOM_DAYS:
			frappe.throw(_("Choose a range of three years or less."))
		return start, end, f"{start:%d %b %Y} – {end:%d %b %Y}"
	if period == "tm":
		return getdate(get_first_day(today)), today, _(LABELS[period])
	if period == "lm":
		first = getdate(get_first_day(add_months(today, -1)))
		return first, getdate(get_last_day(first)), f"{first:%B %Y}"
	if period == "fy":
		from erpnext.accounts.utils import get_fiscal_year

		_name, start, _end = get_fiscal_year(today, company=company)
		return getdate(start), today, _("FY {0}").format(_name)
	if period == "1y":
		return getdate(add_months(today.replace(day=1), -11)), today, _(LABELS[period])
	frappe.throw(_("Unknown dashboard period: {0}").format(period))


def previous(start, end):
	"""The window of equal length immediately before (start, end)."""
	span = date_diff(end, start)
	prev_end = add_days(start, -1)
	return getdate(add_days(prev_end, -span)), getdate(prev_end)


def buckets(start, end):
	"""Chart buckets: weekly up to ~3 months, monthly beyond. Each is (start, end, label)."""
	start, end = getdate(start), getdate(end)
	out = []
	if date_diff(end, start) <= 92:
		cursor = start
		while cursor <= end:
			stop = min(getdate(add_days(cursor, 6)), end)
			out.append((cursor, stop, f"{cursor:%d %b}"))
			cursor = getdate(add_days(stop, 1))
		return out
	cursor = start.replace(day=1)
	while cursor <= end:
		stop = min(getdate(add_days(add_months(cursor, 1), -1)), end)
		out.append((max(cursor, start), stop, f"{cursor:%b}"))
		cursor = getdate(add_months(cursor, 1))
	return out
