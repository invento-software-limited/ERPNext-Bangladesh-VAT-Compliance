// Loads the VAT report header kit once per session. A report calls
//   frappe.require("/assets/vat_compliance/js/vat_report/loader.js", () => vat_compliance.report_kit_ready.then(...))
// The pieces load one at a time because each reads the namespaces the ones before it define.
frappe.provide("vat_compliance");

vat_compliance.report_kit_ready =
	vat_compliance.report_kit_ready ||
	[
		"/assets/vat_compliance/js/vat_dashboard/format.js",
		"/assets/vat_compliance/js/vat_dashboard/charts.js",
		"/assets/vat_compliance/js/vat_dashboard/styles.js",
		"/assets/vat_compliance/js/vat_report/kit.js",
	]
		.reduce((chain, src) => chain.then(() => new Promise((done) => frappe.require(src, done))), Promise.resolve())
		.then(() => vat_compliance.report_kit);
