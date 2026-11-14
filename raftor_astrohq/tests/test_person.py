"""What the guides remember about a person and the people in their profiles: notes tied to profiles, a summary per person, family added from the chat, and the guide's tool."""
import frappe

from raftor_astrohq import person, profiles
from raftor_astrohq.tests.helpers import GOOD, TABLE, AstroTestCase, make_user


def _user(**values):
	"""A person on the Plus plan, which keeps family (these tests are about what the guides remember, not about what a plan holds: see test_plan_rules)."""
	from raftor_servicehq import plans

	user = make_user()
	user.append(TABLE, GOOD)
	user.save(ignore_permissions=True)
	plans.assign(user.name, "Plus")
	return user.name


def _rows(user):
	return frappe.get_all("Astro Birth Profile", filters={"parent": user, "parentfield": TABLE}, fields=["name", "full_name", "relationship", "date_of_birth", "from_chat", "permission_given", "summary", "place_of_birth"], order_by="idx")


class TestPersonNotes(AstroTestCase):
	def test_a_note_is_dated_tied_to_the_profile_and_summarised_on_it(self):
		user = _user()
		done = person.write(user, {"notes": [{"about": "You", "kind": "worry", "point": "Worried about money."}]}, "Pandit ji", "s1")
		self.assertEqual((done["added"], done["replaced"]), (1, 0))
		note = frappe.get_all("Profile Note", filters={"user": user}, fields=["profile", "about", "guide", "noted_on", "is_current"])[0]
		self.assertEqual((note.about, note.guide, note.is_current), ("You", "Pandit ji", 1))
		self.assertEqual(note.profile, _rows(user)[0].name)
		self.assertEqual(_rows(user)[0].summary, "Worried about money")

	def test_a_dropped_note_is_kept_as_replaced_and_the_summary_follows_the_current_ones(self):
		user = _user()
		person.write(user, {"notes": [{"point": "Wants a Yellow Sapphire"}]}, "Pandit ji", "s")
		done = person.write(user, {"notes": [{"point": "Declined the Yellow Sapphire as too costly"}]}, "Pandit ji", "s")
		self.assertEqual((done["added"], done["replaced"]), (1, 1))
		self.assertEqual(frappe.db.count("Profile Note", {"user": user, "is_current": 0}), 1)
		self.assertEqual(_rows(user)[0].summary, "Declined the Yellow Sapphire as too costly")
		self.assertEqual(person.write(user, {"notes": [{"point": "Declined the Yellow Sapphire as too costly"}]}, "x", "s")["added"], 0)

	def test_someone_spoken_of_gets_a_profile_marked_from_chat_with_only_what_was_said(self):
		user = _user()
		done = person.write(user, {"notes": [{"about": "Rhenna (daughter)", "kind": "worry", "point": "Stressed about exams"}],
								   "people": [{"name": "Rhenna", "relationship": "daughter", "date_of_birth": "2015-03-03", "place_of_birth": "Pune"}]}, "Pandit ji", "s")
		self.assertEqual(done["people_added"], 1)
		rhenna = next(r for r in _rows(user) if r.full_name == "Rhenna")
		self.assertEqual((rhenna.relationship, str(rhenna.date_of_birth), rhenna.place_of_birth, rhenna.from_chat, rhenna.permission_given), ("Child", "2015-03-03", "Pune", 1, 1))
		self.assertEqual(rhenna.summary, "Stressed about exams")
		self.assertEqual(len([r for r in _rows(user) if r.full_name == "Rhenna"]), 1)

	def test_a_name_alone_makes_a_profile_and_a_bare_relation_does_not(self):
		user = _user()
		person.write(user, {"notes": [{"about": "my daughter", "point": "Is shy"}, {"about": "Meera (sister)", "point": "Lives abroad"}]}, "Dream guide", "s")
		names = [r.full_name for r in _rows(user)]
		self.assertIn("Meera", names)
		self.assertEqual(len(names), 2)  # You and Meera; 'my daughter' with no name is only a note

	def test_a_profile_from_chat_does_not_break_saving_the_account_and_is_not_usable_for_reports(self):
		user = _user()
		person.write(user, {"notes": [{"about": "Tara (daughter)", "point": "Likes art"}]}, "Pandit ji", "s")
		frappe.get_doc("User", user).save(ignore_permissions=True)
		from raftor_astrohq import reports

		self.assertNotIn("Tara", [r.full_name for r in reports._usable_profiles(user)])
		self.assertFalse(profiles.row_errors(profiles.row_values(frappe.get_doc("User", user).get(TABLE)[-1])) == {})

	def test_a_profile_is_found_by_name_by_relation_and_by_me(self):
		user = _user()
		person.write(user, {"notes": [], "people": [{"name": "Rhenna", "relationship": "daughter", "date_of_birth": "2015-03-03"}]}, "g", "s")
		for who in ("Rhenna", "my daughter", "rhenna", "daughter"):
			self.assertEqual(person.member(user, who)["name"], "Rhenna", who)
		self.assertEqual(person.member(user, "me")["name"], "Asha Rao")
		self.assertFalse(person.member(user, "my uncle")["found"])

	def test_the_tool_returns_the_profile_the_summary_and_the_numerology_headline(self):
		user = _user()
		person.write(user, {"notes": [{"about": "Rhenna (daughter)", "kind": "worry", "point": "Stressed about exams"}], "people": [{"name": "Rhenna", "relationship": "daughter", "date_of_birth": "2015-03-03"}]}, "g", "s")
		out = person.member(user, "my daughter")
		self.assertEqual((out["found"], out["details_complete"], out["summary"]), (True, False, "Stressed about exams"))
		self.assertEqual(out["notes"][0]["point"], "Stressed about exams")
		if out.get("numerology"):
			self.assertEqual(out["numerology"]["birth_number"], 3)

	def test_the_card_lists_each_person_with_their_own_summary(self):
		user = _user()
		person.write(user, {"notes": [{"about": "You", "point": "Wants guidance on career"}, {"about": "Tara (daughter)", "point": "Likes art"}]}, "g", "s")
		card = person.card(user)
		self.assertIn("- You: Asha Rao", card)
		self.assertIn("What we know: Wants guidance on career", card)
		self.assertIn("Tara (child)", card)

	def test_forgetting_a_note_is_only_for_its_owner(self):
		mine, other = _user(), _user()
		person.write(mine, {"notes": [{"point": "A private thing"}]}, "g", "s")
		name = frappe.get_all("Profile Note", filters={"user": mine}, pluck="name")[0]
		self.assertFalse(person.forget(other, name))
		self.assertTrue(person.forget(mine, name))
		self.assertEqual(_rows(mine)[0].summary, "")


