// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

// Header above the table: KPI cards and charts from this report's own rows (vat_report/kit.js).
const vat_report_header = (report, build) =>
	frappe.require("/assets/vat_compliance/js/vat_report/loader.js", () =>
		vat_compliance.report_kit_ready.then((kit) => kit.render(report, (meta) => build(meta, kit)))
	);

frappe.query_reports["Purchase Sales Ledger For Trader"] = {
	after_refresh(report) {
		vat_report_header(report, trader_header);
	},
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

function trader_header(m, kit) {
	const net = m.output_vat - m.input_vat;
	const chart = kit.bars({ series: m.trend_output, line: m.trend_input, act: "period", names: [__("Output VAT"), __("Input VAT")] });
	const rate = (vat, value) => kit.fmt.pct(value ? (vat / value) * 100 : 0, 1);
	const cards = [
		kit.card({ k: __("Purchases"), v: kit.money(m.purchases), pill: [__("{0} bill(s)", [m.purchase_bills]), "#22405e"], sub: __("taxable value"),
			visual: kit.mini.area_sparkline(m.trend_purchases.values, m.trend_purchases.labels, "#2f5a86") }),
		kit.card({ k: __("Input VAT"), v: kit.money(m.input_vat), pill: [rate(m.input_vat, m.purchases), "#17505d"], sub: __("of purchases"),
			visual: kit.mini.area_sparkline(m.trend_input.values, m.trend_input.labels, "#17626e") }),
		kit.card({ k: __("Sales"), v: kit.money(m.sales), pill: [__("{0} invoice(s)", [m.sales_invoices]), "#0a5a3c"], sub: __("taxable value"),
			visual: kit.mini.area_sparkline(m.trend_sales.values, m.trend_sales.labels, "#097C52") }),
		kit.card({ k: __("Output VAT"), v: kit.money(m.output_vat), pill: [rate(m.output_vat, m.sales), "#0a5a3c"], sub: __("of sales"),
			visual: kit.mini.area_sparkline(m.trend_output.values, m.trend_output.labels, "#097C52") }),
		kit.card({ k: __("Net VAT"), tint: true, v: kit.money(net), pill: [net < 0 ? __("credit") : __("payable"), net < 0 ? "#17505d" : "#7e2a30"], sub: __("output − input"),
			visual: kit.mini.bipolar_sparkline(m.trend_net.values, m.trend_net.labels, "#a3302f", "#17626e") }),
	];
	return {
		html: `<div class="mx surf c5">${cards.join("")}</div>
			<div class="surf card"><div class="two">
				<div><div class="hrow"><div class="h">${__("Output vs input VAT")}</div><div class="hs">${kit.esc(kit.subtitle(m, chart.unit))}</div></div>${chart.svg}
					<div class="lgd"><span><i style="background:#097C52"></i>${__("Output VAT")}</span><span><i style="background:#a3552f;height:2px"></i>${__("Input VAT")}</span></div></div>
				<div><div class="hrow"><div class="h">${__("VAT position")}</div><div class="hs">${__("This ledger's period")}</div></div>
					${kit.composition([{ label: __("Output VAT"), value: m.output_vat, color: "#097C52" }, { label: __("Input VAT"), value: m.input_vat, color: "#2f5a86" }])}
					<div class="note">${kit.esc(__("Net {0} = output {1} − input {2}", [kit.fmt.compact(net), kit.fmt.compact(m.output_vat), kit.fmt.compact(m.input_vat)]))}</div></div>
			</div></div>`,
		actions: { period: (range, report) => kit.set_filters(report, range) },
	};
}
