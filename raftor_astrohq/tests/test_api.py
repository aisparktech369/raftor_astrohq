"""Website endpoints: own rows only, per-field errors, and "You" behaving as one special row."""
from unittest import TestCase

import frappe

from raftor_astrohq import api, profiles
from raftor_astrohq.tests.helpers import FAMILY, GOOD, TABLE, make_user

YOU_FORM = {"relationship": "You"}


class ApiTestCase(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.me = make_user()
		frappe.set_user(self.me.name)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def rows(self, user=None):
		return frappe.get_doc("User", (user or self.me).name).get(TABLE)

	def save(self, values, **kw):
		return api.save_profile(values=values, **kw)


class TestSigningIn(ApiTestCase):
	def test_guests_are_refused_everywhere(self):
		frappe.set_user("Guest")
		for call in (lambda: api.list_profiles(), lambda: api.get_profile(), lambda: api.save_profile(values={}), lambda: api.delete_profile("x")):
			with self.assertRaises(frappe.PermissionError):
				call()


class TestYou(ApiTestCase):
	def test_saving_you_creates_then_updates_one_row(self):
		self.assertEqual(self.save(GOOD, **YOU_FORM), {"ok": True})
		self.assertEqual(self.save({**GOOD, "place_of_birth": "Mumbai, India"}, **YOU_FORM), {"ok": True})
		rows = self.rows()
		self.assertEqual((len(rows), rows[0].relationship, rows[0].place_of_birth), (1, "You", "Mumbai, India"))

	def test_the_onboarding_form_fixes_the_relationship_to_you(self):
		self.save({**GOOD, "relationship": "Spouse"}, relationship="You")  # the form's fixed value wins
		self.assertEqual(self.rows()[0].relationship, "You")

	def test_mistakes_come_back_per_field_and_nothing_is_saved(self):
		out = self.save({**GOOD, "full_name": "", "date_of_birth": "2999-01-01", "time_of_birth": "99:99", "place_of_birth": ""}, **YOU_FORM)
		self.assertFalse(out["ok"])
		self.assertEqual(set(out["errors"]), {"full_name", "date_of_birth", "time_of_birth", "place_of_birth"})
		self.assertEqual(self.rows(), [])

	def test_get_profile_returns_what_the_form_needs(self):
		self.assertEqual(api.get_profile(relationship="You"), {"values": {}})
		self.save(GOOD, **YOU_FORM)
		values = api.get_profile(relationship="You")["values"]
		self.assertEqual((values["full_name"], values["date_of_birth"], values["time_of_birth"], values["time_unknown"]), ("Asha Rao", "1990-08-14", "06:42", 0))

	def test_you_cannot_be_deleted(self):
		self.save(GOOD, **YOU_FORM)
		with self.assertRaises(frappe.PermissionError):
			api.delete_profile(self.rows()[0].name)
		self.assertEqual(len(self.rows()), 1)


class TestFamily(ApiTestCase):
	def test_add_edit_and_delete_a_family_member(self):
		self.save(GOOD, **YOU_FORM)
		self.assertEqual(self.save(FAMILY), {"ok": True})
		member = self.rows()[1]
		self.assertEqual(self.save({**FAMILY, "full_name": "Ravi K Rao"}, id=member.name), {"ok": True})
		self.assertEqual(self.rows()[1].full_name, "Ravi K Rao")
		self.assertEqual(api.delete_profile(member.name), {"message": "Deleted."})
		self.assertEqual([r.relationship for r in self.rows()], ["You"])

	def test_family_needs_the_permission_tick(self):
		out = self.save({**FAMILY, "permission_given": 0})
		self.assertEqual(set(out["errors"]), {"permission_given"})

	def test_no_limit_on_how_many(self):
		for n in range(12):
			self.assertEqual(self.save({**FAMILY, "full_name": f"Person {n}"}), {"ok": True})
		self.assertEqual(len(self.rows()), 12)

	def test_there_can_still_be_only_one_you(self):
		self.save(GOOD, **YOU_FORM); self.save(FAMILY)
		member = self.rows()[1]
		# a family member cannot be turned into "You" ...
		out = self.save({**FAMILY, "relationship": "You"}, id=member.name)
		self.assertEqual(set(out["errors"]), {"relationship"})
		# ... and "You" cannot be turned into a family member
		out = self.save({**FAMILY}, id=self.rows()[0].name)
		self.assertEqual(set(out["errors"]), {"relationship"})
		self.assertEqual([r.relationship for r in self.rows()], ["You", "Spouse"])

	def test_the_list_puts_you_first_and_only_family_can_be_deleted(self):
		self.save(FAMILY); self.save(GOOD, **YOU_FORM)
		listed = api.list_profiles()["items"]
		items = [i for i in listed if i["id"] != "match"]
		self.assertEqual([i["badge"] for i in items], ["You", "Spouse"])
		self.assertEqual([i["id"] for i in listed][-1], "match")  # with two people saved, one more card offers to check how well they match
		self.assertEqual([a["label"] for a in items[0]["actions"]], ["Edit"])
		self.assertEqual([a["label"] for a in items[1]["actions"]], ["Edit", "Delete"])
		self.assertIn("06:42", items[0]["lines"][0]); self.assertIn("time not known", items[1]["lines"][0])
		self.assertEqual([i["badge"] for i in api.list_profiles(who="you")["items"]], ["You"])


class TestOtherPeopleCannotBeTouched(ApiTestCase):
	def test_nobody_sees_changes_or_deletes_anyone_elses_rows(self):
		self.save(GOOD, **YOU_FORM); self.save(FAMILY)
		mine = [r.name for r in self.rows()]
		frappe.set_user("Administrator")
		other = make_user()
		frappe.set_user(other.name)
		self.assertEqual([i["id"] for i in api.list_profiles()["items"]], ["you"])  # only the empty place for "You": none of the other person's rows
		self.assertEqual(api.get_profile(id=mine[1]), {"values": {}})
		with self.assertRaises(frappe.DoesNotExistError):
			self.save(FAMILY, id=mine[1])
		with self.assertRaises(frappe.DoesNotExistError):
			api.delete_profile(mine[1])
		frappe.set_user(self.me.name)
		self.assertEqual(len(self.rows()), 2)
