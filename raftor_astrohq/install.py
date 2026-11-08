"""Idempotent: safe to run on every migrate."""
import frappe

from raftor_astrohq.journey import register_journey, register_provider_steps
from raftor_astrohq.profiles import ensure_fields


def after_install():
	ensure_fields()
	from raftor_astrohq import products

	products.ensure_fields()
	products.sync_planets()
	register_journey()
	register_provider_steps()
	sync_portal_menu()
	seed_topics_and_wishes()
	sync_written_content()


WISHES = ["Prosperity", "Health", "Family", "Protection", "Peace", "Success"]


def starting_topics() -> list[str]:
	"""The topics are the ones the consulting services ship for (pack/consulting.json): one list for the guides page and for the services a guide enrols in."""
	from raftor_astrohq import vocabulary

	return list(dict.fromkeys(entry["topic"] for entry in vocabulary.pack_services() if entry.get("topic")))  # (a topic has a service for each length of session: it is listed once)


def sync_written_content():
	"""The Rudraksha articles and the like: the blog is made from content/, so a fresh install has them and a migrate brings them up to date."""
	from raftor_astrohq import content

	content.name_the_blog()
	content.sync_blog()


def seed_topics_and_wishes():
	"""The starting topics and wishes, as records staff change in Desk (Guidance Topic, Blessing Wish). Only when there are none, so a list staff have edited
	is never put back."""
	for doctype, field, names in (("Guidance Topic", "topic_name", starting_topics()), ("Blessing Wish", "wish_name", WISHES)):
		if frappe.db.count(doctype):
			continue
		for n, name in enumerate(names, 1):
			frappe.get_doc({"doctype": doctype, field: name, "enabled": 1, "sequence": n * 10}).insert(ignore_permissions=True)


def sync_portal_menu():
	"""Adds this app's My account menu entry (hooks.py) if it is missing; never overwrites an admin's edits."""
	frappe.get_doc("Portal Settings", "Portal Settings").sync_menu()
