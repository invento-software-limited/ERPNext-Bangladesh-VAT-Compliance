// Copyright (c) 2025, Invento Software Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Retailer Branch Registration", {
	branch_address: function (frm) {
		if (frm.doc.branch_address) {
			// Fetch the selected Address
			frappe.db.get_doc("Address", frm.doc.branch_address).then((address) => {
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
});
