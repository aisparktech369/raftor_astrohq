"""astrohq's words for servicehq's kinds: registered through the hook, and valid for servicehq."""
from unittest import TestCase

import frappe

from raftor_astrohq import vocabulary
from raftor_servicehq import kinds


class TestVocabulary(TestCase):
	def test_astrohq_is_registered_and_uses_all_four_kinds(self):
		self.assertIn("astrohq", kinds.registered_verticals())
		self.assertEqual(kinds.enabled_kinds("astrohq"), kinds.KINDS)

	def test_an_astrologers_session_must_end_with_a_remedy_unless_said_otherwise(self):
		self.assertEqual(kinds.recommendation_default("astrohq", "Consultation"), "Required")  # the guide writes the remedy or reading before it is marked done
		self.assertEqual(kinds.recommendation_default("astrohq", "Event"), "None")
		self.assertEqual(kinds.recommendation_default("", "Consultation"), "Optional")  # (a vertical that says nothing: as before)
		self.assertEqual(kinds.words("astrohq", "Consultation")["recommendation"], "remedy")  # (the setting is not a word: it must not replace the word for a recommendation)

	def test_every_kind_has_the_words_a_page_needs(self):
		for kind in kinds.KINDS:
			w = kinds.words("astrohq", kind)
			for key in ("service", "services", "unit", "units", "book"):
				self.assertTrue(w[key], (kind, key))
		self.assertEqual(kinds.words("astrohq", "Event")["service"], "havan")
		self.assertEqual(kinds.words("astrohq", "Subscription")["unit"], "day")
		self.assertEqual(kinds.words("astrohq", "Consultation")["provider"], "astrologer")


class TestTheKindsOfGuide(TestCase):
	def test_they_come_in_the_order_leaders_list_them(self):
		self.assertEqual(list(vocabulary.vocabulary()["personas"]), ["Astrologer", "KP astrologer", "Numerologist", "Tarot reader", "Pandit ji", "Vastu expert", "Palmist"])

	def test_every_free_report_belongs_to_one_of_them(self):
		vocab = vocabulary.vocabulary()
		for name, report in vocab["reports"].items():
			self.assertIn(report.get("kind"), vocab["personas"], name)
		self.assertEqual(vocab["reports"]["kp"]["kind"], "KP astrologer")

