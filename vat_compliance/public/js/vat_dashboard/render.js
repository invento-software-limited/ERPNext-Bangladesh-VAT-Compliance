// Binds the VAT payload (vat_compliance.dashboard.vat_dashboard) into the page skeleton.
frappe.provide("vat_compliance.page");

vat_compliance.page.render = (() => {
	const fmt = vat_compliance.dashboard.format;
	const mini = vat_compliance.dashboard.charts;
	const charts = vat_compliance.page.charts;
	const esc = (v) => fmt.esc(v);
	const SOURCE = {
		output: [__("Output VAT"), "#097C52"], input: [__("Input VAT"), "#2f5a86"], adjustment: [__("Adjustments"), "#8a5a16"],
		deposit: [__("Deposits"), "#17626e"], opening: [__("Opening"), "#5c6672"],
	};
	const TOP = ["#0e442e", "#1a6f4a", "#2b8b62", "#5aa584", "#8fbfa8"];
	const SUPP = ["#22405e", "#2f5a86", "#4f77a3", "#7d9cc0", "#aabfd6"];

	function bind(root, d) {
		fmt.use_currency(d.currency, d.currency_symbol, d.currency_symbol_on_right);
		const ctx = make_ctx(root, d);
		bind_header(ctx);
		bind_metrics(ctx);
		bind_status(ctx);
		bind_charts(ctx);
		bind_parties(ctx);
		bind_worklist(ctx, d.worklist, false);
	}

	function make_ctx(root, d) {
		const $ = (f) => root.querySelector(`[data-field="${f}"]`);
		return {
			root, d, $,
			text: (f, v) => $(f) && ($(f).textContent = v),
			slot: (s, html) => (root.querySelector(`[data-slot="${s}"]`).innerHTML = html),
			width: (s) => Math.max(root.querySelector(`[data-slot="${s}"]`).clientWidth, 200),
		};
	}

	function bind_header({ d, $, text }) {
		const accounts = d.accounts.length ? d.accounts.join(", ") : __("no VAT account found");
		$("meta").innerHTML = [esc(d.company), `<b>${esc(__("as of {0}", [fmt.date(d.today)]))}</b>`, esc(accounts)].join(" &nbsp;·&nbsp; ");
		text("hd_balance", fmt.compact(d.balance));
		text("hd_period", d.period_label);
		text("hd_net", fmt.compact(d.totals.net));
	}

	function bind_metrics({ d, $, text, slot }) {
		const t = d.totals, s = d.series;
		fmt.set_compact($("output"), t.output);
		change_pill($("output_change"), t.output, d.prior.output);
		text("output_caption", __("prior {0}", [fmt.compact(d.prior.output)]));
		$("output_caption").title = __("{0} invoice(s) this period", [d.counts.output]);
		slot("output_trend", mini.area_sparkline(s.output, s.labels, "#097C52"));

		fmt.set_compact($("input"), t.input);
		pill($("input_share"), t.output ? fmt.pct((t.input / t.output) * 100, 0) : "—", "#22405e");
		text("input_caption", __("of output · {0} bill(s)", [d.counts.input]));
		slot("input_trend", mini.area_sparkline(s.input, s.labels, "#2f5a86"));

		fmt.set_compact($("net"), t.net);
		const refund = t.net < 0;
		pill($("net_pill"), refund ? __("credit") : __("payable"), refund ? "#17505d" : "#7e2a30");
		text("net_caption", __("output − input"));
		slot("net_trend", mini.bipolar_sparkline(s.net, s.labels, "#a3302f", "#17626e"));

		fmt.set_compact($("balance"), d.balance);
		const moved = d.balance - d.balance_at_start;
		text("balance_caption", __("{0} {1} since {2}", [moved >= 0 ? "▲" : "▼", fmt.compact(Math.abs(moved)), fmt.date(d.period_start, false)]));
		slot("balance_trend", mini.area_sparkline(s.balance, s.labels, "#a3552f"));
	}

	function bind_status({ d, text }) {
		const st = d.status;
		const n = (group, key) => (group ? group[key] : { count: 0, amount: 0 });
		const set = (key, cell, sub) => {
			text(`st_${key}`, cell == null ? "—" : fmt.compact(cell.amount));
			text(`st_${key}_s`, sub);
		};
		const none = __("no report access");
		const sales = st.sales, vds = st.vds;
		set("ipnr", sales && n(sales, "IPNR"), sales ? __("{0} invoice(s)", [sales.IPNR.count]) : none);
		set("collected", sales && n(sales, "Collected"), sales ? __("{0} · awaiting deposit", [sales.Collected.count]) : none);
		set("cdgt", sales && n(sales, "CDGT"), sales ? __("{0} into treasury", [sales.CDGT.count]) : none);
		const withheld = sales && { amount: sales.DVCNR.amount + sales.DVCR.amount };
		set("withheld", withheld, sales ? __("{0} certificate(s) pending", [sales.DVCNR.count]) : none);
		set("dngt", vds && n(vds, "DNGT"), vds ? __("{0} · {1} deposited", [vds.DNGT.count, fmt.compact(vds.DDGT.amount)]) : none);
		text("status_sub", st.awaiting_deposit == null ? "" : __("{0} awaiting deposit", [fmt.compact(st.awaiting_deposit)]));
	}

	function bind_charts(ctx) {
		const { d, text, slot, width, root } = ctx;
		const chart = charts.combo(d.series.labels, d.series.output, d.series.input, width("combo"));
		slot("combo", chart.svg || chart);
		text("combo_sub", `${d.period_label}, ${d.currency} ${chart.unit || ""}`.trim());
		const parts = Object.entries(SOURCE).map(([key, [label, color]]) => ({ key, label, color, value: Math.abs(d.totals[key]), count: d.counts[key] }))
			.filter((p) => p.value > 0);
		const total = parts.reduce((s, p) => s + p.value, 0);
		text("mix_sub", __("Absolute amounts posted · {0}", [d.period_label.toLowerCase()]));
		const legend = parts.map((p, i) => `<div class="dn-r lk" data-i="${i}"><i style="background:${p.color}"></i><span class="n">${esc(p.label)}</span>
			<span class="p">${fmt.pct((p.value / (total || 1)) * 100, 0)}</span><span class="v">${esc(fmt.compact(p.value))}</span></div>`).join("");
		slot("mix", parts.length ? `<div class="dn">${charts.donut(parts, String(parts.reduce((s, p) => s + p.count, 0)), __("documents"))}<div class="dn-l">${legend}</div></div>`
			: `<div class="empty">${__("No VAT postings in this period.")}</div>`);
		root.querySelectorAll('[data-slot="mix"] [data-i]').forEach((el) => {
			el.onclick = () => go_ledger(d, parts[el.dataset.i].key);
		});
	}

	function bind_parties({ d, text, slot, root }) {
		const rows = (list, colors, slot_name, doctype) => {
			slot(slot_name, list.length ? list.map((p, i) => `<div class="lk" data-i="${i}" title="${esc(__("Open {0} list", [__(doctype)]))}">
				<div class="rk-r"><span class="rk-d" style="background:${colors[i]}"></span><span class="rk-n">${esc(p.name)}</span>
				<span class="rk-v">${esc(fmt.compact(p.vat))}<em> · ${p.count} · ${fmt.pct(p.pct, 0)}</em></span></div>
				<div class="rk-t"><div class="rk-f" style="width:${Math.max(p.pct, 2).toFixed(0)}%;background:${colors[i]}"></div></div></div>`).join("")
				: `<div class="empty">${__("Nothing posted in this period.")}</div>`);
			root.querySelectorAll(`[data-slot="${slot_name}"] [data-i]`).forEach((el) => {
				el.onclick = () => frappe.set_route("List", doctype, { name: ["in", list[el.dataset.i].names] });
			});
		};
		text("cust_sub", d.period_label);
		text("supp_sub", d.period_label);
		rows(d.top_customers, TOP, "customers", "Sales Invoice");
		rows(d.top_suppliers, SUPP, "suppliers", "Purchase Invoice");
	}

	// `append` adds the next page under the rows already shown.
	function bind_worklist(ctx, w, append) {
		const { d, text, slot, root } = ctx;
		const gap = d.no_template ? ` · ${__("{0} without an item tax template (Mushak reports skip these)", [d.no_template])}` : "";
		text("work_sub", __("{0} document(s)", [w.total]) + gap);
		const html = w.rows.map((r) => {
			const [label, color] = SOURCE[r.source] || [r.source, "#5c6672"];
			const template = r.doctype in { "Sales Invoice": 1, "Purchase Invoice": 1 }
				? `<span class="pill" style="background:${r.has_template ? "#0a5a3c" : "#8a4527"}">${esc(r.has_template ? __("set") : __("missing"))}</span>` : "—";
			return `<tr><td>${esc(fmt.date(r.date))}</td><td class="doc"><a class="lk" data-doctype="${esc(r.doctype)}" data-name="${esc(r.name)}">${esc(r.name)}</a></td>
				<td><span class="pill" style="background:${color}">${esc(label)}</span>${r.is_return ? ` <span class="pill" style="background:#7e2a30">${esc(__("return"))}</span>` : ""}</td>
				<td>${esc(r.party_name || "")}</td><td class="n">${r.net == null ? "—" : esc(fmt.full(r.net))}</td>
				<td class="n">${esc(fmt.full(r.vat))}</td><td>${template}</td></tr>`;
		}).join("");
		const tbody = root.querySelector('[data-slot="work"]');
		if (append) tbody.insertAdjacentHTML("beforeend", html);
		else tbody.innerHTML = html || `<tr><td colspan="7" class="empty">${__("No VAT postings in this period.")}</td></tr>`;
		tbody.querySelectorAll("a[data-doctype]").forEach((a) => (a.onclick = () => frappe.set_route("Form", a.dataset.doctype, a.dataset.name)));
		const shown = w.start + w.rows.length;
		slot("work_more", shown < w.total ? `<button type="button" data-more="${shown}">${__("Show more ({0} of {1})", [shown, w.total])}</button>` : "");
		bind_drills(ctx);
	}

	function bind_drills({ root, d }) {
		const ledger = { output: 1, input: 1, balance: 1 };
		root.querySelectorAll("[data-drill]").forEach((el) => {
			const key = el.dataset.drill;
			if (ledger[key]) return (el.onclick = () => go_ledger(d, key));
			const [kind, status] = key.split("_");
			const report = kind === "s" ? "Sales VAT Management" : "VDS Management";
			const allowed = kind === "s" ? !!d.status.sales : !!d.status.vds;
			el.classList.toggle("lk", allowed);
			el.title = allowed ? __("Open {0}", [__(report)]) : "";
			el.onclick = allowed ? () => frappe.set_route("query-report", report, { company: d.company, from_date: d.period_start, to_date: d.period_end, status }) : null;
		});
	}

	// GL Entry list for one source of VAT postings (or the whole balance as of today).
	function go_ledger(d, key) {
		const vouchers = { output: ["in", ["Sales Invoice", "POS Invoice"]], input: "Purchase Invoice" };
		const filters = { company: d.company, account: ["in", d.accounts], is_cancelled: 0 };
		if (key === "balance") filters.posting_date = ["<=", d.today];
		else filters.posting_date = ["between", [d.period_start, d.period_end]];
		if (vouchers[key]) filters.voucher_type = vouchers[key];
		else if (key !== "balance") filters.voucher_type = "Journal Entry";
		frappe.set_route("List", "GL Entry", filters);
	}

	function change_pill(el, now, prior) {
		if (!prior) return pill(el, now ? __("new") : "—", "#3b4757");
		const pct = ((now - prior) / Math.abs(prior)) * 100;
		pill(el, `${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct).toFixed(0)}%`, pct >= 0 ? "#0a5a3c" : "#7e2a30");
	}

	function pill(el, label, color) {
		el.textContent = label;
		el.style.background = color;
	}

	return { bind, bind_worklist, make_ctx };
})();
