"""astrohq's questions and its one rule (details.py, declared in vocabulary.py)."""
from unittest import TestCase

import frappe

from raftor_astrohq import details
from raftor_astrohq.tests.helpers import GOOD, TABLE, make_user
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
		self.assertEqual((errors, message), ({}, "Please add your birth details first, then book."))
		doc = frappe.get_doc("User", user.name)
		doc.append(TABLE, GOOD)
		doc.save(ignore_permissions=True)
		self.assertEqual(intake.validate("astrohq", "Consultation", {"question": "Career?"}, user.name)[1:], ({}, ""))

	def test_the_words_still_come_without_the_questions_mixed_in(self):
		self.assertNotIn("details", kinds.words("astrohq", "Consultation"))
