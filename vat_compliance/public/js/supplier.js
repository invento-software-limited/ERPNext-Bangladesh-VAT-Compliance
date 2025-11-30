frappe.ui.form.on("Supplier", {
    custom_verify_bin: function (frm) {
        if (frm.doc.custom_bin_no) {
            frappe.call({
                method: "vat_compliance.api.validate_bin",
                args: {
                    bin_no: frm.doc.custom_bin_no
                },
                freeze: true,
                freeze_message: __("Verifying BIN..."),
                callback: function (r) {
                    if (!r.exc && r.message) {
                        if (r.message.responseCode === "0") {
                            frappe.msgprint({
                                title: __('Success'),
                                indicator: 'green',
                                message: __('BIN Verified Successfully: {0}', [r.message.message])
                            });
                            frm.set_value('custom_bin_verification_status', 'Verified');
                        } else {
                            frappe.msgprint({
                                title: __('Invalid'),
                                indicator: 'red',
                                message: __('{0}', [r.message.message || "Unknown error"])
                            });
                            frm.set_value('custom_bin_verification_status', 'Not Verified');
                        }
                    }
                }
            });
        } else {
            frappe.msgprint(__('Please enter a BIN/VAT Registration No first.'));
        }
    },
    custom_verify_tin: function (frm) {
        if (frm.doc.custom_tin_no) {
            frappe.call({
                method: "vat_compliance.api.validate_tin",
                args: {
                    tin_no: frm.doc.custom_tin_no
                },
                freeze: true,
                freeze_message: __("Verifying TIN..."),
                callback: function (r) {
                    if (!r.exc && r.message) {
                        if (r.message.responseCode === "0") {
                            frappe.msgprint({
                                title: __('Success'),
                                indicator: 'green',
                                message: __('{0}', [r.message.message])
                            });
                            frm.set_value('custom_tin_verification_status', 'Verified');
                        } else {
                            frappe.msgprint({
                                title: __('Invalid'),
                                indicator: 'red',
                                message: __('{0}', [r.message.message || "Unknown error"])
                            });
                            frm.set_value('custom_tin_verification_status', 'Not Verified');
                        }
                    }
                }
            });
        } else {
            frappe.msgprint(__('Please enter a TIN/VAT Registration No first.'));
        }
    }
});
