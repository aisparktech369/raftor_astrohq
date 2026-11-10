"""The three monthly plans of the AI guides: Free, Seeker (now and then) and Needy (every day), and what each one allows.

A plan is a row of AI Plan, and its limits are the business team's to change there: how many replies a month and a day, how many people in the profiles, how many notes a guide reads, how many reports a month, and which guides.
Nobody has to take a plan: a person with none has Free. A person who takes one has a row in AI Plan Member for a month (the PaymentHQ auto-pay agreement renews it); when the month ends without a renewal they are Free again.

What a person has used lives in AI Usage, one row for each month. Staff (System Users) are not counted or limited.

    plan_of(user)                   the plan the person has now, with the month it counts in
    allowance(user, guide)          whether a guide may answer now: {"ok": True, ...} or {"ok": False, "reason", "message"} (the words the guide says)
    record_reply(user, guide)       one reply was given (called by AgentsHQ when a turn is done)
    family_room(user)               how many more people the profiles may hold
    notes_read(user)                how many notes a guide reads each turn
    reports_left(user), record_report(user)
    assign(user, plan, ...)         gives a person a plan for a month (the Desk, a trial, or a payment)
"""
import calendar

import frappe
from frappe.utils import add_days, cint, getdate, now_datetime, today

FREE = "Free"
FIELDS = ["name", "plan_name", "sort_order", "monthly_price", "tagline", "replies_per_month", "replies_per_day", "family_profiles", "notes_read", "reports_per_month", "guides",
		  "limit_month_message", "limit_day_message", "limit_guide_message", "family_message", "upgrade_message"]

UPGRADE = "The {next} plan gives you {next_limit} replies a month."
DEFAULT_PLANS = [
	{"plan_name": "Free", "sort_order": 1, "monthly_price": 0, "tagline": "Try the guides and keep your own profile",
	 "replies_per_month": 60, "replies_per_day": 10, "family_profiles": 2, "notes_read": 10, "reports_per_month": 5},
	{"plan_name": "Seeker", "sort_order": 2, "monthly_price": 149, "tagline": "For when you want guidance now and then",
	 "replies_per_month": 300, "replies_per_day": 40, "family_profiles": 6, "notes_read": 40, "reports_per_month": 20},
	{"plan_name": "Needy", "sort_order": 3, "monthly_price": 399, "tagline": "For people who talk to the guides every day",
	 "replies_per_month": 1000, "replies_per_day": 100, "family_profiles": 15, "notes_read": 100, "reports_per_month": 60},
]
WORDS = {
	"limit_month_message": "You have used all {limit} replies of your {plan} plan for this month. They start again on {date}. {upgrade}",
	"limit_day_message": "That is the {limit} replies a day your {plan} plan allows. I will be here again tomorrow. {upgrade}",
	"limit_guide_message": "I am not part of your {plan} plan. {upgrade}",
	"family_message": "Your {plan} plan keeps {limit} people in your profiles. {upgrade}",
	"upgrade_message": UPGRADE,
}


def ensure_plans() -> None:
	"""Makes the three plans if they are not there; one that exists is left as the business team has set it. Safe to repeat."""
	for plan in DEFAULT_PLANS:
		if not frappe.db.exists("AI Plan", plan["plan_name"]):
			frappe.get_doc({"doctype": "AI Plan", "enabled": 1, **WORDS, **plan}).insert(ignore_permissions=True)


def _staff(user: str) -> bool:
	return frappe.db.get_value("User", user, "user_type") == "System User"


def _month_of(day) -> tuple:
	day = getdate(day)
	return day.replace(day=1), day.replace(day=calendar.monthrange(day.year, day.month)[1])


def _plan_row(name: str):
	row = frappe.db.get_value("AI Plan", name, FIELDS, as_dict=True)
	return row


def plan_of(user: str) -> frappe._dict:
	"""The plan the person has now, as a dict of its limits with `period_start` and `period_end` (the month their replies are counted in: their paid month, or the calendar month for Free)."""
	member = frappe.db.get_value("AI Plan Member", user, ["plan", "status", "period_start", "period_end"], as_dict=True)
	plan = None
	if member and member.status == "Active" and member.period_end and getdate(member.period_end) >= getdate(today()) and frappe.db.get_value("AI Plan", member.plan, "enabled"):
		plan = _plan_row(member.plan)
		start, end = getdate(member.period_start or today()), getdate(member.period_end)
	if plan is None:
		plan = _plan_row(FREE) or frappe._dict(plan_name=FREE, replies_per_month=0, replies_per_day=0, family_profiles=1, notes_read=10, reports_per_month=0, guides="", sort_order=1, monthly_price=0)
		start, end = _month_of(today())
	plan.update(period_start=start, period_end=end)
	return plan


