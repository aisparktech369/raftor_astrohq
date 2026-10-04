"""astrohq's words for servicehq's kinds: registered through the hook, and valid for servicehq."""
from unittest import TestCase

import frappe

from raftor_servicehq import kinds


class TestVocabulary(TestCase):
	def test_astrohq_is_registered_and_uses_all_four_kinds(self):
		self.assertIn("astrohq", kinds.registered_verticals())
		self.assertEqual(kinds.enabled_kinds("astrohq"), kinds.KINDS)

	def test_every_kind_has_the_words_a_page_needs(self):
		for kind in kinds.KINDS:
			w = kinds.words("astrohq", kind)
			for key in ("service", "services", "unit", "units", "book"):
				self.assertTrue(w[key], (kind, key))
		self.assertEqual(kinds.words("astrohq", "Event")["service"], "havan")
		self.assertEqual(kinds.words("astrohq", "Subscription")["unit"], "day")
		self.assertEqual(kinds.words("astrohq", "Consultation")["provider"], "astrologer")


class TestAstroSubscriptionPages(TestCase):
	def test_astrohqs_pages_are_servicehqs_builders_with_its_config(self):
		from raftor_astrohq import pages
		from raftor_websitehq.website_hq.app_pages import check_definition, registered_pages

		for route in ("astro/plans", "astro/subscribe", "astro/subscription"):
			self.assertIn(route, registered_pages())
		plans = check_definition(pages.plans())
		self.assertFalse(plans["login_required"])
		self.assertEqual(plans["blocks"][1]["args"], {"vertical": "astrohq", "prefix": "/astro"})
		frappe.set_user("Administrator")
		dashboard = check_definition(pages.subscription())
		self.assertEqual(dashboard["blocks"][1]["add"]["href"], "/astro/plans")
		self.assertEqual(dashboard["blocks"][-1]["links"][0]["href"], "/birth-profiles")  # astrohq's own section
