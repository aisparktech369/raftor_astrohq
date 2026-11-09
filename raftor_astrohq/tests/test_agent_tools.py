from unittest import TestCase

import frappe

KEYS = {"title", "shelf", "topic", "status", "bookable", "price", "price_before_offer", "book_link", "button"}


class TestServiceTools(TestCase):
	def setUp(self):
		try:
			from raftor_astrohq.assistant_tools import services
		except ImportError:
			self.skipTest("FAC is not installed on this site")
		self.services = services
		if not frappe.db.count("Service"):
			self.skipTest("no services on this site")

	def test_find_services_gives_cards_with_a_price_and_a_state(self):
		found = self.services.FindServices().execute({"limit": 5})
		self.assertGreater(found["count"], 0)
		for card in found["services"]:
			self.assertEqual(set(card), KEYS)
			self.assertIn(card["status"], ("Bookable now", "Coming soon"))
			self.assertEqual(card["bookable"], card["status"] == "Bookable now" and bool(card["book_link"]))

	def test_a_service_that_is_coming_soon_has_no_link_to_book(self):
		for card in self.services.FindServices().execute({"limit": 12})["services"]:
			if card["status"] == "Coming soon":
				self.assertEqual(card["book_link"], "")

	def test_search_and_bookable_only_narrow_the_list(self):
		everything = self.services.FindServices().execute({"limit": 12})["services"]
		word = everything[0]["title"].split()[0].lower()
		hits = self.services.FindServices().execute({"search": word, "limit": 12})["services"]
		self.assertTrue(hits and all(word in f"{c['title']} {c['topic']} {c['shelf']}".lower() for c in hits))
		for card in self.services.FindServices().execute({"bookable_only": True, "limit": 12})["services"]:
			self.assertTrue(card["bookable"])

	def test_get_service_finds_one_by_name_and_says_so_when_there_is_none(self):
		title = self.services.FindServices().execute({"limit": 1})["services"][0]["title"]
		one = self.services.GetService().execute({"title": title})
		self.assertTrue(one["found"])
		self.assertEqual(one["title"], title)
		self.assertIn("how_to_book", one)
		self.assertFalse(self.services.GetService().execute({"title": "no such service anywhere"})["found"])

	def test_the_tools_change_nothing(self):
		before = frappe.db.count("Booking") if frappe.db.exists("DocType", "Booking") else 0
		self.services.FindServices().execute({})
		self.services.GetService().execute({"title": "Griha pravesh pooja"})
		after = frappe.db.count("Booking") if frappe.db.exists("DocType", "Booking") else 0
		self.assertEqual(before, after)


class TestPanditJiRecord(TestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_the_agent_is_registered_for_signed_in_customers_only_and_left_alone_once_it_is(self):
		from raftor_astrohq import agents

		if "raftor_agentshq" not in frappe.get_installed_apps():
			self.skipTest("AgentsHQ is not installed")
		agents.ensure_blueprint()
		bp = frappe.db.get_value("Blueprint Reference", agents.BLUEPRINT, ["is_active", "is_public", "agent_role", "blueprint_type"], as_dict=True)
		self.assertEqual((bp.is_active, bp.is_public, bp.agent_role, bp.blueprint_type or ""), (1, 0, "Customer", ""))
		frappe.db.set_value("Blueprint Reference", agents.BLUEPRINT, "is_active", 0)  # staff switch it off
		agents.ensure_blueprint()
		self.assertEqual(frappe.db.get_value("Blueprint Reference", agents.BLUEPRINT, "is_active"), 0)
