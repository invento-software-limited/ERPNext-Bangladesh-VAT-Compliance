// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

// Deep-fill status colours for the table pills.
const VDS_COLORS = { DNGT: "#7e2a30", DDGT: "#0a5a3c" };

// Header above the table: KPI cards and charts from this report's own rows (vat_report/kit.js).
const vat_report_header = (report, build) =>
	frappe.require("/assets/vat_compliance/js/vat_report/loader.js", () =>
		vat_compliance.report_kit_ready.then((kit) => kit.render(report, (meta) => build(meta, kit)))
	);

frappe.query_reports["VDS Management"] = {
	after_refresh(report) {
		vat_report_header(report, vds_header);
	},
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
			options: "\nPaid\nPartly Paid\nOverdue",
		},
		{
			fieldname: "status",
			label: "Challan Status",
			fieldtype: "Select",
			options: "\nDNGT\nDDGT",
		},
		{
			fieldname: "supplier",
			label: "Supplier",
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "company",
			label: "Company",
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			read_only: 1,
		},
	],
	get_datatable_options(options) {
		return Object.assign(options, {
			checkboxColumn: true,
		});
	},
	formatter: function (value, row, column, data, default_formatter) {
		let formatted_value = default_formatter(value, row, column, data);
		if (data && column.fieldname === "status" && VDS_COLORS[data.status]) {
			formatted_value = `<span style="display:inline-block;padding:2px 8px;border-radius:5px;font-size:10.5px;font-weight:600;color:#fff;background:${VDS_COLORS[data.status]}">${frappe.utils.escape_html(value)}</span>`;
		}
		return formatted_value;
	},
	onload: function (report) {
		report.page.add_inner_button(__("Make Payment"), function () {
			let selected_rows = report.get_checked_items();

			// Filter out rows that are already paid (DDGT)
			let valid_rows = selected_rows.filter((row) => row.status !== "DDGT");

			if (valid_rows.length === 0) {
				if (selected_rows.length > 0) {
					frappe.msgprint(
						__("Selected rows are already paid (DDGT). Please select unpaid rows.")
					);
				} else {
					frappe.msgprint(__("Please select at least one row to make payment."));
				}
				return;
			}

			frappe.call({
				method: "vat_compliance.vat_compliance.report.vds_management.vds_management.make_journal_entry",
				args: {
					rows: valid_rows,
				},
				callback: function (r) {
					if (r.message) {
						frappe.set_route("Form", "Journal Entry", r.message);
					}
				},
			});
		});
	},
};

function vds_header(m, kit) {
	const share = (v) => (m.deducted ? (v / m.deducted) * 100 : 0);
	const chart = kit.bars({ series: m.trend, line: m.trend_deposited, act: "period", names: [__("Deducted"), __("Deposited")] });
	const cards = [
		kit.card({ k: __("VDS deducted"), v: kit.money(m.deducted), pill: [__("{0} payment(s)", [m.payments]), "#3b4757"], sub: __("from suppliers"),
			visual: kit.mini.area_sparkline(m.trend.values, m.trend.labels, "#097C52") }),
		kit.card({ k: __("To deposit"), tint: true, v: kit.money(m.pending), act: "status", arg: "DNGT", pill: [`DNGT · ${m.pending_count}`, "#7e2a30"],
			sub: __("not yet in treasury"), visual: kit.mini.gauge(share(m.pending), "#a3302f", [`${kit.fmt.pct(share(m.pending), 0)} ${__("of deducted")}`, ""]) }),
		kit.card({ k: __("Deposited"), v: kit.money(m.deposited), act: "status", arg: "DDGT", pill: [`DDGT · ${m.deposited_count}`, "#0a5a3c"],
			sub: __("into treasury"), visual: kit.mini.gauge(share(m.deposited), "#097C52", [`${kit.fmt.pct(share(m.deposited), 0)} ${__("of deducted")}`, ""]) }),
		kit.card({ k: __("Suppliers"), v: kit.count(m.suppliers.length), sub: __("with VDS deducted"),
			visual: kit.seg_bar(m.suppliers.slice(0, 5).map((s, i) => ({ label: s.key, value: s.value, color: ["#22405e", "#2f5a86", "#4f77a3", "#7d9cc0", "#aabfd6"][i] }))) }),
	];
	return {
		html: `<div class="mx surf">${cards.join("")}</div>
			<div class="surf card"><div class="two">
				<div><div class="hrow"><div class="h">${__("Deducted vs deposited")}</div><div class="hs">${kit.esc(kit.subtitle(m, chart.unit))}</div></div>${chart.svg}
					<div class="lgd"><span><i style="background:#097C52"></i>${__("Deducted")}</span><span><i style="background:#a3552f;height:2px"></i>${__("Deposited")}</span></div></div>
				<div><div class="hrow"><div class="h">${__("Top suppliers")}</div><div class="hs">${__("Click to filter the table")}</div></div>
					${kit.rank(m.suppliers.slice(0, 6).map((s) => ({ label: s.key, value: s.value, sub: s.count, act: "supplier", arg: s.key })))}</div>
			</div></div>
			<div class="chips"><span><b style="background:#7e2a30">DNGT</b>${__("Deducted, not deposited into treasury")}</span><span><b style="background:#0a5a3c">DDGT</b>${__("Deducted and deposited")}</span></div>`,
		actions: {
			status: (status, report) => kit.set_filters(report, { status }),
			supplier: (supplier, report) => kit.set_filters(report, { supplier }),
			period: (range, report) => kit.set_filters(report, range),
		},
	};
}
