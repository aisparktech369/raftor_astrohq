"""What AstroHQ adds to a free report (servicehq free_reports.py, the vocabulary's "free" of each report): who a kundli is for, keeping its details as a birth profile, who it is
for in a few words, the name of a new account, and the person's own profile filling the form.

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_free_report_hooks
"""
import frappe

from raftor_astrohq import details, profiles, reports, vocabulary
from raftor_astrohq.tests.helpers import GOOD, TABLE, AstroTestCase, make_user

KUNDLI = {"report_name": "Asha Rao", "birth_date": "1990-08-14", "birth_time": "06:42", "birth_place": "Pune, Maharashtra", "whose": "You"}


def rows_of(user: str) -> list[dict]:
	return [profiles.row_values(row) for row in frappe.get_doc("User", user).get(TABLE)]


class TestTheQuestion(AstroTestCase):
	def test_who_it_is_for_offers_the_relationships_the_profile_has_and_starts_with_me(self):
		field = details.whose()
		self.assertEqual((field["name"], field["type"], field["required"], field["default"]), ("whose", "select", True, "You"))
		self.assertEqual([o["value"] for o in field["options"]], profiles.relationships())
		self.assertEqual(field["options"][0], {"value": "You", "label": "Me"})
		self.assertEqual(dict((o["value"], o["label"]) for o in field["options"])["Child"], "My child")

	def test_a_relationship_an_admin_adds_is_offered_under_its_own_name(self):
		meta = frappe.get_meta("Astro Birth Profile")
		field = meta.get_field("relationship")
		original = field.options
		try:
			field.options = original + "\nCousin"
			self.assertEqual(details.whose()["options"][-1], {"value": "Cousin", "label": "Cousin"})
		finally:
			field.options = original


class TestKeepingTheDetails(AstroTestCase):
	def test_a_kundli_for_the_person_becomes_their_own_profile(self):
		user = make_user().name
		reports.keep_birth_profile(user, KUNDLI)
		(row,) = rows_of(user)
		self.assertEqual((row["relationship"], row["full_name"], row["date_of_birth"], row["time_of_birth"], row["place_of_birth"]), ("You", "Asha Rao", "1990-08-14", "06:42", "Pune, Maharashtra"))
		self.assertEqual((row["time_unknown"], row["permission_given"]), (0, 0))
		self.assertEqual(profiles.row_errors(row), {})
		self.assertTrue(profiles.has_birth_profile(user))

	def test_a_kundli_for_someone_in_the_family_is_kept_as_theirs_with_the_persons_confirmation(self):
		user = make_user().name
		reports.keep_birth_profile(user, {**KUNDLI, "report_name": "Little Ravi", "whose": "Child", "birth_date": "2015-03-02"})
		(row,) = rows_of(user)
		self.assertEqual((row["relationship"], row["full_name"], row["permission_given"]), ("Child", "Little Ravi", 1))
		self.assertEqual(profiles.row_errors(row), {})

	def test_the_same_person_is_not_kept_twice_and_two_children_are_two_profiles(self):
		user = make_user().name
		reports.keep_birth_profile(user, KUNDLI)
		reports.keep_birth_profile(user, KUNDLI)
		reports.keep_birth_profile(user, {**KUNDLI, "report_name": "asha rao", "whose": "Other"})  # the same name and day, written differently
		self.assertEqual(len(rows_of(user)), 1)
		reports.keep_birth_profile(user, {**KUNDLI, "report_name": "One", "whose": "Child", "birth_date": "2015-03-02"})
		reports.keep_birth_profile(user, {**KUNDLI, "report_name": "Two", "whose": "Child", "birth_date": "2018-07-09"})
		self.assertEqual(sorted(r["full_name"] for r in rows_of(user)), ["Asha Rao", "One", "Two"])

	def test_the_persons_own_profile_is_never_overwritten_by_a_report(self):
		user = make_user(**{TABLE: [GOOD]}).name
		reports.keep_birth_profile(user, {**KUNDLI, "report_name": "Somebody Else", "birth_date": "1971-01-01", "birth_place": "Delhi"})
		(row,) = rows_of(user)
		self.assertEqual((row["full_name"], row["date_of_birth"], row["place_of_birth"]), (GOOD["full_name"], GOOD["date_of_birth"], GOOD["place_of_birth"]))

	def test_with_no_answer_to_whose_it_is_the_persons_own(self):
		user = make_user().name
		without = {k: v for k, v in KUNDLI.items() if k != "whose"}
		reports.keep_birth_profile(user, without)
		self.assertEqual([r["relationship"] for r in rows_of(user)], ["You"])


