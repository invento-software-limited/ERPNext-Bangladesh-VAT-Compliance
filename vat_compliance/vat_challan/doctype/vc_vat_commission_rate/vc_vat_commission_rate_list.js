frappe.listview_settings["VC VAT Commission Rate"] = {
	onload: function (listview) {
		listview.page.add_inner_button(__("Sync VAT Commission Rate"), function () {
			frappe.call({
				method: "vat_compliance.vat_challan.doctype.vc_vat_commission_rate.vc_vat_commission_rate.sync_vc_vat_commission_rate",
				args: {},
				freeze: true,
				freeze_message: __("Syncing VAT Commission Rates..."),
				callback: function (r) {
					if (r.message) {
						frappe.msgprint(__("VAT Commission Rates synced successfully!"));
						listview.refresh();
					}
				},
			});
		});
	},
};
