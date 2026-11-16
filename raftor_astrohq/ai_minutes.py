"""AI minutes a person buys during a chat, for when the free minutes of their plan are used up.

    plan's free minutes (servicehq plans, meter ai_minutes)  ->  then the minutes bought here, oldest pack first

A pack is 10, 20 or 30 minutes, or any amount from CUSTOM_MIN to CUSTOM_MAX. It is bought the way more time in a live session is (servicehq sessions.extend): PaymentHQ is asked for a payment, the chat shows the payment
page over itself, and when PaymentHQ says it was paid (hook paymenthq_on_paid) the minutes are added as one AI Minute Credit row, once. An AI minute costs AI_MINUTE_PRICE rupees, and a minute of talk uses the guide's number of AI minutes (AI Guide Persona.minute_factor, set in Desk: 1, 2 or 3 for now), so a minute with a guide costs AI_MINUTE_PRICE times it. The multiplier is 1 for a guide with no record of its own
(Pandit ji, the numerologist and the others). AI minutes bought are used with any AI guide. Every AI chat shows how many minutes are left (`my_status`), warns when they are few, and, when none are left, says so and
offers the packs (plan_rules.allowance).

Staff and people whose plan has no limit on AI minutes are never counted or shown a counter."""
import frappe
from frappe import _
from frappe.utils import cint, flt, fmt_money, now_datetime

from raftor_astrohq import plan_rules

AI_MINUTE_PRICE = 1.0  # what one AI minute costs (rupees): always 1 for 1, so the balance is in effect rupees; a guide's number says how many AI minutes one minute of talk with it uses (1 to 5 rupees a minute)
CREDIT = "AI Minute Credit"
KEY = "aiminutes"  # a payment for minutes carries a request key that starts with this
PACKS = (10, 20, 30)
CUSTOM_MIN, CUSTOM_MAX = 5, 300
LOW = 3.0  # minutes: at this much or less the chat warns
PAUSE, FIRST = 5.0, 0.5  # the same rule as the plan's minutes (servicehq plans.use_time): a gap over PAUSE minutes is a pause and is not counted; the first use after a pause counts FIRST
BUY = "raftor_astrohq.ai_minutes.buy"


def _limited(user: str) -> bool:
	from raftor_servicehq import plans

	return bool(user) and user != "Guest" and not plans._staff(user)


def plan_left(user: str):
	"""Free minutes the person's plan still has in this period (0 when the plan has none), or None when the plan puts no limit on them."""
	from raftor_servicehq import plans

	plan = plans.plan_of(user)
	rows = plans.covering(plan, plan_rules.AI_MINUTES)
	if not rows:
		return 0.0
	left = None
	for row in rows:
		if row.period not in plans.COUNTED:
			continue
		used = flt(frappe.db.get_value(plans.USAGE, plans._key(user, row, plan), "used"))
		have = max(0.0, flt(row.quota) - used)
		left = have if left is None else min(left, have)
	return left


def bought_left(user: str) -> float:
	return flt(frappe.db.sql("select coalesce(sum(minutes_left), 0) from `tabAI Minute Credit` where user = %s and minutes_left > 0", user)[0][0])


def status(user: str, factor: float = 1) -> dict:
	"""What the chat shows: {"limited": False} when nothing is counted for this person, else their AI minutes (free and bought), the time that is with the guide they are talking to (a minute with it uses
	`factor` AI minutes), and whether to warn or to say they are out."""
	if not _limited(user):
		return {"limited": False}
	factor = factor if factor and factor > 0 else 1.0
	free = plan_left(user)
	if free is None:
		return {"limited": False}
	bought = bought_left(user)
	total = free + bought
	left = total / factor
	return {"limited": True, "total": round(total, 1), "factor": factor, "free": round(free / factor, 1), "bought": round(bought / factor, 1), "left": round(left, 1), "left_seconds": max(0, int(round(left * 60))), "low": 0 < left <= LOW, "out": total <= 0}


