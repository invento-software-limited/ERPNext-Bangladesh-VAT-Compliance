// Copyright (c) 2025, Invento Software Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("POS Vendor Configuration", {
	refresh: function (frm) {
		frm.add_custom_button(__("Fetch Token"), function () {
			frappe.call({
				method: "vat_compliance.vat_challan.doctype.pos_vendor_configuration.pos_vendor_configuration.fetch_pos_vendor_token",
				args: {},
				callback: function (r) {
					if (!r.exc) {
						frappe.msgprint(__("Access token fetched successfully!"));
						frm.reload_doc();
					}
				},
			});
		});

		if (!frm.doc.access_token) {
			frm.set_df_property(
				"html_eoct",
				"options",
				`
				<div style="padding: 15px; background-color: #fff3cd; border: 1px solid #ffeeba; border-radius: 4px; color: #856404;">
					<p style="margin: 0; font-size: 14px;">
						Contact <a href="https://dgepay.net/contact.html" target="_blank" style="font-weight: bold; text-decoration: underline;">dgepay</a> to have your Vendor Credentials.
					</p>
					<p style="margin-top: 5px; font-size: 14px;">
						Also tell them if you want a quick solution please contact <a href="https://invento.com.bd/contact/" target="_blank" style="font-weight: bold; text-decoration: underline;">Invento Software Limited</a>.
					</p>
				</div>
			`
			);
			frm.refresh_field("html_eoct");
		} else {
			frm.set_df_property("html_eoct", "options", "");
			frm.refresh_field("html_eoct");
		}
	},
});
