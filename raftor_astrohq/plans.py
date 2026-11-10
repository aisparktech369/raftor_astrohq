"""AstroHQ's three monthly plans: Free (Rs 0), Seeker (Rs 149, now and then) and Needy (Rs 399, every day), and what each one allows.

The plans are AstroHQ's own: servicehq has a plan engine for its services and knows nothing of these. The standard plans are data (plans.json), made by `ensure_plans()` on a fresh install and on migrate when they are missing.
A plan is a row of Astro Plan, and its limits are the business team's to change there: how many replies a month and a day, how many people in the profiles, how many notes a guide reads, how many reports a month, and which guides.
A person who takes a plan has a row in Astro Plan Member for a month (the PaymentHQ auto-pay agreement renews it); when the month ends without a renewal they have no plan. What a person with no plan can do is the business team's
choice in Astro Plan Settings: while plans are not required they have the lowest plan's limits (so the guides can be tried before buying is open); once required they need a plan, after the few trial replies the settings give, if any.

What a person has used lives in Astro Plan Usage, one row for each month. Staff (System Users) are not counted or limited.

    plan_of(user)                   the plan the person has now, with the month it counts in
    allowance(user, guide)          whether a guide may answer now: {"ok": True, ...} or {"ok": False, "reason", "message", "cards"} (the words and cards the guide gives)
    record_reply(user, guide)       one reply was given (called by AgentsHQ when a turn is done)
    family_room(user)               how many more people the profiles may hold
    notes_read(user)                how many notes a guide reads each turn
    reports_used(user), reports_left(user), report_allowance(user)
    quota(user)                     what the plan allows and what has been used, for the page that shows it
    limit_lines(plan)               what a plan gives, in words (its box on the plans page and its card on the person's own page)
    assign(user, plan, ...), end(user)   gives a person a plan for a month (the Desk, or a payment), or ends it
"""
import calendar
import json
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, getdate, now_datetime, today

FIELDS = ["name", "plan_name", "sort_order", "monthly_price", "tagline", "replies_per_month", "replies_per_day", "family_profiles", "notes_read", "reports_per_month", "guides",
		  "limit_month_message", "limit_day_message", "limit_guide_message", "family_message", "upgrade_message", "limit_cards", "no_plan_message", "limit_reports_message",
		  "button_label", "button_url", "price_note", "badge"]

HERE = Path(__file__).parent
PLANS_PAGE = "/plans"            # the plans to choose from, a box for each (plans_api.boxes)
MY_PLAN_PAGE = "/my/astro-plan"  # the person's own plan, what they have used and how to change or stop it (plans_api.my_plan)
WORDS = ["limit_month_message", "limit_day_message", "limit_guide_message", "family_message", "upgrade_message", "limit_reports_message", "no_plan_message", "limit_cards"]  # what a guide says at a limit: filled when blank, never over what staff wrote


def limit_lines(plan) -> list[str]:
	"""What a plan gives, in words, the one that matters most first. A plan that names no guides gives all of them."""
	lines = [_("{0} AI replies a month").format(f"{cint(plan.replies_per_month):,}"),
			 _("Up to {0} replies a day").format(f"{cint(plan.replies_per_day):,}"),
			 _("{0} people in your profiles").format(f"{cint(plan.family_profiles):,}"),
			 _("{0} free reports a month").format(f"{cint(plan.reports_per_month):,}"),
			 _("Guides remember {0} notes").format(f"{cint(plan.notes_read):,}")]
	lines.append(_("Guides: {0}").format(plan.guides) if plan.guides else _("All the AI guides"))
	return lines


def defaults() -> list[dict]:
	"""The plans that ship (plans.json), each as the fields of an Astro Plan: its own, the words every plan says at a limit, and the cards it hands over then."""
	data = json.loads((HERE / "plans.json").read_text(encoding="utf-8"))
	rows = []
	for plan in data["plans"]:
		row = {**data["words"], **{k: v for k, v in plan.items() if k != "cards"}}
		row["limit_cards"] = json.dumps([data["cards"][name] for name in plan.get("cards", [])])
		rows.append(row)
	return rows