def next_plan(plan) -> frappe._dict | None:
	"""The plan one step above, if there is one."""
	rows = frappe.get_all("AI Plan", filters={"enabled": 1, "sort_order": [">", cint(plan.sort_order)]}, fields=FIELDS, order_by="sort_order asc", limit=1)
	return frappe._dict(rows[0]) if rows else None


def _key(user: str, start) -> str:
	return f"{user}|{getdate(start)}"


def usage(user: str, plan=None) -> frappe._dict:
	"""What the person has used in the plan's month: replies, the replies of today, reports."""
	plan = plan or plan_of(user)
	row = frappe.db.get_value("AI Usage", _key(user, plan.period_start), ["replies", "day", "day_replies", "reports"], as_dict=True) or frappe._dict(replies=0, day=None, day_replies=0, reports=0)
	if not row.day or getdate(row.day) != getdate(today()):
		row.day_replies = 0
	return row


def _bump(user: str, plan, column: str) -> None:
	key = _key(user, plan.period_start)
	if not frappe.db.exists("AI Usage", key):
		try:
			frappe.get_doc({"doctype": "AI Usage", "usage_key": key, "user": user, "period_start": plan.period_start}).insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			pass  # another reply made it at the same moment
	if column == "replies":
		frappe.db.sql("update `tabAI Usage` set replies = replies + 1, day_replies = if(day = %(day)s, day_replies + 1, 1), day = %(day)s, last_reply = %(now)s where name = %(key)s",
					  {"day": getdate(today()), "now": now_datetime(), "key": key})
	else:
		frappe.db.sql("update `tabAI Usage` set reports = reports + 1 where name = %(key)s", {"key": key})


def record_reply(user: str, guide: str = "") -> None:
	"""One reply was given to this person by a guide. Staff are not counted."""
	if not user or user == "Guest" or _staff(user):
		return
	_bump(user, plan_of(user), "replies")


def record_report(user: str) -> None:
	if not user or user == "Guest" or _staff(user):
		return
	_bump(user, plan_of(user), "reports")


def _say(template: str, plan, **extra) -> str:
	nxt = next_plan(plan)
	upgrade = ""
	if nxt and plan.upgrade_message:
		upgrade = _fill(plan.upgrade_message, next=nxt.plan_name, next_limit=nxt.replies_per_month, next_price=int(nxt.monthly_price or 0))
	return _fill(template or "", plan=plan.plan_name, limit=extra.pop("limit", ""), date=extra.pop("date", ""), upgrade=upgrade, **extra).strip()


def _fill(template: str, **values) -> str:
	class Keep(dict):
		def __missing__(self, key):
			return ""

	return " ".join(str(template).format_map(Keep(**values)).split())


def allowance(user: str, guide: str) -> dict:
	"""Whether a guide may answer this person now. {"ok": True, "plan", "left"} or {"ok": False, "reason": "guide"|"month"|"day", "message": the words the guide says, "plan"}."""
	if not user or user == "Guest" or _staff(user):
		return {"ok": True}
	plan = plan_of(user)
	allowed = [g.strip() for g in str(plan.guides or "").split(",") if g.strip()]
	if allowed and guide not in allowed:
		return {"ok": False, "reason": "guide", "plan": plan.plan_name, "message": _say(plan.limit_guide_message, plan)}
	used = usage(user, plan)
	if cint(used.replies) >= cint(plan.replies_per_month):
		again = add_days(plan.period_end, 1)
		return {"ok": False, "reason": "month", "plan": plan.plan_name, "message": _say(plan.limit_month_message, plan, limit=plan.replies_per_month, date=frappe.utils.formatdate(again, "d MMMM"))}
	if cint(used.day_replies) >= cint(plan.replies_per_day):
		return {"ok": False, "reason": "day", "plan": plan.plan_name, "message": _say(plan.limit_day_message, plan, limit=plan.replies_per_day)}
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


def reports_left(user: str) -> int:
	if _staff(user):
		return 1000
	plan = plan_of(user)
	return max(0, cint(plan.reports_per_month) - cint(usage(user, plan).reports))


def assign(user: str, plan: str, days: int = 31, source: str = "Desk", agreement: str = "", note: str = "") -> frappe._dict:
	"""Gives the person a plan for a month (31 days from today, or `days`). Giving the Free plan ends whatever they had. Returns the row."""
	if not frappe.db.exists("AI Plan", plan):
		frappe.throw(f"There is no plan called {plan}.")
	values = {"plan": plan, "status": "Ended" if plan == FREE else "Active", "period_start": getdate(today()), "period_end": add_days(today(), days - 1), "source": source, "agreement": agreement, "note": note}
	if frappe.db.exists("AI Plan Member", user):
		doc = frappe.get_doc("AI Plan Member", user)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({"doctype": "AI Plan Member", "user": user, **values}).insert(ignore_permissions=True)
	return doc
