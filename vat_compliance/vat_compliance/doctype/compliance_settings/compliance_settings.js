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
		frm.trigger("render_tax_template_table");
		frm.add_custom_button(__("Create Selected Templates"), () => {
			frm.trigger("create_templates");
		});
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
