// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

frappe.query_reports["Supplier Mushak 6 3"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "Collected", "Not Collected"],
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "status") {
			if (data.status == "Collected") {
				value = `<span class="indicator green">${__("Collected")}</span>`;
			} else {
				value = `<span class="indicator red">${__("Not Collected")}</span>`;
			}
		}

		if (column.fieldname == "custom_mushak_63" && value) {
			value = `<a href="${value}" target="_blank" style="text-decoration: underline;">${value}</a>`;
		}

		if (column.fieldname == "action") {
			if (data.status == "Not Collected") {
				value = `<button class="btn btn-xs btn-primary" onclick="frappe.query_reports['Supplier Mushak 6 3'].upload_file('${
					data.invoice
				}')">${__("Upload")}</button>`;
			} else {
				value = "";
			}
		}

		return value;
	},

	upload_file: function (invoice_id) {
		new frappe.ui.FileUploader({
			doctype: "Purchase Invoice",
			docname: invoice_id,
			on_success: (file_doc) => {
				frappe.call({
					method: "vat_compliance.vat_compliance.report.supplier_mushak_6_3.supplier_mushak_6_3.upload_mushak_63",
					args: {
						invoice_id: invoice_id,
						file_url: file_doc.file_url,
					},
					callback: function (r) {
						if (r.message) {
							frappe.show_alert({
								message: __("File uploaded successfully"),
								indicator: "green",
							});
							frappe.query_report.refresh();
						}
					},
				});
			},
		});
	},
};
