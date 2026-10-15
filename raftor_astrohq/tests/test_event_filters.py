"""What astrohq adds to the listing of events: the wish a visitor comes with, read from the tags staff put on each event (event_filters.py)."""
import frappe
from frappe.desk.doctype.tag.tag import add_tag
from unittest.mock import patch

from raftor_astrohq import event_filters as ef
from raftor_servicehq import kinds
from raftor_servicehq.tests.test_events import EventCase


class TestWishFilters(EventCase):
	def tag(self, *words):
		for word in words:
			add_tag(word, "Service Event", self.event)

	def test_nothing_is_offered_until_an_event_is_tagged_with_a_wish(self):
		self.assertEqual(ef.wish_filters([self.event], {})["facets"], [])

	def test_a_wish_is_offered_with_how_many_events_serve_it_and_only_the_wishes_that_have_one(self):
		self.tag("Peace", "Success", "Something else")
		facet = ef.wish_filters([self.event], {})["facets"][0]
		self.assertEqual((facet["name"], facet["heading"], facet["display"]), ("wish", "What do you wish for?", "chips"))
		self.assertEqual({o["value"]: o["count"] for o in facet["options"]}, {"Peace": 1, "Success": 1})  # a tag that is not one of the wishes is just a tag

	def test_a_wish_narrows_in_any_case_and_nothing_chosen_keeps_everything(self):
		self.tag("Peace")
		self.assertEqual(ef.wish_filters([self.event], {})["names"], [self.event])
		self.assertEqual(ef.wish_filters([self.event], {"wish": "peace"})["names"], [self.event])
		self.assertEqual(ef.wish_filters([self.event], {"wish": "Success"})["names"], [])
		self.assertEqual(ef.wish_filters([self.event], {"wish": "Success,Peace"})["names"], [self.event])  # either

	def test_servicehq_gets_them_through_the_vocabulary(self):
		self.tag("Health")
		facets, names = kinds.event_filters("astrohq", [self.event], {"wish": "Health"})
		self.assertEqual([f["name"] for f in facets], ["wish"])
		self.assertEqual(names, [self.event])
		self.assertEqual(kinds.event_filters("astrohq", [self.event], {"wish": "Peace"})[1], [])