def factor(persona: str = "") -> float:
	"""How many AI minutes one minute of talk with this guide uses (1 when the guide sets none)."""
	value = flt(frappe.db.get_value("AI Guide Persona", {"slug": persona}, "minute_factor")) if persona else 0.0
	return max(value, 1.0)  # no AI guide is free: the least is one AI minute (a rupee) for a minute


def rate_of(provider: str) -> float:
	"""For a guide's card (hook servicehq_ai_rate): the rupees a minute with this guide costs, or nothing for a provider that is not an AI guide with a record here."""
	return per_minute(provider) if frappe.db.exists("AI Guide Persona", {"slug": provider}) else 0.0


def per_minute(persona: str = "") -> float:
	"""What a minute costs in rupees with this guide: the price of an AI minute times the guide's number."""
	return AI_MINUTE_PRICE * factor(persona)


def on_sale(persona: str = "") -> bool:
	"""Whether AI minutes can be bought (always: a guide's price follows its number)."""
	return per_minute(persona) > 0


def _money(amount: float) -> str:
	return fmt_money(amount, currency=frappe.defaults.get_global_default("currency") or "INR")


def packs(persona: str = "") -> list[dict]:
	"""The packs on offer with their prices at this guide's rate."""
	rate = per_minute(persona)
	return [{"minutes": m, "price": _money(rate * m)} for m in PACKS]


def words() -> dict:
	"""Every word the counter shows (the chat holds none of its own)."""
	return {"left": _("{0} min left"), "low": _("Only {0} min left. Add minutes to keep talking."), "out": _("You are out of minutes. Add some and carry on where we stopped."), "minutes": _("min"),
			"other": _("Other"), "add": _("Add"), "custom": _("Minutes ({0}-{1})"), "trouble": _("AI minutes cannot be added just now. Please try again in a moment."), "price_each": _("{0} a minute"), "paying": _("Add AI minutes"), "close": _("Close"), "added": _("{0} minutes added. Carry on!"), "sheet_title": _("Add AI minutes"),
			"sheet_low": _("Your time is almost up. Add minutes to keep talking: the clock waits until you are back."), "sheet_out": _("Your minutes are used up. Add some and we carry on where we stopped: the clock starts again when you are back."),
			"not_now": _("Not now"), "continue": _("Minutes added. Let us carry on."), "clock": _("Time left")}


@frappe.whitelist()
def my_status(persona: str = "") -> dict:
	"""For the chat's counter, asked after each reply: the person's minutes, and what they can buy with the guide they are talking to (`persona` is that guide's slug, when it is one of the named ones)."""
	user = frappe.session.user
	out = status(user, factor(persona))
	if out.get("limited"):
		out.update({"packs": packs(persona), "custom": {"min": CUSTOM_MIN, "max": CUSTOM_MAX, "rate": _money(per_minute(persona))}, "buy": BUY, "words": words()})
	return out



@frappe.whitelist(methods=["POST"])
def touch() -> dict:
	"""The person's clock starts from now: the time they spent away from the chat (choosing minutes, paying) is not counted. The chat calls this when its recharge sheet is closed or the payment is done."""
	from raftor_servicehq import plans

	user = frappe.session.user
	if not _limited(user):
		return {"ok": True}
	plan = plans.plan_of(user)
	for row in plans.covering(plan, plan_rules.AI_MINUTES):
		key = plans._key(user, row, plan)
		if frappe.db.exists(plans.USAGE, key):
			frappe.db.set_value(plans.USAGE, key, "last_at", now_datetime(), update_modified=False)
	frappe.db.sql("update `tabAI Minute Credit` set last_used = %s where user = %s and minutes_left > 0", (now_datetime(), user))
	return {"ok": True}


# ---- the plan's rule, with the bought minutes behind it ----
def allowance(user: str) -> dict:
	"""May this person have an AI answer now: yes while the plan's free minutes last, then while bought minutes last; else the plan's own words, with the packs."""
	from raftor_servicehq import plans

	result = plans.check(user, plan_rules.AI_MINUTES)
	if result.get("ok") or not _limited(user):
		return result
	if bought_left(user) > 0:
		return {"ok": True, "plan": result.get("plan"), "bought": True}
	words = _("You have used your AI minutes. You can add more right here and carry on where we stopped: 10, 20 or 30 minutes, or an amount of your own.")
	return {**result, "message": f"{result.get('message') or ''} {words}".strip()}


