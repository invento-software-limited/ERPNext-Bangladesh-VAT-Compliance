// Copyright (c) 2025, Invento Software Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Service Type wise Sales"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			width: 100,
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			width: 100,
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "service_type",
			label: __("Service Type"),
			fieldtype: "Link",
			options: "VC Service Type",
			width: 120,
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nPending\nSynced\nFailed\nReturn\nPartly Return",
			width: 100,
		},
	],
};
