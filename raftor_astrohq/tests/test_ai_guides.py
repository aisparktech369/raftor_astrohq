"""The AI guides on the Seek guidance page (ai_guides.py, servicehq card_feeds and presence): data, always online, labelled AI, chat button, no booking."""
import unittest

import frappe

from raftor_astrohq import ai_guides


class TestAIGuides(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		ai_guides.ensure()

	def test_making_them_again_changes_nothing(self):
		before = frappe.db.count("Provider")
		ai_guides.ensure()
		self.assertEqual(frappe.db.count("Provider"), before)

	def test_each_row_of_the_file_is_a_live_provider_with_its_page_its_kind_and_a_public_photo(self):
		for row in ai_guides.rows():
			provider = frappe.db.get_value("Provider", row["slug"], ["status", "ai_guide_page", "photo"], as_dict=True)
			self.assertEqual((provider.status, provider.ai_guide_page), ("Live", row["page"]))
			self.assertTrue(provider.photo.startswith("/files/"))
			self.assertTrue(frappe.db.exists("Provider Persona", {"parent": row["slug"], "persona": row["persona"], "approved": 1}))

	def test_an_ai_guide_is_always_online_and_never_busy_and_a_person_is_unchanged(self):
		from raftor_servicehq import presence

		slug = ai_guides.rows()[0]["slug"]
		self.assertTrue(presence.is_online(slug))
		self.assertFalse(presence.is_busy(slug))
		self.assertTrue(presence.is_available(slug))
		person = frappe.get_all("Provider", filters={"ai_guide_page": ["in", ("", None)], "status": "Live"}, pluck="name", limit=1)
		if person:
			self.assertFalse(presence.is_ai(person[0]))

	def test_its_card_says_ai_and_chat_now_and_opens_its_chat_page_with_no_price_or_rating(self):
		from raftor_servicehq import card_feeds

		for row in ai_guides.rows():
			items = card_feeds.providers(persona=row["persona"], free="0", limit=50)["items"]
			card = next(i for i in items if i["full_name"] == row["name"])
			self.assertEqual((card["badge"], card["button_label"], card["button_url"]), ("AI", "Chat now", "/" + row["page"]))
			self.assertEqual((card["price_was"], card["rating_text"], card.get("button2_label")), ("", "", None))

	def test_the_kind_of_an_ai_guide_is_one_of_the_tiles(self):
		from raftor_servicehq import card_feeds

		tiles = next(f for f in card_feeds.providers()["filters"] if f["name"] == "persona")["options"]
		for row in ai_guides.rows():
			self.assertIn(row["persona"], [t["value"] for t in tiles])
