from unittest import TestCase

import frappe


class TestAgentChat(TestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def setUp(self):
		if "raftor_agentshq" not in frappe.get_installed_apps():
			self.skipTest("AgentsHQ is not installed")
		from raftor_astrohq import agents

		agents.ensure_blueprint()

	def test_a_guest_meets_the_agents_sign_up_conversation_in_its_own_words(self):
		from raftor_astrohq import agent_chat

		frappe.set_user("Guest")
		answer = agent_chat.info()
		self.assertNotIn("blueprint", answer)  # no agent is reached before there is an account
		self.assertTrue(answer["gate"]["greeting"].startswith("Hi, I'm Pandit ji"))
		self.assertNotIn("promise", answer["gate"]["greeting"])  # casual first; the disclaimer is the small line at the bottom
		self.assertIn("promise", answer["notice"])
		self.assertIn("{name}", answer["gate"]["ask_contact"])
		self.assertEqual(answer["gate"]["contacts"], ["phone", "email"])

	def test_with_no_conversation_a_guest_is_asked_to_sign_in_and_comes_back_to_the_chat(self):
		from unittest.mock import patch

		from raftor_astrohq import agent_chat

		frappe.set_user("Guest")
		with patch.object(agent_chat, "_gate", return_value=None):
			answer = agent_chat.info()
		self.assertEqual(list(answer), ["sign_in"])
		self.assertIn("redirect-to=/ask/pandit-ji", answer["sign_in"]["href"])

	def test_a_signed_in_person_gets_the_agent_and_the_words_and_an_ai_label(self):
		from raftor_astrohq import agent_chat, agents

		answer = agent_chat.info()
		self.assertEqual(answer["blueprint"], agents.BLUEPRINT)
		for key in ("title", "subtitle", "welcome", "placeholder", "send_word", "notice"):
			self.assertTrue(answer[key], key)
		self.assertIn("AI", answer["notice"])
		self.assertIn("promise", answer["notice"])  # the disclaimer is the small line under the chat, not the first thing it says
		self.assertNotIn("promise", answer["welcome"])
		self.assertLess(len(answer["welcome"]), 80)

	def test_a_switched_off_agent_draws_no_chat(self):
		from raftor_astrohq import agent_chat, agents

		frappe.db.set_value("Blueprint Reference", agents.BLUEPRINT, "is_active", 0)
		answer = agent_chat.info()
		self.assertNotIn("blueprint", answer)
		self.assertTrue(answer["notice"])

	def test_the_page_is_defined_with_the_chat_card(self):
		from raftor_astrohq import page_definitions

		page = next(p for p in page_definitions.definitions() if p["route"] == "ask/pandit-ji")
		cards = [c for section in page["sections"] for c in section.get("cards", [])]
		self.assertEqual([(c["type"], c["values"]["info"]) for c in cards], [("App Chat Card", "raftor_astrohq.agent_chat.info")])


class TestConversionNeedsAnAccount(TestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_a_guest_can_add_nothing_to_a_cart_book_nothing_and_buy_no_seat(self):
		from raftor_servicehq import booking_api, shop_orders
		from webshop.webshop.shopping_cart.cart import update_cart

		frappe.set_user("Guest")
		for call in (lambda: update_cart("RUD005", 1), lambda: booking_api.book("SVC-14009", "2099-01-01 09:00:00", {}), lambda: shop_orders.add_event_seats("EVT-X", 1)):
			with self.assertRaises(frappe.PermissionError):
				call()


class TestGuideButton(TestCase):
	def test_the_guide_opens_the_chat_page_and_stays_out_of_the_way_on_its_own_page_and_the_sign_in(self):
		from raftor_astrohq import agent_chat

		guide = agent_chat.guide()
		self.assertEqual(guide["url"], "/ask/pandit-ji")
		self.assertTrue(guide["icon"].startswith("/") and guide["title"] and guide["label"])
		self.assertIn("/ask/pandit-ji", guide["hide_on"])
		self.assertIn("/login", guide["hide_on"])
