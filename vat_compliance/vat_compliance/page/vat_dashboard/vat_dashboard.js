// VAT page dashboard (/app/vat-dashboard): output, input and net VAT with treasury status.
// Renders into a shadow root so no other app's CSS reaches it, and none of its CSS leaks out.
(() => {
	const VAT_PAGE_SCRIPTS = [
		"/assets/vat_compliance/js/vat_dashboard/format.js",
		"/assets/vat_compliance/js/vat_dashboard/charts.js",
		"/assets/vat_compliance/js/vat_dashboard/styles.js",
		"/assets/vat_compliance/js/vat_dashboard/page_styles.js",
		"/assets/vat_compliance/js/vat_dashboard/page_charts.js",
		"/assets/vat_compliance/js/vat_dashboard/markup.js",
		"/assets/vat_compliance/js/vat_dashboard/render.js",
	];

	frappe.pages["vat-dashboard"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __("VAT Dashboard"), single_column: true });
		// One script at a time: each helper reads the namespaces defined by the ones before it,
		// and a single frappe.require call does not guarantee execution order.
		VAT_PAGE_SCRIPTS.reduce((chain, src) => chain.then(() => new Promise((done) => frappe.require(src, done))), Promise.resolve())
			.then(() => (wrapper.vat_dashboard = new VATDashboard(wrapper, page)));
	};

	frappe.pages["vat-dashboard"].on_page_show = function (wrapper) {
		if (wrapper.vat_dashboard) wrapper.vat_dashboard.show();
	};

	class VATDashboard {
		constructor(wrapper, page) {
			this.wrapper = $(wrapper);
			this.page = page;
			this.state = { company: frappe.defaults.get_user_default("Company"), period: "tm", from_date: null, to_date: null };
			this.seq = 0;
			page.add_inner_button(__("Refresh"), () => this.load());
			this.full_width();
			this.mount();
			this.bind_filters();
			this.load();
		}

		show() {
			this.full_width();
			this.load();
		}

		// page.scss caps the main section at 80% even without a sidebar.
		full_width() {
			const apply = () => {
				this.wrapper.find(".layout-main, .layout-main-section-wrapper, .layout-main-section, .page-content").css({ width: "100%", maxWidth: "none" });
				this.wrapper.find(".layout-main-section-wrapper").css("flex", "1 0 100%");
			};
			apply();
			requestAnimationFrame(apply);
		}

		mount() {
			const host = document.createElement("div");
			host.className = "vat-page-dashboard";
			this.page.main.empty().css("padding", "var(--padding-xs) var(--padding-md)").append(host);
			this.root = host.attachShadow({ mode: "open" });
			this.root.innerHTML = `<style>${vat_compliance.dashboard.CSS}${vat_compliance.page.CSS}</style>${vat_compliance.page.HTML()}`;
			this.$ = (s) => this.root.querySelector(s);
		}

		bind_filters() {
			this.$('[data-f="company"]').onchange = (e) => this.set({ company: e.target.value });
			this.root.querySelectorAll(".per [data-p]").forEach((btn) => {
				btn.onclick = () => (btn.dataset.p === "custom" ? this.toggle_custom() : this.set({ period: btn.dataset.p, from_date: null, to_date: null }));
			});
			this.root.addEventListener("click", (e) => {
				const more = e.target.closest("[data-more]");
				if (more) this.load_more(+more.dataset.more);
			});
		}

		// Custom period: a popover in <body> (outside the shadow root) so Frappe's DateRange
		// control and its datepicker get the desk's own styling and behaviour.
		toggle_custom() {
			if (this.custom_open()) return this.close_custom();
			if (!this.pop) this.make_custom_pop();
			const today = frappe.datetime.get_today();
			const from_date = this.state.from_date || (this.data && this.data.period_start) || frappe.datetime.add_days(today, -29);
			const to_date = this.state.to_date || (this.data && this.data.period_end) || today;
			this.range.set_value([from_date, to_date]);
			this.custom_error("");
			this.pop.style.display = "block";
			this.place_custom();
			this.range.$input.trigger("focus");
		}

		make_custom_pop() {
			const pop = (this.pop = document.createElement("div"));
			pop.setAttribute("role", "dialog");
			pop.setAttribute("aria-label", __("Custom period"));
			pop.style.cssText = "display:none;position:fixed;z-index:1030;width:280px;padding:12px;background:var(--fg-color,#fff);"
				+ "border:1px solid var(--border-color,#ededed);border-radius:var(--radius,8px);box-shadow:var(--shadow-lg)";
			pop.innerHTML = `<div class="range"></div><div class="perr text-danger small" style="display:none;margin-top:-4px"></div>
				<div style="display:flex;justify-content:flex-end;gap:6px;margin-top:8px">
				<button type="button" class="btn btn-default btn-sm cancel">${__("Cancel")}</button>
				<button type="button" class="btn btn-primary btn-sm go">${__("Apply")}</button></div>`;
			document.body.appendChild(pop);
			this.range = frappe.ui.form.make_control({
				parent: pop.querySelector(".range"),
				df: { fieldtype: "DateRange", fieldname: "period_range", label: __("Date Range") },
				render_input: true,
			});
			pop.querySelector(".go").onclick = () => this.apply_custom();
			pop.querySelector(".cancel").onclick = () => this.close_custom();
			pop.onkeydown = (e) => {
				if (e.key === "Escape") this.close_custom();
				if (e.key === "Enter") this.apply_custom();
			};
			document.addEventListener("pointerdown", (e) => {
				const path = e.composedPath();
				const keep = path.some((n) => n === pop || (n.classList && (n.classList.contains("datepicker") || n.classList.contains("cu"))));
				if (this.custom_open() && !keep) this.close_custom();
			});
			const reposition = () => this.custom_open() && this.place_custom();
			window.addEventListener("resize", reposition);
			window.addEventListener("scroll", reposition, true);
			frappe.router.on("change", () => this.close_custom());
		}

		custom_open() {
			return this.pop && this.pop.style.display !== "none";
		}

		// Anchor under the Custom button, right-aligned, kept inside the viewport.
		place_custom() {
			const btn = this.$(".per .cu").getBoundingClientRect();
			const width = this.pop.offsetWidth;
			this.pop.style.top = `${btn.bottom + 6}px`;
			this.pop.style.left = `${Math.max(8, Math.min(btn.right - width, window.innerWidth - width - 8))}px`;
		}

		close_custom() {
			if (!this.pop) return;
			this.range.datepicker && this.range.datepicker.hide();
			this.pop.style.display = "none";
		}

		custom_error(message) {
			const err = this.pop.querySelector(".perr");
			err.textContent = message;
			err.style.display = message ? "block" : "none";
		}

		apply_custom() {
			const value = this.range.get_value();
			const [from_date, to_date] = Array.isArray(value) ? value : [];
			if (!from_date || !to_date) return this.custom_error(__("Choose both dates."));
			this.close_custom();
			this.set({ period: "custom", from_date, to_date });
		}

		set(patch) {
			Object.assign(this.state, patch);
			this.load();
		}

		args(start = 0) {
			return { ...this.state, start, page_length: 20 };
		}

		load() {
			const seq = ++this.seq;
			const body = this.$('[data-slot="body"]');
			body.classList.add("loading");
			this.paint_filters();
			Promise.resolve(frappe.call({ method: "vat_compliance.dashboard.vat_dashboard.get_dashboard_data", args: this.args() }))
				.then((r) => {
					if (seq !== this.seq || !r.message) return;
					this.data = r.message;
					Object.assign(this.state, { company: r.message.company });
					if (!body.querySelector(".mx")) body.innerHTML = vat_compliance.page.BODY();
					vat_compliance.page.render.bind(this.root, r.message);
					this.paint_filters();
				})
				.catch(() => {
					if (seq === this.seq) body.innerHTML = `<div class="err">${__("Could not load the VAT dashboard.")}</div>`;
				})
				.finally(() => seq === this.seq && body.classList.remove("loading"));
		}

		load_more(start) {
			const seq = this.seq;
			frappe.call({ method: "vat_compliance.dashboard.vat_dashboard.get_dashboard_data", args: this.args(start) }).then((r) => {
				if (seq !== this.seq || !r.message) return;
				const render = vat_compliance.page.render;
				render.bind_worklist(render.make_ctx(this.root, this.data), r.message.worklist, true);
			});
		}

		paint_filters() {
			const select = this.$('[data-f="company"]');
			const companies = (this.data && this.data.companies) || [this.state.company].filter(Boolean);
			select.innerHTML = companies.map((c) => `<option value="${frappe.utils.escape_html(c)}">${frappe.utils.escape_html(c)}</option>`).join("");
			select.value = this.state.company || "";
			this.root.querySelectorAll(".per [data-p]").forEach((b) => b.classList.toggle("on", b.dataset.p === this.state.period));
			const cu = this.$(".per .cu");
			cu.textContent = this.state.period === "custom"
				? `${frappe.datetime.str_to_user(this.state.from_date)} – ${frappe.datetime.str_to_user(this.state.to_date)}`
				: __("Custom");
		}
	}
})();
