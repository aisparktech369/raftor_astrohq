"""The tarot page (tarot.py): a spread of cards for anyone from the whole deck, their meanings (the Academy's: tarot_deck.py reads them from the knowledge base), and the reading of the cards together for someone signed in."""
import json
import os
from unittest.mock import patch

import frappe

from raftor_astrohq import page_definitions, tarot, tarot_deck as deck, vocabulary
from raftor_astrohq.tests.helpers import AstroTestCase, make_user


class TestTheDeck(AstroTestCase):
	def setUp(self):
		super().setUp()
		deck.load(force=True)

	def test_the_deck_is_the_whole_knowledge_base_seventy_eight_cards_each_with_its_words(self):
		cards = deck.cards()
		self.assertEqual(len(cards), 78)
		self.assertEqual(len({c["id"] for c in cards}), 78)
		self.assertEqual(len({c["name"] for c in cards}), 78)
		self.assertEqual([c["arcana"] for c in cards].count("major"), 22)
		for card in cards:
			self.assertTrue(card["picture"] and card["headline"] and card["upright"] and card["reversed"] and card["numeral"], card["id"])
			self.assertTrue(card["link"].startswith("/blog/tarot/"), card["id"])  # every card has its page in the Academy
			for phrase in ("will happen", "you will die"):  # reflection, never a forecast
				self.assertNotIn(phrase, (card["upright"] + card["reversed"]).lower(), card["id"])

	def test_the_order_is_fixed_the_major_cards_first_by_number_then_the_suits_ace_to_king(self):
		cards = deck.cards()
		self.assertEqual([c["id"] for c in cards[:3]], ["00-fool", "01-magician", "02-high-priestess"])  # (a draw kept before spreads holds a place in this order)
		self.assertEqual(cards[21]["id"], "21-world")
		self.assertEqual([c["id"] for c in cards[22:24]], ["wands-ace", "wands-two"])
		self.assertEqual(cards[-1]["id"], "pentacles-king")

	def test_every_card_has_a_symbol_from_the_sites_icon_set_and_the_major_cards_each_their_own(self):
		from raftor_websitehq.website_hq import icons

		majors = [c for c in deck.cards() if c["arcana"] == "major"]
		self.assertEqual(len({c["icon"] for c in majors}), 22)
		for card in deck.cards():
			self.assertTrue(str(icons.svg(card["icon"])).startswith("<svg"), card["id"])
		self.assertEqual({c["icon"] for c in deck.cards() if c["suit"] == "swords"}, {"sword"})

	def test_the_minor_cards_carry_their_extra_meanings_and_the_major_ones_do_not(self):
		for card in deck.cards():
			self.assertEqual(bool(card["extra"]), card["arcana"] == "minor", card["id"])


class TestTheSpreads(AstroTestCase):
	def test_the_page_offers_the_four_simple_spreads_with_the_places_the_academy_gives_them(self):
		offered = deck.spreads()
		self.assertEqual([s["key"] for s in offered], list(deck.OFFERED))
		self.assertEqual([len(s["positions"]) for s in offered], [1, 3, 1, 5])
		for spread in offered:
			self.assertTrue(spread["title"] and spread["intro"] and spread["read"], spread["key"])
			self.assertTrue(all(p["label"] and p["hint"] for p in spread["positions"]), spread["key"])
		self.assertEqual([p["label"] for p in deck.spread("three-card-spread")["positions"]], ["Past", "Present", "Outcome"])

	def test_a_spread_that_is_not_offered_is_the_default_one(self):
		for odd in (None, "", "celtic-cross", "nonsense", "<b>x</b>"):
			self.assertEqual(deck.spread(odd)["key"], deck.DEFAULT_SPREAD, odd)


