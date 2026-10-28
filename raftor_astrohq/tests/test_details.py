"""astrohq's questions and its one rule (details.py, declared in vocabulary.py)."""
from unittest import TestCase

import frappe

from raftor_astrohq import details, profiles
from raftor_astrohq.tests.helpers import FAMILY, GOOD, TABLE, make_user
from raftor_servicehq import intake, kinds


class TestAstroDetails(TestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_each_kind_asks_what_astrohq_declared(self):
		names = lambda kind: [f["name"] for f in intake.fields("astrohq", kind)]
		self.assertEqual(names("Consultation"), ["question"])
		self.assertEqual(names("Subscription"), ["sankalp_name", "gotra", "wish"])
		self.assertEqual(names("Event"), ["sankalp_name", "gotra"])
		self.assertEqual(names("Timed service"), ["sankalp_name", "gotra", "wish"])
		self.assertTrue(intake.is_per_person("astrohq", "Event"))
		self.assertFalse(intake.is_per_person("astrohq", "Subscription"))

	def test_a_pooja_needs_the_sankalp_name_and_gotra(self):
		for kind in ("Subscription", "Event", "Timed service"):
			_c, errors, _m = intake.validate("astrohq", kind, {})
			self.assertEqual(set(errors), {"sankalp_name", "gotra"}, kind)
		clean, errors, _m = intake.validate("astrohq", "Subscription", {"sankalp_name": "Asha Rao", "gotra": "Kashyap"})
		self.assertEqual((errors, clean["wish"]), ({}, ""))

	def test_a_consultation_needs_the_customers_birth_details_first(self):
		frappe.set_user("Administrator")
		user = make_user()
		_c, errors, message = intake.validate("astrohq", "Consultation", {}, user.name)
		self.assertEqual((set(errors), message), ({"full_name", "date_of_birth", "place_of_birth"}, ""))  # (asked for on the same form: none given)
		self.assertEqual(details.consultation_rules({}, user.name), {"_form": "Please add your birth details first, then book."})  # (the rule itself, when none are given)
		doc = frappe.get_doc("User", user.name)
		doc.append(TABLE, GOOD)
		doc.save(ignore_permissions=True)
		self.assertEqual(intake.validate("astrohq", "Consultation", {"question": "Career?"}, user.name)[1:], ({}, ""))

	def test_a_family_members_profile_is_enough_for_a_consultation(self):
		frappe.set_user("Administrator")
		user = make_user()
		doc = frappe.get_doc("User", user.name)
		doc.append(TABLE, FAMILY)
		doc.save(ignore_permissions=True)
		self.assertEqual(intake.validate("astrohq", "Consultation", {"question": "Career?"}, user.name)[1:], ({}, ""))

	def test_the_words_still_come_without_the_questions_mixed_in(self):
		self.assertNotIn("details", kinds.words("astrohq", "Consultation"))

	def test_someone_with_no_birth_details_is_asked_for_them_once_on_the_same_form(self):
		user = make_user()
		names = lambda who: [f["name"] for f in intake.form_fields("astrohq", "Consultation", who)]
		self.assertEqual(names(user.name), ["full_name", "date_of_birth", "time_of_birth", "time_unknown", "place_of_birth", "question"])
		doc = frappe.get_doc("User", user.name)
		doc.append(TABLE, GOOD)
		doc.save(ignore_permissions=True)
		self.assertEqual(names(user.name), ["question"])  # (kept: never asked again)

	def test_the_details_given_on_the_form_are_kept_as_their_own_profile_and_not_on_the_booking(self):
		user = make_user()
		given = {"full_name": "Asha Rao", "date_of_birth": "1990-08-14", "time_of_birth": "06:42", "place_of_birth": "Pune, India", "question": "Career?"}
		clean, errors, message = intake.validate("astrohq", "Consultation", given, user.name)
		self.assertEqual((errors, message), ({}, ""))
		self.assertEqual(clean, {"question": "Career?"})  # the booking keeps the question only: the details are in the profile
		self.assertTrue(profiles.has_birth_profile(user.name))
		row = profiles.you_row(frappe.get_doc("User", user.name))
		self.assertEqual((row.relationship, row.full_name, str(row.date_of_birth), row.place_of_birth), ("You", "Asha Rao", "1990-08-14", "Pune, India"))

	def test_not_knowing_the_birth_time_is_enough_and_a_wrong_detail_comes_back_by_field_and_keeps_nothing(self):
		user = make_user()
		given = {"full_name": "Asha Rao", "date_of_birth": "1990-08-14", "time_unknown": 1, "place_of_birth": "Pune, India"}
		self.assertEqual(intake.validate("astrohq", "Consultation", given, user.name)[1:], ({}, ""))
		other = make_user()
		wrong = {"full_name": "Asha Rao", "date_of_birth": "2999-01-01", "time_unknown": 1, "place_of_birth": "Pune, India"}
		_c, errors, _m = intake.validate("astrohq", "Consultation", wrong, other.name)
		self.assertEqual(set(errors), {"date_of_birth"})
		self.assertFalse(profiles.has_birth_profile(other.name))

	def test_the_first_time_page_and_the_booking_form_ask_the_same_birth_questions(self):
		self.assertEqual([f["name"] for f in details.you_fields()], ["full_name", "date_of_birth", "time_of_birth", "time_unknown", "place_of_birth"])
		from raftor_astrohq.page_definitions import _you_fields

		self.assertEqual(_you_fields(), details.you_fields())
