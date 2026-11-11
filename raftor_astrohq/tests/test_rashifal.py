"""The daily rashifal (rashifal.py): the houses and leans worked out from the sky, the check on what the writer sends back, what a visitor is shown, and that a day is written once."""
import datetime
import json
from unittest.mock import patch

import frappe

from raftor_astrohq import rashifal
from raftor_astrohq.tests.helpers import AstroTestCase

# every planet in Libra (7) but the Moon in Scorpio (8) and Jupiter in Leo (5)
SKY = {"positions": {p: {"sign": 7, "retrograde": False} for _, p in rashifal.PLANETS} | {"Moon": {"sign": 8, "retrograde": False}, "Jupiter": {"sign": 5, "retrograde": False}},
	   "nakshatra": "Anuradha", "sunrise": "06:40", "weekday": "Wednesday"}
GOOD_WORDS = {"en": {k: f"A sentence for {k}." for k in rashifal.PARTS}, "hi": {k: f"{k} के लिए एक वाक्य।" for k in rashifal.PARTS}}
DAY = datetime.date(2031, 3, 5)  # far from any real day written on a dev site


class TestSkyMaths(AstroTestCase):
	def test_house_counts_the_sign_itself_as_first(self):
		self.assertEqual(rashifal.house(7, 7), 1)
		self.assertEqual(rashifal.house(8, 7), 2)
		self.assertEqual(rashifal.house(6, 7), 12)
		self.assertEqual(rashifal.house(1, 12), 2)

	def test_facts_follow_the_traditional_houses(self):
		given = rashifal.facts(SKY, 1)  # from Aries: Moon in Scorpio is the 8th (not good for it), Jupiter in Leo the 5th (good), the rest in Libra the 7th
		self.assertEqual(given["moon_house_from_sign"], 8)
		self.assertEqual(given["sign"], "Aries")
		self.assertEqual((given["element"], given["ruling_planet"]), ("fire", "Mars"))
		self.assertEqual(given["lucky_colour"], "Yellow")  # Jupiter is in a good house and comes first
		self.assertEqual(given["lucky_number"], 3)
		self.assertIn(given["lean"]["money"], ("positive", "mixed", "careful"))

	def test_lean_thresholds(self):
		self.assertEqual(rashifal.lean(1.0), "positive")
		self.assertEqual(rashifal.lean(0.5), "mixed")
		self.assertEqual(rashifal.lean(0.0), "careful")

	def test_a_sign_with_no_good_planet_still_has_a_colour(self):
		sky = {**SKY, "positions": {p: {"sign": 1, "retrograde": False} for _, p in rashifal.PLANETS}}
		given = rashifal.facts(sky, 4)  # every planet in the 10th from Cancer... the colour is never blank
		self.assertTrue(given["lucky_colour"] and given["lucky_number"])


class TestWhatTheWriterSends(AstroTestCase):
	def test_good_answer_is_kept_clean(self):
		words = rashifal.parse("```json\n" + json.dumps({"en": {k: f"<b>{v}</b>  x" for k, v in GOOD_WORDS["en"].items()}, "hi": GOOD_WORDS["hi"]}) + "\n```")
		self.assertEqual(words["en"]["love"], "A sentence for love. x")
		self.assertNotIn("<", words["en"]["summary"])

	def test_answers_that_are_not_what_was_asked_are_refused(self):
		with self.assertRaises(ValueError):
			rashifal.parse("not json at all")
		with self.assertRaises(ValueError):
			rashifal.parse(json.dumps({"en": GOOD_WORDS["en"]}))  # no Hindi
		with self.assertRaises(ValueError):
			rashifal.parse(json.dumps({"en": GOOD_WORDS["en"], "hi": GOOD_WORDS["en"]}))  # the Hindi is English
		with self.assertRaises(ValueError):
			rashifal.parse(json.dumps({"en": {**GOOD_WORDS["en"], "work": ""}, "hi": GOOD_WORDS["hi"]}))  # a part is empty

	def test_a_long_sentence_is_cut(self):
		words = rashifal.parse(json.dumps({"en": {**GOOD_WORDS["en"], "love": "word " * 100}, "hi": GOOD_WORDS["hi"]}))
		self.assertLessEqual(len(words["en"]["love"]), rashifal.LIMITS["love"])


