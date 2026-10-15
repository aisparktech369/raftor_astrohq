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


class TestPersonaStep(AstrologerTestCase):
	def test_the_form_has_one_box_per_persona_the_vertical_lists(self):
		fields = api.personas_form_fields()["fields"]
		self.assertEqual([f["label"] for f in fields], ["Astrologer", "Tarot reader", "Pandit ji", "Palmist", "Numerologist", "Vastu expert"])
		self.assertTrue(all(f["type"] == "checkbox" for f in fields))

	def test_nothing_chosen_is_refused_and_the_step_is_not_complete(self):
		self.assertFalse(api.save_personas({})["ok"])
		self.assertFalse(astrologer.personas_complete(frappe._dict(applicant_user=self.me.name)))

	def test_chosen_personas_are_saved_waiting_for_approval(self):
		self.assertTrue(api.save_personas({"p_astrologer": 1, "p_palmist": "1"})["ok"])
		rows = {r.persona: r.approved for r in frappe.get_doc("Provider", self.provider.name).personas}
		self.assertEqual(rows, {"Astrologer": 0, "Palmist": 0})
		self.assertTrue(astrologer.personas_complete(frappe._dict(applicant_user=self.me.name)))
		self.assertEqual(api.personas_form_fields()["values"], {"p_astrologer": 1, "p_palmist": 1})

	def test_changing_the_choice_keeps_what_was_approved(self):
		api.save_personas({"p_astrologer": 1})
		frappe.db.set_value("Provider Persona", {"parent": self.provider.name}, "approved", 1)
		api.save_personas({"p_astrologer": 1, "p_palmist": 1})
		rows = {r.persona: r.approved for r in frappe.get_doc("Provider", self.provider.name).personas}
		self.assertEqual(rows, {"Astrologer": 1, "Palmist": 0})

	def test_approving_the_application_approves_the_chosen_personas(self):
		from raftor_servicehq.onboarding import sync_from_application

		api.save_personas({"p_tarot_reader": 1})
		sync_from_application(self.provider.name, frappe._dict(status="Live", verification_status="Unverified"))
		self.assertEqual(frappe.db.get_value("Provider Persona", {"parent": self.provider.name}, "approved"), 1)


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


class TestCardLines(AstrologerTestCase):
	def test_the_card_says_years_and_languages_and_nothing_private(self):
		self.assertEqual(astrologer.card_lines(self.provider.name), [])
		api.save_details(GOOD)
		self.assertEqual(astrologer.card_lines(self.provider.name), ["12 years", "English, Hindi"])

	def test_servicehq_gets_them_through_the_vocabulary(self):
		from raftor_servicehq import kinds

		api.save_details(GOOD)
		self.assertEqual(kinds.provider_lines("astrohq", self.provider.name), ["12 years", "English, Hindi"])


class TestCardFilters(AstrologerTestCase):
	"""What astrohq adds to the listing of astrologers: the language they consult in, and what is troubling the visitor."""

	def facets(self, **choices):
		return {f["name"]: f for f in astrologer.card_filters([self.provider.name], choices)["facets"]}

	def test_a_language_is_offered_only_when_someone_speaks_it_with_how_many(self):
		self.assertNotIn("language", self.facets())  # no profile yet
		api.save_details({**GOOD, "languages": "english; Hindi ,Tamil"})
		options = {o["value"]: o["count"] for o in self.facets()["language"]["options"]}
		self.assertEqual(options, {"English": 1, "Hindi": 1, "Tamil": 1})
		self.assertEqual(self.facets()["language"]["display"], "chips")

	def test_a_language_narrows_the_list_and_nothing_chosen_keeps_everyone(self):
		api.save_details(GOOD)
		name = self.provider.name
		self.assertEqual(astrologer.card_filters([name], {})["names"], [name])
		self.assertEqual(astrologer.card_filters([name], {"language": "Hindi"})["names"], [name])
		self.assertEqual(astrologer.card_filters([name], {"language": "hindi,Tamil"})["names"], [name])  # any of them, in any case
		self.assertEqual(astrologer.card_filters([name], {"language": "Tamil"})["names"], [])

	def test_the_trouble_is_asked_with_the_astrologers_words_and_never_narrows(self):
		api.save_details(GOOD)
		topic = self.facets()["topic"]
		self.assertEqual((topic["heading"], topic["carry"], topic["display"]), ("What is troubling you?", True, "chips"))
		self.assertEqual([o["value"] for o in topic["options"]], ["Career", "Marriage", "Love", "Money", "Health", "Children", "Auspicious date"])  # the topics staff keep in Desk, as seeded
		self.assertEqual(astrologer.card_filters([self.provider.name], {"topic": "Career"})["names"], [self.provider.name])

	def test_servicehq_gets_them_through_the_vocabulary(self):
		from raftor_servicehq import kinds

		api.save_details(GOOD)
		facets, names = kinds.provider_filters("astrohq", [self.provider.name], {"language": "English"})
		self.assertEqual({f["name"] for f in facets}, {"topic", "language"})
		self.assertEqual(names, [self.provider.name])
		self.assertEqual(kinds.provider_filters("astrohq", [self.provider.name], {"language": "Tamil"})[1], [])

	def test_the_booking_question_is_the_one_the_topic_starts(self):
		from raftor_servicehq import kinds

		self.assertEqual(kinds.details("astrohq", "Consultation")["topic_field"], "question")
		self.assertIn("question", [f["name"] for f in kinds.details("astrohq", "Consultation")["fields"]])


class TestTopicsAndWishesAreData(AstrologerTestCase):
	"""The buttons staff cannot change in code: topics and wishes are records in Desk, in the order and with the on/off staff give them."""

	def test_a_topic_staff_add_is_a_button_and_one_they_switch_off_is_not(self):
		from raftor_astrohq import details

		frappe.get_doc({"doctype": "Guidance Topic", "topic_name": "Test topic", "enabled": 1, "sequence": 1}).insert(ignore_permissions=True)
		self.assertEqual(details.topics()[0], "Test topic")  # first because staff numbered it first
		frappe.db.set_value("Guidance Topic", "Test topic", "enabled", 0)
		self.assertNotIn("Test topic", details.topics())

	def test_a_wish_staff_add_can_be_put_on_an_event(self):
		from raftor_astrohq import details

		frappe.get_doc({"doctype": "Blessing Wish", "wish_name": "Test wish", "enabled": 1, "sequence": 1}).insert(ignore_permissions=True)
		self.assertEqual(details.wishes()[0], "Test wish")

	def test_the_starting_lists_are_only_put_in_when_there_are_none(self):
		from raftor_astrohq.patches import seed_topics_and_wishes as seed

		before = frappe.db.count("Guidance Topic")
		seed.execute()
		self.assertEqual(frappe.db.count("Guidance Topic"), before)  # a list that exists is never put back
