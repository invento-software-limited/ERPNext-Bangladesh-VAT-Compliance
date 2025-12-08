app_name = "vat_compliance"
app_title = "Vat Compliance"
app_publisher = "Invento Software Limited"
app_description = "NA"
app_email = "munim@invento.com.bd"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "vat_compliance",
# 		"logo": "/assets/vat_compliance/logo.png",
# 		"title": "Vat Compliance",
# 		"route": "/vat_compliance",
# 		"has_permission": "vat_compliance.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/vat_compliance/css/vat_compliance.css"
# app_include_js = "/assets/vat_compliance/js/vat_compliance.js"

# include js, css files in header of web template
# web_include_css = "/assets/vat_compliance/css/vat_compliance.css"
# web_include_js = "/assets/vat_compliance/js/vat_compliance.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "vat_compliance/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Payment Entry": "public/js/payment_entry.js",
	"Customer": "public/js/customer.js",
	"Supplier": "public/js/supplier.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "vat_compliance/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": "vat_compliance.vat_compliance.doctype.vat_deduction_certificate.vat_deduction_certificate.parse_context",
}

# Installation
# ------------

# before_install = "vat_compliance.install.before_install"
# after_install = "vat_compliance.setup.setup_item_tax_templates"

# Uninstallation
# ------------

# before_uninstall = "vat_compliance.uninstall.before_uninstall"
# after_uninstall = "vat_compliance.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "vat_compliance.utils.before_app_install"
# after_app_install = "vat_compliance.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "vat_compliance.utils.before_app_uninstall"
# after_app_uninstall = "vat_compliance.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "vat_compliance.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {"Payment Entry": "vat_compliance.hook_functions.payment_entry.CustomPaymentEntry"}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"vat_compliance.tasks.all"
# 	],
# 	"daily": [
# 		"vat_compliance.tasks.daily"
# 	],
# 	"hourly": [
# 		"vat_compliance.tasks.hourly"
# 	],
# 	"weekly": [
# 		"vat_compliance.tasks.weekly"
# 	],
# 	"monthly": [
# 		"vat_compliance.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "vat_compliance.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "vat_compliance.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "vat_compliance.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["vat_compliance.utils.before_request"]
# after_request = ["vat_compliance.utils.after_request"]

# Job Events
# ----------
# before_job = ["vat_compliance.utils.before_job"]
# after_job = ["vat_compliance.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"vat_compliance.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

fixtures = [
	{
		"dt": "Address Template",
		"filters": [
			[
				"name",
				"in",
				[
					"Bangladesh",
				],
			]
		],
	}
]
