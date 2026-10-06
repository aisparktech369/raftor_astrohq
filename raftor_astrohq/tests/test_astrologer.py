"""What an astrologer adds to servicehq's Provider: rules, endpoints (own Provider only), the two journey steps
and the pages."""
import uuid
from unittest import TestCase

import frappe

from raftor_astrohq import astrologer, astrologer_api as api
from raftor_astrohq.journey import PROVIDER_JOURNEY, PROVIDER_STEPS
from raftor_astrohq.tests.helpers import make_user

GOOD = {"expertise": "Vedic, Tarot", "languages": "English, Hindi", "years_of_practice": "12"}


def make_provider(user):
	return frappe.get_doc({"doctype": "Provider", "user": user.name, "slug": f"astro-{uuid.uuid4().hex[:8]}",
						   "display_name": "Test Astrologer", "provider_type": "Individual"}).insert(ignore_permissions=True)


class AstrologerTestCase(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.me = make_user()
		self.provider = make_provider(self.me)
		frappe.set_user(self.me.name)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()


class TestRules(AstrologerTestCase):
	def test_good_details_have_no_errors(self):
		self.assertEqual(astrologer.details_errors(GOOD), {})

	def test_each_missing_detail_is_reported_on_its_own_field(self):
		self.assertEqual(set(astrologer.details_errors({})), {"expertise", "languages", "years_of_practice"})

	def test_years_must_be_a_sensible_whole_number(self):
		for bad in ("-1", "abc", "3.5", "81", ""):
			self.assertIn("years_of_practice", astrologer.details_errors({**GOOD, "years_of_practice": bad}), bad)
		self.assertEqual(astrologer.details_errors({**GOOD, "years_of_practice": "0"}), {})

	def test_credential_needs_a_title_and_a_real_year_if_given(self):
		self.assertIn("title", astrologer.credential_errors({"title": " "}))
		self.assertIn("year", astrologer.credential_errors({"title": "Jyotish", "year": "1800"}))
		self.assertIn("year", astrologer.credential_errors({"title": "Jyotish", "year": "3000"}))
		self.assertEqual(astrologer.credential_errors({"title": "Jyotish", "year": "2010"}), {})
		self.assertEqual(astrologer.credential_errors({"title": "Jyotish"}), {})


class TestEndpoints(AstrologerTestCase):
	def test_guests_and_non_providers_are_refused(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			api.get_details()
		frappe.set_user("Administrator")
		other = make_user()
		frappe.set_user(other.name)
		with self.assertRaises(frappe.PermissionError):
			api.save_details(GOOD)

	def test_save_creates_one_profile_row_pointing_at_the_provider(self):
		self.assertEqual(api.save_details(GOOD), {"ok": True})
		self.assertEqual(api.save_details({**GOOD, "expertise": "Numerology"}), {"ok": True})
		rows = frappe.get_all(astrologer.DOCTYPE, filters={"provider": self.provider.name}, fields=["expertise", "years_of_practice"])
		self.assertEqual(rows, [{"expertise": "Numerology", "years_of_practice": 12}])
		self.assertEqual(api.get_details()["values"]["expertise"], "Numerology")

	def test_the_provider_record_itself_is_not_changed(self):
		before = frappe.db.get_value("Provider", self.provider.name, "modified")
		api.save_details(GOOD)
		self.assertEqual(frappe.db.get_value("Provider", self.provider.name, "modified"), before)

	def test_bad_details_come_back_per_field_and_save_nothing(self):
		out = api.save_details({**GOOD, "languages": ""})
		self.assertFalse(out["ok"])
		self.assertIn("languages", out["errors"])
		self.assertFalse(frappe.db.exists(astrologer.DOCTYPE, self.provider.name))

	def test_credentials_need_the_details_first_then_add_list_and_remove(self):
		self.assertFalse(api.add_credential({"title": "Jyotish Visharad"})["ok"])
		api.save_details(GOOD)
		self.assertEqual(api.add_credential({"title": "Jyotish Visharad", "issued_by": "Bharatiya Vidya", "year": "2010"}), {"ok": True})
		items = api.list_credentials()["items"]
		self.assertEqual((items[0]["title"], items[0]["lines"]), ("Jyotish Visharad", ["Bharatiya Vidya · 2010"]))
		api.delete_credential(items[0]["id"])
		self.assertEqual(api.list_credentials()["items"], [])

	def test_nobody_can_remove_someone_elses_credential(self):
		api.save_details(GOOD)
		api.add_credential({"title": "Jyotish Visharad"})
		credential = api.list_credentials()["items"][0]["id"]
		frappe.set_user("Administrator")
		other = make_user()
		make_provider(other)
		frappe.set_user(other.name)
		api.save_details(GOOD)
		with self.assertRaises(frappe.DoesNotExistError):
			api.delete_credential(credential)


class TestCompletionChecks(AstrologerTestCase):
	def application(self):
		return frappe._dict(applicant_user=self.me.name)

	def test_details_and_credentials_checks_follow_the_data(self):
		self.assertFalse(astrologer.details_complete(self.application()))
		api.save_details(GOOD)
		self.assertTrue(astrologer.details_complete(self.application()))
		self.assertFalse(astrologer.credentials_complete(self.application()))
		api.add_credential({"title": "Jyotish Visharad"})
		self.assertTrue(astrologer.credentials_complete(self.application()))

	def test_saving_finishes_the_onboarding_steps_by_itself(self):
		from raftor_onboardinghq.applications import open_application

		frappe.set_user("Administrator")
		application = open_application(self.me.name, PROVIDER_JOURNEY)
		frappe.set_user(self.me.name)
		api.save_details(GOOD)
		api.add_credential({"title": "Jyotish Visharad"})
		done = {r.step_key: r.status for r in frappe.get_doc("Onboarding Application", application).steps}
		self.assertEqual((done["astro_details"], done["astro_credentials"]), ("Complete", "Complete"))


class TestJourney(TestCase):
	def test_steps_sit_between_servicehqs_own_by_order_and_servicehq_keeps_its_steps(self):
		rows = frappe.get_all("Onboarding Flow Step", filters={"module": PROVIDER_JOURNEY}, fields=["step_key", "order"], order_by="`order`")
		keys = [r.step_key for r in rows]
		self.assertEqual(keys[:1], ["profile"])
		self.assertLess(keys.index("profile"), keys.index("astro_details"))
		self.assertLess(keys.index("astro_credentials"), keys.index("offering"))
		self.assertEqual({s["step_key"] for s in PROVIDER_STEPS} - set(keys), set())

	def test_both_steps_name_a_page_and_a_check(self):
		for step in PROVIDER_STEPS:
			row = frappe.get_doc("Onboarding Flow Step", {"module": PROVIDER_JOURNEY, "step_key": step["step_key"]})
			self.assertTrue(frappe.parse_json(row.config)["page"].startswith("/onboarding/astrologer-"))
			self.assertTrue(frappe.get_attr(row.completion_check))


class TestAstrologerPages(TestCase):
	def test_the_pages_are_shipped_and_pass_the_kits_checks(self):
		from raftor_astrohq import page_definitions
		from raftor_websitehq.website_hq.page_sync import check

		routes = {d["route"]: d for d in page_definitions.definitions()}
		for route in ("onboarding/astrologer-details", "onboarding/astrologer-credentials", "onboarding/astrologer-credentials/new"):
			self.assertTrue(check(routes[route])["login_required"], route)

	def test_details_form_fields_and_next_page(self):
		from raftor_astrohq import page_definitions

		page = next(d for d in page_definitions.definitions() if d["route"] == "onboarding/astrologer-details")
		form = page["sections"][1]["cards"][0]["values"]
		self.assertEqual([f["name"] for f in form["fields"]], ["expertise", "languages", "years_of_practice"])
		self.assertEqual(form["success_redirect"], "/onboarding/astrologer-credentials")