NUMEROLOGIST, PANDIT, DREAMER = "numerology-guide-agent@agents.astrohq.in", "pandit-ji-agent@agents.astrohq.in", "dream-guide-agent@agents.astrohq.in"
VEDIC, KP = "vedic-astrologer-guide-agent@agents.astrohq.in", "kp-astrologer-guide-agent@agents.astrohq.in"


class TestReportsFromTheChat(AstroTestCase):
	def test_a_guide_reads_only_the_reports_of_its_own_area(self):
		user = _user()
		self.assertIn("outside your area", person.read_report(user, "me", "kundli", NUMEROLOGIST)["message"])
		self.assertIn("outside your area", person.read_report(user, "me", "numerology", DREAMER)["message"])
		self.assertIn("outside your area", person.read_report(user, "me", "numerology", "someone-else@example.com")["message"])
		self.assertTrue(person.read_report(user, "me", "numerology", PANDIT)["found"])
		self.assertEqual(frappe.db.count("Free Report", {"user": user}), 1)  # only the one that was in an area was made

	def test_the_astrologer_guides_read_their_own_charts_and_match_but_not_each_others(self):
		user = _user()
		self.assertIn("outside your area", person.read_report(user, "me", "kp", VEDIC)["message"])
		self.assertIn("outside your area", person.read_report(user, "me", "kundli", KP)["message"])
		self.assertIn("outside your area", person.read_report(user, "me", "numerology", VEDIC)["message"])
		self.assertNotIn("outside your area", person.read_report(user, "me", "match", VEDIC, "Tara")["message"])
		self.assertNotIn("outside your area", person.read_report(user, "me", "match", KP, "Tara")["message"])

	def test_only_the_astrologer_guides_get_the_chart_card_when_they_open_a_person(self):
		from unittest.mock import patch

		user = _user()
		with patch("raftor_astrohq.person.chart_summary", return_value={"ascendant": "Libra"}):
			self.assertEqual(person.member(user, "me", VEDIC)["chart_cards"][0]["kind"], "chart")
			self.assertEqual(person.member(user, "me", KP)["chart_cards"][0]["kind"], "chart")
			self.assertNotIn("chart_cards", person.member(user, "me", PANDIT))
			self.assertEqual(person.member(user, "me", PANDIT)["chart"], {"ascendant": "Libra"})

	def test_a_match_needs_to_know_the_groom_and_two_different_saved_people(self):
		user = _user()
		person.write(user, {"notes": [], "people": [{"name": "Tara", "relationship": "sister", "date_of_birth": "1992-04-04", "time_of_birth": "06:30", "place_of_birth": "Delhi"}]}, "g", "s")
		self.assertIn("which of the two is the groom", person.read_report(user, "me", "match", VEDIC, "Tara")["message"])
		self.assertIn("same person twice", person.read_report(user, "Tara", "match", VEDIC, "my sister", "bride")["message"])
		self.assertIn("not among the saved profiles", person.read_report(user, "me", "match", VEDIC, "Nobody Here", "groom")["message"])
		gone = person.read_report(user, "me", "kundli", VEDIC)  # a person with only family saved is told who is saved, not that nothing is
		self.assertTrue(gone["found"] or "Tara" in gone["message"] or "profiles" in gone)

	def test_a_profile_lookup_shows_only_what_the_guides_area_allows(self):
		user = _user()
		self.assertNotIn("numerology", person.member(user, "me", DREAMER))
		self.assertNotIn("chart", person.member(user, "me", NUMEROLOGIST))
		self.assertIn("numerology", person.member(user, "me", NUMEROLOGIST))

	def test_asking_names_what_is_missing_and_never_guesses(self):
		user = _user()
		person.write(user, {"notes": [], "people": [{"name": "Rhenna", "relationship": "daughter", "date_of_birth": "2015-03-03"}]}, "g", "s")
		self.assertIn("time of birth and place of birth", person.read_report(user, "my daughter", "kundli", PANDIT)["message"])
		self.assertIn("Say which report", person.read_report(user, "me", "tarot", PANDIT)["message"])
		self.assertIn("No profile matches", person.read_report(user, "my uncle", "numerology", PANDIT)["message"])
		person.write(user, {"notes": [], "people": [{"name": "Nameless", "relationship": "other"}]}, "g", "s")
		self.assertIn("date of birth is not saved", person.read_report(user, "Nameless", "numerology", PANDIT)["message"])

	def test_a_missing_report_is_made_once_kept_as_available_and_given_as_a_summary_not_a_link(self):
		user = _user()
		first = person.read_report(user, "me", "numerology", NUMEROLOGIST)
		self.assertTrue(first["found"] and first["newly_made"])
		self.assertIn("number", first["summary"]["birth"])
		self.assertNotIn("services", first)
		self.assertIn("give no link", first["message"])
		second = person.read_report(user, "me", "numerology", NUMEROLOGIST)
		self.assertFalse(second["newly_made"])
		self.assertEqual(frappe.db.count("Free Report", {"user": user}), 1)

	def test_the_chart_headline_comes_from_the_kept_engine_answer(self):
		from unittest.mock import patch

		user = _user()
		row = frappe._dict(date_of_birth="1980-05-12", time_of_birth="10:30", place_of_birth="Mumbai", time_unknown=0)
		chart = {"lagna": {"sign": "♋︎Cancer", "lord": "Moon"},
				 "planetary_positions": [{"planet": "Su☉", "sign": "♈︎Aries", "absolute_longitude": 28.0, "nakshatra": "Bharani", "pada": 4},
										 {"planet": "Mo☾", "sign": "♓︎Pisces", "absolute_longitude": 356.0, "nakshatra": "Revathi", "pada": 3}],
				 "dasha_sequences": {"vimshottari": {"mahadasha": [{"lord": "Mo☾", "start_date": "2018-01-01", "end_date": "2099-01-01",
																	 "antardasha": [{"lord": "Ve♀", "start_date": "2018-01-01", "end_date": "2099-01-01"}]}]}}}
		with patch.object(person.report_view, "profile_numbers", lambda r: {"day": 12}), patch.object(person.answers, "get", lambda *a, **k: chart):
			out = person.chart_summary(user, row)
		self.assertEqual((out["ascendant"], out["sun_sign"], out["moon_sign"], out["moon_nakshatra"]), ("Cancer", "Aries", "Pisces", "Revathi, pada 3"))
		self.assertTrue(out["running_mahadasha"].startswith("Moon until") and out["running_antardasha"].startswith("Venus until"))
		self.assertIsNone(person.chart_summary(user, frappe._dict(date_of_birth="1980-05-12", time_of_birth="", place_of_birth="Mumbai", time_unknown=1)))


