// KPI mini-visuals for the VAT dashboard: area and bipolar sparklines, gauge, segmented bar.
frappe.provide("vat_compliance.dashboard");

vat_compliance.dashboard.charts = (() => {
	const fmt = vat_compliance.dashboard.format;
	const clamp = (v, lo = 0, hi = 100) => Math.max(lo, Math.min(hi, v));

	// A KPI's trend across the period's buckets, with a soft fill under the line.
	function area_sparkline(values, labels, color) {
		const W = 170, H = 26, top = 5, bottom = 23;
		const pts = values && values.length ? values : [0];
		const n = pts.length, min = Math.min(...pts), max = Math.max(...pts), range = max - min || 1;
		const xs = pts.map((_, i) => (n > 1 ? 1 + (i * (W - 2)) / (n - 1) : W / 2));
		const ys = pts.map((v) => (n > 1 ? bottom - ((v - min) / range) * (bottom - top) : 14));
		const line = xs.map((x, i) => `${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(" L ");
		const gid = "vatsp" + color.replace("#", "");
		const tips = pts.map((v, i) => `${labels[i] || ""}: ${fmt.compact(v)}`).join("\n");
		return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none" role="img"><title>${fmt.esc(tips)}</title>
			<defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="${color}" stop-opacity=".16"/><stop offset="100%" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
			<path d="M ${line} L ${xs[n - 1].toFixed(1)} ${H} L ${xs[0].toFixed(1)} ${H} Z" fill="url(#${gid})"/>
			<path d="M ${line}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
			<circle cx="${xs[n - 1].toFixed(1)}" cy="${ys[n - 1].toFixed(1)}" r="2.4" fill="${color}"/></svg>`;
	}

	// Bars up from a centre line for positive values, down for negative (net VAT can be a refund).
	function bipolar_sparkline(values, labels, color, negative_color) {
		const W = 170, H = 26, gap = 3, n = values.length || 1;
		const bw = Math.min(28, (W - gap * (n - 1)) / n);
		const zero = H / 2, max = Math.max(...values.map(Math.abs), 1);
		return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none">${values.map((v, i) => {
			const h = Math.max(1, (Math.abs(v) / max) * (H / 2 - 1));
			return `<rect x="${(i * (bw + gap)).toFixed(1)}" y="${(v >= 0 ? zero - h : zero).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="1" fill="${v < 0 ? negative_color : color}"><title>${fmt.esc(`${labels[i] || ""}: ${fmt.compact(v)}`)}</title></rect>`;
		}).join("")}<line x1="0" x2="${W}" y1="${zero}" y2="${zero}" stroke="#e3e7ec"/></svg>`;
	}

	// Progress against a target.
	function gauge(fill_pct, color, labels, title) {
		return `<div class="pg" title="${fmt.esc(title || "")}">
			<div class="pg-t"><div class="pg-f" style="width:${clamp(fill_pct)}%;background:${color}"></div></div>
			<div class="pg-l"><span>${fmt.esc(labels[0])}</span><span>${fmt.esc(labels[1])}</span></div></div>`;
	}

	// One bar split into named parts; each part is {label, value, color}.
	function segmented(parts) {
		const total = parts.reduce((s, p) => s + Math.max(p.value, 0), 0) || 1;
		const bar = parts.filter((p) => p.value > 0)
			.map((p) => `<i style="width:${((p.value / total) * 100).toFixed(2)}%;background:${p.color}" title="${fmt.esc(`${p.label}: ${fmt.compact(p.value)}`)}"></i>`).join("");
		const legend = parts.map((p) => `<span><i style="background:${p.color}"></i>${fmt.esc(p.label)}</span>`).join("");
		return `<div class="sg-b">${bar}</div><div class="sg-l">${legend}</div>`;
	}

	return { area_sparkline, bipolar_sparkline, gauge, segmented };
})();
