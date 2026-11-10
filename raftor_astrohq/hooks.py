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
doc_events = {"User": {"validate": "raftor_astrohq.profiles.validate_user", "on_trash": "raftor_astrohq.answers.forget_user"}}

# Pages as data for websitehq to build (page_definitions.py), and the old addresses forwarded to them.
rfhq_page_definitions = ["raftor_astrohq.page_definitions.definitions"]

# What a gemstone is sold as (Type: stone only, ring, pendant...), with the icon of each: data for websitehq to draw (attributes.py).
rfhq_attribute_sets = ["raftor_astrohq.attributes.attribute_sets"]
# The blog is named Academy (install step, content.py); its address stays /blog, which Frappe owns. /academy goes there, keeping any path after it.
rfhq_blog_store = ["Divine store"]
rfhq_blog_booking = ["Book blessings|/services/events"]
rfhq_blog_closing = ["Have a question about this?|Ask a guide|/consult"]
website_redirects = [
    {"source": r"/academy(.*)", "target": r"/blog\1"},
    {"source": "/birth-profiles", "target": "/my/birth-profiles"},
    {"source": "/birth-profiles/new", "target": "/my/birth-profiles/new"},
    {"source": "/birth-profiles/edit", "target": "/my/birth-profiles"},
    {"source": "/birth-details", "target": "/onboarding/birth-details"},
    {"source": "/birth-details/done", "target": "/onboarding/birth-details/done"},
    {"source": "/astrologer/details", "target": "/onboarding/astrologer-details"},
    {"source": "/astrologer/credentials", "target": "/onboarding/astrologer-credentials"},
    {"source": "/astrologer/credentials/new", "target": "/onboarding/astrologer-credentials/new"},
]
standard_portal_menu_items = [
    {"title": "Birth profiles", "route": "/my/birth-profiles", "reference_doctype": "Astro Birth Profile"},
]

# servicehq's service kinds, in astrohq's words (vocabulary.py). Only words; the mechanics are servicehq's.
servicehq_vocabulary = {"astrohq": "raftor_astrohq.vocabulary.vocabulary"}
rfhq_report_makers = ["raftor_astrohq.reports.birth_summary"]

# The methods whose markup websitehq lets reach a page (website_hq/report_html.py cleans it first): the astrologer's page of a customer's chart, and the Panchang page.
rfhq_trusted_html_sources = ["raftor_astrohq.report_view.chart_view", "raftor_astrohq.panchang.page", "raftor_astrohq.panchang.widget_cards"]

# Shortly after midnight the Panchang's town is worked out for the week ahead (panchang.warm).
scheduler_events = {"cron": {"10 0 * * *": ["raftor_astrohq.panchang.warm"], "40 1 * * *": ["raftor_astrohq.plan_billing.daily"]}}

# The Panchang is a page group of its own: /panchang is its page (page_definitions.py).
rfhq_page_groups = {"panchang": "Panchang", "ask": "Ask Pandit ji"}
rfhq_window_guide = ["raftor_astrohq.agent_chat.guide"]  # (websitehq draws a round button on every page that opens the guide in a drawer)
rfhq_product_pills = ["raftor_astrohq.products.product_pills"]  # (the pills of a group of products: websitehq asks, and draws them under the store's tiles)


# Tools for the AI guide, read by FAC (the tool server) from every installed app.
assistant_tools = [
	"raftor_astrohq.assistant_tools.services.FindServices",
	"raftor_astrohq.assistant_tools.services.GetService",
	"raftor_astrohq.assistant_tools.numerology.CalculateNumerology",
	"raftor_astrohq.assistant_tools.people.GetFamilyMember",
	"raftor_astrohq.assistant_tools.people.GetReport",
]

# AgentsHQ calls this when it puts the astrohq domain's files in the store: it labels each file's pieces
agent_rag_enrichers = ["astrohq:raftor_astrohq.knowledge.enrich"]

# What the AI guides remember about a person and the people in their profiles, and what the site knows of them: a dotted path to a module with read(user), write(user, payload, guide, session) and forget(user, name).
agent_person = ["raftor_astrohq.person"]

# The AI plans (plans.py, plan_billing.py): what PaymentHQ tells us about a plan's payments, and whether the website's free-report form may make another report for a person.
paymenthq_on_paid = {"AI Plan Member": ["raftor_astrohq.plan_billing.paid"]}
paymenthq_on_failed = {"AI Plan Member": ["raftor_astrohq.plan_billing.payment_not_taken"]}
paymenthq_on_expired = {"AI Plan Member": ["raftor_astrohq.plan_billing.payment_not_taken"]}
paymenthq_on_cancelled = {"AI Plan Member": ["raftor_astrohq.plan_billing.payment_not_taken"]}
free_reports_allowance = ["raftor_astrohq.plans.report_allowance"]