def turn_done(user: str, persona: str = "") -> None:
	"""An answer was given. While the plan has free minutes they are counted there (as always); once they are used up the minutes since the last answer come off the bought ones. A minute of talk uses the guide's
	number of AI minutes (a guide of 3 uses 3 a minute)."""
	from raftor_servicehq import plans

	times = factor(persona)
	if not _limited(user) or plans.check(user, plan_rules.AI_MINUTES).get("ok") or bought_left(user) <= 0:
		plans.use_time(user, plan_rules.AI_MINUTES, factor=times)
		return
	rows = frappe.get_all(CREDIT, filters={"user": user, "minutes_left": [">", 0]}, fields=["name", "minutes_left", "last_used"], order_by="bought_on asc, creation asc")
	last = max((r.last_used for r in frappe.get_all(CREDIT, filters={"user": user}, fields=["last_used"]) if r.last_used), default=None)
	minutes = FIRST
	if last:
		gap = (now_datetime() - last).total_seconds() / 60
		if 0 <= gap <= PAUSE:
			minutes = gap
	remaining = round(minutes * times, 2)
	for row in rows:
		if remaining <= 0:
			break
		take = min(remaining, flt(row.minutes_left))
		frappe.db.set_value(CREDIT, row.name, {"minutes_left": round(flt(row.minutes_left) - take, 2), "last_used": now_datetime()}, update_modified=False)
		remaining = round(remaining - take, 2)


# ---- buying ----
@frappe.whitelist(methods=["POST"])
def buy(minutes: int = 10, persona: str = "") -> dict:
	"""The person chooses minutes to add: asks PaymentHQ for the payment and answers where to pay (a page of this site, shown over the chat). The minutes are added when PaymentHQ says it was paid."""
	from raftor_servicehq import payments_port
	from raftor_servicehq.sessions import _on_this_site

	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Sign in to add AI minutes."), frappe.PermissionError)
	minutes = cint(minutes)
	if not (CUSTOM_MIN <= minutes <= CUSTOM_MAX):
		frappe.throw(_("Choose between {0} and {1} minutes.").format(CUSTOM_MIN, CUSTOM_MAX))
	if not on_sale(persona):
		frappe.throw(_("AI minutes cannot be bought with this guide."))
	credit = flt(minutes * factor(persona), 2)  # what is kept is AI minutes: they go with the person to any guide (a minute with another guide uses that guide's number)
	key = f"{KEY}:{user}:{credit:g}:{frappe.db.count(CREDIT, {'user': user})}"  # asking again for the same thing gives the same payment, until it is paid
	made = payments_port.request(user, flt(AI_MINUTE_PRICE * credit, 2), "User", user, _("{0} minutes of talk with the AI astrologers").format(minutes), key=key, return_to="/")
	return {"ok": bool(made.get("url")), "url": _on_this_site(made.get("url")), "payment": made["payment"], "minutes": minutes}


def payment_arrived(payment) -> None:
	"""PaymentHQ's news that a payment for a User arrived (hook paymenthq_on_paid): when it was for AI minutes, they are added, once. A problem here never undoes the payment."""
	key = payment.get("request_key") or ""
	if payment.purpose_doctype != "User" or not key.startswith(f"{KEY}:"):
		return
	try:
		give(payment.name, payment.purpose_name, flt(key.split(":")[-2]))
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"AI minutes for {payment.name}")


def give(payment: str, user: str, minutes: float) -> bool:
	"""One credit for one payment, once. Returns whether it was made."""
	if minutes <= 0 or frappe.db.exists(CREDIT, {"payment": payment}) or not frappe.db.exists("User", user):
		return False
	frappe.get_doc({"doctype": CREDIT, "user": user, "minutes_bought": minutes, "minutes_left": minutes, "bought_on": now_datetime(), "payment": payment}).insert(ignore_permissions=True)
	return True