class TestWhoItIsFor(AstroTestCase):
	def test_a_new_account_is_called_by_the_name_only_when_the_kundli_is_the_persons_own(self):
		self.assertEqual(reports.kundli_account_name(KUNDLI), "Asha Rao")
		self.assertEqual(reports.kundli_account_name({k: v for k, v in KUNDLI.items() if k != "whose"}), "Asha Rao")
		for relation in ("Spouse", "Child", "Parent", "Sibling", "Other"):
			self.assertEqual(reports.kundli_account_name({**KUNDLI, "whose": relation}), "", relation)

	def test_the_summary_names_the_person_or_the_couple(self):
		self.assertEqual(reports.kundli_summary(KUNDLI), "Asha Rao")
		self.assertEqual(reports.match_summary({"boy_name": "Vikram Mehta", "girl_name": "Priya Shah"}), "Vikram Mehta and Priya Shah")
		self.assertEqual(reports.match_summary({"boy_name": "Vikram Mehta", "girl_name": ""}), "")
		self.assertEqual(reports.match_summary({}), "")


class TestFillingTheForm(AstroTestCase):
	def test_the_persons_own_profile_fills_the_kundli_form(self):
		user = make_user(**{TABLE: [GOOD]}).name
		self.assertEqual(reports.kundli_prefill(user), {"whose": "You", "report_name": "Asha Rao", "birth_date": "1990-08-14", "birth_time": "06:42", "birth_place": "Pune, India"})

	def test_nothing_is_filled_when_there_is_no_profile_or_the_time_is_not_known(self):
		self.assertEqual(reports.kundli_prefill(make_user().name), {})
		unknown = make_user(**{TABLE: [{**GOOD, "time_of_birth": "", "time_unknown": 1}]}).name
		self.assertEqual(reports.kundli_prefill(unknown), {})  # the report needs the time: better to ask than to guess

	def test_only_the_persons_own_profile_is_used_not_a_family_members(self):
		family = make_user(**{TABLE: [{**GOOD, "relationship": "Child", "permission_given": 1}]}).name
		self.assertEqual(reports.kundli_prefill(family), {})


class TestWhatTheVocabularySays(AstroTestCase):
	def test_both_reports_are_free_and_say_what_is_theirs_to_do_when_given(self):
		listed = vocabulary.vocabulary()["reports"]
		for name in ("kundli", "match"):
			self.assertEqual(listed[name]["price"], 0, name)
			self.assertIn("free", listed[name]["description"].lower(), name)
			self.assertNotIn("order is paid", listed[name]["description"], name)
		kundli, match = listed["kundli"]["free"], listed["match"]["free"]
		self.assertEqual([f["name"] for f in kundli["fields"]], ["whose"])
		self.assertTrue(kundli["keep_line"])
		self.assertNotIn("keep", match)  # a match is between two people: nothing of it is kept as a profile on its own
		self.assertNotIn("fields", match)

	def test_every_function_the_vocabulary_names_exists(self):
		for name, entry in vocabulary.vocabulary()["reports"].items():
			for key, path in (entry.get("free") or {}).items():
				if key in ("fields", "keep_line"):
					continue
				self.assertTrue(callable(frappe.get_attr(path)), f"{name}: {key} -> {path}")