def ensure_plans() -> None:
	"""Makes the standard plans that are not there (a fresh install); one that exists is left as the business team has set it, except that the words it lacks are filled. Safe to repeat."""
	for plan in defaults():
		if not frappe.db.exists("Astro Plan", plan["plan_name"]):
			frappe.get_doc({"doctype": "Astro Plan", "enabled": 1, **plan}).insert(ignore_permissions=True)
		else:  # the words a guide says at a limit, added later, are filled when blank; one the business team has written is left alone
			blank = {k: plan[k] for k in WORDS if k in plan and not frappe.db.get_value("Astro Plan", plan["plan_name"], k)}
			if blank:
				frappe.db.set_value("Astro Plan", plan["plan_name"], blank)


def _staff(user: str) -> bool:
	return frappe.db.get_value("User", user, "user_type") == "System User"


def _month_of(day) -> tuple:
	day = getdate(day)
	return day.replace(day=1), day.replace(day=calendar.monthrange(day.year, day.month)[1])


def _plan_row(name: str):
	return frappe.db.get_value("Astro Plan", name, FIELDS, as_dict=True)


def entry_plan() -> frappe._dict:
	"""The lowest plan: the enabled one with the lowest order."""
	rows = frappe.get_all("Astro Plan", filters={"enabled": 1}, fields=FIELDS, order_by="sort_order asc", limit=1)
	return frappe._dict(rows[0]) if rows else frappe._dict(plan_name="", replies_per_month=0, replies_per_day=0, family_profiles=1, notes_read=10, reports_per_month=0, guides="", sort_order=1, monthly_price=0)


def membership(user: str):
	"""The plan the person has taken and that has not run out, or None."""
	member = frappe.db.get_value("Astro Plan Member", user, ["plan", "status", "period_start", "period_end"], as_dict=True)
	if member and member.status == "Active" and member.period_end and getdate(member.period_end) >= getdate(today()) and frappe.db.get_value("Astro Plan", member.plan, "enabled"):
		return member
	return None


def payment_required() -> bool:
	return bool(cint(frappe.db.get_single_value("Astro Plan Settings", "payment_required")))


def month_window(anchor, day=None) -> tuple:
	"""The month of a plan that began on `anchor` that `day` (today) falls in: from the day of the month it began on to the day before the same day next month. Counted from the anchor each time, so a plan
	that began on the 31st has its months on the 28th or 30th and then on the 31st again."""
	anchor, day = getdate(anchor), getdate(day or today())
	k = (day.year - anchor.year) * 12 + day.month - anchor.month
	if getdate(add_months(anchor, k)) > day:
		k -= 1
	k = max(k, 0)
	return getdate(add_months(anchor, k)), add_days(getdate(add_months(anchor, k + 1)), -1)


def plan_of(user: str) -> frappe._dict:
	"""The plan the person has now, as a dict of its limits with `period_start` and `period_end` (the month their replies are counted in: the month of their plan they are in, or the calendar month when they have
	none, when they have the lowest plan's limits), `paid_through` (the last day they have paid for) and `taken` (whether they have taken a plan)."""
	member = membership(user)
	if member:
		plan = frappe._dict(_plan_row(member.plan))
		start, end = month_window(member.period_start or today())
		taken = True
		plan.paid_through = getdate(member.period_end)
	else:
		plan = entry_plan()
		start, end = _month_of(today())
		taken = False
		plan.paid_through = None
	plan.update(period_start=start, period_end=end, taken=taken)
	return plan


def next_plan(plan) -> frappe._dict | None:
	"""The plan one step above, if there is one."""
	rows = frappe.get_all("Astro Plan", filters={"enabled": 1, "sort_order": [">", cint(plan.sort_order)]}, fields=FIELDS, order_by="sort_order asc", limit=1)
	return frappe._dict(rows[0]) if rows else None


def _key(user: str, start) -> str:
	return f"{user}|{getdate(start)}"


