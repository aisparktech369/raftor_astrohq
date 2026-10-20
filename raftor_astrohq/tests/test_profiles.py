"""Birth profiles on the User: the rules (one set, used by the website and by every User save)."""
from datetime import datetime
from unittest import TestCase

import frappe
from frappe.utils import add_days, today

from raftor_astrohq import profiles
from raftor_astrohq.tests.helpers import FAMILY, GOOD, TABLE, AstroTestCase, make_user


class TestTable(AstroTestCase):
	def test_the_table_sits_on_the_user_and_nothing_else_is_added(self):
		field = frappe.get_meta("User").get_field(TABLE)
		self.assertEqual((field.fieldtype, field.options), ("Table", "Astro Birth Profile"))
		for gone in ("astro_time_of_birth", "astro_place_of_birth"):
			self.assertIsNone(frappe.get_meta("User").get_field(gone), gone)

	def test_setting_up_twice_changes_nothing(self):
		before = frappe.db.count("Custom Field", {"dt": "User"})
		profiles.ensure_fields(); profiles.ensure_fields()
		self.assertEqual(frappe.db.count("Custom Field", {"dt": "User"}), before)

	def test_relationship_choices_come_from_the_table_so_an_admin_can_edit_them(self):
		self.assertEqual(profiles.relationships(), ["You", "Spouse", "Child", "Parent", "Sibling", "Other"])


class TestRules(AstroTestCase):
	def errors(self, **override):
		return profiles.row_errors({**GOOD, **override})

	def test_a_good_profile_has_no_errors_for_you_and_for_family(self):
		self.assertEqual(self.errors(), {})
		self.assertEqual(profiles.row_errors(FAMILY), {})

	def test_each_required_thing_is_reported_on_its_own_field(self):
		self.assertIn("full_name", self.errors(full_name=" x "))
		self.assertIn("date_of_birth", self.errors(date_of_birth=""))
		self.assertIn("date_of_birth", self.errors(date_of_birth="not a date"))
		self.assertIn("place_of_birth", self.errors(place_of_birth=" "))
		self.assertIn("relationship", self.errors(relationship="Cousin"))
		self.assertIn("relationship", self.errors(relationship=""))

	def test_dates_in_the_future_are_refused(self):
		self.assertIn("date_of_birth", self.errors(date_of_birth=add_days(today(), 1)))
		if datetime.now().hour < 22:
			self.assertIn("time_of_birth", self.errors(date_of_birth=today(), time_of_birth="23:59"))
		self.assertEqual(self.errors(date_of_birth=today(), time_of_birth="00:00"), {})

	def test_a_time_or_the_tick_but_exactly_one(self):
		self.assertEqual(self.errors(time_of_birth="", time_unknown=1), {})
		self.assertIn("time_of_birth", self.errors(time_of_birth="", time_unknown=0))
		self.assertIn("time_of_birth", self.errors(time_of_birth="06:42", time_unknown=1))

	def test_times_are_checked_and_tidied(self):
		for bad in ("25:00", "12:60", "6", "noon", "12:5", "12:00:99"):
			self.assertIn("time_of_birth", self.errors(time_of_birth=bad), bad)
		self.assertEqual(profiles.clean({**GOOD, "time_of_birth": " 6:42 "})["time_of_birth"], "06:42")
		self.assertEqual(self.errors(time_of_birth="00:00"), {})  # midnight is a real time

	def test_family_members_need_the_permission_tick_but_you_does_not(self):
		self.assertIn("permission_given", profiles.row_errors({**FAMILY, "permission_given": 0}))
		self.assertNotIn("permission_given", self.errors(permission_given=0))

	def test_ticks_accept_the_forms_a_browser_sends(self):
		for ticked in (1, True, "1", "true"):
			self.assertEqual(profiles.clean({**GOOD, "time_unknown": ticked})["time_unknown"], 1)
		for unticked in (0, False, "", None, "0"):
			self.assertEqual(profiles.clean({**GOOD, "time_unknown": unticked})["time_unknown"], 0)


class TestSavingAUser(AstroTestCase):
	def test_rows_are_checked_whoever_saves_and_wherever(self):
		user = make_user()
		user.append(TABLE, {**GOOD, "date_of_birth": add_days(today(), 3)})
		with self.assertRaises(frappe.ValidationError):
			user.save(ignore_permissions=True)

	def test_there_can_be_only_one_you(self):
		user = make_user()
		user.append(TABLE, GOOD); user.append(TABLE, {**GOOD, "full_name": "Another"})
		with self.assertRaises(frappe.ValidationError):
			user.save(ignore_permissions=True)

	def test_good_rows_are_saved_and_tidied(self):
		user = make_user()
		user.append(TABLE, {**GOOD, "time_of_birth": "6:42", "full_name": "  Asha Rao "})
		user.append(TABLE, FAMILY)
		user.save(ignore_permissions=True)
		rows = frappe.get_doc("User", user.name).get(TABLE)
		self.assertEqual((rows[0].full_name, rows[0].time_of_birth, rows[1].relationship), ("Asha Rao", "06:42", "Spouse"))

	def test_users_without_profiles_are_unaffected(self):
		make_user(); make_user(birth_date="1990-08-14")


class TestCompleteness(AstroTestCase):
	def application(self, user):
		return frappe._dict(applicant_user=user.name)

	def test_only_a_complete_you_profile_counts(self):
		user = make_user()
		self.assertFalse(profiles.birth_details_complete(self.application(user)))
		user.append(TABLE, FAMILY); user.save(ignore_permissions=True)
		self.assertFalse(profiles.birth_details_complete(self.application(user)))  # family never counts
		user.append(TABLE, GOOD); user.save(ignore_permissions=True)
		self.assertTrue(profiles.birth_details_complete(self.application(user)))

	def test_unknown_time_counts_as_complete(self):
		user = make_user()
		user.append(TABLE, {**GOOD, "time_of_birth": "", "time_unknown": 1}); user.save(ignore_permissions=True)
		self.assertTrue(profiles.birth_details_complete(self.application(user)))

