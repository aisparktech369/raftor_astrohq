app_name = "raftor_astrohq"
app_title = "Raftor Astro HQ"
app_publisher = "Raftor"
app_description = "Astrology vertical: birth details and its onboarding journey"
app_email = "dev@raftor.io"
app_license = "Proprietary"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "raftor_astrohq",
# 		"logo": "/assets/raftor_astrohq/logo.png",
# 		"title": "Raftor Astro HQ",
# 		"route": "/raftor_astrohq",
# 		"has_permission": "raftor_astrohq.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/raftor_astrohq/css/raftor_astrohq.css"
# app_include_js = "/assets/raftor_astrohq/js/raftor_astrohq.js"

# include js, css files in header of web template
# web_include_css = "/assets/raftor_astrohq/css/raftor_astrohq.css"
# web_include_js = "/assets/raftor_astrohq/js/raftor_astrohq.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "raftor_astrohq/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "raftor_astrohq/public/icons.svg"

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
# jinja = {
# 	"methods": "raftor_astrohq.utils.jinja_methods",
# 	"filters": "raftor_astrohq.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "raftor_astrohq.install.before_install"
# after_install = "raftor_astrohq.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "raftor_astrohq.uninstall.before_uninstall"
# after_uninstall = "raftor_astrohq.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "raftor_astrohq.utils.before_app_install"
# after_app_install = "raftor_astrohq.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "raftor_astrohq.utils.before_app_uninstall"
# after_app_uninstall = "raftor_astrohq.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "raftor_astrohq.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["raftor_astrohq.search.awesomebar_results"]

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
# 		"raftor_astrohq.tasks.all"
# 	],
# 	"daily": [
# 		"raftor_astrohq.tasks.daily"
# 	],
# 	"hourly": [
# 		"raftor_astrohq.tasks.hourly"
# 	],
# 	"weekly": [
# 		"raftor_astrohq.tasks.weekly"
# 	],
# 	"monthly": [
# 		"raftor_astrohq.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "raftor_astrohq.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "raftor_astrohq.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "raftor_astrohq.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["raftor_astrohq.utils.before_request"]
# after_request = ["raftor_astrohq.utils.after_request"]

# Job Events
# ----------
# before_job = ["raftor_astrohq.utils.before_job"]
# after_job = ["raftor_astrohq.utils.after_job"]

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
# 	"raftor_astrohq.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# This vertical describes its journey with onboardinghq's tools, so it needs that app installed.
required_apps = ["raftor_onboardinghq", "raftor_servicehq"]

after_install = "raftor_astrohq.install.after_install"
after_migrate = "raftor_astrohq.install.after_install"

# Birth profiles are rows of a table on the User; these rules run whenever a User is saved.
doc_events = {"User": {"validate": "raftor_astrohq.profiles.validate_user"}}

# Pages for websitehq's page kit to draw (see pages.py), and the My account menu entry for the list.
rfhq_app_pages = {
    "birth-profiles": "raftor_astrohq.pages.birth_profiles",
    "birth-profiles/new": "raftor_astrohq.pages.new_person",
    "birth-profiles/edit": "raftor_astrohq.pages.edit_person",
    "birth-details": "raftor_astrohq.pages.birth_details",
    "birth-details/done": "raftor_astrohq.pages.birth_details_done",
    "astrologer/details": "raftor_astrohq.pages.astrologer_details",
    "astrologer/credentials": "raftor_astrohq.pages.astrologer_credentials",
    "astrologer/credentials/new": "raftor_astrohq.pages.astrologer_credential_new",
}
standard_portal_menu_items = [
    {"title": "Birth profiles", "route": "/birth-profiles", "reference_doctype": "Astro Birth Profile"},
]

# servicehq's service kinds, in astrohq's words (vocabulary.py). Only words; the mechanics are servicehq's.
servicehq_vocabulary = {"astrohq": "raftor_astrohq.vocabulary.vocabulary"}
