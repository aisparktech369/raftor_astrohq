"""Idempotent: safe to run on every migrate."""
import frappe

from raftor_astrohq.journey import register_journey, register_provider_steps
from raftor_astrohq.profiles import ensure_fields


def after_install():
	ensure_fields()
	register_journey()
	register_provider_steps()
	sync_portal_menu()
	from raftor_astrohq.branding import apply

	apply()  # the brand and the menus, where the site still has the defaults


def sync_portal_menu():
	"""Adds this app's My account menu entry (hooks.py) if it is missing; never overwrites an admin's edits."""
	frappe.get_doc("Portal Settings", "Portal Settings").sync_menu()
