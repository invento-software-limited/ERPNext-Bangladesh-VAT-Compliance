// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

// Header above the table: KPI cards and charts from this report's own rows (vat_report/kit.js).
const vat_report_header = (report, build) =>
	frappe.require("/assets/vat_compliance/js/vat_report/loader.js", () =>
		vat_compliance.report_kit_ready.then((kit) => kit.render(report, (meta) => build(meta, kit)))
	);

frappe.query_reports["Supplier Mushak 6 3"] = {
	after_refresh(report) {
		vat_report_header(report, supplier_63_header);
	},
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
			const collected = data.status == "Collected";
			value = `<span style="display:inline-block;padding:2px 8px;border-radius:5px;font-size:10.5px;font-weight:600;color:#fff;background:${collected ? "#0a5a3c" : "#7e2a30"}">${frappe.utils.escape_html(collected ? __("Collected") : __("Not Collected"))}</span>`;
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

function supplier_63_header(m, kit) {
	const share = m.bills ? (m.collected / m.bills) * 100 : 0;
	const chart = kit.bars({ series: m.trend_count, act: "period", counts: true });
	const cards = [
		kit.card({ k: __("Purchase bills"), v: kit.count(m.bills), sub: __("in this period"),
			visual: kit.mini.area_sparkline(m.trend_count.values, m.trend_count.labels, "#2f5a86") }),
		kit.card({ k: __("Certificates collected"), v: kit.count(m.collected), act: "status", arg: "Collected", pill: [kit.fmt.pct(share, 0), "#0a5a3c"],
			sub: __("of bills"), visual: kit.mini.gauge(share, "#097C52", [__("collected"), __("target 100%")]) }),
		kit.card({ k: __("Pending certificates"), tint: true, v: kit.count(m.pending), act: "status", arg: "Not Collected",
			pill: [kit.fmt.compact(m.pending_value), "#7e2a30"], sub: __("bill value without 6.3"),
			visual: kit.mini.gauge(100 - share, "#a3302f", [__("pending"), ""]) }),
		kit.card({ k: __("Value covered"), v: kit.money(m.collected_value), sub: __("of {0} billed", [kit.fmt.compact(m.value)]),
			visual: kit.seg_bar([{ label: __("Collected"), value: m.collected_value, color: "#097C52" }, { label: __("Pending"), value: m.pending_value, color: "#a3302f" }]) }),
	];
	return {
		html: `<div class="mx surf">${cards.join("")}</div>
			<div class="surf card"><div class="two">
				<div><div class="hrow"><div class="h">${__("Bills by period")}</div><div class="hs">${kit.esc(kit.subtitle(m, ""))}</div></div>${chart.svg}</div>
				<div><div class="hrow"><div class="h">${__("Pending by supplier")}</div><div class="hs">${__("Bill value · click to filter")}</div></div>
					${kit.rank(m.pending_suppliers.map((s) => ({ label: s.key, value: s.value, sub: __("{0} bill(s)", [s.count]), act: "pending_supplier", arg: s.key })), ["#7e2a30", "#a3302f", "#a3552f", "#8a5a16", "#c58a6a", "#d9b39c"])}</div>
			</div></div>`,
		actions: {
			status: (status, report) => kit.set_filters(report, { status }),
			pending_supplier: (supplier, report) => kit.set_filters(report, { supplier, status: "Not Collected" }),
			period: (range, report) => kit.set_filters(report, range),
		},
	};
}