class TestWhatEachGuideSees(AstroTestCase):
	def _seeded(self):
		user = _user()
		person.write(user, {"notes": [{"about": "Rhenna (daughter)", "kind": "worry", "point": "Stressed about exams"}, {"about": "You", "kind": "dream", "point": "Dreams of falling from a height"},
									  {"about": "You", "kind": "shown", "point": "Birth number 5"}], "people": [{"name": "Rhenna", "relationship": "daughter", "date_of_birth": "2015-03-03"}]}, "g", "s")
		return user

	def test_the_dream_guide_sees_only_the_dream_notes_and_who_is_in_the_family(self):
		user = self._seeded()
		seen = person.read(user, "dream_guide")
		self.assertEqual([n["point"] for n in seen["notes"]], ["Dreams of falling from a height"])
		self.assertIn("Rhenna (child): Rhenna", seen["card"])
		for hidden in ("2015", "born", "Saved report", "Bought", "Stressed", "What we know"):
			self.assertNotIn(hidden, seen["card"])

	def test_the_other_guides_see_everything_as_before(self):
		user = self._seeded()
		for guide in ("pandit_ji", "numerologist"):
			seen = person.read(user, guide)
			self.assertEqual(len(seen["notes"]), 3)
			self.assertIn("born 3 Mar 2015", seen["card"])

	def test_the_dream_guides_profile_lookup_gives_a_name_and_dream_notes_only(self):
		user = self._seeded()
		out = person.member(user, "me", DREAMER)
		self.assertEqual(out["name"], "Asha Rao")
		self.assertEqual([n["point"] for n in out["notes"]], ["Dreams of falling from a height"])
		self.assertNotIn("date_of_birth", out)
		self.assertNotIn("summary", person.member(user, "my daughter", DREAMER))
		self.assertEqual(person.member(user, "my daughter", PANDIT)["date_of_birth"], "2015-03-03")

	def test_an_unknown_guide_sees_nothing(self):
		user = self._seeded()
		from raftor_astrohq import agents

		self.assertEqual(agents.reads_of("some_new_guide"), {"notes": [], "card": "none"})
		self.assertEqual(person.read(user, "some_new_guide"), {"notes": [], "card": ""})

	def test_a_tarot_guide_will_see_only_the_tarot_notes_and_the_family_names(self):
		user = _user()
		person.write(user, {"notes": [{"about": "You", "kind": "tarot", "point": "Drew the Tower for a question about work"}, {"about": "You", "kind": "dream", "point": "Dreams of falling"}]}, "g", "s")
		seen = person.read(user, "tarot")
		self.assertEqual([n["point"] for n in seen["notes"]], ["Drew the Tower for a question about work"])
		self.assertNotIn("born", seen["card"])
		self.assertEqual([n["point"] for n in person.read(user, "dream_guide")["notes"]], ["Dreams of falling"])
