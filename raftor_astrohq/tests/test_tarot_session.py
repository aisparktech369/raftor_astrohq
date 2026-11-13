"""A tarot session in a chat (tarot_session.py and the three tools of assistant_tools/tarot.py): the page's draw, one card at a time, for a guide to conduct."""
import json
from unittest.mock import patch

import frappe

from raftor_astrohq import tarot_deck as deck
from raftor_astrohq import tarot_session as session
from raftor_astrohq.tests.helpers import AstroTestCase, make_user


_PACE = session.PACE_SECONDS


def setUpModule():
	session.PACE_SECONDS = 0  # the tests deal card after card at once; the pace has its own test


def tearDownModule():
	session.PACE_SECONDS = _PACE


def fan(*ids):
	"""A face-down deck in a known order (all upright), for a test that needs to know which card comes."""
	rest = [c["id"] for c in deck.cards() if c["id"] not in ids]
	return [{"id": i, "r": False} for i in [*ids, *rest]]


class TestTheShuffle(AstroTestCase):
	def test_the_whole_deck_is_shuffled_once_every_card_once_and_it_is_not_always_the_same(self):
		first = deck.shuffled()
		self.assertEqual(len(first), 78)
		self.assertEqual(len({c["id"] for c in first}), 78)
		self.assertEqual({c["id"] for c in first}, {c["id"] for c in deck.cards()})
		self.assertTrue(any(c["r"] for c in first) and not all(c["r"] for c in first))  # some reversed, some upright
		self.assertNotEqual([c["id"] for c in first], [c["id"] for c in deck.shuffled()])


