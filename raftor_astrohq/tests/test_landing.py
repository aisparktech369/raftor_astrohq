from unittest import TestCase

import frappe

from raftor_astrohq.landing import default_home


class TestLanding(TestCase):
	def test_staff_are_not_sent_to_the_customer_dashboard(self):
		self.assertEqual(default_home("Administrator"), "")

	def test_a_website_user_lands_on_the_dashboard(self):
		user = frappe.db.get_value("User", {"user_type": "Website User", "enabled": 1})
		if user:
			self.assertEqual(default_home(user), "/my")
