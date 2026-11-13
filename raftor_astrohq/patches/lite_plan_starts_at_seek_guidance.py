"""The Lite plan's "Start free" button led to a chat with Pandit ji (an AI guide for Rudraksha and gemstones), which is not a start: it now leads to Seek guidance, where a guide is chosen and the first session is free.
Only the plan as it was shipped is changed: a plan the business team has pointed somewhere else is left alone."""
import frappe


def execute():
	for name in frappe.get_all("Subscription Plan", filters={"plan_name": "Lite", "button_url": "/ask/pandit-ji"}, pluck="name"):
		frappe.db.set_value("Subscription Plan", name, "button_url", "/consult")
