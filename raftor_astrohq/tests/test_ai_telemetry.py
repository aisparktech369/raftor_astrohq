"""What the AI guides use and cost: the daily token cap of a guide, the guide resting kindly, and the staff stats page keeping to the team."""
from unittest.mock import patch

import frappe

from raftor_astrohq import ai_telemetry, plan_rules, stats_page
from raftor_astrohq.tests.helpers import AstroTestCase


class TestAITelemetry(AstroTestCase):
	def test_a_guide_with_no_cap_is_never_over_it_and_one_with_a_cap_is_over_it_once_the_tokens_are_used(self):
		with patch.object(frappe.db, "get_value", return_value=0), patch.object(ai_telemetry, "tokens_today", return_value=10**9):
			self.assertFalse(ai_telemetry.over_cap("maya-kapoor"))  # 0 is no cap
		with patch.object(frappe.db, "get_value", return_value=1000):
			with patch.object(ai_telemetry, "tokens_today", return_value=999):
				self.assertFalse(ai_telemetry.over_cap("maya-kapoor"))
			with patch.object(ai_telemetry, "tokens_today", return_value=1000):
				self.assertTrue(ai_telemetry.over_cap("maya-kapoor"))

	def test_a_guide_over_its_cap_rests_with_a_kind_word_and_any_other_guide_carries_on(self):
		with patch.object(ai_telemetry, "over_cap", side_effect=lambda guide: guide == "maya-kapoor"), patch("raftor_astrohq.ai_minutes.allowance", return_value={"ok": True}):
			resting = plan_rules.allowance("someone@example.com", "tarot", "maya-kapoor")
			self.assertEqual((resting["ok"], resting["reason"]), (False, "guide_rest"))
			self.assertIn("tomorrow", resting["message"])
			self.assertTrue(plan_rules.allowance("someone@example.com", "tarot", "leela-das")["ok"])
			self.assertTrue(plan_rules.allowance("someone@example.com", "tarot")["ok"])  # a chat that names no guide is only counted by minutes

	def test_the_stats_page_is_for_the_team_only(self):
		frappe.set_user("Guest")
		try:
			for method in (stats_page.summary, stats_page.guides, stats_page.weekly):
				self.assertRaises(frappe.PermissionError, method)
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(stats_page.summary()["items"] is not None)

	def test_the_cost_of_a_turn_follows_the_rate_card_and_is_nothing_without_one(self):
		from raftor_agentshq.api import queue

		with patch.object(frappe, "get_cached_doc", return_value=frappe._dict(token_cost_in=0, token_cost_out=0)):
			self.assertIsNone(queue.turn_cost(1000, 500))
		with patch.object(frappe, "get_cached_doc", return_value=frappe._dict(token_cost_in=40, token_cost_out=160)):
			self.assertEqual(queue.turn_cost(1_000_000, 500_000), 120.0)
