"""The tarot page (tarot.py): three cards for anyone, their meanings, and the reading of the three together for someone signed in."""
import json
from unittest.mock import patch

import frappe

from raftor_astrohq import page_definitions, tarot, vocabulary
from raftor_astrohq.tarot_deck import MAJOR
from raftor_astrohq.tests.helpers import AstroTestCase, make_user


class TestTheDeck(AstroTestCase):
	def test_there_are_twenty_two_cards_each_with_its_own_symbol_from_the_sites_icon_set(self):
		from raftor_websitehq.website_hq import icons

		self.assertEqual(len(MAJOR), 22)
		self.assertEqual(len({card[1] for card in MAJOR}), 22)
		self.assertEqual(len({card[2] for card in MAJOR}), 22)
		for numeral, name, icon, keywords, upright, reversed_text in MAJOR:
			self.assertTrue(str(icons.svg(icon)).startswith("<svg"), name)
			self.assertTrue(upright and reversed_text and keywords, name)
			for word in ("will happen", "you will die", "doctor", "lawyer"):  # reflection, never a forecast or advice
				self.assertNotIn(word, (upright + reversed_text).lower(), name)


class TestTheDraw(AstroTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def guest_draw(self, question=None):
		frappe.set_user("Guest")
		return tarot.draw(question)

	def test_three_different_cards_in_their_places_each_with_a_meaning(self):
		reading = self.guest_draw("Should I change my work?")["reading"]
		self.assertEqual([c["position"] for c in reading["cards"]], ["past", "present", "future"])
		self.assertEqual(len({c["name"] for c in reading["cards"]}), 3)
		for card in reading["cards"]:
			self.assertTrue(card["meaning"] and card["keywords"] and card["numeral"])
			self.assertIn(card["orientation"], ("Upright", "Reversed"))
		self.assertEqual(reading["question"], "Should I change my work?")

	def test_the_words_come_with_it_and_a_question_is_cleaned_and_kept_short(self):
		answer = self.guest_draw("<b>Hello</b> " + "x" * 500)
		self.assertTrue(answer["words"]["title"] and answer["words"]["positions"]["past"]["label"])
		self.assertNotIn("<b>", answer["reading"]["question"])
		self.assertLessEqual(len(answer["reading"]["question"]), tarot.QUESTION_LENGTH)

	def test_the_machine_has_one_central_button_and_a_way_to_consult_after_the_reading(self):
		words = self.guest_draw()["words"]
		self.assertTrue(words["shuffle"] and words["stop"] and words["press"])
		self.assertEqual(len(words["ornament"].split()), 12)
		self.assertEqual(words["consult"]["url"], "/consult?persona=Tarot+reader")  # the tarot readers, AI and human
		self.assertTrue(words["consult"]["label"] and words["consult"]["text"])

	def test_a_visitor_gets_the_three_cards_and_a_locked_reading_with_the_way_to_sign_in(self):
		reading = self.guest_draw()["reading"]
		state = reading["interpretation"]
		self.assertEqual(state["state"], "locked")
		self.assertTrue(state["login_url"].startswith("/login?redirect-to="))
		self.assertIn(reading["token"], state["login_url"])  # they come back to the same draw
		with patch.object(tarot, "_write") as written:
			self.assertEqual(tarot.interpret(reading["token"])["interpretation"]["state"], "locked")
		written.assert_not_called()  # nothing is written for someone who has not signed in

	def test_the_topics_are_chips_with_a_symbol_and_the_one_chosen_is_kept_with_the_draw(self):
		from raftor_websitehq.website_hq import icons

		frappe.set_user("Guest")
		answer = tarot.draw("What now?", "career")
		topics = answer["words"]["topics"]
		self.assertEqual([t["key"] for t in topics], ["love", "career", "money", "health", "family", "self", "general"])
		for topic in topics:
			self.assertTrue(topic["label"] and str(icons.svg(topic["icon"])).startswith("<svg"), topic["key"])
		self.assertEqual(answer["reading"]["topic"], "career")
		self.assertEqual(tarot.view(answer["reading"]["token"])["reading"]["topic"], "career")  # the same when they come back from signing in
		for odd in (None, "", "politics", "<b>x</b>"):
			self.assertEqual(tarot.draw(None, odd)["reading"]["topic"], "", odd)  # one of ours, or none

	def test_the_topic_is_told_to_the_writer_and_kept_with_the_reading(self):
		frappe.set_user("Guest")
		token = tarot.draw("", "money")["reading"]["token"]
		frappe.set_user(make_user().name)
		sent = {}

		def fake(url, json=None, headers=None, timeout=None):
			sent.update(json)

			class Answer:
				status_code = 200

				def json(self_inner):
					return {"data": {"content": "Words.", "model": "m"}}
			return Answer()

		settings = frappe._dict(address="http://hub", site="", key="k", api_name="text-to-text", timeout=5)
		with patch.object(tarot.rashifal, "settings", return_value=settings), patch.object(tarot.requests, "post", fake):
			tarot.interpret(token)
		self.assertEqual(frappe.parse_json(sent["payload"]["prompt"])["topic"], "Money")
		self.assertEqual(frappe.db.get_value("Tarot Reading", token, "topic"), "money")

	def test_coming_back_with_the_token_shows_the_same_three(self):
		first = self.guest_draw()["reading"]
		again = tarot.view(first["token"])["reading"]
		self.assertEqual([c["name"] for c in again["cards"]], [c["name"] for c in first["cards"]])
		self.assertIsNone(tarot.view("nothing-like-it")["reading"])
		self.assertIsNone(tarot.view(None)["reading"])

	def test_someone_signed_in_has_the_reading_written_once_and_kept(self):
		token = self.guest_draw("What now?")["reading"]["token"]
		user = make_user().name
		frappe.set_user(user)
		self.assertEqual(tarot.view(token)["reading"]["interpretation"]["state"], "pending")
		with patch.object(tarot, "_write", return_value=("A calm reading.", "a-model")) as written:
			first = tarot.interpret(token)
			second = tarot.interpret(token)
		self.assertEqual(first["interpretation"], {"state": "ready", "text": "A calm reading."})
		self.assertEqual(second["interpretation"], first["interpretation"])
		self.assertEqual(written.call_count, 1)
		row = frappe.db.get_value("Tarot Reading", token, ["user", "question", "model"], as_dict=True)
		self.assertEqual((row.user, row.question, row.model), (user, "What now?", "a-model"))
		self.assertEqual(tarot.view(token)["reading"]["interpretation"], {"state": "ready", "text": "A calm reading."})

	def test_the_reading_asked_to_the_writer_holds_only_the_cards_and_the_question(self):
		token = self.guest_draw("What now?")["reading"]["token"]
		frappe.set_user(make_user().name)
		sent = {}

		def fake(url, json=None, headers=None, timeout=None):
			sent.update(json)

			class Answer:
				status_code = 200

				def json(self_inner):
					return {"data": {"content": "**Words** here", "model": "m"}}
			return Answer()

		settings = frappe._dict(address="http://hub", site="", key="k", api_name="text-to-text", timeout=5)
		with patch.object(tarot.rashifal, "settings", return_value=settings), patch.object(tarot.requests, "post", fake):
			text = tarot.interpret(token)["interpretation"]["text"]
		prompt = frappe.parse_json(sent["payload"]["prompt"])
		self.assertEqual(sorted(prompt), ["cards", "question", "topic"])
		self.assertEqual(len(prompt["cards"]), 3)
		self.assertEqual(text, "Words here")  # the markup of a model is not kept

	def test_a_writer_that_is_away_says_so_and_nothing_is_kept(self):
		token = self.guest_draw()["reading"]["token"]
		frappe.set_user(make_user().name)
		with patch.object(tarot, "_write", side_effect=tarot.ReadingUnavailable):
			self.assertEqual(tarot.interpret(token)["interpretation"], {"state": "later"})
		self.assertFalse(frappe.db.exists("Tarot Reading", token))
		with patch.object(tarot, "_write", return_value=("Now it is written.", "m")):
			self.assertEqual(tarot.interpret(token)["interpretation"]["state"], "ready")  # asking again works

	def test_another_persons_reading_is_not_opened_by_its_address(self):
		token = self.guest_draw()["reading"]["token"]
		frappe.set_user(make_user().name)
		with patch.object(tarot, "_write", return_value=("Mine.", "m")):
			tarot.interpret(token)
		frappe.set_user(make_user().name)
		self.assertFalse(tarot.interpret(token)["ok"])

	def test_a_draw_nobody_made_is_gone(self):
		frappe.set_user(make_user().name)
		self.assertFalse(tarot.interpret("x" * 30)["ok"])

	def test_the_cards_are_not_always_the_same(self):
		seen = {tuple(c["name"] for c in self.guest_draw()["reading"]["cards"]) for _ in range(12)}
		self.assertGreater(len(seen), 1)


class TestThePage(AstroTestCase):
	def test_the_page_is_open_to_anyone_and_uses_the_card_with_the_apps_methods(self):
		page = next(p for p in page_definitions.definitions() if p["route"] == "services/tarot")
		self.assertFalse(page["login_required"])
		card = page["sections"][0]["cards"][0]
		self.assertEqual(card["type"], "Tarot Draw Card")
		self.assertEqual(card["values"], {"view": "raftor_astrohq.tarot.view", "draw": "raftor_astrohq.tarot.draw", "interpret": "raftor_astrohq.tarot.interpret", "url_args": "draw"})
		self.assertTrue(frappe.db.exists("Web Template", "Tarot Draw Card"))

	def test_every_method_the_page_names_can_be_called_by_a_visitor(self):
		for name in ("view", "draw", "interpret"):
			function = getattr(tarot, name)
			self.assertIn(function, frappe.whitelisted, name)
			self.assertIn(function, frappe.guest_methods, name)

	def test_the_free_reports_row_gives_the_tarot_its_way_in(self):
		(soon,) = [r for r in vocabulary.vocabulary()["reports_soon"] if r["title"] == "Tarot reading"]
		self.assertEqual(soon["link"], "/services/tarot")
