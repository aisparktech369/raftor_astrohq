"""The Blessings AstroHQ ships (pack/blessings.json): 52 poojas in four kinds, priced alike for now, each with its words and its shelf."""
from unittest import TestCase

from raftor_astrohq import vocabulary

KINDS = ("Home services", "Kamna purti", "Samasya samadhan", "Graha shanti")


class TestBlessingsPack(TestCase):
	def setUp(self):
		self.entries = [e for e in vocabulary.pack_services() if (e.get("shelf") or [""])[0] == "Blessings"]

	def test_it_ships_the_agreed_52_poojas_each_named_once(self):
		self.assertEqual(len(self.entries), 52)
		self.assertEqual(len({e["name"] for e in self.entries}), 52)

	def test_each_pooja_sits_under_a_kind_and_a_topic_and_has_words(self):
		counts = {}
		for e in self.entries:
			self.assertEqual(len(e["shelf"]), 3, e["name"])
			self.assertIn(e["shelf"][1], KINDS, e["name"])
			self.assertTrue(e["description"].strip(), e["name"])
			counts[e["shelf"][1]] = counts.get(e["shelf"][1], 0) + 1
		self.assertEqual(counts, {"Home services": 10, "Kamna purti": 9, "Samasya samadhan": 9, "Graha shanti": 24})

	def test_home_poojas_are_done_at_the_home_on_request_and_the_rest_come_in_two_forms_on_dates(self):
		for e in self.entries:
			if e["shelf"][1] == "Home services":
				self.assertEqual((e["kind"], e["on_request"], e["at_customer"], e.get("dated")), ("Timed service", True, True, None), e["name"])
				self.assertEqual((e["price"], e["offer_price"]), (2100, 1100), e["name"])
			else:
				self.assertTrue(e["dated"], e["name"])
				self.assertEqual(e["prices"], {"Shared": {"price": 501, "offer": 101}, "Personalised": {"price": 2100, "offer": 1100}}, e["name"])

	def test_every_offer_is_below_its_price_and_the_words_promise_no_result(self):
		for e in self.entries:
			for p in ([e] if "price" in e else e["prices"].values()):
				self.assertLess(p.get("offer_price", p.get("offer")), p["price"], e["name"])
			for word in ("guarantee", "ensure", "100%", "certain"):
				self.assertNotIn(word, e["description"].lower(), e["name"])
