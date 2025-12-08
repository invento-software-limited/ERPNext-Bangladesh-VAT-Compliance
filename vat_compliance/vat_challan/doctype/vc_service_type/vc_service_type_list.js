frappe.listview_settings["VC Service Type"] = {
	onload: function (listview) {
		listview.page.add_inner_button(__("Sync Service Type"), function () {
			frappe.call({
				method: "vat_compliance.vat_challan.doctype.vc_service_type.vc_service_type.sync_vc_service_type",
				args: {},
				freeze: true,
				freeze_message: __("Syncing Service Types..."),
				callback: function (r) {
					if (r.message) {
						frappe.msgprint(__("Service Types synced successfully!"));
						listview.refresh();
					}
				},
			});
		});
	},
};
