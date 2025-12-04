// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

frappe.query_reports["Purchase Sales Ledger For Trader"] = {
	filters: [
		{
			fieldname: "from_date",
			fieldtype: "Date",
			label: "From Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			fieldtype: "Date",
			label: "To Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
		},
		{
			fieldname: "company",
			fieldtype: "Link",
			options: "Company",
			label: "Company",
			default: frappe.defaults.get_user_default("Company"),
			read_only: 1,
			reqd: 1,
		},
	],
};
