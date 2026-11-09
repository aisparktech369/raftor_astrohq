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

	def test_a_guest_is_asked_to_sign_in_and_comes_back_to_the_chat(self):
		from raftor_astrohq import agent_chat

		frappe.set_user("Guest")
		answer = agent_chat.info()
		self.assertEqual(list(answer), ["sign_in"])
		self.assertIn("redirect-to=/ask/pandit-ji", answer["sign_in"]["href"])

	def test_a_signed_in_person_gets_the_agent_and_the_words_and_an_ai_label(self):
		from raftor_astrohq import agent_chat, agents

		answer = agent_chat.info()
		self.assertEqual(answer["blueprint"], agents.BLUEPRINT)
		for key in ("title", "subtitle", "welcome", "placeholder", "send_word", "notice"):
			self.assertTrue(answer[key], key)
		self.assertIn("AI", answer["notice"] + answer["welcome"])
		self.assertIn("cannot", answer["welcome"])  # it says at once that it promises nothing

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
