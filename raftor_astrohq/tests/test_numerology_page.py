"""The numerology page (numerology_page.py): a name and a date of birth for anyone, the numbers with their working, and the reading of the numbers together for someone signed in."""
import datetime
import unittest
from unittest.mock import patch

import frappe

from raftor_astrohq import astrology, numerology_page, page_definitions, vocabulary
from raftor_astrohq.tests.helpers import AstroTestCase, make_user

OK = {"name": "Asha Rao", "birth_date": "1990-05-14"}


class TestTheChecks(AstroTestCase):
	def test_what_is_wrong_is_said_by_field(self):
		today = datetime.date.today()
		for values, field in (({"name": "", "birth_date": "1990-05-14"}, "name"), ({"name": "A", "birth_date": "1990-05-14"}, "name"), ({"name": "आशा", "birth_date": "1990-05-14"}, "name"),
							  ({"name": "x" * 200, "birth_date": "1990-05-14"}, "name"), ({"name": "Asha", "birth_date": ""}, "birth_date"), ({"name": "Asha", "birth_date": "not a date"}, "birth_date"),
							  ({"name": "Asha", "birth_date": (today + datetime.timedelta(days=3)).isoformat()}, "birth_date"), ({"name": "Asha", "birth_date": "1500-01-01"}, "birth_date")):
			with self.subTest(values):
				frappe.set_user("Guest")
				answer = numerology_page.reveal(**values)
				self.assertFalse(answer["ok"])
				self.assertIn(field, answer["errors"])
		frappe.set_user("Administrator")

	def test_both_at_once_and_spaces_are_tidied(self):
		frappe.set_user("Guest")
		both = numerology_page.reveal("", "")
		self.assertEqual(set(both["errors"]), {"name", "birth_date"})
		self.assertEqual(numerology_page._check("  Asha   Rao ", "1990-05-14")[0], "Asha Rao")
		frappe.set_user("Administrator")


class TestThePage(AstroTestCase):
	def setUp(self):
		super().setUp()
		try:
			frappe.set_user("Guest")
			self.asked = numerology_page.reveal(**OK)
		except astrology.AstrologyUnavailable:
			self.skipTest("the astrology service is not running")
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_anyone_gets_the_numbers_their_working_the_topics_and_a_locked_reading_with_the_way_to_sign_in(self):
		self.assertTrue(self.asked["ok"])
		reading = self.asked["reading"]
		self.assertEqual([n["key"] for n in reading["numbers"]][:2], ["birth", "name"])
		self.assertEqual(len(reading["topics"]), 6)
		state = reading["interpretation"]
		self.assertEqual(state["state"], "locked")
		self.assertTrue(state["login_url"].startswith("/login?redirect-to="))
		self.assertIn(reading["token"], state["login_url"])  # they come back to the same numbers
		self.assertTrue(self.asked["words"]["title"] and len(self.asked["words"]["preview"]) == 4)

	def test_nothing_is_written_for_someone_who_has_not_signed_in(self):
		token = self.asked["reading"]["token"]
		frappe.set_user("Guest")
		with patch.object(numerology_page, "_write") as written:
			self.assertEqual(numerology_page.interpret(token)["interpretation"]["state"], "locked")
		written.assert_not_called()

	def test_coming_back_with_the_token_shows_the_same_numbers(self):
		token = self.asked["reading"]["token"]
		frappe.set_user("Guest")
		again = numerology_page.view(token)["reading"]
		self.assertEqual([n["value"] for n in again["numbers"]], [n["value"] for n in self.asked["reading"]["numbers"]])
		self.assertIsNone(numerology_page.view("nothing-like-it")["reading"])
		self.assertIsNone(numerology_page.view(None)["reading"])

	def test_someone_signed_in_has_the_reading_written_once_and_kept(self):
		token = self.asked["reading"]["token"]
		user = make_user().name
		frappe.set_user(user)
		self.assertEqual(numerology_page.view(token)["reading"]["interpretation"]["state"], "pending")
		with patch.object(numerology_page, "_write", return_value=("A calm reading.", "a-model")) as written:
			first = numerology_page.interpret(token)
			second = numerology_page.interpret(token)
		self.assertEqual(first["interpretation"], {"state": "ready", "text": "A calm reading."})
		self.assertEqual(second["interpretation"], first["interpretation"])
		self.assertEqual(written.call_count, 1)
		row = frappe.db.get_value("Numerology Reading", token, ["user", "person_name", "birth_date", "model"], as_dict=True)
		self.assertEqual((row.user, row.person_name, str(row.birth_date), row.model), (user, "Asha Rao", "1990-05-14", "a-model"))
		self.assertEqual(numerology_page.view(token)["reading"]["interpretation"], {"state": "ready", "text": "A calm reading."})

	def test_the_writer_is_asked_with_the_numbers_only(self):
		token = self.asked["reading"]["token"]
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
		with patch("raftor_astrohq.hub.rashifal.settings", return_value=settings), patch("raftor_astrohq.hub.requests.post", fake):
			text = numerology_page.interpret(token)["interpretation"]["text"]
		prompt = frappe.parse_json(sent["payload"]["prompt"])
		self.assertEqual(list(prompt), ["numbers"])
		self.assertEqual(len(prompt["numbers"]), 4)
		self.assertEqual(text, "Words here")  # the markup of a model is not kept

	def test_a_writer_that_is_away_says_so_and_nothing_is_kept(self):
		token = self.asked["reading"]["token"]
		frappe.set_user(make_user().name)
		with patch.object(numerology_page, "_write", side_effect=numerology_page.ReadingUnavailable):
			self.assertEqual(numerology_page.interpret(token)["interpretation"], {"state": "later"})
		self.assertFalse(frappe.db.exists("Numerology Reading", token))

	def test_another_persons_reading_is_not_opened_by_its_address_and_a_draw_nobody_made_is_gone(self):
		token = self.asked["reading"]["token"]
		frappe.set_user(make_user().name)
		with patch.object(numerology_page, "_write", return_value=("Mine.", "m")):
			numerology_page.interpret(token)
		frappe.set_user(make_user().name)
		self.assertFalse(numerology_page.interpret(token)["ok"])
		self.assertFalse(numerology_page.interpret("x" * 30)["ok"])


class TestWhereItIsAsked(AstroTestCase):
	def test_the_page_is_open_to_anyone_and_uses_the_card_with_the_apps_methods(self):
		page = next(p for p in page_definitions.definitions() if p["route"] == "services/numerology")
		self.assertFalse(page["login_required"])
		card = page["sections"][0]["cards"][0]
		self.assertEqual(card["type"], "Number Reveal Card")
		self.assertEqual(card["values"], {"view": "raftor_astrohq.numerology_page.view", "reveal": "raftor_astrohq.numerology_page.reveal", "interpret": "raftor_astrohq.numerology_page.interpret", "url_args": "reading"})
		self.assertTrue(frappe.db.exists("Web Template", "Number Reveal Card"))

	def test_every_method_the_page_names_can_be_called_by_a_visitor(self):
		for name in ("view", "reveal", "interpret"):
			function = getattr(numerology_page, name)
			self.assertIn(function, frappe.whitelisted, name)
			self.assertIn(function, frappe.guest_methods, name)

	def test_the_free_reports_row_opens_it_and_consulting_goes_to_the_numerologists(self):
		(soon,) = [r for r in vocabulary.vocabulary()["reports_soon"] if r["title"] == "Numerology"]
		self.assertEqual(soon["link"], "/services/numerology")
		self.assertEqual(numerology_page._words()["consult"]["url"], "/consult?persona=Numerologist")
