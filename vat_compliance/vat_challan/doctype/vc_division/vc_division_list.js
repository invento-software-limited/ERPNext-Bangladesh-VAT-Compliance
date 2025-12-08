frappe.listview_settings["VC Division"] = {
	onload: function (listview) {
		listview.page.add_inner_button(__("Sync Division"), function () {
			frappe.call({
				method: "vat_compliance.vat_challan.doctype.vc_division.vc_division.sync_vc_division",
				args: {},
				freeze: true,
				freeze_message: __("Syncing Divisions..."),
				callback: function (r) {
					if (r.message) {
						frappe.msgprint(__("Divisions synced successfully!"));
						listview.refresh();
					}
				},
			});
		});
	},
};
