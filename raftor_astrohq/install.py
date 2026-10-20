"""Idempotent: safe to run on every migrate."""
import frappe

from raftor_astrohq.journey import register_journey, register_provider_steps
from raftor_astrohq.profiles import ensure_fields


def after_install():
	ensure_fields()
	register_journey()
	register_provider_steps()
	sync_portal_menu()
	seed_topics_and_wishes()


TOPICS = ["Career", "Marriage", "Love", "Money", "Health", "Children", "Auspicious date"]
WISHES = ["Prosperity", "Health", "Family", "Protection", "Peace", "Success"]


def seed_topics_and_wishes():
	"""The starting topics and wishes, as records staff change in Desk (Guidance Topic, Blessing Wish). Only when there are none, so a list staff have edited
	is never put back."""
	for doctype, field, names in (("Guidance Topic", "topic_name", TOPICS), ("Blessing Wish", "wish_name", WISHES)):
		if frappe.db.count(doctype):
			continue
		for n, name in enumerate(names, 1):
			frappe.get_doc({"doctype": doctype, field: name, "enabled": 1, "sequence": n * 10}).insert(ignore_permissions=True)


def sync_portal_menu():
	"""Adds this app's My account menu entry (hooks.py) if it is missing; never overwrites an admin's edits."""
	frappe.get_doc("Portal Settings", "Portal Settings").sync_menu()
