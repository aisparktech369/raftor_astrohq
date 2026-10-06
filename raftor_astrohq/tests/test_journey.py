"""The journey AstroHQ describes, and that onboarding finishes the step by itself."""
import json
from unittest import TestCase

import frappe

from raftor_astrohq import api
from raftor_astrohq.journey import APP_KEY, JOURNEY, register_journey
from raftor_astrohq.tests.helpers import GOOD, AstroTestCase, make_user
from raftor_onboardinghq.applications import open_application
from raftor_onboardinghq.handoff import after_login, after_signup


class TestJourney(AstroTestCase):
	def test_it_is_data_naming_a_page_and_a_check_and_registering_twice_changes_nothing(self):
		register_journey(); register_journey()
		rows = frappe.get_all("Onboarding Flow Step", filters={"module": APP_KEY}, fields=["step_key", "step_type", "config", "required", "completion_check"])
		self.assertEqual(len(rows), len(JOURNEY))
		self.assertEqual((rows[0].step_type, rows[0].required), ("Form", 1))
		self.assertEqual(json.loads(rows[0].config), {"page": "/onboarding/birth-details", "entry": True})
		self.assertEqual(rows[0].completion_check, "raftor_astrohq.profiles.birth_details_complete")

	def test_signing_up_for_astrohq_lands_on_the_birth_details_page(self):
		user = make_user()
		self.assertEqual(after_signup(user.name, "astrohq"), {"redirect_to": "/onboarding/birth-details"})

	def test_saving_your_details_finishes_the_step_and_ends_the_redirects(self):
		user = make_user()
		name = open_application(user.name, APP_KEY)
		self.assertEqual(after_login(user.name), {"redirect_to": "/onboarding/birth-details"})
		frappe.set_user(user.name)
		self.assertEqual(api.save_profile(values=GOOD, relationship="You"), {"ok": True})
		step = frappe.get_doc("Onboarding Application", name).steps[0]
		self.assertEqual((step.step_key, step.status), ("birth_details", "Complete"))
		self.assertIsNone(after_login(user.name))

	def test_saving_a_family_member_does_not_finish_it(self):
		user = make_user()
		name = open_application(user.name, APP_KEY)
		frappe.set_user(user.name)
		api.save_profile(values={**GOOD, "relationship": "Spouse", "permission_given": 1})
		self.assertEqual(frappe.get_doc("Onboarding Application", name).steps[0].status, "Pending")
