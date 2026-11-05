// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

frappe.ui.form.on("VAT Deduction Certificate", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.company) {
			frm.set_value("company", frappe.defaults.get_user_default("Company"));
		}
	},
	refresh(frm) {
		const generate_mushak = () => {
			frappe.call({
				method: "vat_compliance.vat_compliance.doctype.vat_deduction_certificate.vat_deduction_certificate.generate_mushak_6_6",
				args: { name: frm.doc.name },
				callback(r) {
					if (!r.exc) {
						frappe.show_alert({ message: "Mushak 6.6 Generated", indicator: "green" });
						frm.reload_doc();
					}
				},
			});
		};

		const wrapper = $(frm.fields_dict["vat_deduction_certificate"].wrapper).empty();
		if (frm.doc.certificate_html) {
			// No allow-scripts: stored HTML can be displayed here but can never run code.
			const frame = $(`<iframe sandbox="allow-same-origin" style="width:100%;border:0"></iframe>`);
			frame.attr("srcdoc", frm.doc.certificate_html);
			frame.on("load", function () {
				this.style.height = `${this.contentDocument.documentElement.scrollHeight}px`;
			});
			wrapper.append(frame);
		}

		if (!frm.doc.__islocal) {
			frm.add_custom_button(
				frm.doc.certificate_html ? "Regenerate Mushak-6.6" : "Generate Mushak-6.6",
				generate_mushak
			);
		}
	},
});
