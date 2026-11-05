# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""Permission checks for whitelisted methods. A whitelisted method is open to every logged-in
user, and page or report role lists do not protect it."""

import frappe
from frappe import _
from frappe.core.doctype.file.utils import find_file_by_url
from frappe.core.doctype.user_permission.user_permission import get_user_permissions


def require_doc(doctype, name, *ptypes):
	"""Throw unless the user holds every ptype on the document (read when none is given).

	The doctype check runs first: the document check loads `name`, and would otherwise tell
	an unauthorized caller which names exist.
	"""
	for ptype in ptypes or ("read",):
		frappe.has_permission(doctype, ptype, throw=True)
		frappe.has_permission(doctype, ptype, doc=name, throw=True)


def require_company(company):
	if not company or company not in allowed_companies():
		frappe.throw(_("You do not have access to company {0}").format(company or ""), frappe.PermissionError)


def require_report(report):
	if not frappe.get_doc("Report", report).is_permitted():
		frappe.throw(_("You do not have access to report {0}").format(report), frappe.PermissionError)


def scope_report_to_company(filters):
	"""Raw-SQL reports skip User Permissions, and their rows have no Company column for Frappe
	to filter on, so a user restricted by company must name one they are allowed."""
	company = (filters or {}).get("company")
	if company:
		require_company(company)
	elif get_user_permissions().get("Company"):
		frappe.throw(_("Select a company to run this report."))


def require_readable_file(file_url):
	"""A file URL from the browser must be a File this user can already read, so recording it
	cannot point a document at someone else's private file."""
	if not find_file_by_url(file_url):
		frappe.throw(_("File not found or you do not have access to it."), frappe.PermissionError)


def allowed_companies():
	names = frappe.get_all("Company", pluck="name", order_by="name asc")
	restricted = get_user_permissions().get("Company")
	if restricted:
		allowed = {p.get("doc") for p in restricted}
		names = [n for n in names if n in allowed]
	return names
