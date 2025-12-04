frappe.pages["vat_payment"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "VAT Payment",
		single_column: true,
	});

	page.vat_payment = new VATPayment(page);
};

class VATPayment {
	constructor(page) {
		this.page = page;
		this.make_filters();
		this.make_table();
		this.refresh();
	}

	make_filters() {
		this.from_date = this.page.add_field({
			label: "From Date",
			fieldtype: "Date",
			fieldname: "from_date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			change: () => this.refresh(),
		});

		this.to_date = this.page.add_field({
			label: "To Date",
			fieldtype: "Date",
			fieldname: "to_date",
			default: frappe.datetime.get_today(),
			change: () => this.refresh(),
		});

		this.company = this.page.add_field({
			label: "Company",
			fieldtype: "Link",
			options: "Company",
			fieldname: "company",
			default: frappe.defaults.get_user_default("Company"),
			change: () => this.refresh(),
		});

		this.page.set_primary_action("Refresh", () => this.refresh());
		this.page.add_inner_button("Make Payment", () => this.make_payment());
	}

	make_table() {
		this.table_wrapper = $(
			'<div style="border: 1px solid #ccc; border-radius: 5px;">'
		).appendTo(this.page.main);
		this.datatable = null;
	}

	refresh() {
		let filters = {
			from_date: this.from_date.get_value(),
			to_date: this.to_date.get_value(),
			company: this.company.get_value(),
		};

		if (!filters.company) return;

		frappe.call({
			method: "vat_compliance.vat_compliance.page.vat_payment.vat_payment.get_vat_payment_data",
			args: filters,
			callback: (r) => {
				this.render_data(r.message || []);
			},
		});
	}

	render_data(data) {
		if (data.length > 0) {
			let total_vds = data.reduce((sum, row) => sum + (parseFloat(row.vds_amount) || 0), 0);
			data.push({
				invoice_id: "Total",
				vds_amount: total_vds,
				is_total_row: true,
			});
		}

		let columns = [
			{
				name: "Payment Date",
				field: "payment_date",
				width: 100,
				format: (value) => frappe.datetime.str_to_user(value),
				id: "payment_date",
			},
			{ name: "Source Report", field: "source_report", width: 150, id: "source_report" },
			{ name: "Invoice ID", field: "invoice_id", width: 140, id: "invoice_id" },
			{ name: "Party Type", field: "party_type", width: 100, id: "party_type" },
			{ name: "Party Name", field: "party_name", width: 150, id: "party_name" },
			{
				name: "VAT Amount",
				field: "vds_amount",
				width: 120,
				format: (value) => format_currency(value),
				id: "vds_amount",
			},
			{ name: "Account Head", field: "liability_head", width: 200, id: "liability_head" },
			{ name: "Status", field: "status", width: 100, id: "status" },
		];

		if (this.datatable) {
			this.datatable.refresh(data);
		} else {
			this.datatable = new frappe.DataTable(this.table_wrapper.get(0), {
				columns: columns,
				data: data,
				checkboxColumn: true,
				layout: "fluid",
			});
		}
	}

	make_payment() {
		if (!this.datatable) return;
		let selected_indices = this.datatable.rowmanager.getCheckedRows();
		if (selected_indices.length === 0) {
			frappe.msgprint(__("Please select at least one row."));
			return;
		}

		let selected_rows = selected_indices
			.map((idx) => this.datatable.datamanager.data[idx])
			.filter((row) => row && !row.is_total_row);

		if (selected_rows.length === 0) {
			frappe.msgprint(__("Please select at least one valid row."));
			return;
		}

		frappe.call({
			method: "vat_compliance.vat_compliance.page.vat_payment.vat_payment.make_journal_entry",
			args: {
				rows: selected_rows,
			},
			freeze: true,
			callback: (r) => {
				if (r.message) {
					frappe.set_route("Form", "Journal Entry", r.message);
				}
			},
		});
	}
}
