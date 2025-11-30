// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

frappe.query_reports["Sales VAT Management"] = {
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
			"options": "\nUnpaid\nPaid\nPartly Paid\nOverdue",
		},
		{
			fieldname: "status",
			label: "Challan Status",
			fieldtype: "MultiSelectList",
			options: [
				{ value: "IPNR", description: "Invoiced (Payment Not Received)" },
				{ value: "Collected", description: "Collected" },
				{ value: "DVCR", description: "Deducted (VDS Certificate received)" },
				{ value: "DVCNR", description: "Deducted  (VDS Certificate Not received)" },
			],
			get_data: () => {
				return [
					{ value: "IPNR", description: "Invoiced (Payment Not Received)" },
					{ value: "Collected", description: "Collected" },
					{ value: "DVCR", description: "Deducted (VDS Certificate received)" },
					{ value: "DVCNR", description: "Deducted  (VDS Certificate Not received)" },
				];
			}
		},
		{
			"fieldname": "customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer"
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
			if (data.status === "DVCR" || data.status === "Collected") {
				formatted_value = `<span class="indicator green">${value}</span>`;
			} else if (data.status === "DVCNR") {
				formatted_value = `<span class="indicator red">${value}</span>`;
			} else if (data.status === "IPNR") {
				formatted_value = `<span class="indicator blue">${value}</span>`;
			}
		}

		return formatted_value;
	},
	onload: function (report) {
		report.page.add_inner_button(__("Upload Challan"), function () {
			let selected_rows = report.get_checked_items();

			if (selected_rows.length === 0) {
				frappe.msgprint(__("Please select rows to upload challan."));
				return;
			}

			// Validate that selected rows have payment_entry_id
			let invalid_rows = selected_rows.filter(row => !row.payment_entry_id);
			if (invalid_rows.length > 0) {
				frappe.msgprint(__("Selected rows must have a Payment Entry."));
				return;
			}

			let invalid_status_rows = selected_rows.filter(row => row.status !== "DVCNR");
			if (invalid_status_rows.length > 0) {
				frappe.msgprint(__("Only rows with status 'DVCNR' can be selected for Upload Challan."));
				return;
			}

			let d = new frappe.ui.Dialog({
				title: 'Upload Challan',
				fields: [
					{
						label: 'Challan No',
						fieldname: 'challan_no',
						fieldtype: 'Data',
						reqd: 1
					},
					{
						label: 'Challan Date',
						fieldname: 'challan_date',
						fieldtype: 'Date',
						reqd: 1
					},
					{
						label: 'Challan Amount',
						fieldname: 'challan_amount',
						fieldtype: 'Currency',
						reqd: 1
					},
					{
						label: 'Branch and Bank Name',
						fieldname: 'branch_and_bank_name',
						fieldtype: 'Data',
						reqd: 1
					},
					{
						label: 'File',
						fieldname: 'file',
						fieldtype: 'Attach',
						reqd: 1
					},
					{
						label: 'Remarks',
						fieldname: 'remarks',
						fieldtype: 'Small Text'
					}
				],
				primary_action_label: 'Upload',
				primary_action(values) {
					frappe.call({
						method: 'vat_compliance.vat_compliance.report.sales_vat_management.sales_vat_management.upload_challan',
						args: {
							rows: selected_rows,
							challan_data: values
						},
						callback: function (r) {
							if (r.message) {
								frappe.msgprint(__("Challan uploaded successfully."));
								d.hide();
								report.refresh();
							}
						}
					});
				}
			});
			d.show();
		});
	}
};

