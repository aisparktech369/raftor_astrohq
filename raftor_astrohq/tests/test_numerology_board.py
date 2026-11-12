"""What the numerology page shows for a name and a birth date (numerology_board.py): the numbers as medallions with their working and meaning, a topic chip for each of self, love, career, money, health and family,
and what the tradition says under the one chosen."""
import datetime
import unittest

from raftor_astrohq import astrology, numerology_board, numerology_topics


class TestTheTopicsText(unittest.TestCase):
	def test_every_number_has_a_line_for_each_topic_and_none_forecasts_or_gives_medical_advice(self):
		self.assertEqual(sorted(numerology_topics.TOPICS), list(range(1, 10)))
		for number, topics in numerology_topics.TOPICS.items():
			self.assertEqual(sorted(topics), ["career", "family", "health", "love", "money"], number)
			for key, text in topics.items():
				self.assertGreater(len(text), 40, (number, key))
				for word in ("will happen", "you will die", "cure", "diagnos", "disease", "guarantee"):
					self.assertNotIn(word, text.lower(), (number, key))


class TestTheWorking(unittest.TestCase):
	def test_a_sum_is_spaced_for_reading(self):
		self.assertEqual(numerology_board._sum("1+4=5"), "1 + 4 = 5")
		self.assertEqual(numerology_board._chain(["1+9+9+0=19", "1+9=10"]), "1 + 9 + 9 + 0 = 19 → 1 + 9 = 10")
		self.assertEqual(numerology_board._day_month("04-20"), "20 Apr")


class TestTheBuild(unittest.TestCase):
	def setUp(self):
		try:
			self.board = numerology_board.build("Asha Rao", datetime.date(1990, 5, 14))
		except astrology.AstrologyUnavailable:
			self.skipTest("the astrology service is not running")

	def test_the_numbers_come_with_their_value_caption_working_and_meaning(self):
		keys = [n["key"] for n in self.board["numbers"]]
		self.assertEqual(keys[:2], ["birth", "name"])
		for number in self.board["numbers"]:
			self.assertTrue(number["value"].isdigit() and number["caption"] and number["found"] and number["text"], number["key"])
		self.assertEqual(self.board["numbers"][0]["found"], "14: 1 + 4 = 5")
		self.assertIn("A1 + S3 + H5 + A1 = 10", self.board["numbers"][1]["found"])  # the letters of the name and their values
		self.assertEqual(self.board["name"], "Asha Rao")
		self.assertEqual(self.board["born_label"], "14 May 1990")

	def test_there_is_a_chip_for_each_topic_with_a_symbol_and_a_section_to_show(self):
		from raftor_websitehq.website_hq import icons

		self.assertEqual([t["key"] for t in self.board["topics"]], ["self", "love", "career", "money", "health", "family"])
		for topic in self.board["topics"]:
			self.assertTrue(str(icons.svg(topic["icon"])).startswith("<svg"), topic["key"])
			blocks = self.board["sections"][topic["key"]]
			self.assertTrue(blocks and all(b["heading"] and b["text"] for b in blocks), topic["key"])

	def test_the_topic_lines_are_the_ones_for_the_persons_own_numbers(self):
		birth = int(self.board["numbers"][0]["value"])
		self.assertEqual(self.board["sections"]["love"][0]["text"], numerology_topics.TOPICS[birth]["love"])
		self.assertEqual(self.board["sections"]["money"][0]["text"], numerology_topics.TOPICS[birth]["money"])

	def test_a_name_number_that_differs_adds_its_own_line_and_one_that_is_the_same_adds_none(self):
		birth, name = int(self.board["numbers"][0]["value"]), int(self.board["numbers"][1]["value"])
		self.assertEqual(len(self.board["sections"]["family"]), 2 if birth != name else 1)

	def test_the_page_says_it_is_a_tradition_and_not_a_prediction(self):
		self.assertIn("not a prediction", self.board["note"])
