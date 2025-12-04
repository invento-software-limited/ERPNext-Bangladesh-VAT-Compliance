frappe.ui.form.on("Payment Entry", {
	onload(frm) {
		if (!frm.payment_controller) {
			frm.payment_controller = new PaymentController(frm);
		}
	},
	custom_vdsvcs(frm) {
		const vds_value = frm.doc.custom_vdsvcs;

		(frm.doc.references || []).forEach((row) => {
			row.custom_vdsvcs = vds_value;
		});

		frm.refresh_field("references");
		frm.payment_controller.calculate_deduction_rows();
	},
});

frappe.ui.form.on("Payment Entry Reference", {
	onload(frm) {
		if (!frm.payment_controller) {
			frm.payment_controller = new PaymentController(frm);
		}
	},
	custom_vdsvcs(frm) {
		if (frm.payment_controller) {
			frm.payment_controller.calculate_deduction_rows();
		}
	},
});

class PaymentController {
	constructor(frm) {
		this.frm = frm;
	}

	calculate_deduction_rows() {
		const me = this;
		const frm = me.frm;

		if (!frm.doc.docstatus && frm.doc.references && frm.doc.references.length > 0) {
			frappe.call({
				method: "vat_compliance.hook_functions.payment_entry.calculate_tax_rows",
				args: {
					doc: frm.doc,
				},
				callback: function (r) {
					if (r.message) {
						frm.clear_table("deductions");

						$.each(r.message, function (i, d) {
							let row = frm.add_child("deductions");
							$.extend(row, d);
						});

						frm.refresh_field("deductions");
					}
				},
			});
		}
	}
}
