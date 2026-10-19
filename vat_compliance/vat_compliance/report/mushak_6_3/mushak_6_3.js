// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

// Header above the table: KPI cards and charts from this report's own rows (vat_report/kit.js).
const vat_report_header = (report, build) =>
	frappe.require("/assets/vat_compliance/js/vat_report/loader.js", () =>
		vat_compliance.report_kit_ready.then((kit) => kit.render(report, (meta) => build(meta, kit)))
	);

frappe.query_reports["Mushak 6_3"] = {
	after_refresh(report) {
		vat_report_header(report, mushak_63_header);
	},
	formatter(value, row, column, data, default_formatter) {
		const out = default_formatter(value, row, column, data);
		if (data && column.fieldname === "status" && value) {
			return `<span style="display:inline-block;padding:2px 8px;border-radius:5px;font-size:10.5px;font-weight:600;color:#fff;background:${MUSHAK_63_COLORS[value] || "#3b4757"}">${frappe.utils.escape_html(value)}</span>`;
		}
		return out;
	},
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

const MUSHAK_63_COLORS = { Paid: "#0a5a3c", Unpaid: "#7a4f12", Overdue: "#7e2a30", "Partly Paid": "#8a5a16", Return: "#3b4757", "Credit Note Issued": "#5c6672" };

function mushak_63_header(m, kit) {
	const rate = m.net ? (m.vat / m.net) * 100 : 0;
	const open = m.statuses.filter((s) => ["Unpaid", "Overdue", "Partly Paid"].includes(s.key));
	const open_value = open.reduce((t, s) => t + s.value, 0);
	const parts = m.statuses.map((s) => ({ label: __(s.key), value: s.value, count: s.count, color: MUSHAK_63_COLORS[s.key] || "#5c6672", act: "status", arg: s.key }));
	const chart = kit.bars({ series: m.trend_vat, act: "period" });
	const cards = [
		kit.card({ k: __("Invoices issued"), v: kit.count(m.invoices), sub: __("Mushak 6.3 challans"),
			visual: kit.mini.area_sparkline(m.trend_count.values, m.trend_count.labels, "#2f5a86") }),
		kit.card({ k: __("Net value"), v: kit.money(m.net), sub: __("excluding VAT"), visual: kit.seg_bar(parts) }),
		kit.card({ k: __("VAT charged"), tint: true, v: kit.money(m.vat), pill: [kit.fmt.pct(rate, 1), "#0a5a3c"], sub: __("of net value"),
			visual: kit.mini.area_sparkline(m.trend_vat.values, m.trend_vat.labels, "#097C52") }),
		kit.card({ k: __("Unpaid & overdue"), v: kit.money(open_value), pill: [__("{0} inv.", [open.reduce((t, s) => t + s.count, 0)]), "#7e2a30"],
			sub: __("net value still open"), visual: kit.mini.gauge(m.net ? (open_value / m.net) * 100 : 0, "#a3302f", [__("of net value"), ""]) }),
	];
	return {
		html: `<div class="mx surf">${cards.join("")}</div>
			<div class="surf card"><div class="two">
				<div><div class="hrow"><div class="h">${__("VAT charged by period")}</div><div class="hs">${kit.esc(kit.subtitle(m, chart.unit))}</div></div>${chart.svg}</div>
				<div><div class="hrow"><div class="h">${__("Invoice status")}</div><div class="hs">${__("Net value · click to filter")}</div></div>${kit.composition(parts)}</div>
			</div></div>`,
		actions: {
			status: (status, report) => kit.set_filters(report, { status }),
			period: (range, report) => kit.set_filters(report, range),
		},
	};
}
