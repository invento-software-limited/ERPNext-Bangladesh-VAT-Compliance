// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

frappe.query_reports["Mushak 6_3"] = {
	filters: [
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			label: "To Date",
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
		},
		{
			fieldname: "company",
			label: "Company",
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			read_only: 1,
		},
		{
			fieldname: "customer",
			label: "Customer",
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "sales_invoice",
			label: "Sales Invoice",
			fieldtype: "Link",
			options: "Sales Invoice",
		},
		{
			fieldname: "status",
			label: "Status",
			fieldtype: "Select",
			options: [
				"",
				"Draft",
				"Return",
				"Credit Note Issued",
				"Submitted",
				"Paid",
				"Partly Paid",
				"Unpaid",
				"Unpaid and Discounted",
				"Partly Paid and Discounted",
				"Overdue and Discounted",
				"Overdue",
				"Cancelled",
				"Internal Transfer",
			].join("\n"),
		},
	],
	get_datatable_options(options) {
		return Object.assign(options, {
			cellHeight: 36,
		});
	},
	onload(report) {
		// Add Download All button
		this.setup_download_all_button(report);
	},

	setup_download_all_button(report) {
		// Add Download All button to the page
		report.page.add_inner_button(__("Download All"), () => {
			this.download_all_invoices(report);
		});
	},

	download_all_invoices(report) {
		// Show loading indicator
		const filters = report.get_values();

		window.open(
			frappe.urllib.get_full_url(
				"/api/method/vat_compliance.vat_compliance.report.mushak_6_3.mushak_6_3.download_all_invoices?filters=" +
					encodeURIComponent(JSON.stringify(filters))
			)
		);
	},
};
