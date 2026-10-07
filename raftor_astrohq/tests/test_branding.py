"""AstroHQ's brand and menus go on a site once, where it still has the defaults; what the business team changed stays."""
from unittest import TestCase

import frappe

from raftor_astrohq import branding


class TestBranding(TestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_the_site_shows_the_brand_and_the_services_menu(self):
		ws = frappe.get_single("Website Settings")
		self.assertEqual(ws.app_name, "AstroHQ")
		self.assertIn("AstroHQ", ws.footer_powered)
		self.assertNotIn("ERPNext", ws.footer_powered or "")
		urls = [r.url for r in ws.top_bar_items]
		for url in ("/services/book", "/services/events", "/services/subscriptions", "/services/plans", "/all-products"):
			self.assertIn(url, urls)
		self.assertEqual(frappe.db.get_single_value("System Settings", "app_name"), "AstroHQ")
		self.assertFalse(frappe.db.get_single_value("System Settings", "login_with_email_link"))

	def test_menu_words_come_from_the_verticals_vocabulary(self):
		labels = [row["label"] for row in branding._top_bar()]
		self.assertIn("Astrologers", labels)  # astrohq's word for providers
		self.assertIn("Havans", labels)
		self.assertIn("Daily pooja", labels)

	def test_running_it_again_keeps_what_the_site_changed(self):
		frappe.db.set_single_value("Website Settings", "app_name", "Our own name")
		ws = frappe.get_single("Website Settings")
		ws.set("top_bar_items", [{"label": "Only this", "url": "/x"}])
		ws.save(ignore_permissions=True)
		branding.apply()
		ws = frappe.get_single("Website Settings")
		self.assertEqual(ws.app_name, "Our own name")
		self.assertEqual([(r.label, r.url) for r in ws.top_bar_items], [("Only this", "/x")])

	def test_the_account_menu_has_the_persons_own_pages_and_drops_the_unused_ones(self):
		menu = {row.route: row for row in frappe.get_single("Portal Settings").menu}
		for route in ("/my/bookings", "/my/plan", "/my/birth-profiles"):
			self.assertIn(route, menu)
			self.assertTrue(menu[route].enabled)
		self.assertEqual(menu["/provider"].role, "Service Provider")
		for route in ("/project", "/timesheets", "/rfhq/plans"):
			if route in menu:
				self.assertFalse(menu[route].enabled, route)
