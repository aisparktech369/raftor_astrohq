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

	def test_birth_profiles_join_the_customers_left_menu_after_remedies_and_before_orders(self):
		clean = check(pages()["my/birth-profiles"])
		self.assertEqual(clean["side"], {"label": "", "order": 30, "parent": ""})
		self.assertEqual(clean["menu"]["label"], "Birth profiles")
		self.assertEqual(clean["sidebar"], 1)

	def test_every_page_passes_the_kits_checks_and_needs_a_sign_in(self):
		self.assertEqual(set(pages()), {"onboarding/birth-details", "onboarding/birth-details/done", "my/birth-profiles", "my/birth-profiles/new", "my/birth-profiles/edit", "my/birth-profiles/you",
										"onboarding/astrologer-personas", "onboarding/astrologer-details", "onboarding/astrologer-credentials", "onboarding/astrologer-credentials/new", "provider/chart", "panchang"})
		for route, page in pages().items():
			self.assertEqual(check(page)["login_required"], route != "panchang", route)  # the Panchang is for everyone, every other page is for someone signed in

	def test_onboarding_form_is_for_you_and_has_the_short_field_set(self):
		form = form_of(pages()["onboarding/birth-details"])
		self.assertEqual(form["static_args"], {"relationship": "You"})
		self.assertEqual([f["name"] for f in form["fields"]], ["full_name", "date_of_birth", "time_of_birth", "time_unknown", "place_of_birth"])
		time = next(f for f in form["fields"] if f["name"] == "time_of_birth")
		self.assertEqual(time["disabled_when"], "time_unknown")
		self.assertEqual(form["success_redirect"], "/onboarding/birth-details/done")

	def test_the_person_form_offers_you_with_the_others_and_asks_permission_only_for_others(self):
		form = form_of(pages()["my/birth-profiles/new"])
		names = [f["name"] for f in form["fields"]]
		self.assertEqual(names[0], "relationship")
		self.assertIn("permission_given", names)
		self.assertEqual([o["value"] if isinstance(o, dict) else o for o in form["fields"][0]["options"]][0], "You")
		self.assertFalse(next(f for f in form["fields"] if f["name"] == "permission_given").get("required"))
		user = make_user()
		frappe.set_user(user.name)
		spouse = {**GOOD, "relationship": "Spouse", "permission_given": 0}
		self.assertIn("permission_given", api.save_profile(values=spouse)["errors"])  # the server still asks for others
		self.assertEqual(api.save_profile(values={**GOOD, "relationship": "You"}), {"ok": True})  # and not for yourself
		self.assertEqual([i["badge"] for i in api.list_profiles()["items"]], ["You"])

	def test_the_all_set_page_shows_only_you_and_offers_family_and_continue(self):
		source = check(pages()["onboarding/birth-details/done"])["sections"][1]["source"]
		self.assertEqual(source["args"], {"who": "you"})
		self.assertEqual([link["href"] for link in source["links"]], ["/my/birth-profiles/new", "/"])

	def test_the_list_page_is_on_the_my_account_menu_and_adds_a_person(self):
		page = check(pages()["my/birth-profiles"])
		self.assertEqual(page["menu"]["label"], "Birth profiles")
		self.assertEqual(page["sections"][1]["source"]["links"][0]["href"], "/my/birth-profiles/new")

	def test_the_list_always_has_a_place_for_you_until_you_are_filled_in(self):
		user = make_user()
		frappe.set_user(user.name)
		first = api.list_profiles()["items"][0]
		self.assertEqual((first["badge"], first["actions"][0]["href"]), ("You", "/my/birth-profiles/you"))
		self.assertEqual(api.list_profiles(who="you")["items"], [])  # the onboarding summary shows only a saved one
		frappe.set_user("Administrator")
		user.append(TABLE, GOOD)
		user.save(ignore_permissions=True)
		frappe.set_user(user.name)
		items = api.list_profiles()["items"]
		self.assertEqual([i["badge"] for i in items], ["You"])
		self.assertNotEqual(items[0]["id"], "you")

	def test_the_page_for_you_saves_back_to_the_list(self):
		form = form_of(pages()["my/birth-profiles/you"])
		self.assertEqual((form["static_args"], form["success_redirect"]), ({"relationship": "You"}, "/my/birth-profiles"))

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