class TestAChatSession(AstroTestCase):
	def setUp(self):
		super().setUp()
		deck.load(force=True)
		self.user = make_user().name

	def begin(self, spread="three-card-spread", **more):
		return session.start(self.user, spread, **more)

	def test_a_second_card_is_not_turned_over_in_the_same_reply(self):
		"""One card for each reply: the person answers before the next card comes (the tool refuses a second deal a moment after the first)."""
		self.begin()
		first = session.deal(self.user)
		self.assertTrue(first.get("ok", True) and first.get("dealt"))
		self.assertIn("STOP", first["note"])
		with patch.object(session, "PACE_SECONDS", 600):
			again = session.deal(self.user)
		self.assertFalse(again.get("ok"))
		self.assertNotIn("dealt", again)
		self.assertIn("wait for their answer", again["message"])

	def test_without_a_spread_the_offered_ones_are_listed_to_choose_from_and_nothing_is_started(self):
		for given in (None, "", "celtic-cross", "nonsense"):
			answer = session.start(self.user, given)
			self.assertFalse(answer["ok"], given)
			self.assertEqual([s["key"] for s in answer["choose_a_spread"]], list(deck.OFFERED))
			for s in answer["choose_a_spread"]:
				self.assertTrue(s["title"] and s["use_for"] and s["cards"] and s["places"])
		self.assertEqual(frappe.db.count("Tarot Reading", {"user": self.user}), 0)

	def test_a_session_begins_with_the_whole_deck_face_down_and_the_places_of_the_spread(self):
		answer = self.begin(question="<b>Should I move?</b>", topic="family")
		self.assertTrue(answer["ok"] and answer["session"])
		self.assertEqual(answer["spread"], {"key": "three-card-spread", "title": "Three-Card Spread", "cards": 3})
		self.assertEqual([p["label"] for p in answer["places"]], ["Past", "Present", "Outcome"])
		self.assertEqual((answer["face_down"], answer["cards_turned_over"], answer["spread_full"]), (78, [], False))
		self.assertEqual((answer["question"], answer["topic"]), ("Should I move?", "family"))
		self.assertIn("pick", answer["note"])  # the guide is told it may let the person choose
		row = frappe.db.get_value("Tarot Reading", answer["session"], ["user", "source", "spread"], as_dict=True)
		self.assertEqual((row.user, row.source, row.spread), (self.user, "chat", "three-card-spread"))

	def test_a_visitor_who_is_not_signed_in_gets_no_session(self):
		for nobody in (None, "", "Guest"):
			self.assertFalse(session.start(nobody, "one-card-draw")["ok"])
			self.assertFalse(session.deal(nobody)["ok"])
			self.assertFalse(session.state(nobody)["ok"])

	def test_the_cards_come_one_at_a_time_in_the_places_in_order_and_the_last_one_asks_for_the_reading(self):
		self.begin()
		started = session.state(self.user)
		self.assertEqual(started["places_left"], ["Past", "Present", "Outcome"])
		first = session.deal(self.user)
		self.assertEqual([first["dealt"]["place"], first["dealt"]["where"]], [1, "Past"])
		self.assertEqual(first["places_left"], ["Present", "Outcome"])
		self.assertFalse(first["spread_full"])
		self.assertNotIn("reading_guide", first)
		second = session.deal(self.user)
		self.assertEqual(second["dealt"]["where"], "Present")
		third = session.deal(self.user)
		self.assertEqual(third["dealt"]["where"], "Outcome")
		self.assertTrue(third["spread_full"])
		self.assertEqual(third["places_left"], [])
		self.assertIn("reading", third["note"])
		self.assertTrue(third["reading_guide"]["how_to_read_this_spread"] and third["reading_guide"]["practice_notes"])
		self.assertEqual(len({c["id"] for c in third["cards_turned_over"]}), 3)  # three different cards
		self.assertEqual(third["face_down"], 75)

	def test_what_is_given_of_a_card_is_the_academys_words_with_its_place_and_orientation(self):
		self.begin("one-card-draw")
		dealt = session.deal(self.user)["dealt"]
		card = deck.card(dealt["id"])
		self.assertEqual(dealt["card"], card["name"])
		self.assertEqual(dealt["what_it_means"], card["headline"])
		self.assertEqual(dealt["what_it_says"], card["reversed"] if dealt["orientation"] == "Reversed" else card["upright"])
		self.assertEqual(dealt["also_said"], card["extra"])
		self.assertEqual((dealt["picture"], dealt["link"]), (card["picture"], card["link"]))
		self.assertEqual(dealt["image"], deck.image(dealt["id"]))  # the card's picture, from the same address as on the page and in the Academy ("" while the factory has none)

	def test_the_person_may_choose_the_card_by_a_number_among_those_still_face_down(self):
		with patch.object(deck, "shuffled", return_value=fan("19-sun", "18-moon", "17-star", "wands-king")):
			self.begin("three-card-spread")
		self.assertEqual(session.deal(self.user, pick=3)["dealt"]["id"], "17-star")  # the third of the face-down cards
		self.assertEqual(session.deal(self.user, pick="1")["dealt"]["id"], "19-sun")  # a number as text is fine too
		after = session.deal(self.user)  # no pick: the top card of what is left
		self.assertEqual(after["dealt"]["id"], "18-moon")
		self.assertEqual(after["face_down"], 75)

	def test_a_number_outside_the_cards_face_down_is_refused_and_nothing_is_dealt(self):
		self.begin("one-card-draw")
		for bad in (0, 79, -3, "x", 1.5 * 100):
			answer = session.deal(self.user, pick=bad)
			self.assertFalse(answer["ok"], bad)
			self.assertEqual(answer["face_down"], 78)
		self.assertEqual(session.state(self.user)["cards_turned_over"], [])
		self.assertTrue(session.deal(self.user, pick=78)["ok"])  # the last of them is a good pick

	def test_a_full_spread_deals_no_more_but_may_take_up_to_two_clarifiers(self):
		self.begin("yes-or-no")
		self.assertTrue(session.deal(self.user)["spread_full"])
		again = session.deal(self.user)
		self.assertFalse(again["ok"])
		self.assertTrue(again["spread_full"] and again["reading_guide"])  # it tells the guide to give the reading
		first = session.deal(self.user, clarifier=True)
		self.assertTrue(first["ok"])
		self.assertEqual((first["dealt"]["where"], first["clarifiers_used"], first["clarifiers_left"]), ("Clarifier", 1, 1))
		second = session.deal(self.user, clarifier=True)
		self.assertEqual((second["dealt"]["where"], second["clarifiers_left"]), ("Clarifier", 0))
		self.assertFalse(session.deal(self.user, clarifier=True)["ok"])
		self.assertEqual(len(session.state(self.user)["cards_turned_over"]), 3)  # the answer card and the two clarifiers

	def test_a_clarifier_waits_until_the_spread_is_full(self):
		self.begin("three-card-spread")
		session.deal(self.user)
		self.assertFalse(session.deal(self.user, clarifier=True)["ok"])

	def test_the_guide_can_come_back_to_the_same_cards_in_a_later_turn(self):
		self.begin("one-card-draw", question="Work?")
		dealt = session.deal(self.user)["dealt"]
		later = session.state(self.user)
		self.assertTrue(later["spread_full"])
		self.assertEqual(later["question"], "Work?")
		self.assertEqual([c["id"] for c in later["cards_turned_over"]], [dealt["id"]])
		self.assertEqual(session.state(self.user, later["session"])["session"], later["session"])
		self.assertFalse(session.state(self.user, "no-such-session")["ok"])

	def test_with_no_session_named_the_latest_is_meant_and_a_new_one_starts_a_new_route(self):
		old = self.begin("one-card-draw")["session"]
		session.deal(self.user)
		newer = self.begin("five-card-spread")["session"]
		self.assertNotEqual(old, newer)
		self.assertEqual(session.state(self.user)["session"], newer)
		self.assertEqual(session.deal(self.user)["dealt"]["where"], "Present")  # the five-card spread begins with the centre

	def test_a_session_of_another_person_cannot_be_opened_or_dealt_from(self):
		mine = self.begin("three-card-spread")["session"]
		someone = make_user().name
		self.assertFalse(session.state(someone, mine)["ok"])
		self.assertFalse(session.deal(someone, session=mine)["ok"])
		self.assertEqual(frappe.db.get_value("Tarot Reading", mine, "cards"), "[]")  # nothing was turned over for them

	def test_a_session_older_than_a_day_is_not_picked_up(self):
		token = self.begin("one-card-draw")["session"]
		frappe.db.set_value("Tarot Reading", token, "creation", "2020-01-01 00:00:00", update_modified=False)
		self.assertFalse(session.state(self.user)["ok"])

	def test_when_the_deck_is_not_in_the_knowledge_base_nothing_is_started(self):
		with patch.object(deck, "shuffled", return_value=[]):
			self.assertFalse(session.start(self.user, "three-card-spread")["ok"])

	def test_the_face_down_deck_is_kept_on_the_record_and_never_given_to_the_guide(self):
		answer = self.begin("three-card-spread")
		self.assertEqual(len(json.loads(frappe.db.get_value("Tarot Reading", answer["session"], "fan"))), 78)
		self.assertNotIn("fan", json.dumps(answer))
		dealt = session.deal(self.user)
		self.assertEqual([k for k in dealt if "fan" in k], [])


