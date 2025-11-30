// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

frappe.query_reports["VDS Management"] = {
	filters: [
		{
			"fieldname": "from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "invoice_status",
			"label": "Invoice Status",
			"fieldtype": "Select",
			"options": "\nPaid\nPartly Paid\nOverdue",
		},
		{
			"fieldname": "status",
			"label": "Challan Status",
			"fieldtype": "Select",
			"options": "\nDNGT\nDDGT",
		},
		{
			"fieldname": "vendor",
			"label": "Vendor",
			"fieldtype": "Link",
			"options": "Supplier"
		},
		{
			"fieldname": "company",
			"label": "Company",
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"read_only": 1
		}
	],
	get_datatable_options(options) {
		return Object.assign(options, {
			checkboxColumn: true,
		});
	},
	formatter: function (value, row, column, data, default_formatter) {
		let formatted_value = default_formatter(value, row, column, data);
		if (data && column.fieldname === "status") {
			if (data.status === "DDGT") {
				formatted_value = `<span class="indicator green">${value}</span>`;
			} else if (data.status === "DNGT") {
				formatted_value = `<span class="indicator red">${value}</span>`;
			}
		}

		return formatted_value;
	},
	onload: function (report) {
		report.page.add_inner_button(__("Make Payment"), function () {
			let selected_rows = report.get_checked_items();
			console.log(selected_rows);

			// Filter out rows that are already paid (DDGT)
			let valid_rows = selected_rows.filter(row => row.status !== "DDGT");

			if (valid_rows.length === 0) {
				if (selected_rows.length > 0) {
					frappe.msgprint(__("Selected rows are already paid (DDGT). Please select unpaid rows."));
				} else {
					frappe.msgprint(__("Please select at least one row to make payment."));
				}
				return;
			}

			frappe.call({
				method: "vat_compliance.vat_compliance.report.vds_management.vds_management.make_journal_entry",
				args: {
					rows: valid_rows
				},
				callback: function (r) {
					if (r.message) {
						frappe.set_route("Form", "Journal Entry", r.message);
					}
				}
			});
		});
	}
};
