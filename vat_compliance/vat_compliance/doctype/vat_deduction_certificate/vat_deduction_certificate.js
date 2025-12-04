// Copyright (c) 2025, na and contributors
// For license information, please see license.txt

frappe.ui.form.on("VAT Deduction Certificate", {
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

		if (frm.doc.certificate_html) {
			$(frm.fields_dict["vat_deduction_certificate"].wrapper).html(frm.doc.certificate_html);
		} else {
			$(frm.fields_dict["vat_deduction_certificate"].wrapper).html(`<div></div>`);
		}

		if (!frm.doc.__islocal) {
			frm.add_custom_button(
				frm.doc.certificate_html ? "Regenerate Mushak-6.6" : "Generate Mushak-6.6",
				generate_mushak
			);
		}
	},
});