def usage(user: str, plan=None) -> frappe._dict:
	"""What the person has used in the plan's month: replies, and the replies of today."""
	plan = plan or plan_of(user)
	row = frappe.db.get_value("Astro Plan Usage", _key(user, plan.period_start), ["replies", "day", "day_replies"], as_dict=True) or frappe._dict(replies=0, day=None, day_replies=0)
	if not row.day or getdate(row.day) != getdate(today()):
		row.day_replies = 0
	return row


def _bump(user: str, plan) -> None:
	key = _key(user, plan.period_start)
	if not frappe.db.exists("Astro Plan Usage", key):
		try:
			frappe.get_doc({"doctype": "Astro Plan Usage", "usage_key": key, "user": user, "period_start": plan.period_start}).insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			pass  # another reply made it at the same moment
	frappe.db.sql("update `tabAstro Plan Usage` set replies = replies + 1, day_replies = if(day = %(day)s, day_replies + 1, 1), day = %(day)s, last_reply = %(now)s where name = %(key)s",
				  {"day": getdate(today()), "now": now_datetime(), "key": key})


def record_reply(user: str, guide: str = "") -> None:
	"""One reply was given to this person by a guide. Staff are not counted."""
	if not user or user == "Guest" or _staff(user):
		return
	plan = plan_of(user)
	if not plan.taken and payment_required():  # a trial reply, once, before any plan
		key = f"{user}|trial"
		if not frappe.db.exists("Astro Plan Usage", key):
			try:
				frappe.get_doc({"doctype": "Astro Plan Usage", "usage_key": key, "user": user}).insert(ignore_permissions=True)
			except frappe.DuplicateEntryError:
				pass
		frappe.db.sql("update `tabAstro Plan Usage` set replies = replies + 1, last_reply = %(now)s where name = %(key)s", {"now": now_datetime(), "key": key})
		return
	_bump(user, plan)


def _say(template: str, plan, **extra) -> str:
	nxt = next_plan(plan)
	upgrade = ""
	if nxt and plan.upgrade_message:
		upgrade = _fill(plan.upgrade_message, next=nxt.plan_name, next_limit=nxt.replies_per_month, next_price=int(nxt.monthly_price or 0))
	return _fill(template or "", plan=plan.plan_name, price=int(plan.monthly_price or 0), limit=extra.pop("limit", ""), date=extra.pop("date", ""), upgrade=upgrade, **extra).strip()


def _fill(template: str, **values) -> str:
	class Keep(dict):
		def __missing__(self, key):
			return ""

	return " ".join(str(template).format_map(Keep(**values)).split())


def _cards(plan) -> list:
	try:
		cards = json.loads(plan.limit_cards or "[]")
	except ValueError:
		return []
	return [c for c in cards if isinstance(c, dict)] if isinstance(cards, list) else []


def allowance(user: str, guide: str) -> dict:
	"""Whether a guide may answer this person now. {"ok": True, "plan", "left"} or {"ok": False, "reason": "guide"|"month"|"day", "message": the words the guide says, "plan"}."""
	if not user or user == "Guest" or _staff(user):
		return {"ok": True}
	plan = plan_of(user)
	if not plan.taken and payment_required():
		spent = frappe.db.get_value("Astro Plan Usage", f"{user}|trial", "replies") or 0
		if cint(spent) >= cint(frappe.db.get_single_value("Astro Plan Settings", "trial_replies")):
			return {"ok": False, "reason": "no_plan", "plan": plan.plan_name, "message": _say(plan.no_plan_message, plan), "cards": _cards(plan)}
		return {"ok": True, "plan": plan.plan_name, "trial": True}
	allowed = [g.strip() for g in str(plan.guides or "").split(",") if g.strip()]
	if allowed and guide not in allowed:
		return {"ok": False, "reason": "guide", "plan": plan.plan_name, "message": _say(plan.limit_guide_message, plan), "cards": _cards(plan)}
	used = usage(user, plan)
	if cint(used.replies) >= cint(plan.replies_per_month):
		again = add_days(plan.period_end, 1)
		return {"ok": False, "reason": "month", "plan": plan.plan_name, "message": _say(plan.limit_month_message, plan, limit=plan.replies_per_month, date=frappe.utils.formatdate(again, "d MMMM")), "cards": _cards(plan)}
	if cint(used.day_replies) >= cint(plan.replies_per_day):
		return {"ok": False, "reason": "day", "plan": plan.plan_name, "message": _say(plan.limit_day_message, plan, limit=plan.replies_per_day), "cards": _cards(plan)}
	return {"ok": True, "plan": plan.plan_name, "left": cint(plan.replies_per_month) - cint(used.replies)}


