app_name = "financial_report_tool"
app_title = "Financial Report Tool"
app_publisher = "Hybrowlabs Pvt Ltd"
app_description = "This Financial Report Tool."
app_email = "contact@hybrowlabs.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "financial_report_tool",
# 		"logo": "/assets/financial_report_tool/logo.png",
# 		"title": "Financial Report Tool",
# 		"route": "/financial_report_tool",
# 		"has_permission": "financial_report_tool.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/financial_report_tool/css/financial_report_tool.css"
# app_include_js = "/assets/financial_report_tool/js/financial_report_tool.js"

# include js, css files in header of web template
# web_include_css = "/assets/financial_report_tool/css/financial_report_tool.css"
# web_include_js = "/assets/financial_report_tool/js/financial_report_tool.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "financial_report_tool/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"Account" : "public/js/account.js"}
doctype_list_js = {"DocType" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "financial_report_tool/public/icons.svg"

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

# Website Routes
# ------------

# Remove the website route as it's not working properly
# We'll use the standard API method approach instead

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "financial_report_tool.utils.jinja_methods",
# 	"filters": "financial_report_tool.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "financial_report_tool.install.before_install"
# after_install = "financial_report_tool.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "financial_report_tool.uninstall.before_uninstall"
# after_uninstall = "financial_report_tool.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "financial_report_tool.utils.before_app_install"
# after_app_install = "financial_report_tool.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "financial_report_tool.utils.before_app_uninstall"
# after_app_uninstall = "financial_report_tool.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "financial_report_tool.notifications.get_notification_config"

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

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

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
# 		"financial_report_tool.tasks.all"
# 	],
# 	"daily": [
# 		"financial_report_tool.tasks.daily"
# 	],
# 	"hourly": [
# 		"financial_report_tool.tasks.hourly"
# 	],
# 	"weekly": [
# 		"financial_report_tool.tasks.weekly"
# 	],
# 	"monthly": [
# 		"financial_report_tool.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "financial_report_tool.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "financial_report_tool.event.get_events"
# }
#
# SAP's z_f01_extract program appends the closing JSON quote of `callback_url`
# to the outbound callback path, so it POSTs to
# `.../sync_sap_trial_balance.receive_sap_trial_balance"` — Frappe then looks up
# a method named `receive_sap_trial_balance"` (trailing quote) and fails with
# AttributeError. Alias that mangled command back to the real callback so the
# push succeeds without waiting on a SAP-side fix.
_SAP_TB_CALLBACK = (
	"financial_report_tool.financial_report_tool.doctype.fr_sync_sap_trial_balance"
	".fr_sync_sap_trial_balance.receive_sap_trial_balance"
)
override_whitelisted_methods = {
	_SAP_TB_CALLBACK + '"': _SAP_TB_CALLBACK,
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "financial_report_tool.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["financial_report_tool.utils.before_request"]
# after_request = ["financial_report_tool.utils.after_request"]

# Job Events
# ----------
# before_job = ["financial_report_tool.utils.before_job"]
# after_job = ["financial_report_tool.utils.after_job"]

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
# 	"financial_report_tool.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

fixtures = [
    {
        "dt": "Print Format",
        "filters": [["name", "in", ["Financial Report", "Console Financial Report"]]]
    },
    {
        "dt": "Workspace",
        "filters": [["name", "in", ["Finova"]]]
    },
    {
        "dt": "Role",
        "filters": [["name", "in", ["Financial Report User", "Financial Report Manager"]]]
    },
    {
        "dt": "Workflow",
        "filters": [["name", "in", ["Financial Report Workflow", "Console Financial Report Workflow", "GL Account Creation Request Workflow"]]]
    },
    {
        "dt": "Workflow State",
        "filters": [["name", "in", ["Request For Creation", "Account Created"]]]
    },
    {
        "dt": "Custom DocPerm",
        "filters": [["role", "in", ["Financial Report User", "Financial Report Manager"]]]
    },
    {
        "dt": "Custom Field",
        "filters": [["name", "in", ["Company-custom_include_in_consolidated_financials"]]]
    }
]

# after_migrate = ["financial_report_tool.setup.cost_center.create_root_cost_centers"]