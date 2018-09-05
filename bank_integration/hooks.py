# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "bank_integration"
app_title = "Bank Integration"
app_publisher = "Resilient Tech"
app_description = "Unofficial API to handle bank transactions using ERPNext"
app_icon = "fa fa-university"
app_color = "#f77174"
app_email = "info@resilient.tech"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/bank_integration/css/bank_integration.css"
# app_include_js = "/assets/bank_integration/js/bank_integration.js"

# include js, css files in header of web template
# web_include_css = "/assets/bank_integration/css/bank_integration.css"
# web_include_js = "/assets/bank_integration/js/bank_integration.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

doctype_js = {
    'Payment Entry': 'public/js/payment_entry.js'
}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "bank_integration.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "bank_integration.install.before_install"
# after_install = "bank_integration.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "bank_integration.notifications.get_notification_config"

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

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"bank_integration.tasks.all"
# 	],
# 	"daily": [
# 		"bank_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"bank_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"bank_integration.tasks.weekly"
# 	]
# 	"monthly": [
# 		"bank_integration.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "bank_integration.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "bank_integration.event.get_events"
# }

