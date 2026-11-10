"""What the guides remember about a person and the people in their profiles: notes tied to profiles, a summary per person, family added from the chat, and the guide's tool."""
import frappe

from raftor_astrohq import person, profiles
from raftor_astrohq.tests.helpers import GOOD, TABLE, AstroTestCase, make_user


def _user(**values):
	user = make_user()
	user.append(TABLE, GOOD)
	user.save(ignore_permissions=True)
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
		self.assertEqual((rhenna.relationship, str(rhenna.date_of_birth), rhenna.place_of_birth, rhenna.from_chat, rhenna.permission_given), ("Child", "2015-03-03", "Pune", 1, 0))
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