class TestTheDraw(AstroTestCase):
	def setUp(self):
		super().setUp()
		deck.load(force=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def guest_draw(self, question=None, spread=None):
		frappe.set_user("Guest")
		return tarot.draw(question, None, spread)

	def test_three_different_cards_in_their_places_each_with_a_meaning(self):
		reading = self.guest_draw("Should I change my work?")["reading"]
		self.assertEqual([c["label"] for c in reading["cards"]], ["Past", "Present", "Outcome"])
		self.assertEqual(reading["spread"], {"key": "three-card-spread", "label": "Three-Card Spread", "count": 3})
		self.assertEqual(len({c["name"] for c in reading["cards"]}), 3)
		for card in reading["cards"]:
			self.assertTrue(card["meaning"] and card["keywords"] and card["numeral"] and card["hint"])
			self.assertIn(card["orientation"], ("Upright", "Reversed"))
		self.assertEqual(reading["question"], "Should I change my work?")

	def test_each_spread_draws_its_own_number_of_different_cards(self):
		for key, count in (("one-card-draw", 1), ("three-card-spread", 3), ("yes-or-no", 1), ("five-card-spread", 5)):
			reading = self.guest_draw(None, key)["reading"]
			self.assertEqual(reading["spread"]["key"], key)
			self.assertEqual(len(reading["cards"]), count, key)
			self.assertEqual(len({c["id"] for c in reading["cards"]}), count, key)
		self.assertEqual(self.guest_draw(None, "something-else")["reading"]["spread"]["key"], deck.DEFAULT_SPREAD)

	def test_the_cards_come_from_the_whole_deck_the_minor_ones_too(self):
		seen = {c["arcana"] for _ in range(40) for c in self.guest_draw(None, "five-card-spread")["reading"]["cards"]}
		self.assertEqual(seen, {"major", "minor"})

	def test_the_words_come_with_it_and_a_question_is_cleaned_and_kept_short(self):
		answer = self.guest_draw("<b>Hello</b> " + "x" * 500)
		words = answer["words"]
		self.assertTrue(words["title"] and words["spread_label"] and words["learn_more"])
		self.assertEqual([s["key"] for s in words["spreads"]], list(deck.OFFERED))
		self.assertEqual(words["default_spread"], "three-card-spread")
		self.assertEqual([p["label"] for p in words["spreads"][3]["positions"]], ["Present", "Past", "Hope", "Obstacle", "Outcome"])
		self.assertNotIn("<b>", answer["reading"]["question"])
		self.assertLessEqual(len(answer["reading"]["question"]), tarot.QUESTION_LENGTH)

	def test_the_machine_has_one_central_button_and_a_way_to_consult_after_the_reading(self):
		words = self.guest_draw()["words"]
		self.assertTrue(words["shuffle"] and words["stop"] and words["press"])
		self.assertEqual(len(words["ornament"].split()), 12)
		self.assertEqual(words["consult"]["url"], "/consult?persona=Tarot+reader")  # the tarot readers, AI and human
		self.assertTrue(words["consult"]["label"] and words["consult"]["text"])

	def test_a_picture_named_by_the_cards_id_is_used_for_it_and_for_the_back_and_without_one_the_card_is_drawn(self):
		with patch("raftor_agentshq.media.url", return_value=""):  # nothing delivered by the factory: an earlier version's folder is the fallback
			self._the_folder_fallback()

	def _the_folder_fallback(self):
		import tempfile

		self.assertEqual(deck.image("99-no-such-card"), "")
		with tempfile.TemporaryDirectory() as folder:  # a stand-in for the app's public/tarot: the test never writes into the real one (it holds the real pictures)
			for name in ("00-fool.webp", "wands-king.jpg", "back.png"):
				open(os.path.join(folder, name), "wb").write(b"x")
			real = frappe.get_app_path
			with patch.object(deck.frappe, "get_app_path", lambda app, *parts: os.path.join(folder, parts[-1]) if parts[-2:-1] == ("tarot",) else real(app, *parts)):
				spread = deck.spread("three-card-spread")
				self.assertEqual(deck.image("00-fool"), "/assets/raftor_astrohq/tarot/00-fool.webp")
				self.assertEqual(self.guest_draw()["words"]["back_image"], "/assets/raftor_astrohq/tarot/back.png")
				self.assertEqual(tarot._card({"id": "00-fool", "r": False}, spread, 0)["image"], "/assets/raftor_astrohq/tarot/00-fool.webp")
				self.assertEqual(tarot._card({"id": "wands-king", "r": True}, spread, 1)["image"], "/assets/raftor_astrohq/tarot/wands-king.jpg")  # a minor card the same way
				self.assertEqual(tarot._card({"id": "01-magician", "r": False}, spread, 2)["image"], "")  # the Magician has none yet

	def test_a_visitor_gets_the_cards_and_a_locked_reading_with_the_way_to_sign_in(self):
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

	def write_with(self, token, sent):
		"""Has the reading of this draw written by a stand-in hub that records what it was sent."""
		frappe.set_user(make_user().name)

		def fake(url, json=None, headers=None, timeout=None):
			sent.update(json)

			class Answer:
				status_code = 200

				def json(self_inner):
					return {"data": {"content": "**Words** here", "model": "m"}}
			return Answer()

		settings = frappe._dict(address="http://hub", site="", key="k", api_name="text-to-text", timeout=5)
		with patch("raftor_astrohq.hub.rashifal.settings", return_value=settings), patch("raftor_astrohq.hub.requests.post", fake):
			return tarot.interpret(token)["interpretation"]["text"]

	def test_the_topic_and_the_spread_are_told_to_the_writer_and_kept_with_the_reading(self):
		frappe.set_user("Guest")
		token = tarot.draw("", "money", "five-card-spread")["reading"]["token"]
		sent = {}
		self.write_with(token, sent)
		facts = frappe.parse_json(sent["payload"]["prompt"])
		self.assertEqual((facts["topic"], facts["spread"], len(facts["cards"])), ("Money", "Five-Card Spread", 5))
		self.assertEqual(frappe.db.get_value("Tarot Reading", token, ["topic", "spread"], as_dict=True), {"topic": "money", "spread": "five-card-spread"})

	def test_the_writer_follows_the_academys_guidance_for_the_spread_and_for_giving_a_reading(self):
		token = self.guest_draw("What now?", "yes-or-no")["reading"]["token"]
		sent = {}
		self.write_with(token, sent)
		system = sent["payload"]["system"]
		self.assertIn("1 card", system)
		self.assertIn(deck.spread("yes-or-no")["read"][:60], system)  # the Academy's words on how to read this spread
		self.assertIn("reflection", system.lower())
		self.assertIn("qualified professional", system)

	def test_the_reading_asked_to_the_writer_holds_only_the_cards_and_the_question(self):
		token = self.guest_draw("What now?")["reading"]["token"]
		sent = {}
		text = self.write_with(token, sent)
		prompt = frappe.parse_json(sent["payload"]["prompt"])
		self.assertEqual(sorted(prompt), ["cards", "question", "spread", "topic"])
		self.assertEqual(len(prompt["cards"]), 3)
		self.assertEqual(sorted(prompt["cards"][0]), ["also_said", "card", "orientation", "position", "said_of_it", "what_it_means"])
		self.assertEqual(text, "Words here")  # the markup of a model is not kept

	def test_coming_back_with_the_token_shows_the_same_cards(self):
		first = self.guest_draw(None, "five-card-spread")["reading"]
		again = tarot.view(first["token"])["reading"]
		self.assertEqual([c["name"] for c in again["cards"]], [c["name"] for c in first["cards"]])
		self.assertEqual(again["spread"], first["spread"])
		self.assertIsNone(tarot.view("nothing-like-it")["reading"])
		self.assertIsNone(tarot.view(None)["reading"])

	def test_a_draw_kept_before_the_deck_grew_still_shows_its_three_major_cards(self):
		tarot._keep("old-draw-token", {"question": "", "topic": "", "cards": [{"i": 0, "r": False}, {"i": 1, "r": True}, {"i": 21, "r": False}], "user": None, "interpretation": "", "model": ""})
		frappe.set_user("Guest")
		reading = tarot.view("old-draw-token")["reading"]
		self.assertEqual([c["name"] for c in reading["cards"]], ["The Fool", "The Magician", "The World"])
		self.assertEqual(reading["spread"]["key"], "three-card-spread")
		self.assertEqual([c["reversed"] for c in reading["cards"]], [False, True, False])

	def test_a_reading_saved_before_spreads_has_no_spread_and_is_the_three_card_one(self):
		frappe.get_doc({"doctype": "Tarot Reading", "token": "saved-before-spreads-1", "user": "Administrator", "question": "", "topic": "", "cards": json.dumps([{"i": 2, "r": False}, {"i": 3, "r": False}, {"i": 4, "r": True}]),
						"interpretation": "Old words.", "model": "m"}).insert(ignore_permissions=True)
		frappe.set_user("Administrator")
		reading = tarot.view("saved-before-spreads-1")["reading"]
		self.assertEqual([c["name"] for c in reading["cards"]], ["The High Priestess", "The Empress", "The Emperor"])
		self.assertEqual(reading["spread"]["key"], "three-card-spread")
		self.assertEqual(reading["interpretation"], {"state": "ready", "text": "Old words."})

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

	def test_with_no_deck_in_the_knowledge_base_nothing_is_drawn_and_nothing_breaks(self):
		frappe.set_user("Guest")
		with patch.object(deck, "cards", return_value=[]):
			self.assertIsNone(tarot.draw("What now?")["reading"])


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
