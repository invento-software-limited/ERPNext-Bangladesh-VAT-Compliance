frappe.ui.form.on("Compliance Settings", {
	setup: function (frm) {
		frm.set_query("default_account", function () {
			return {
				filters: {
					account_type: "Tax",
					is_group: 0,
					company: frm.doc.company,
				},
			};
		});
	},

	refresh: function (frm) {
		frm.trigger("render_guidelines");
		frm.trigger("render_tax_template_table");
		frm.add_custom_button(__("Create Selected Templates"), () => {
			frm.trigger("create_templates");
		});
	},

	render_guidelines: function (frm) {
		if (frm.fields_dict.tax_template_guidelines) {
			frm.fields_dict.tax_template_guidelines.$wrapper.html(`
				<div class="tax-template-guideline-box" style="background: var(--bg-light-gray, #f8f9fa); border-left: 4px solid var(--primary, #1b84ff); padding: 12px 16px; margin-bottom: 16px; border-radius: 4px;">
					<div style="font-weight: 600; font-size: 13px; margin-bottom: 6px; color: var(--text-color, #1f272e);">
						Tax Template Setup Guidelines
					</div>
					<ol style="margin: 0; padding-left: 20px; font-size: 12px; color: var(--text-muted, #525252); line-height: 1.6;">
						<li><b>Select Company:</b> Choose your company to associate with the created Item Tax Templates.</li>
						<li><b>Select Default VAT Account:</b> Choose the designated Tax Account (e.g. VAT / Output VAT under Current Liabilities).</li>
						<li><b>Review Statutory Rates:</b> The table below displays standard Bangladesh VAT service codes, rates, and deduction rules according to NBR SROs.</li>
						<li><b>Select &amp; Create:</b> Check the boxes for the templates your business requires and click <b>Create Selected Templates</b>.</li>
						<li><b>Assign to Items:</b> Link the generated Item Tax Templates to items in <b>Item Master &gt; Item Tax</b> to automate VAT and VDS calculation on invoices.</li>
					</ol>
				</div>
			`);
		}
	},

	company: function (frm) {
		frm.set_value("default_account", "");
	},

	create_templates: function (frm) {
		if (!frm.doc.default_account || !frm.doc.company) {
			frappe.msgprint(__("Please select Default Tax Account and Company first."));
			return;
		}

		let selected_indices = [];
		frm.fields_dict.tax_template_html.$wrapper
			.find(".template-checkbox:checked")
			.each(function () {
				selected_indices.push($(this).data("index"));
			});

		if (selected_indices.length === 0) {
			frappe.msgprint(__("Please select at least one template."));
			return;
		}

		if (!frm.tax_templates) {
			frappe.msgprint(__("Templates not loaded yet. Please refresh."));
			return;
		}

		let selected_templates = selected_indices.map((i) => frm.tax_templates[i]);

		frappe.call({
			doc: frm.doc,
			method: "create_tax_templates",
			args: {
				templates: JSON.stringify(selected_templates),
				default_account: frm.doc.default_account,
				company: frm.doc.company,
			},
			freeze: true,
			callback: function (r) {
				if (r.message) {
					frappe.msgprint(
						__("Successfully created {0} Item Tax Templates.", [r.message])
					);
				} else {
					frappe.msgprint(
						__("No new templates were created (they might already exist).")
					);
				}
			},
		});
	},

	render_tax_template_table: function (frm) {
		frm.call({
			doc: frm.doc,
			method: "get_tax_templates",
			callback: function (r) {
				if (r.message) {
					frm.tax_templates = r.message;
					let templates = r.message;
					let html = `
						<table class="table table-bordered">
							<thead>
								<tr>
									<th style="width: 40px;"><input type="checkbox" id="select-all-templates"></th>
									<th>Service Code</th>
									<th>Service Provider</th>
									<th>Rate (%)</th>
									<th>Deduction Applicability</th>
									<th>Section Reference</th>
									<th>Remarks</th>
								</tr>
							</thead>
							<tbody>
					`;

					templates.forEach((item, index) => {
						html += `
							<tr>
								<td><input type="checkbox" class="template-checkbox" data-index="${index}"></td>
								<td>${item.service_code}</td>
								<td>${item.service_provider}</td>
								<td>${item.rate}</td>
								<td>${item.deduction_applicability ? "Yes" : "No"}</td>
								<td>${item.sec_ref}</td>
								<td>${item.remarks}</td>
							</tr>
						`;
					});

					html += `
							</tbody>
						</table>
					`;

					frm.fields_dict.tax_template_html.$wrapper.html(html);

					// Bind Events
					frm.fields_dict.tax_template_html.$wrapper
						.find("#select-all-templates")
						.on("change", function () {
							let checked = $(this).prop("checked");
							frm.fields_dict.tax_template_html.$wrapper
								.find(".template-checkbox")
								.prop("checked", checked);
						});
				}
			},
		});
	},
});
