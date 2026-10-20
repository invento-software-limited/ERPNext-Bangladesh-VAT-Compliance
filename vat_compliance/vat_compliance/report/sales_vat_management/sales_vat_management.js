// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

// Deep-fill status colours, shared by the table pills and the header.
const SALES_VAT_COLORS = { IPNR: "#22405e", Collected: "#7a4f12", CDGT: "#0a5a3c", DVCR: "#17505d", DVCNR: "#7e2a30" };

// Header above the table: KPI cards and charts from this report's own rows (vat_report/kit.js).
const vat_report_header = (report, build) =>
	frappe.require("/assets/vat_compliance/js/vat_report/loader.js", () =>
		vat_compliance.report_kit_ready.then((kit) => kit.render(report, (meta) => build(meta, kit)))
	);

frappe.query_reports["Sales VAT Management"] = {
	filters: [
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: "To Date",
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "invoice_status",
			label: "Invoice Status",
			fieldtype: "Select",
			options: "\nUnpaid\nPaid\nPartly Paid\nOverdue",
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
					{ value: "CDGT", description: "Collected And Deposited Into Gov't Treasury" },
					{ value: "DVCR", description: "Deducted (VDS Certificate received)" },
					{ value: "DVCNR", description: "Deducted  (VDS Certificate Not received)" },
				];
			},
		},
		{
			fieldname: "customer",
			label: "Customer",
			fieldtype: "Link",
			options: "Customer",
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
			fieldname: "sales_invoice",
			label: "Sales Invoice",
			fieldtype: "Link",
			options: "Sales Invoice",
		},
		{
			fieldname: "payment_entry",
			label: "Payment Entry",
			fieldtype: "Link",
			options: "Payment Entry",
		},
	],
	get_datatable_options(options) {
		return Object.assign(options, {
			checkboxColumn: true,
		});
	},
	formatter: function (value, row, column, data, default_formatter) {
		let formatted_value = default_formatter(value, row, column, data);
		if (data && column.fieldname === "status" && SALES_VAT_COLORS[data.status]) {
			formatted_value = `<span style="display:inline-block;padding:2px 8px;border-radius:5px;font-size:10.5px;font-weight:600;color:#fff;background:${
				SALES_VAT_COLORS[data.status]
			}">${frappe.utils.escape_html(value)}</span>`;
		}
		return formatted_value;
	},
	after_refresh(report) {
		vat_report_header(report, sales_vat_header);
	},
	onload: function (report) {
		report.page.add_inner_button(__("Upload Challan"), function () {
			let selected_rows = report.get_checked_items();

			if (selected_rows.length === 0) {
				frappe.msgprint(__("Please select rows to upload challan."));
				return;
			}

			// Validate that selected rows have payment_entry_id
			let invalid_rows = selected_rows.filter((row) => !row.payment_entry_id);
			if (invalid_rows.length > 0) {
				frappe.msgprint(__("Selected rows must have a Payment Entry."));
				return;
			}

			let invalid_status_rows = selected_rows.filter((row) => row.status !== "DVCNR");
			if (invalid_status_rows.length > 0) {
				frappe.msgprint(
					__("Only rows with status 'DVCNR' can be selected for Upload Challan.")
				);
				return;
			}

			let d = new frappe.ui.Dialog({
				title: "Upload Challan",
				fields: [
					{
						label: "Challan No",
						fieldname: "challan_no",
						fieldtype: "Data",
						reqd: 1,
					},
					{
						label: "Challan Date",
						fieldname: "challan_date",
						fieldtype: "Date",
						reqd: 1,
					},
					{
						label: "Challan Amount",
						fieldname: "challan_amount",
						fieldtype: "Currency",
						reqd: 1,
					},
					{
						label: "Branch and Bank Name",
						fieldname: "branch_and_bank_name",
						fieldtype: "Data",
						reqd: 1,
					},
					{
						label: "File",
						fieldname: "file",
						fieldtype: "Attach",
						reqd: 1,
					},
					{
						label: "Remarks",
						fieldname: "remarks",
						fieldtype: "Small Text",
					},
				],
				primary_action_label: "Upload",
				primary_action(values) {
					frappe.call({
						method: "vat_compliance.vat_compliance.report.sales_vat_management.sales_vat_management.upload_challan",
						args: {
							rows: selected_rows,
							challan_data: values,
						},
						callback: function (r) {
							if (r.message) {
								frappe.msgprint(__("Challan uploaded successfully."));
								d.hide();
								report.refresh();
							}
						},
					});
				},
			});
			d.show();
		});
	},
};

function sales_vat_header(m, kit) {
	const st = Object.fromEntries(m.statuses.map((s) => [s.status, s]));
	const share = (keys) => (m.output ? (keys.reduce((t, k) => t + st[k].amount, 0) / m.output) * 100 : 0);
	const gauge = (keys) => kit.mini.gauge(share(keys), SALES_VAT_COLORS[keys[0]], [`${kit.fmt.pct(share(keys), 0)} ${__("of output")}`, ""]);
	const status_card = (k, keys, sub, tint) =>
		kit.card({
			k, tint, sub, act: "status", arg: keys, title: __("Show these rows"),
			v: kit.money(keys.reduce((t, s) => t + st[s].amount, 0)),
			pill: [__("{0} inv.", [keys.reduce((t, s) => t + st[s].count, 0)]), SALES_VAT_COLORS[keys[0]]],
			visual: gauge(keys),
		});
	const withheld = st.DVCR.amount + st.DVCNR.amount;
	const chart = kit.bars({ series: m.trend, act: "period" });
	const cards = [
		kit.card({ k: __("Output VAT"), v: kit.money(m.output), pill: [__("{0} inv.", [m.invoices]), "#3b4757"], sub: __("on these invoices"),
			visual: kit.mini.area_sparkline(m.trend.values, m.trend.labels, "#097C52") }),
		status_card(__("Invoiced, unpaid"), ["IPNR"], "IPNR"),
		status_card(__("Collected, to deposit"), ["Collected"], __("awaiting deposit"), true),
		status_card(__("Deposited"), ["CDGT"], "CDGT"),
		kit.card({ k: __("Withheld by customers"), v: kit.money(withheld), act: "status", arg: ["DVCR", "DVCNR"],
			pill: [__("{0} cert. pending", [st.DVCNR.count]), st.DVCNR.count ? "#7e2a30" : "#3b4757"],
			visual: kit.seg_bar([{ label: "DVCR", value: st.DVCR.amount, color: "#17505d" }, { label: "DVCNR", value: st.DVCNR.amount, color: "#7e2a30" }]) }),
	];
	const parts = m.statuses.map((s) => ({ label: `${s.status} · ${s.label}`, value: s.amount, count: s.count, color: SALES_VAT_COLORS[s.status], act: "status", arg: [s.status] }));
	return {
		html: `<div class="mx surf c5">${cards.join("")}</div>
			<div class="surf card"><div class="two">
				<div><div class="hrow"><div class="h">${__("Output VAT by period")}</div><div class="hs">${kit.esc(kit.subtitle(m, chart.unit))}</div></div>${chart.svg}</div>
				<div><div class="hrow"><div class="h">${__("Challan status")}</div><div class="hs">${__("Click a status to filter the table")}</div></div>${kit.composition(parts)}</div>
			</div></div>`,
		actions: {
			status: (keys, report) => kit.set_filters(report, { status: keys }),
			period: (range, report) => kit.set_filters(report, range),
		},
	};
}
