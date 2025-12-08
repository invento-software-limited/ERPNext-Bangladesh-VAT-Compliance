// Copyright (c) 2025, Invento Software Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Retailer Registration", {
	business_address: function (frm) {
		if (frm.doc.business_address) {
			// Fetch the selected Address
			frappe.db.get_doc("Address", frm.doc.business_address).then((address) => {
				let display = "";
				if (address.address_line1) display += address.address_line1;
				if (address.address_line2) display += ", " + address.address_line2;
				if (address.city) display += ", " + address.city;
				if (address.state) display += ", " + address.state;
				if (address.pincode) display += ", " + address.pincode;
				if (address.country) display += ", " + address.country;

				frm.set_value("address_display", display);
			});
		} else {
			frm.set_value("address_display", "");
		}
	},
	zone: function (frm) {
		if (frm.doc.zone) {
			frm.set_query("vat_commission_rate", function () {
				return {
					filters: {
						zone: frm.doc.zone,
					},
				};
			});
		}
	},
	vat_commission_rate: function (frm) {
		if (frm.doc.vat_commission_rate && frm.doc.zone) {
			frm.set_query("division", function () {
				return {
					filters: {
						zone: frm.doc.zone,
						vat_commission_rate: frm.doc.vat_commission_rate,
					},
				};
			});
		}
	},
	division: function (frm) {
		if (frm.doc.division && frm.doc.vat_commission_rate && frm.doc.zone) {
			frm.set_query("circle", function () {
				return {
					filters: {
						zone: frm.doc.zone,
						vat_commission_rate: frm.doc.vat_commission_rate,
						division: frm.doc.division,
					},
				};
			});
		}
	},
	nid_document: function (frm) {
		submit_document(frm.doc.nid_document, frm.doc.retailer_id, "nid_document");
	},
	bin_document: function (frm) {
		submit_document(
			frm.doc.bin_document,
			frm.doc.retailer_id,
			"business_identification_number"
		);
	},
	trade_document: function (frm) {
		submit_document(frm.doc.trade_document, frm.doc.retailer_id, "trade_license");
	},
	tin_document: function (frm) {
		submit_document(frm.doc.tin_document, frm.doc.retailer_id, "tax_identification");
	},
});

function submit_document(file_path, retailer_id, document_category_key) {
	if (file_path) {
		frappe.call({
			method: "vat_compliance.vat_challan.doctype.retailer_registration.retailer_registration.upload_file",
			args: {
				file_path: file_path,
				retailer_id: retailer_id,
				document_category_key: document_category_key,
			},
			callback: function (r) {
				// if (r.message) {
				// 	frappe.msgprint(`${r.message.message}: ${r.message.file_url}`);
				// }
			},
		});
	}
}
