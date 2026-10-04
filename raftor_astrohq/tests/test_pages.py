"""AstroHQ's page descriptions are accepted by websitehq's page kit, and say what the wireframes say."""
from unittest import TestCase

import frappe

from raftor_astrohq import pages, profiles
from raftor_astrohq.tests.helpers import GOOD, TABLE, make_user
from raftor_websitehq.website_hq.app_pages import check_definition, registered_pages


class TestPages(TestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.form_dict.pop("id", None)
		frappe.db.rollback()

	def test_every_page_is_registered_and_passes_the_kits_checks(self):
		routes = registered_pages()
		for route, fn in {"birth-profiles": pages.birth_profiles, "birth-profiles/new": pages.new_person,
						  "birth-details": pages.birth_details, "birth-details/done": pages.birth_details_done}.items():
			self.assertIn(route, routes)
			self.assertTrue(check_definition(fn())["login_required"], route)
		self.assertIn("birth-profiles/edit", routes)

	def test_onboarding_form_is_for_you_and_has_the_short_field_set(self):
		form = check_definition(pages.birth_details())["blocks"][2]
		self.assertEqual(form["args"], {"relationship": "You"})
		self.assertEqual([f["name"] for f in form["fields"]], ["full_name", "date_of_birth", "time_of_birth", "time_unknown", "place_of_birth"])
		time = next(f for f in form["fields"] if f["name"] == "time_of_birth")
		self.assertEqual(time["disabled_when"], "time_unknown")
		self.assertEqual(form["success"], {"redirect": "/birth-details/done"})

	def test_the_family_form_has_relationship_without_you_and_the_permission_tick(self):
		form = check_definition(pages.new_person())["blocks"][1]
		names = [f["name"] for f in form["fields"]]
		self.assertEqual(names[0], "relationship"); self.assertIn("permission_given", names)
		self.assertNotIn("You", [o["value"] for o in form["fields"][0]["options"]])
		self.assertTrue(next(f for f in form["fields"] if f["name"] == "permission_given")["required"])

	def test_all_set_page_offers_family_and_continue(self):
		blocks = check_definition(pages.birth_details_done())["blocks"]
		self.assertEqual(blocks[0]["current"], len(blocks[0]["steps"]))  # every step shown as done
		self.assertEqual(blocks[2]["args"], {"who": "you"})
		self.assertEqual([l["href"] for l in blocks[3]["links"]], ["/birth-profiles/new", "/"])

	def test_editing_chooses_the_short_form_for_you_and_the_full_one_for_family(self):
		user = make_user()
		user.append(TABLE, GOOD); user.append(TABLE, {**GOOD, "relationship": "Spouse", "full_name": "Ravi", "permission_given": 1})
		user.save(ignore_permissions=True)
		you, spouse = frappe.get_doc("User", user.name).get(TABLE)
		frappe.set_user(user.name)
		frappe.form_dict.id = you.name
		self.assertEqual(check_definition(pages.edit_person())["blocks"][1]["id"], "you")
		frappe.form_dict.id = spouse.name
		self.assertEqual(check_definition(pages.edit_person())["blocks"][1]["id"], "person")
		frappe.form_dict.id = "does-not-exist"
		with self.assertRaises(frappe.DoesNotExistError):
			pages.edit_person()
