"""What the account menu (Portal Settings) shows each kind of person: their own pages, never ERPNext's procurement pages."""
import uuid
from unittest import TestCase

import frappe
from frappe.website.utils import get_portal_sidebar_items

PROCUREMENT = {"Request for Quotations", "Supplier Quotation", "Purchase Orders", "Purchase Invoices"}


def titles_for(*roles):
	email = f"menu-{uuid.uuid4().hex[:8]}@example.com"
	frappe.get_doc({"doctype": "User", "email": email, "first_name": "Menu", "send_welcome_email": 0, "user_type": "Website User",
					"roles": [{"role": r} for r in roles]}).insert(ignore_permissions=True)
	frappe.cache.hdel("portal_menu_items", email)
	frappe.set_user(email)
	try:
		return [item["title"] for item in get_portal_sidebar_items()]
	finally:
		frappe.set_user("Administrator")
		frappe.cache.hdel("portal_menu_items", email)


class TestAccountMenu(TestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_a_seeker_sees_their_own_pages_first_and_no_provider_or_staff_link(self):
		titles = titles_for("Customer")
		self.assertEqual(titles[:7], ["My bookings", "My registrations", "My subscriptions", "My plan", "My schedule", "Remedies", "Birth profiles"])
		self.assertNotIn("Your astrologer page", titles)
		self.assertNotIn("Business team", titles)

	def test_a_provider_sees_their_page_in_the_verticals_word(self):
		self.assertIn("Your astrologer page", titles_for("Service Provider"))

	def test_staff_see_the_business_team_page(self):
		self.assertIn("Business team", titles_for("Business Team"))

	def test_nobody_sees_the_procurement_pages_even_as_a_supplier(self):
		self.assertFalse(PROCUREMENT & set(titles_for("Supplier", "Customer")))

	def test_the_old_second_birth_profiles_link_is_gone(self):
		self.assertEqual(titles_for("Customer").count("Birth profiles"), 1)
