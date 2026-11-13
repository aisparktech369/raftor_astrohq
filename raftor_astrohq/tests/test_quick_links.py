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


class TestTheFreeReportsPageIsWritten(TestCase):
	def test_the_welcome_steps_questions_and_the_way_to_talk_are_all_there_and_short(self):
		page = vocabulary()["free_reports_page"]
		self.assertTrue(page["heading"] and page["subheading"] and page["cta"] and page["badge"])
		self.assertEqual(len(page["steps"]), 3)
		self.assertTrue(all(s["title"] and s["body"] for s in page["steps"]))
		self.assertGreaterEqual(len(page["faq"]), 4)
		self.assertTrue(all(i["q"] and i["a"] for i in page["faq"]))
		self.assertTrue(all(len(i["q"]) <= 120 for i in page["faq"]))
		self.assertTrue(page["consult"]["heading"] and page["consult"]["label"])

	def test_the_free_tools_with_a_page_of_their_own_are_named_with_a_line_and_a_way_in(self):
		soon = vocabulary()["reports_soon"]
		linked = [r for r in soon if r.get("link")]
		self.assertGreaterEqual(len(linked), 3)
		self.assertTrue(all(r["blurb"] and r["icon"] and r["link"].startswith("/") for r in linked))
