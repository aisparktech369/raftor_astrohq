"""The numerology report as a page (numerology_board.py): the numbers as medallions, a topic chip for each of self, love, career, money, health and family, and what the tradition says under the one chosen."""
import unittest

import frappe

from raftor_astrohq import astrology, numerology_board, numerology_topics, vocabulary

DETAILS = {"report_name": "Asha Rao", "birth_date": "1990-05-14"}


class TestTheTopicsText(unittest.TestCase):
	def test_every_number_has_a_line_for_each_topic_and_none_forecasts_or_gives_medical_advice(self):
		self.assertEqual(sorted(numerology_topics.TOPICS), list(range(1, 10)))
		for number, topics in numerology_topics.TOPICS.items():
			self.assertEqual(sorted(topics), ["career", "family", "health", "love", "money"], number)
			for key, text in topics.items():
				self.assertGreater(len(text), 40, (number, key))
				for word in ("will happen", "you will die", "cure", "diagnos", "disease", "guarantee"):
					self.assertNotIn(word, text.lower(), (number, key))


class TestTheBoard(unittest.TestCase):
	def setUp(self):
		try:
			self.board = numerology_board.board("ITEM", DETAILS, "x@example.com")
		except astrology.AstrologyUnavailable:
			self.skipTest("the astrology service is not running")

	def test_the_numbers_are_medallions_with_the_engines_own_values(self):
		labels = [m["label"] for m in self.board["medallions"]]
		self.assertEqual(labels[:2], ["Birth number", "Name number"])
		for medallion in self.board["medallions"]:
			self.assertTrue(medallion["value"].isdigit() and medallion["caption"])
		self.assertIn("Asha Rao", self.board["subtitle"])

	def test_there_is_a_chip_for_each_topic_with_a_symbol_and_a_section_to_show(self):
		from raftor_websitehq.website_hq import icons

		self.assertEqual([t["key"] for t in self.board["topics"]], ["self", "love", "career", "money", "health", "family"])
		for topic in self.board["topics"]:
			self.assertTrue(str(icons.svg(topic["icon"])).startswith("<svg"), topic["key"])
			blocks = self.board["sections"][topic["key"]]
			self.assertTrue(blocks and all(b["heading"] and b["text"] for b in blocks), topic["key"])

	def test_the_topic_lines_are_the_ones_for_the_persons_own_numbers(self):
		birth = int(self.board["medallions"][0]["value"])
		self.assertEqual(self.board["sections"]["love"][0]["text"], numerology_topics.TOPICS[birth]["love"])
		self.assertEqual(self.board["sections"]["money"][0]["text"], numerology_topics.TOPICS[birth]["money"])

	def test_a_name_number_that_differs_adds_its_own_line_and_one_that_is_the_same_adds_none(self):
		birth, name = int(self.board["medallions"][0]["value"]), int(self.board["medallions"][1]["value"])
		self.assertEqual(len(self.board["sections"]["career"]) >= 2, True)
		self.assertEqual(len([b for b in self.board["sections"]["family"]]), 2 if birth != name else 1)

	def test_the_page_says_it_is_a_tradition_and_not_a_prediction(self):
		self.assertIn("not a prediction", self.board["note"])


class TestWhereItIsAsked(unittest.TestCase):
	def test_the_numerology_report_names_its_board_and_the_page_uses_the_card(self):
		from raftor_servicehq import page_definitions

		self.assertEqual(vocabulary.vocabulary()["reports"]["numerology"]["board"], "raftor_astrohq.numerology_board.board")
		page = next(p for p in page_definitions.definitions() if p["route"] == "my/report")
		card = next(c for s in page["sections"] for c in s.get("cards", []) if c["type"] == "Medallion Report Card")
		self.assertEqual(card["values"], {"view": "raftor_servicehq.free_reports.report_board", "url_args": "report"})
		self.assertTrue(frappe.db.exists("Web Template", "Medallion Report Card"))
