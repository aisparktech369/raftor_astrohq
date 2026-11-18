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

	def test_the_status_gives_the_seconds_for_the_clock(self):
		user = make_user().name
		with patch.object(ai_minutes, "_limited", return_value=True), patch.object(ai_minutes, "plan_left", return_value=2.5):
			self.assertEqual(ai_minutes.status(user)["left_seconds"], 150)
			_credit(user, 1)
			self.assertEqual(ai_minutes.status(user)["left_seconds"], 210)

	def test_coming_back_from_the_sheet_restarts_the_persons_clock(self):
		user = make_user().name
		credit = _credit(user, 10)
		frappe.db.set_value("AI Minute Credit", credit.name, "last_used", "2026-01-01 10:00:00")
		frappe.set_user(user)
		try:
			with patch.object(ai_minutes, "_limited", return_value=True):
				self.assertTrue(ai_minutes.touch()["ok"])
		finally:
			frappe.set_user("Administrator")
		self.assertGreater(frappe.db.get_value("AI Minute Credit", credit.name, "last_used"), frappe.utils.get_datetime("2026-06-01"))

	def test_a_minute_costs_the_price_of_an_ai_minute_times_the_guides_number(self):
		self.assertEqual((ai_minutes.factor(""), ai_minutes.per_minute("")), (1.0, 1.0))  # no guide named: one AI minute a minute, 1 rupee
		for multiplier, rupees in ((1, 1.0), (2, 2.0), (3, 3.0), (5, 5.0)):
			with patch.object(frappe.db, "get_value", return_value=multiplier):
				self.assertEqual(ai_minutes.per_minute("devika-iyer"), rupees)
		with patch.object(frappe.db, "get_value", return_value=2):
			self.assertEqual([p["price"] for p in ai_minutes.packs("devika-iyer")][0], ai_minutes._money(20))  # a pack of 10 minutes with a guide of 2
		with patch.object(frappe.db, "get_value", return_value=0):
			self.assertEqual(ai_minutes.per_minute("devika-iyer"), 1.0)  # a guide that sets none is 1

	def test_the_price_of_an_ai_minute_is_a_setting_and_never_below_a_rupee(self):
		self.assertEqual(ai_minutes.price(), 1.0)  # nothing set: 1 rupee
		with patch.object(frappe.db, "get_single_value", return_value=2.5):
			self.assertEqual(ai_minutes.price(), 2.5)
			with patch.object(frappe.db, "get_value", return_value=2):
				self.assertEqual(ai_minutes.per_minute("devika-iyer"), 5.0)
		with patch.object(frappe.db, "get_single_value", return_value=0.2):
			self.assertEqual(ai_minutes.price(), 1.0)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "AI Minute Settings", "minute_price": 0.5}).validate()

	def test_a_minute_with_a_guide_uses_its_number_of_ai_minutes_and_the_clock_reads_time_with_that_guide(self):
		user = make_user().name
		credit = _credit(user, 30)
		with patch.object(ai_minutes, "_limited", return_value=True), patch.object(ai_minutes, "plan_left", return_value=0.0):
			self.assertEqual((ai_minutes.status(user, 3)["total"], ai_minutes.status(user, 3)["left"], ai_minutes.status(user, 3)["left_seconds"]), (30.0, 10.0, 600))  # 30 AI minutes are 10 minutes of talk with a guide of 3
			self.assertEqual(ai_minutes.status(user, 1)["left"], 30.0)
		with patch.object(ai_minutes, "_limited", return_value=True), patch("raftor_servicehq.plans.check", return_value={"ok": False, "reason": "quota"}), patch.object(ai_minutes, "factor", return_value=3.0):
			ai_minutes.turn_done(user, "devika-iyer")  # the first turn after a pause counts half a minute: 1.5 AI minutes at 3
		self.assertEqual(frappe.db.get_value("AI Minute Credit", credit.name, "minutes_left"), 28.5)
		with patch.object(ai_minutes, "_limited", return_value=True), patch("raftor_servicehq.plans.check", return_value={"ok": True}), patch("raftor_servicehq.plans.use_time") as free, patch.object(ai_minutes, "factor", return_value=2.0):
			ai_minutes.turn_done(user, "devika-iyer")
		self.assertEqual(free.call_args.kwargs.get("factor"), 2.0)  # the plan's free minutes are counted at the guide's number too

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
		self.assertEqual((asked["amount"], asked["doctype"], asked["name"], asked["payer"]), (30.0, "User", user, user))  # 30 AI minutes at 1 rupee each
		self.assertTrue(asked["key"].startswith(f"aiminutes:{user}:30:"))
		self.assertEqual(done["url"], "/pay/abc")  # a page of this site, shown over the chat
		frappe.set_user(user)
		try:
			with patch.object(ai_minutes, "factor", return_value=3.0), patch("raftor_servicehq.payments_port.request", side_effect=request):
				ai_minutes.buy(30)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(asked["amount"], 90.0)  # 30 minutes with a guide of 3 are 90 AI minutes, 1 rupee each
		self.assertTrue(asked["key"].startswith(f"aiminutes:{user}:90:"))  # what is given when it is paid is the AI minutes
