"""AstroHQ's pages are page definitions that websitehq accepts, at the agreed addresses, and say what the wireframes say."""
from unittest import TestCase

import frappe

from raftor_astrohq import api, page_definitions, profiles
from raftor_astrohq.tests.helpers import GOOD, TABLE, make_user
from raftor_websitehq.website_hq.page_sync import check


def pages():
	return {d["route"]: d for d in page_definitions.definitions()}


def form_of(page):
	return check(page)["sections"][1]["cards"][0]["values"]


class TestPages(TestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_every_page_passes_the_kits_checks_and_needs_a_sign_in(self):
		self.assertEqual(set(pages()), {"onboarding/birth-details", "onboarding/birth-details/done", "my/birth-profiles", "my/birth-profiles/new", "my/birth-profiles/edit",
										"onboarding/astrologer-details", "onboarding/astrologer-credentials", "onboarding/astrologer-credentials/new"})
		for route, page in pages().items():
			self.assertTrue(check(page)["login_required"], route)

	def test_onboarding_form_is_for_you_and_has_the_short_field_set(self):
		form = form_of(pages()["onboarding/birth-details"])
		self.assertEqual(form["static_args"], {"relationship": "You"})
		self.assertEqual([f["name"] for f in form["fields"]], ["full_name", "date_of_birth", "time_of_birth", "time_unknown", "place_of_birth"])
		time = next(f for f in form["fields"] if f["name"] == "time_of_birth")
		self.assertEqual(time["disabled_when"], "time_unknown")
		self.assertEqual(form["success_redirect"], "/onboarding/birth-details/done")

	def test_the_family_form_has_relationship_without_you_and_the_permission_tick(self):
		form = form_of(pages()["my/birth-profiles/new"])
		names = [f["name"] for f in form["fields"]]
		self.assertEqual(names[0], "relationship")
		self.assertIn("permission_given", names)
		self.assertNotIn("You", [o["value"] if isinstance(o, dict) else o for o in form["fields"][0]["options"]])
		self.assertTrue(next(f for f in form["fields"] if f["name"] == "permission_given")["required"])

	def test_the_all_set_page_shows_only_you_and_offers_family_and_continue(self):
		source = check(pages()["onboarding/birth-details/done"])["sections"][1]["source"]
		self.assertEqual(source["args"], {"who": "you"})
		self.assertEqual([link["href"] for link in source["links"]], ["/my/birth-profiles/new", "/"])

	def test_the_list_page_is_on_the_my_account_menu_and_adds_a_person(self):
		page = check(pages()["my/birth-profiles"])
		self.assertEqual(page["menu"]["label"], "Birth profiles")
		self.assertEqual(page["sections"][1]["source"]["links"][0]["href"], "/my/birth-profiles/new")

	def test_editing_gives_the_short_form_for_you_and_the_full_one_for_family(self):
		user = make_user()
		user.append(TABLE, GOOD)
		user.append(TABLE, {**GOOD, "relationship": "Spouse", "full_name": "Ravi", "permission_given": 1})
		user.save(ignore_permissions=True)
		you, spouse = frappe.get_doc("User", user.name).get(TABLE)
		frappe.set_user(user.name)
		mine = api.profile_form_fields(you.name)
		self.assertEqual([f["name"] for f in mine["fields"]], ["full_name", "date_of_birth", "time_of_birth", "time_unknown", "place_of_birth"])
		self.assertEqual(mine["values"]["full_name"], GOOD["full_name"])
		family = api.profile_form_fields(spouse.name)
		self.assertEqual(family["fields"][0]["name"], "relationship")
		self.assertEqual(family["values"]["full_name"], "Ravi")
		with self.assertRaises(frappe.DoesNotExistError):
			api.profile_form_fields("does-not-exist")

	def test_saving_the_edit_of_your_own_profile_keeps_it_yours(self):
		user = make_user()
		user.append(TABLE, GOOD)
		user.save(ignore_permissions=True)
		you = frappe.get_doc("User", user.name).get(TABLE)[0]
		frappe.set_user(user.name)
		out = api.save_profile(id=you.name, values={"full_name": "New Name", "date_of_birth": "1990-01-02", "time_of_birth": "10:30", "place_of_birth": "Pune"})
		self.assertEqual(out, {"ok": True})
		self.assertEqual(frappe.get_doc("User", user.name).get(TABLE)[0].relationship, profiles.SELF)

	def test_the_old_addresses_forward_and_the_journey_names_the_new_ones(self):
		rules = {r["source"]: r["target"] for r in frappe.get_hooks("website_redirects")}
		self.assertEqual(rules["/birth-details"], "/onboarding/birth-details")
		self.assertEqual(rules["/astrologer/credentials"], "/onboarding/astrologer-credentials")
