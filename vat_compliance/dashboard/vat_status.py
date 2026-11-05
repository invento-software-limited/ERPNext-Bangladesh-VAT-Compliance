# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""Treasury status exactly as the app's own reports define it.

Sales VAT Management: IPNR (invoiced, payment not received) · Collected · CDGT (deposited) ·
DVCNR / DVCR (withheld by the customer, certificate not received / received).
VDS Management: DNGT (deducted from a supplier, not deposited) · DDGT (deposited).
The VAT Payment page treats Collected + DNGT as what is still to be deposited.
"""

import frappe
from frappe.utils import flt

SALES_REPORT = "Sales VAT Management"
VDS_REPORT = "VDS Management"
SALES_STATUSES = ("IPNR", "Collected", "CDGT", "DVCNR", "DVCR")
VDS_STATUSES = ("DNGT", "DDGT")


def treasury_status(company, start, end):
	filters = frappe._dict(company=company, from_date=start, to_date=end)
	failed = []
	sales = _by_status(SALES_REPORT, filters, SALES_STATUSES, failed) if _can_open(SALES_REPORT) else None
	vds = _by_status(VDS_REPORT, filters, VDS_STATUSES, failed) if _can_open(VDS_REPORT) else None
	due = None
	if sales is not None and vds is not None:
		due = sales["Collected"]["amount"] + vds["DNGT"]["amount"]
	return {"sales": sales, "vds": vds, "awaiting_deposit": due, "failed": failed}


def _can_open(report):
	return frappe.db.exists("Report", report) and bool(frappe.get_doc("Report", report).is_permitted())


def _by_status(report, filters, statuses, failed):
	"""Rows grouped by status, or None when the report fails: zero would read as nothing due.
	An indented tax group has its own status, and counts only if it differs from its payment."""
	execute = _execute(report)
	out = {s: {"count": 0, "amount": 0.0} for s in statuses}
	try:
		_columns, rows, *_rest = execute(frappe._dict(filters))
	except Exception:
		frappe.log_error(title=f"VAT dashboard: {report} failed")
		failed.append(report)
		return None
	parent = None
	for row in rows or []:
		status = row.get("status") or parent
		if status in out:
			out[status]["amount"] += flt(row.get("vds_amount"))
			if not row.get("indent") or status != parent:
				out[status]["count"] += 1
		if not row.get("indent"):
			parent = status
	return out


def _execute(report):
	if report == SALES_REPORT:
		from vat_compliance.vat_compliance.report.sales_vat_management.sales_vat_management import execute
	else:
		from vat_compliance.vat_compliance.report.vds_management.vds_management import execute
	return execute
