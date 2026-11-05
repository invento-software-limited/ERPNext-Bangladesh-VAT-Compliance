# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

"""Daily alert for challans that have not reached NBR, so nobody has to watch the list."""

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.utils import add_to_date, cint, now_datetime
from frappe.utils.user import get_users_with_role

ALERT_ROLES = ("System Manager", "Accounts Manager")


def report_sync_health():
	problems = _problems()
	if not problems:
		return
	users = {user for role in ALERT_ROLES for user in get_users_with_role(role)}
	if users:
		enqueue_create_notification(
			list(users),
			{
				"type": "Alert",
				"document_type": "VAT Invoice",
				"subject": _("VAT challan sync: {0}").format(", ".join(problems)),
			},
		)


def _problems():
	yesterday = add_to_date(now_datetime(), days=-1)
	counts = (
		(_("{0} pending over 24 hours"), {"status": "Pending", "creation": ["<", yesterday]}),
		(_("{0} failed"), {"status": "Failed"}),
		(_("{0} stuck syncing"), {"status": "Syncing"}),
	)
	problems = [
		label.format(n) for label, filters in counts if (n := frappe.db.count("VAT Invoice", filters))
	]
	if _integration_in_use() and not frappe.db.get_single_value("POS Vendor Configuration", "sync_schedule"):
		problems.append(_("no sync schedule set"))
	return problems


def _integration_in_use():
	# Sites that never set up the vendor must not get a daily alert about it.
	config = frappe.db.get_singles_dict("POS Vendor Configuration")
	return bool(config.get("base_url")) and not cint(config.get("disabled"))
