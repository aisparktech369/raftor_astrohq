"""Taking a plan with monthly auto-pay (PaymentHQ's Sandbox here), keeping it month to month, stopping it, changing it, and the page that shows it."""
import uuid
from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.utils import add_days, add_months, add_to_date, getdate, now_datetime, today

from raftor_astrohq import plan_billing, plans, plans_api
from raftor_astrohq.tests.helpers import GOOD, TABLE
from raftor_paymenthq import lifecycle, mandates, notify as payment_notify
from raftor_paymenthq.gateways import sandbox as sandbox_gateway
from raftor_paymenthq.tests import helpers as pay
from raftor_servicehq.tests.test_booking_api import link_customer


class PlanCase(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.said = []
		self.talk = patch.object(payment_notify, "send", lambda event, user, context: self.said.append((event, user, context)))
		self.talk.start()
		self.payments = pay.sandbox()
		self.payments.__enter__()
		plans.ensure_plans()
		tag = uuid.uuid4().hex[:6]
		self.email = f"plan-{tag}@example.com"
		self.customer = frappe.get_doc({"doctype": "Customer", "customer_name": f"T-PLAN Customer {tag}", "customer_type": "Individual"}).insert(ignore_permissions=True).name
		user = frappe.get_doc({"doctype": "User", "email": self.email, "first_name": "Plan", "send_welcome_email": 0, "user_type": "Website User", "roles": [{"role": "Customer"}]}).insert(ignore_permissions=True)
		user.append(TABLE, GOOD)
		user.save(ignore_permissions=True)
		link_customer(self.email, self.customer)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for dt in ("AI Plan Member", "AI Usage"):
			frappe.db.delete(dt, {"user": self.email})
		pay.drop_everything() if hasattr(pay, "drop_everything") else None
		frappe.db.delete("Contact", {"user": self.email})
		frappe.db.delete("Dynamic Link", {"link_name": self.customer})
		frappe.delete_doc("User", self.email, force=True, ignore_permissions=True)
		frappe.db.delete("Customer", {"name": self.customer})
		frappe.db.commit()
		self.payments.__exit__(None, None, None)
		self.talk.stop()

	# ---- what a person does ----
	def take(self, plan="Seeker"):
		out = plan_billing.start(self.email, plan)
		mandate = frappe.db.get_value("AI Plan Member", self.email, "pending_agreement")
		price = frappe.db.get_value("AI Plan", plan, "monthly_price")
		mandates.confirm(mandate, {"agree": 1, "amount": price})
		return out, mandate

	def member(self):
		return frappe.db.get_value("AI Plan Member", self.email, ["plan", "status", "period_start", "period_end", "months_paid", "renews", "agreement", "pending_plan", "pending_agreement", "charge_asked_for"], as_dict=True)

	def near_the_end_of_the_month(self):
		"""The month the plan is in ends in two days: its anchor is a month before the day after tomorrow's tomorrow."""
		anchor = add_months(add_days(today(), 3), -1)
		frappe.db.set_value("AI Plan Member", self.email, {"period_start": anchor, "months_paid": 1, "period_end": plan_billing.paid_through(anchor, 1)})

	def charge(self, mandate):
		for payment in frappe.get_all("Payment", filters={"mandate": mandate, "workflow_state": "Requested", "method": "Auto-pay"}, pluck="name"):
			frappe.db.set_value("Payment", payment, {"notice_sent_on": add_to_date(now_datetime(), hours=-25), "charge_on": add_to_date(now_datetime(), minutes=-1)})
		mandates.charge_due()


class TestTakingAPlan(PlanCase):
	def test_choosing_a_plan_sends_the_person_to_agree_and_the_plan_is_theirs_when_the_first_payment_arrives(self):
		out = plan_billing.start(self.email, "Seeker")
		self.assertIn("/my/auto-pay/agree?mandate=", out["redirect"])
		waiting = self.member()
		self.assertEqual((waiting.status, waiting.pending_plan), ("Waiting", "Seeker"))
		self.assertFalse(plans.plan_of(self.email).taken)  # nothing is theirs yet
		mandates.confirm(waiting.pending_agreement, {"agree": 1, "amount": 149})
		now = self.member()
		self.assertEqual((now.plan, now.status, now.months_paid, now.renews, now.pending_agreement), ("Seeker", "Active", 1, 1, None))
		self.assertEqual(now.period_end, plan_billing.paid_through(now.period_start, 1))
		self.assertEqual((plans.plan_of(self.email).plan_name, plans.plan_of(self.email).taken), ("Seeker", True))

	def test_a_plan_that_costs_nothing_or_is_off_cannot_be_taken(self):
		with self.assertRaises(frappe.ValidationError):
			plan_billing.start(self.email, "Free")
		frappe.db.set_value("AI Plan", "Needy", "enabled", 0)
		with self.assertRaises(frappe.ValidationError):
			plan_billing.start(self.email, "Needy")

	def test_a_person_who_does_not_agree_is_left_with_no_plan(self):
		plan_billing.start(self.email, "Seeker")
		self.assertEqual(mandates.confirm(self.member().pending_agreement, {}), "Failed")
		now = self.member()
		self.assertEqual((now.status, now.pending_agreement), ("Ended", None))
		self.assertFalse(plans.plan_of(self.email).taken)

	def test_an_agreement_never_completed_lapses_and_the_plan_is_never_taken(self):
		plan_billing.start(self.email, "Needy")
		payment = frappe.db.get_value("Payment", {"mandate": self.member().pending_agreement, "method": "Online"}, "name")
		frappe.db.set_value("Payment", payment, "window_until", add_to_date(now_datetime(), minutes=-1))
		lifecycle.expire_lapsed()
		self.assertEqual((self.member().status, self.member().pending_agreement), ("Ended", None))

	def test_taking_the_plan_you_already_have_is_refused_and_changing_to_another_stops_the_old_agreement(self):
		_, first = self.take("Seeker")
		with self.assertRaises(frappe.ValidationError):
			plan_billing.start(self.email, "Seeker")
		_, second = self.take("Needy")
		now = self.member()
		self.assertEqual((now.plan, now.agreement, now.months_paid), ("Needy", second, 1))
		self.assertEqual(mandates.state(first), "Cancelled")


class TestKeepingIt(PlanCase):
	def test_next_month_is_asked_a_few_days_early_taken_after_notice_and_asked_only_once(self):
		_, mandate = self.take("Seeker")
		self.assertEqual(plan_billing.request_renewals(), 0)  # the month has just begun
		self.near_the_end_of_the_month()
		self.assertEqual(plan_billing.request_renewals(), 1)
		self.assertEqual(plan_billing.request_renewals(), 0)  # asked already
		before = self.member()
		self.assertEqual(before.months_paid, 1)
		self.charge(mandate)
		after = self.member()
		self.assertEqual(after.months_paid, 2)
		self.assertEqual(after.period_end, plan_billing.paid_through(after.period_start, 2))
		self.assertEqual(after.period_start, before.period_start)  # the month the replies count in is not moved early

	def test_a_renewal_heard_twice_extends_only_once(self):
		_, mandate = self.take("Seeker")
		self.near_the_end_of_the_month()
		plan_billing.request_renewals()
		self.charge(mandate)
		payment = frappe.get_doc("Payment", frappe.db.get_value("Payment", {"mandate": mandate, "method": "Auto-pay"}, "name"))
		plan_billing.paid(payment)
		self.assertEqual(self.member().months_paid, 2)

	def test_a_refused_renewal_is_not_extended_and_the_plan_ends_with_its_month(self):
		_, mandate = self.take("Seeker")
		self.near_the_end_of_the_month()
		plan_billing.request_renewals()
		sandbox_gateway.fail_next(mandate, 1)
		self.addCleanup(frappe.cache().delete_value, f"paymenthq_sandbox_fail:{mandate}")
		self.charge(mandate)
		self.assertEqual(self.member().months_paid, 1)
		frappe.db.set_value("AI Plan Member", self.email, "period_end", add_days(today(), -1))
		self.assertEqual(plan_billing.end_lapsed(), 1)
		self.assertEqual((self.member().status, plans.plan_of(self.email).taken), ("Ended", False))

	def test_stopping_keeps_the_plan_to_the_end_of_the_month_and_nothing_more_is_asked(self):
		_, mandate = self.take("Needy")
		said = plan_billing.stop(self.email)["message"]
		self.assertIn("Needy plan will not renew", said)
		self.assertEqual((self.member().renews, mandates.state(mandate)), (0, "Cancelled"))
		self.assertTrue(plans.plan_of(self.email).taken)
		self.near_the_end_of_the_month()
		self.assertEqual(plan_billing.request_renewals(), 0)
		with self.assertRaises(frappe.ValidationError):
			plan_billing.stop(self.email)  # nothing left to stop

	def test_an_agreement_that_has_ended_stops_the_plan_renewing(self):
		_, mandate = self.take("Seeker")
		mandates.cancel(mandate, "customer", "stopped at the bank")
		self.assertEqual(plan_billing.check_agreements(), 1)
		self.assertEqual(self.member().renews, 0)

	def test_the_months_are_counted_from_the_day_the_plan_began(self):
		jan31 = getdate("2027-01-31")
		self.assertEqual(plans.month_window(jan31, getdate("2027-02-10")), (getdate("2027-01-31"), getdate("2027-02-27")))
		self.assertEqual(plans.month_window(jan31, getdate("2027-02-28")), (getdate("2027-02-28"), getdate("2027-03-30")))
		self.assertEqual(plans.month_window(jan31, getdate("2027-03-31"))[0], getdate("2027-03-31"))
		self.assertEqual(plan_billing.paid_through(jan31, 2), getdate("2027-03-30"))


class TestThePage(PlanCase):
	def cards(self):
		frappe.set_user(self.email)
		return {c["id"]: c for c in plans_api.plan_cards()["items"]}

	def test_the_page_shows_the_plan_the_use_and_the_plans_with_a_button_for_each_paid_one(self):
		plans.record_reply(self.email)
		cards = self.cards()
		self.assertEqual(list(cards), ["now", "Free", "Seeker", "Needy"])
		self.assertEqual(cards["now"]["title"], "Your plan: Free")
		self.assertTrue(any("1 / 100" in line for line in cards["now"]["lines"]))
		self.assertEqual(cards["Free"]["badge"], "Your plan")
		self.assertEqual([a["args"] for a in cards["Seeker"]["actions"]], [{"plan": "Seeker"}])
		self.assertIn("149", cards["Seeker"]["title"])
		self.assertEqual(cards["Free"]["actions"], [])

	def test_after_taking_a_plan_the_page_says_when_it_renews_and_offers_to_change_or_stop(self):
		self.take("Seeker")
		cards = self.cards()
		self.assertEqual(cards["now"]["title"], "Your plan: Seeker")
		self.assertTrue(cards["now"]["badge"].startswith("Renews on"))
		self.assertEqual([a["label"] for a in cards["now"]["actions"]], ["Stop renewing"])
		self.assertEqual(cards["Seeker"]["badge"], "Your plan")
		self.assertEqual(cards["Seeker"]["actions"], [])
		self.assertEqual(cards["Needy"]["actions"][0]["label"], "Change to Needy")
		self.assertIn("charged now", cards["Needy"]["actions"][0]["confirm"])

	def test_buying_and_stopping_are_for_the_signed_in_person_only(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			plans_api.plan_cards()
		frappe.set_user(self.email)
		self.assertIn("redirect", plans_api.start("Seeker"))

	def test_the_plans_page_says_which_plan_the_signed_in_person_is_on(self):
		frappe.set_user("Guest")
		self.assertEqual(plans_api.strip(), {"items": []})  # a visitor who has not signed in sees only the boxes
		frappe.set_user(self.email)
		card = plans_api.strip()["items"][0]
		self.assertEqual((card["title"], card["badge"]), ("You are on the Free plan", "No cost"))
		self.assertEqual([a["href"] for a in card["actions"]], [plans.MY_PLAN_PAGE])
		self.take("Seeker")
		card = plans_api.strip()["items"][0]
		self.assertEqual(card["title"], "You are on the Seeker plan")
		self.assertTrue(card["badge"].startswith("Renews on"))
		self.assertIn("of 300 AI replies used this month", card["lines"][0])

	def test_the_choose_page_confirms_a_paid_plan_before_the_person_is_sent_to_agree_to_auto_pay(self):
		frappe.set_user(self.email)
		card = plans_api.choose_card("Seeker")["items"][0]
		self.assertEqual(card["title"], "Seeker · ₹149 a month")
		self.assertEqual(card["lines"][1:1 + len(plans.limit_lines(frappe._dict(frappe.db.get_value("AI Plan", "Seeker", plans.FIELDS, as_dict=True))))], plans.limit_lines(frappe._dict(frappe.db.get_value("AI Plan", "Seeker", plans.FIELDS, as_dict=True))))
		self.assertIn("₹149 is charged now, and then each month", card["lines"][-1])
		self.assertEqual([(a["label"], a["call"], a["args"]) for a in card["actions"]], [("Agree and pay ₹149", "raftor_astrohq.plans_api.start", {"plan": "Seeker"})])
		for plan in ("Free", "Nope", ""):  # nothing to pay, or no such plan
			self.assertEqual(plans_api.choose_card(plan), {"items": []}, plan)
		frappe.db.set_value("AI Plan", "Needy", "enabled", 0)
		self.assertEqual(plans_api.choose_card("Needy"), {"items": []})

	def test_the_choose_page_for_someone_who_has_a_plan_says_so_or_what_changing_costs(self):
		self.take("Seeker")
		frappe.set_user(self.email)
		own = plans_api.choose_card("Seeker")["items"][0]
		self.assertEqual((own["badge"], own["actions"]), ("Your plan", []))
		change = plans_api.choose_card("Needy")["items"][0]
		self.assertEqual([a["label"] for a in change["actions"]], ["Change to Needy and pay ₹399"])
		self.assertIn("takes the place of the rest of this one", change["lines"][-1])

	def test_the_choose_page_is_for_the_signed_in_person_and_staff_are_not_sold_a_plan(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			plans_api.choose_card("Seeker")
		frappe.set_user("Administrator")
		self.assertEqual(plans_api.choose_card("Seeker")["items"][0]["actions"], [])
		self.assertEqual(plans_api.strip(), {"items": []})

	def test_the_bar_fills_with_use(self):
		self.assertEqual(plans_api._bar(0, 100), "░" * 10)
		self.assertEqual(plans_api._bar(50, 100), "█" * 5 + "░" * 5)
		self.assertEqual(plans_api._bar(150, 100), "█" * 10)
		self.assertEqual(plans_api._bar(3, 0), "█" * 10)


class TestTheReportLimit(PlanCase):
	def test_the_websites_free_report_form_asks_the_plan_before_it_makes_another(self):
		from raftor_servicehq import free_reports

		frappe.db.set_value("AI Plan", "Free", "reports_per_month", 0)
		with self.assertRaises(frappe.ValidationError) as caught:
			free_reports.check_limit(self.email)
		self.assertIn("makes 0 reports a month", str(caught.exception))
		frappe.db.set_value("AI Plan", "Free", "reports_per_month", 5)
		free_reports.check_limit(self.email)  # room again: no error
