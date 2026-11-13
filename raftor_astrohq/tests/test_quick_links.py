"""Where a signed-in customer begins (the tiles on /my, from the vocabulary): each is a page of this site and has an icon the site draws."""
from unittest import TestCase

import frappe

from raftor_astrohq.vocabulary import vocabulary
from raftor_websitehq.website_hq import icons


class TestQuickLinks(TestCase):
	def test_every_place_to_begin_is_a_published_page_of_the_site_with_an_icon_the_site_has(self):
		listed = vocabulary()["quick_links"]
		self.assertGreaterEqual(len(listed), 4)
		published = set(frappe.get_all("Web Page", filters={"published": 1}, pluck="route"))
		for link in listed:
			self.assertTrue(link["label"] and link["summary"], link)
			self.assertTrue(link["url"].startswith("/") and not link["url"].startswith("//"), link)
			self.assertIn(link["url"].strip("/"), published, link["url"])
			self.assertTrue(icons.svg(link["icon"]), link["icon"])
