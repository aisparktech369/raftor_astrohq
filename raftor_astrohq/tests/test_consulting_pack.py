"""The consulting services AstroHQ ships (pack/consulting.json): for each topic a 10, a 20 and a 30 minute session, open to any kind of guide; the guides page lists the same topics."""
from unittest import TestCase

from raftor_astrohq import install, vocabulary

TOPICS = ["Love", "Marriage", "Career", "Wealth", "Business", "Health", "Children", "Education", "Family", "Property", "Foreign travel", "Auspicious date"]


class TestConsultingPack(TestCase):
	def setUp(self):
		self.entries = [e for e in vocabulary.pack_services() if e.get("topic")]

	def test_it_ships_the_twelve_agreed_topics_in_order_each_with_a_10_20_and_30_minute_session(self):
		self.assertEqual(len(self.entries), 36)
		for n, topic in enumerate(TOPICS):
			mine = self.entries[n * 3:n * 3 + 3]
			self.assertEqual([(e["topic"], e["minutes"], e["price"]) for e in mine], [(topic, 10, 251), (topic, 20, 501), (topic, 30, 1100)])

	def test_each_is_a_consultation_with_the_platforms_price_a_50_percent_discount_to_start_and_for_any_kind_of_guide(self):
		for e in self.entries:
			self.assertEqual(e["name"], f"{e['topic']} consulting {e['minutes']} min")
			self.assertEqual((e["kind"], e["default_discount"]), ("Consultation", 50))
			self.assertNotIn("persona", e)  # any kind of guide
			self.assertNotIn("minutes_by_provider", e)  # the minutes are the platform's
			self.assertTrue(e["description"].strip(), e["name"])

	def test_the_topics_the_guides_page_starts_with_are_the_same_list(self):
		self.assertEqual(install.starting_topics(), TOPICS)
