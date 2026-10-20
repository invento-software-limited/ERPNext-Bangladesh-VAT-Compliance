// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

// Header above the table: KPI cards and charts from this report's own rows (vat_report/kit.js).
const vat_report_header = (report, build) =>
	frappe.require("/assets/vat_compliance/js/vat_report/loader.js", () =>
		vat_compliance.report_kit_ready.then((kit) => kit.render(report, (meta) => build(meta, kit)))
	);

frappe.query_reports["Purchase Register - Mushak 6_1"] = {
	after_refresh(report) {
		vat_report_header(report, mushak_61_header);
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
		{
			fieldname: "item_type",
			label: "Item Type",
			fieldtype: "Select",
			options: "\nStock Item\nService Item",
			default: "",
		},
		{
			fieldname: "supplier",
			label: "Supplier",
			fieldtype: "Link",
			options: "Supplier",
		},
	],
};

function mushak_61_header(m, kit) {
	const rate = m.taxable ? (m.vat / m.taxable) * 100 : 0;
	const rated = m.taxable ? (m.rated_taxable / m.taxable) * 100 : 0;
	const types = m.by_item_type.map((t) => ({ label: __(t.key), value: t.value, count: t.count, color: t.key === "Stock Item" ? "#22405e" : "#17626e", act: "item_type", arg: t.key }));
	const chart = kit.bars({ series: m.trend_vat, act: "period" });
	const cards = [
		kit.card({ k: __("Taxable purchases"), v: kit.money(m.taxable), pill: [__("{0} bill(s)", [m.documents]), "#3b4757"], sub: __("{0} line(s)", [m.lines]),
			visual: kit.mini.area_sparkline(m.trend.values, m.trend.labels, "#2f5a86") }),
		kit.card({ k: __("Input VAT"), tint: true, v: kit.money(m.vat), pill: [kit.fmt.pct(rate, 1), "#0a5a3c"], sub: __("of taxable value"),
			visual: kit.mini.area_sparkline(m.trend_vat.values, m.trend_vat.labels, "#097C52") }),
		kit.card({ k: __("VAT-rated value"), v: kit.money(m.rated_taxable), pill: [kit.fmt.pct(rated, 0), "#17505d"], sub: __("of taxable carries VAT"),
			visual: kit.mini.gauge(rated, "#17626e", [__("rated"), __("not rated")]) }),
		kit.card({ k: __("Stock vs service"), v: kit.count(m.by_item_type.length, __("type(s)")), sub: types.map((t) => `${t.label} ${kit.fmt.pct((t.value / (m.taxable || 1)) * 100, 0)}`).join(" · "),
			visual: kit.seg_bar(types) }),
	];
	return {
		html: `<div class="mx surf">${cards.join("")}</div>
			<div class="surf card"><div class="two">
				<div><div class="hrow"><div class="h">${__("VAT by period")}</div><div class="hs">${kit.esc(kit.subtitle(m, chart.unit))}</div></div>${chart.svg}
					<div class="note">${kit.esc(__("Click a bar to narrow the register to that period."))}</div></div>
				<div><div class="hrow"><div class="h">${__("By item type")}</div><div class="hs">${__("Click to filter the table")}</div></div>${kit.composition(types)}
					<div class="hrow" style="margin-top:18px"><div class="h">${__("Top suppliers")}</div><div class="hs">${__("By VAT")}</div></div>
					${kit.rank(m.parties.map((p) => ({ label: p.name || p.key, value: p.value, sub: p.count, act: "supplier", arg: p.key })))}</div>
			</div></div>`,
		actions: {
			item_type: (item_type, report) => kit.set_filters(report, { item_type }),
			period: (range, report) => kit.set_filters(report, range),
			supplier: (supplier, report) => kit.set_filters(report, { supplier }),
		},
	};
}
