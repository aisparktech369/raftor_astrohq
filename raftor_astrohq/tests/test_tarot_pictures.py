"""A card's picture comes from the factory, delivered by AgentsHQ, and the same address serves the page, the Academy and the chat; a card with none is drawn from its symbol."""
from unittest import TestCase
from unittest.mock import patch

from raftor_astrohq import tarot_deck


class TestTarotPictures(TestCase):
	def test_the_factorys_picture_is_the_one_used_and_its_address_is_asked_by_the_cards_id(self):
		with patch("raftor_agentshq.media.url", return_value="/files/factory/astrohq/tarot/00-fool.webp") as asked:
			self.assertEqual(tarot_deck.image("00-fool"), "/files/factory/astrohq/tarot/00-fool.webp")
		asked.assert_called_once_with("astrohq", "tarot/00-fool")

	def test_with_nothing_delivered_an_earlier_version_s_folder_is_the_fallback_and_then_nothing(self):
		with patch("raftor_agentshq.media.url", return_value=""), patch("os.path.exists", side_effect=lambda p: p.endswith("/public/tarot/back.png")):
			self.assertEqual(tarot_deck.image("back"), "/assets/raftor_astrohq/tarot/back.png")
		with patch("raftor_agentshq.media.url", return_value=""), patch("os.path.exists", return_value=False):
			self.assertEqual(tarot_deck.image("01-magician"), "")  # no picture: the page draws the card from its symbol

	def test_the_page_the_chat_and_the_academy_give_a_card_the_same_address(self):
		from raftor_astrohq import tarot

		with patch("raftor_agentshq.media.url", side_effect=lambda domain, name: f"/files/factory/{domain}/{name}.webp"):
			spread = tarot_deck.spread("three-card-spread")
			page = tarot._card({"id": "00-fool", "r": False}, spread, 0)["image"]
			self.assertEqual(page, tarot_deck.image("00-fool"))
			self.assertEqual(page, "/files/factory/astrohq/tarot/00-fool.webp")