def family_room(user: str) -> int:
	"""How many more people the person's profiles may hold on their plan."""
	if _staff(user):
		return 1000
	plan = plan_of(user)
	have = frappe.db.count("Astro Birth Profile", {"parent": user, "parenttype": "User"})
	return max(0, cint(plan.family_profiles) - have)


def family_words(user: str) -> str:
	plan = plan_of(user)
	return _say(plan.family_message, plan, limit=plan.family_profiles)


def notes_read(user: str, default: int = 40) -> int:
	if _staff(user):
		return default
	return max(1, cint(plan_of(user).notes_read) or default)


def reports_used(user: str, plan=None) -> int:
	"""The free reports made for the person in the plan's month, by any way they were asked for (a guide, or the website's own form): counted from the reports themselves."""
	plan = plan or plan_of(user)
	return frappe.db.count("Free Report", {"user": user, "creation": ["between", [plan.period_start, plan.period_end]]})


def reports_left(user: str) -> int:
	if _staff(user):
		return 1000
	plan = plan_of(user)
	return max(0, cint(plan.reports_per_month) - reports_used(user, plan))


def report_allowance(user: str) -> dict:
	"""Whether the person may be given another free report (the hook `free_reports_allowance` asks this before the website makes one, and the guides ask before they do): {"ok": True} or {"ok": False, "message"}."""
	if not user or user == "Guest" or _staff(user) or reports_left(user) > 0:
		return {"ok": True}
	plan = plan_of(user)
	return {"ok": False, "message": _say(plan.limit_reports_message, plan, limit=plan.reports_per_month, date=frappe.utils.formatdate(add_days(plan.period_end, 1), "d MMMM"))}


def quota(user: str) -> dict:
	"""What the person's plan allows and what they have used, for the page that shows it."""
	plan = plan_of(user)
	if _staff(user):
		return {"staff": True, "plan": plan.plan_name}
	used = usage(user, plan)
	member = frappe.db.get_value("Astro Plan Member", user, ["renews", "agreement"], as_dict=True) if plan.taken else None
	return {"staff": False, "plan": plan.plan_name, "taken": plan.taken, "price": cint(plan.monthly_price), "period_start": plan.period_start, "period_end": plan.period_end,
			"renews": bool(member and cint(member.renews) and member.agreement), "paid_through": plan.paid_through, "replies": [cint(used.replies), cint(plan.replies_per_month)], "day": [cint(used.day_replies), cint(plan.replies_per_day)],
			"people": [frappe.db.count("Astro Birth Profile", {"parent": user, "parenttype": "User"}), cint(plan.family_profiles)], "reports": [reports_used(user, plan), cint(plan.reports_per_month)],
			"notes": cint(plan.notes_read)}


def assign(user: str, plan: str, days: int = 31, source: str = "Desk", agreement: str = "", note: str = "") -> frappe._dict:
	"""Gives the person a plan for a month (31 days from today, or `days`). Returns the row."""
	if not frappe.db.exists("Astro Plan", plan):
		frappe.throw(f"There is no plan called {plan}.")
	values = {"plan": plan, "status": "Active", "period_start": getdate(today()), "period_end": add_days(today(), days - 1), "months_paid": 1, "source": source, "agreement": agreement, "note": note, "renews": 1 if agreement else 0,
			  "pending_plan": None, "pending_agreement": None}
	if frappe.db.exists("Astro Plan Member", user):
		doc = frappe.get_doc("Astro Plan Member", user)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({"doctype": "Astro Plan Member", "user": user, **values}).insert(ignore_permissions=True)
	return doc


def end(user: str) -> None:
	"""Ends the person's plan (they have none until they take one again)."""
	if frappe.db.exists("Astro Plan Member", user):
		frappe.db.set_value("Astro Plan Member", user, "status", "Ended")