class TestTheTools(AstroTestCase):
	def setUp(self):
		super().setUp()
		try:
			from raftor_astrohq.assistant_tools import tarot
		except ImportError:
			self.skipTest("FAC is not installed on this site")
		self.tools = tarot
		deck.load(force=True)
		self.user = make_user().name

	def test_the_three_tools_are_named_for_a_guide_and_registered(self):
		names = {cls().name for cls in (self.tools.StartTarotSession, self.tools.DealTarotCard, self.tools.GetTarotSession)}
		self.assertEqual(names, {"start_tarot_session", "deal_tarot_card", "get_tarot_session"})
		registered = frappe.get_hooks("assistant_tools", app_name="raftor_astrohq")
		for cls in ("StartTarotSession", "DealTarotCard", "GetTarotSession"):
			self.assertIn(f"raftor_astrohq.assistant_tools.tarot.{cls}", registered)

	def test_the_person_is_set_by_the_system_and_the_model_is_told_to_leave_it_out(self):
		for cls in (self.tools.StartTarotSession, self.tools.DealTarotCard, self.tools.GetTarotSession):
			tool = cls()
			self.assertIn("Leave it out", tool.inputSchema["properties"]["user"]["description"])
			self.assertNotIn("required", tool.inputSchema)

	def test_the_offered_spreads_are_the_ones_the_tool_lists_as_choices(self):
		spreads = self.tools.StartTarotSession().inputSchema["properties"]["spread"]["enum"]
		self.assertEqual(spreads, list(deck.OFFERED))

	def test_a_session_runs_through_the_tools_from_start_to_the_reading_and_back(self):
		start, deal, get = self.tools.StartTarotSession(), self.tools.DealTarotCard(), self.tools.GetTarotSession()
		self.assertIn("choose_a_spread", start.execute({"user": self.user}))
		begun = start.execute({"user": self.user, "spread": "three-card-spread", "question": "A choice at work"})
		self.assertTrue(begun["ok"])
		for place in ("Past", "Present", "Outcome"):
			self.assertEqual(deal.execute({"user": self.user})["dealt"]["where"], place)
		full = get.execute({"user": self.user})
		self.assertTrue(full["spread_full"] and full["reading_guide"])
		self.assertEqual(len(full["cards_turned_over"]), 3)
		self.assertFalse(deal.execute({"user": self.user})["ok"])  # nothing more to deal: give the reading
		self.assertTrue(deal.execute({"user": self.user, "clarifier": True})["ok"])  # unless something is unclear
		self.assertFalse(deal.execute({"user": ""})["ok"])  # nobody signed in


