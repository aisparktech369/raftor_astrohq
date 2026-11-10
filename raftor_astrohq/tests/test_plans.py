"""The three monthly plans: Free, Seeker, Needy. What each allows, what a person has used, and the words a guide says when a limit is reached."""
import frappe
from frappe.utils import add_days, getdate, today

from raftor_astrohq import person, plans, profiles
from raftor_astrohq.tests.helpers import GOOD, TABLE, AstroTestCase, make_user

DREAMER = "dream_guide"


def _user(profiles_count=1):
	user = make_user()
	user.append(TABLE, GOOD)
	for i in range(profiles_count - 1):
		user.append(TABLE, {**GOOD, "relationship": "Sibling", "full_name": f"Sibling {i}", "permission_given": 1})
	user.save(ignore_permissions=True)
	return user.name


def _set(plan, **values):
	frappe.db.set_value("AI Plan", plan, values)


class TestThePlans(AstroTestCase):
	def test_the_three_plans_exist_in_order_and_are_left_alone_once_edited(self):
		plans.ensure_plans()
		rows = frappe.get_all("AI Plan", fields=["plan_name", "monthly_price", "replies_per_month"], order_by="sort_order asc")
		self.assertEqual([r.plan_name for r in rows], ["Free", "Seeker", "Needy"])
		self.assertEqual(rows[0].monthly_price, 0)
		self.assertLess(rows[1].monthly_price, rows[2].monthly_price)
		_set("Seeker", replies_per_month=77)
		plans.ensure_plans()
		self.assertEqual(frappe.db.get_value("AI Plan", "Seeker", "replies_per_month"), 77)

	def test_a_person_with_no_plan_has_free_and_a_month_is_the_calendar_month(self):
		plan = plans.plan_of(_user())
		self.assertEqual(plan.plan_name, "Free")
		self.assertEqual((plan.period_start.day, plan.period_end >= getdate(today())), (1, True))

	def test_a_plan_taken_runs_for_a_month_then_it_is_free_again(self):
		user = _user()
		plans.assign(user, "Seeker", days=31)
		self.assertEqual(plans.plan_of(user).plan_name, "Seeker")
		frappe.db.set_value("AI Plan Member", user, "period_end", add_days(today(), -1))
		self.assertEqual(plans.plan_of(user).plan_name, "Free")
		plans.assign(user, "Needy")
		plans.assign(user, "Free")
		self.assertEqual(plans.plan_of(user).plan_name, "Free")


class TestWhatAGuideMayDo(AstroTestCase):
	def test_replies_are_counted_and_the_month_runs_out_with_the_words_of_the_plan(self):
		user = _user()
		_set("Free", replies_per_month=3, replies_per_day=10)
		for _ in range(3):
			self.assertTrue(plans.allowance(user, "pandit_ji")["ok"])
			plans.record_reply(user, "pandit_ji")
		gate = plans.allowance(user, "pandit_ji")
		self.assertFalse(gate["ok"])
		self.assertEqual(gate["reason"], "month")
		self.assertIn("all 3 replies of your Free plan", gate["message"])
		self.assertIn("The Seeker plan gives you 300 replies a month.", gate["message"])
		self.assertRegex(gate["message"], r"start again on \d{1,2} \w+")

	def test_the_day_has_its_own_pace(self):
		user = _user()
		_set("Free", replies_per_month=50, replies_per_day=2)
		plans.record_reply(user)
		plans.record_reply(user)
		gate = plans.allowance(user, "pandit_ji")
		self.assertEqual((gate["ok"], gate["reason"]), (False, "day"))
		self.assertIn("2 replies a day", gate["message"])
		frappe.db.set_value("AI Usage", f"{user}|{plans.plan_of(user).period_start}", "day", add_days(today(), -1))
		self.assertTrue(plans.allowance(user, "pandit_ji")["ok"])  # a new day

	def test_the_top_plan_has_no_upgrade_to_offer(self):
		user = _user()
		plans.assign(user, "Needy")
		_set("Needy", replies_per_month=1)
		plans.record_reply(user)
		message = plans.allowance(user, "pandit_ji")["message"]
		self.assertIn("Needy", message)
		self.assertNotIn("plan gives you", message)

	def test_a_plan_can_name_the_guides_it_allows(self):
		user = _user()
		_set("Free", guides="pandit_ji")
		self.assertTrue(plans.allowance(user, "pandit_ji")["ok"])
		gate = plans.allowance(user, DREAMER)
		self.assertEqual((gate["ok"], gate["reason"]), (False, "guide"))
		self.assertIn("not part of your Free plan", gate["message"])

	def test_staff_and_guests_are_not_limited_or_counted(self):
		_set("Free", replies_per_month=0)
		self.assertTrue(plans.allowance("Administrator", "pandit_ji")["ok"])
		self.assertTrue(plans.allowance("Guest", "pandit_ji")["ok"])
		plans.record_reply("Administrator")
		self.assertFalse(frappe.db.exists("AI Usage", {"user": "Administrator"}))


class TestTheOtherLimits(AstroTestCase):
	def test_the_people_in_the_profiles_are_limited_and_a_guide_adds_no_one_past_it(self):
		user = _user()  # You
		self.assertEqual(plans.family_room(user), 1)  # Free keeps two
		self.assertIsNotNone(person._add_member(user, "Rhenna (daughter)", {"name": "Rhenna"}))
		self.assertEqual(plans.family_room(user), 0)
		self.assertIsNone(person._add_member(user, "Tara (daughter)", {"name": "Tara"}))
		self.assertIn("keeps 2 people", plans.family_words(user))
		plans.assign(user, "Seeker")
		self.assertGreater(plans.family_room(user), 0)

	def test_the_website_refuses_one_person_too_many_with_the_plans_words(self):
		from raftor_astrohq import api

		user = _user(profiles_count=2)  # Free is full
		frappe.set_user(user)
		out = api.save_profile(values={"relationship": "Spouse", "full_name": "Ravi Rao", "date_of_birth": "1988-03-02", "time_unknown": 1, "place_of_birth": "Jaipur, India", "permission_given": 1})
		self.assertFalse(out["ok"])
		self.assertIn("keeps 2 people", out["errors"]["full_name"])

	def test_a_guide_reads_as_many_notes_as_the_plan_says(self):
		user = _user()
		person.write(user, {"notes": [{"about": "You", "kind": "fact", "point": f"Note number {i}"} for i in range(14)]}, "g", "s")
		_set("Free", notes_read=5)
		self.assertEqual(len(person.read(user, "pandit_ji")["notes"]), 5)
		plans.assign(user, "Seeker")
		self.assertEqual(len(person.read(user, "pandit_ji")["notes"]), 14)

	def test_reports_are_limited_by_the_plan_in_the_guides_path(self):
		user = _user()
		_set("Free", reports_per_month=1)
		first = person.read_report(user, "me", "numerology", "numerology-guide-agent@agents.astrohq.in")
		self.assertTrue(first["newly_made"])
		self.assertEqual(plans.reports_left(user), 0)
		profile = frappe.get_doc("User", user).get(TABLE)[0]
		profile.full_name = "Asha Rao Second"
		frappe.get_doc("User", user).save(ignore_permissions=True)
		second = person.read_report(user, "me", "numerology", "numerology-guide-agent@agents.astrohq.in")
		self.assertTrue(second["found"])  # the summary is still given
