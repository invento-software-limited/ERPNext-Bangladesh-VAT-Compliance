frappe.listview_settings["VC Circle"] = {
	onload: function (listview) {
		listview.page.add_inner_button(__("Sync Circle"), function () {
			frappe.call({
				method: "vat_compliance.vat_challan.doctype.vc_circle.vc_circle.sync_vc_circle",
				args: {},
				freeze: true,
				freeze_message: __("Syncing Circles..."),
				callback: function (r) {
					if (r.message) {
						frappe.msgprint(__("Circles synced successfully!"));
						listview.refresh();
					}
				},
			});
		});
	},
};
