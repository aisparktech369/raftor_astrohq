"""AI minutes bought during a chat: counted after the plan's free minutes, shown to the person, given once when an order is paid."""
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from raftor_astrohq import ai_minutes
from raftor_astrohq.tests.helpers import AstroTestCase, make_user


def _credit(user, minutes, **values):
	return frappe.get_doc({"doctype": "AI Minute Credit", "user": user, "minutes_bought": minutes, "minutes_left": minutes, "bought_on": values.pop("bought_on", frappe.utils.now_datetime()), **values}).insert(ignore_permissions=True)


class TestAIMinutes(AstroTestCase):
	def test_the_counter_adds_free_and_bought_minutes_and_warns_when_few(self):
		user = make_user().name
		with patch.object(ai_minutes, "_limited", return_value=True):
			with patch.object(ai_minutes, "plan_left", return_value=2.0):
				self.assertTrue(ai_minutes.status(user)["low"])
			with patch.object(ai_minutes, "plan_left", return_value=0.0):
				self.assertTrue(ai_minutes.status(user)["out"])
				_credit(user, 10)
				now = ai_minutes.status(user)
				self.assertEqual((now["left"], now["bought"], now["out"], now["low"]), (10.0, 10.0, False, False))
			with patch.object(ai_minutes, "plan_left", return_value=None):
				self.assertFalse(ai_minutes.status(user)["limited"])  # a plan with no limit on AI minutes shows no counter

	def test_bought_minutes_are_used_after_the_free_ones_oldest_pack_first(self):
		user = make_user().name
		old = _credit(user, 10, bought_on="2026-01-01 10:00:00")
		new = _credit(user, 20, bought_on="2026-02-01 10:00:00")
		with patch.object(ai_minutes, "_limited", return_value=True), patch("raftor_servicehq.plans.check", return_value={"ok": False, "reason": "quota"}):
			ai_minutes.turn_done(user)  # the first turn after a pause counts half a minute
		self.assertEqual(frappe.db.get_value("AI Minute Credit", old.name, "minutes_left"), 9.5)
		self.assertEqual(frappe.db.get_value("AI Minute Credit", new.name, "minutes_left"), 20)
		with patch.object(ai_minutes, "_limited", return_value=True), patch("raftor_servicehq.plans.check", return_value={"ok": True}), patch("raftor_servicehq.plans.use_time") as free:
			ai_minutes.turn_done(user)  # while the plan has free minutes, they are the ones counted
		free.assert_called_once()
		self.assertEqual(frappe.db.get_value("AI Minute Credit", old.name, "minutes_left"), 9.5)

	def test_out_of_minutes_the_person_is_told_they_can_add_more_unless_they_have_bought_some(self):
		user = make_user().name
		out = {"ok": False, "reason": "quota", "message": "You have used your minutes.", "cards": []}
		with patch.object(ai_minutes, "_limited", return_value=True), patch("raftor_servicehq.plans.check", return_value=out), patch.object(ai_minutes, "per_minute", return_value=5.0):
			told = ai_minutes.allowance(user)
			self.assertFalse(told["ok"])
			self.assertIn("add more right here", told["message"])
			_credit(user, 5)
			self.assertTrue(ai_minutes.allowance(user)["ok"])

	def test_a_payment_for_minutes_gives_them_once_and_other_payments_are_ignored(self):
		user = make_user().name
		pay = lambda name, key, doctype="User": frappe._dict(name=name, purpose_doctype=doctype, purpose_name=user, request_key=key)
		ai_minutes.payment_arrived(pay("PAY-1", f"aiminutes:{user}:20:0"))
		ai_minutes.payment_arrived(pay("PAY-1", f"aiminutes:{user}:20:0"))  # PaymentHQ may say it twice
		ai_minutes.payment_arrived(pay("PAY-2", f"extend:SOMETHING:10:2026"))
		ai_minutes.payment_arrived(pay("PAY-3", f"aiminutes:{user}:10:1", doctype="Booking"))
		self.assertEqual(ai_minutes.bought_left(user), 20)

	def test_a_minute_costs_what_the_guide_says_and_one_when_it_says_nothing(self):
		self.assertEqual(ai_minutes.per_minute(""), 1.0)
		with patch.object(frappe.db, "get_value", return_value=2.5):
			self.assertEqual(ai_minutes.per_minute("devika-iyer"), 2.5)
			self.assertEqual([p["price"] for p in ai_minutes.packs("devika-iyer")][0], ai_minutes._money(25))
		with patch.object(frappe.db, "get_value", return_value=0):
			self.assertEqual(ai_minutes.per_minute("devika-iyer"), 1.0)

	def test_buying_needs_a_sensible_amount_and_a_guide_that_sells_minutes(self):
		self.assertRaises(frappe.ValidationError, ai_minutes.buy, 1)
		self.assertRaises(frappe.ValidationError, ai_minutes.buy, 5000)
		with patch.object(ai_minutes, "per_minute", return_value=0):
			self.assertFalse(ai_minutes.on_sale())
			self.assertRaises(frappe.ValidationError, ai_minutes.buy, 10)

	def test_the_buy_asks_paymenthq_for_the_minutes_at_the_price_of_a_minute(self):
		user = make_user().name
		asked = {}

		def request(payer, amount, doctype, name, description, **options):
			asked.update(payer=payer, amount=amount, doctype=doctype, name=name, key=options["key"])
			return {"url": frappe.utils.get_url("/pay/abc"), "payment": "PAY-9"}

		frappe.set_user(user)
		try:
			with patch.object(ai_minutes, "per_minute", return_value=5.0), patch("raftor_servicehq.payments_port.request", side_effect=request):
				done = ai_minutes.buy(30)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual((asked["amount"], asked["doctype"], asked["name"], asked["payer"]), (150.0, "User", user, user))
		self.assertTrue(asked["key"].startswith(f"aiminutes:{user}:30:"))
		self.assertEqual(done["url"], "/pay/abc")  # a page of this site, shown over the chat
