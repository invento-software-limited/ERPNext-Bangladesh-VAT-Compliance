// Copyright (c) 2025, Invento Software Limited and contributors
// For license information, please see license.txt

frappe.listview_settings["VC Zone"] = {
	onload: function (listview) {
		listview.page.add_inner_button(__("Sync Zones"), function () {
			frappe.call({
				method: "vat_compliance.vat_challan.doctype.vc_zone.vc_zone.sync_zone",
				args: {},
				freeze: true,
				freeze_message: __("Syncing Zones..."),
				callback: function (r) {
					if (r.message) {
						frappe.msgprint(__("Zones synced successfully!"));
						listview.refresh();
					}
				},
			});
		});
	},
};