class TestADay(AstroTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.delete(rashifal.DOCTYPE, {"for_date": DAY})
		doc = frappe.get_single(rashifal.SETTINGS)
		doc.enabled, doc.publish_at_once = 1, 0
		doc.save(ignore_permissions=True)

	def _write(self, **kw):
		with patch.object(rashifal, "sky", return_value=SKY), patch.object(rashifal, "write", return_value=(GOOD_WORDS, "test-model")) as writer:
			return rashifal.write_day(DAY, **kw), writer

	def test_twelve_drafts_are_written_once(self):
		result, writer = self._write()
		self.assertEqual((result["made"], result["failed"]), (12, 0))
		self.assertEqual(writer.call_count, 12)
		self.assertEqual(frappe.db.count(rashifal.DOCTYPE, {"for_date": DAY, "status": "Draft"}), 12)
		again, writer = self._write()  # nothing is written twice
		self.assertEqual((again["made"], writer.call_count), (0, 0))

	def test_one_failure_does_not_stop_the_others_and_is_retried(self):
		calls = {"n": 0}

		def flaky(given, s=None):
			calls["n"] += 1
			if calls["n"] == 3:
				raise rashifal.RashifalUnavailable("down")
			return GOOD_WORDS, "m"

		with patch.object(rashifal, "sky", return_value=SKY), patch.object(rashifal, "write", side_effect=flaky):
			result = rashifal.write_day(DAY)
		self.assertEqual((result["made"], result["failed"]), (11, 1))
		result, _ = self._write()  # the next run writes only the missing one
		self.assertEqual(result["made"], 1)

	def test_switched_off_writes_nothing_unless_a_person_asks(self):
		doc = frappe.get_single(rashifal.SETTINGS)
		doc.enabled = 0
		doc.save(ignore_permissions=True)
		result, _ = self._write()
		self.assertEqual(result["made"], 0)
		result, _ = self._write(manual=True)
		self.assertEqual(result["made"], 12)

	def test_the_engine_being_down_is_reported_not_raised(self):
		from raftor_astrohq import astrology

		with patch.object(rashifal, "sky", side_effect=astrology.AstrologyUnavailable("down")):
			result = rashifal.write_day(DAY)
		self.assertFalse(result["ok"])

	def test_only_published_readings_are_shown_and_publishing_a_day(self):
		self._write()
		with patch.object(rashifal, "today", return_value=DAY):
			self.assertEqual(rashifal.cards(), {"items": []})  # drafts are not shown
			self.assertEqual(rashifal.publish_day(DAY)["published"], 12)
			items = rashifal.cards()["items"]
		self.assertEqual(len(items), 12)
		self.assertEqual(items[0]["layout"], "Flip")
		self.assertEqual((items[0]["title"], items[0]["meta"]), ("Aries", "मेष"))
		self.assertTrue(items[0]["body"] and items[0]["pills"].count("\n") == 3 and items[0]["note"])

	def test_a_stale_day_is_not_shown(self):
		self._write()
		rashifal.publish_day(DAY)
		with patch.object(rashifal, "today", return_value=DAY + datetime.timedelta(days=3)):
			self.assertEqual(rashifal.cards(), {"items": []})


class TestTheBand(AstroTestCase):
	def test_the_band_is_one_carousel_section_fed_by_the_cards(self):
		(section,) = rashifal.band()
		self.assertEqual(section["layout"], "Carousel")
		self.assertEqual(section["source"]["method"], "raftor_astrohq.rashifal.cards")
		self.assertEqual(section["source"]["card"], "Feature Card")

	def test_astrohq_asks_servicehq_to_put_it_on_the_consult_page(self):
		self.assertIn("raftor_astrohq.rashifal.band", frappe.get_hooks("servicehq_consult_bands"))
