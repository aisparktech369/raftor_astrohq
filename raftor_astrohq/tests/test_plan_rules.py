"""AstroHQ comes with its plans (plans.json: Lite, Plus, Pro and their quotas, installed by servicehq's plans feature), and says what they count: the time with the AI astrologers, and the people in the profiles."""
import json
from pathlib import Path
from unittest import TestCase

import frappe

from raftor_astrohq import install, person, plan_rules
from raftor_astrohq.tests.helpers import GOOD, TABLE, AstroTestCase, make_user
from raftor_servicehq import plans

DATA = json.loads((Path(install.__file__).parent / "plans.json").read_text(encoding="utf-8"))


def items(plan: str) -> dict:
	return {i["item_key"]: i for i in next(p for p in DATA["plans"] if p["plan_name"] == plan)["items"]}


def _user(people=1):
	user = make_user()
	user.append(TABLE, GOOD)
	for n in range(people - 1):
		user.append(TABLE, {**GOOD, "relationship": "Sibling", "full_name": f"Sibling {n}", "permission_given": 1})
	user.save(ignore_permissions=True)
	return user.name


class TestTheDataFile(TestCase):
	def test_the_plans_and_their_quotas_are_the_ones_agreed(self):
		self.assertEqual([(p["plan_name"], p["price"]) for p in DATA["plans"]], [("Lite", 0), ("Plus", 199), ("Pro", 399)])
		self.assertEqual([items(p)["ai_minutes"]["quota"] for p in ("Lite", "Plus", "Pro")], [30, 100, 300])
		self.assertEqual([items(p)["family_profiles"]["quota"] for p in ("Lite", "Plus", "Pro")], [1, 6, 15])
		for plan in ("Lite", "Plus", "Pro"):
			self.assertIn("10 minutes", items(plan)["live_session"]["note"])  # the first live session, with a real astrologer
			for key in ("free_reports", "panchang", "academy"):
				self.assertEqual(items(plan)[key]["period"], "Unlimited")  # always free, counted for the stats
		self.assertTrue({"free_live_session", "family_matching", "free_rudraksh"} <= set(items("Plus")))
		self.assertTrue({"divine_discount", "priority"} <= set(items("Pro")) and not {"divine_discount", "priority"} & set(items("Plus")))

	def test_every_item_is_one_servicehq_knows_and_no_plan_says_free_in_its_name(self):
		kinds = {"Month", "Once", "Total", "Unlimited", "Included"}
		meta = frappe.get_meta("Plan Item")
		for plan in DATA["plans"]:
			self.assertNotIn("free", plan["plan_name"].lower())
			for item in plan["items"]:
				self.assertIn(item["period"], kinds)
				self.assertFalse(set(item) - {f.fieldname for f in meta.fields}, item["item_key"])

	def test_the_cards_at_a_limit_lead_to_the_plans_and_to_live_astrologers(self):
		from raftor_websitehq.website_hq.page_groups import page_url

		cards = {p["plan_name"]: [DATA["cards"][c]["url"] for c in p["cards"]] for p in DATA["plans"]}
		self.assertEqual(cards["Lite"], [plans.PLANS_PAGE, page_url("consult")])
		self.assertEqual(cards["Pro"], [page_url("consult")])  # the top plan is not sent to a plan above it

	def test_the_plans_are_installed_on_this_site_as_astrohqs(self):
		for plan in DATA["plans"]:
			self.assertEqual(frappe.db.get_value("Subscription Plan", plan["plan_name"], ["vertical", "in_boxes"]), ("astrohq", 1), plan["plan_name"])
		self.assertEqual([p.name for p in plans.offered("astrohq")][:3], ["Lite", "Plus", "Pro"])


class TestWhatAstroHQCounts(AstroTestCase):
	def test_the_ai_astrologers_answer_until_the_persons_minutes_are_used_up_then_say_so_with_the_plans(self):
		user = _user()
		self.assertTrue(plan_rules.allowance(user, "pandit_ji")["ok"])
		plans.use(user, plan_rules.AI_MINUTES, 30)
		gate = plan_rules.allowance(user, "pandit_ji")
		self.assertFalse(gate["ok"])
		self.assertIn("30 minutes of AI astrologers on your Lite plan", gate["message"])
		self.assertIn("The Plus plan gives you 100 minutes", gate["message"])
		self.assertEqual([c["url"] for c in gate["cards"]], [plans.PLANS_PAGE, "/consult"])
		plans.assign(user, "Plus")
		self.assertTrue(person.allowance(user, "pandit_ji")["ok"])  # AgentsHQ asks the person module

	def test_an_answer_counts_the_minutes_the_person_was_talking_and_staff_and_visitors_are_not_limited(self):
		user = _user()
		person.turn_done(user, "pandit_ji")
		self.assertEqual(plans.used(user, plan_rules.AI_MINUTES), plans.FIRST)
		for who in ("Administrator", "Guest"):
			self.assertTrue(plan_rules.allowance(who, "pandit_ji")["ok"])
			plan_rules.turn_done(who, "pandit_ji")
		self.assertFalse(frappe.db.exists("Plan Usage", {"user": ["in", ["Administrator", "Guest"]], "item_key": plan_rules.AI_MINUTES}))

	def test_the_people_a_profile_may_hold_follow_the_plan(self):
		user = _user()
		self.assertEqual(plan_rules.family_room(user), 0)  # Lite keeps one person: the person themselves
		self.assertIn("1 person", plan_rules.family_words(user))
		plans.assign(user, "Plus")
		self.assertEqual(plan_rules.family_room(user), 5)
		plans.assign(user, "Pro")
		self.assertEqual(plan_rules.family_room(user), 14)
		self.assertEqual(plan_rules.family_room("Administrator"), plan_rules.UNLIMITED)

	def test_a_report_is_always_free_so_a_plan_does_not_count_it_but_the_stats_do(self):
		user = _user()
		day = f"{frappe.utils.getdate()}|free_reports"
		before = frappe.db.get_value("Plan Day", day, "events") or 0
		plans.use(user, "free_reports")
		self.assertEqual(frappe.db.get_value("Plan Day", day, "events"), before + 1)
		self.assertTrue(plans.check(user, "free_reports")["ok"])