SECTIONS = ["opening", "choosing the spread", "choosing the cards", "turning over the cards", "giving the reading", "going deeper", "closing", "care"]


class TestTheCeremony(AstroTestCase):
	"""The ceremony a guide conducts is the Academy's methodology ("Conducting a Session"): the tools hand it over, so a change to the article changes the guide, with nothing worded in the guide or in code."""

	def setUp(self):
		super().setUp()
		deck.load(force=True)
		self.user = make_user().name

	def test_the_methodology_is_read_from_the_academy_section_by_section_in_the_order_it_is_written(self):
		self.assertEqual(list(deck.conduct()), SECTIONS)
		self.assertEqual(list(deck.conduct("care", "opening")), ["opening", "care"])  # in the article's order, only those asked for
		self.assertNotIn("related reading", deck.conduct())
		for name, text in deck.conduct().items():
			self.assertTrue(text.strip(), name)

	def test_it_says_when_the_person_chooses_their_cards_and_when_they_are_dealt_and_that_a_card_is_never_picked_by_the_guide(self):
		choosing = deck.conduct("choosing the cards")["choosing the cards"].lower()
		self.assertIn("let the person choose", choosing)
		self.assertIn("deal the cards for them", choosing)
		self.assertIn("never name a card", choosing)

	def test_a_session_begins_with_the_whole_methodology_and_a_note_to_follow_it(self):
		answer = session.start(self.user, "three-card-spread", "Work?")
		self.assertEqual(answer["how_to_conduct"], deck.conduct())
		self.assertIn("how_to_conduct", answer["note"])

	def test_each_card_brings_the_part_of_the_methodology_needed_next_then_the_reading_the_going_deeper_and_the_close(self):
		session.start(self.user, "three-card-spread")
		while_dealing = session.deal(self.user)
		self.assertEqual(list(while_dealing["how_to_conduct"]), ["choosing the cards", "turning over the cards", "care"])
		session.deal(self.user)
		full = session.deal(self.user)
		self.assertEqual(list(full["how_to_conduct"]), ["giving the reading", "going deeper", "closing", "care"])
		self.assertEqual(list(session.state(self.user)["how_to_conduct"]), ["giving the reading", "going deeper", "closing", "care"])  # coming back to a full spread
		self.assertEqual(list(session.deal(self.user, clarifier=True)["how_to_conduct"]), ["giving the reading", "going deeper", "closing", "care"])

	def test_the_page_writer_is_given_the_care_the_academy_asks_for_too(self):
		from raftor_astrohq import tarot

		system = tarot._system(deck.spread("three-card-spread"))
		self.assertIn(deck.conduct("care")["care"][:50], system)
