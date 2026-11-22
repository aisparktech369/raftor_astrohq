"""The business team's stats page (Business stats): what was held with people and with AI guides, how people rated it, and what the AI guides used and cost, for the last 30 days, then each guide and each week.

Every number is counted from what the platform recorded (bookings, chats, reviews, reports, the AI turn log); a figure with nothing behind it is not drawn. The page is for the team (page roles) and each method here checks it again."""
import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, today

from raftor_astrohq import ai_telemetry
from raftor_servicehq import trust
from raftor_servicehq.roles import is_staff

DAYS = 30


def _team() -> None:
	if not is_staff():
		frappe.throw(_("This is for the business team."), frappe.PermissionError)


def _since() -> str:
	return f"{add_days(today(), -DAYS + 1)} 00:00:00"


def _short(n) -> str:
	n = flt(n)
	return f"{n / 1_000_000:.1f}M" if n >= 1_000_000 else f"{n / 1_000:.0f}k" if n >= 10_000 else f"{n:,.0f}"


def _rupees(amount) -> str:
	symbol = frappe.db.get_value("Currency", frappe.defaults.get_global_default("currency") or "INR", "symbol") or "₹"
	return f"{symbol}{flt(amount):,.2f}"


@frappe.whitelist(methods=["POST"])
def summary() -> dict:
	"""Fact Card fields: the last 30 days in numbers."""
	_team()
	since = _since()
	held = frappe.db.sql("""select count(*), coalesce(sum(price = 0), 0), coalesce(sum(session_seconds), 0) from `tabBooking` where workflow_state = 'Delivered' and slot_start >= %s""", since)[0]
	people, free, seconds = cint(held[0]), cint(held[1]), cint(held[2])
	ai = ai_telemetry.totals(DAYS)
	rated = frappe.db.sql("select count(*), coalesce(avg(rating), 0) from `tabBooking Review` where is_published = 1 and creation >= %s", since)[0]
	made = frappe.db.count("Free Report", {"workflow_state": "Ready", "made_on": [">=", since]})
	cards = [{"value": f"{people:,}", "label": _("Sessions with people"), "description": _("{0} free · {1} paid").format(free, people - free) if people else ""},
			 {"value": f"{ai['chats']:,}", "label": _("Chats with AI guides"), "description": _("{0} replies").format(f"{ai['turns']:,}") if ai["turns"] else ""}]
	if seconds >= 60:
		cards.append({"value": trust.span(seconds), "label": _("Time in sessions with people")})
	if cint(rated[0]):
		cards += [{"value": f"{flt(rated[1]):.1f}", "label": _("Average rating"), "description": _("{0} reviews").format(cint(rated[0]))}]
	if made:
		cards.append({"value": f"{made:,}", "label": _("Reports made")})
	if ai["tokens"]:
		cards.append({"value": _short(ai["tokens"]), "label": _("AI tokens used")})
		cards.append({"value": _rupees(ai["cost"]) if ai["cost"] else _("Not set"), "label": _("AI cost"),
					  "description": _("{0} a chat").format(_rupees(ai["cost"] / ai["chats"])) if ai["cost"] and ai["chats"] else _("Set the rates in AgentsHQ Settings")})
	sold = flt(frappe.db.sql("select coalesce(sum(minutes_bought), 0) from `tabAI Minute Credit` where bought_on >= %s", since)[0][0])
	spent = flt(frappe.db.sql("select coalesce(sum(ai_minutes), 0) from `tabAI Minute Use` where used_on >= %s", since)[0][0])
	owed = flt(frappe.db.sql("select coalesce(sum(minutes_left), 0) from `tabAI Minute Credit` where minutes_left > 0")[0][0])
	if sold or spent or owed:
		cards += [{"value": _short(sold), "label": _("AI minutes sold"), "description": _("{0} used from the plan or bought packs").format(_short(spent))},
				  {"value": _short(owed), "label": _("Bought AI minutes still unused"), "description": _("Paid for, not yet used")}]
	return {"items": cards}


@frappe.whitelist(methods=["POST"])
def guides() -> dict:
	"""One record for each AI guide that was used: its chats, tokens and cost, how people rated it, and its daily cap."""
	_team()
	rows, since = ai_telemetry.per_guide(DAYS), _since()
	totals = trust.guide_totals([r.guide for r in rows])
	items = []
	for r in rows:
		provider = frappe.db.get_value("Provider", r.guide, ["avg_rating", "total_reviews"], as_dict=True) if frappe.db.exists("Provider", r.guide) else None
		cap = cint(frappe.db.get_value("AI Guide Persona", {"slug": r.guide}, "daily_token_cap"))
		lines = [(_("{0} chat") if r.chats == 1 else _("{0} chats")).format(r.chats) + " · " + (_("{0} reply") if r.turns == 1 else _("{0} replies")).format(r.turns),
				 (_("Cost {0} · {1} a chat").format(_rupees(r.cost), _rupees(r.per_chat)) if r.cost else _("Cost: set the rates in AgentsHQ Settings"))]
		if provider and provider.total_reviews:
			lines.append(f"★ {provider.avg_rating:.1f} ({provider.total_reviews})" + (_(" · {0} sessions").format(f"{totals.get(r.guide, {}).get('sessions', 0):,}")))
		used = flt(frappe.db.sql("select coalesce(sum(ai_minutes), 0) from `tabAI Minute Use` where guide = %s and used_on >= %s", (r.guide, since))[0][0])
		if used:
			lines.append(_("{0} AI minutes used").format(_short(used)))
		if cap:
			lines.append(_("Daily cap {0} tokens (used today {1})").format(_short(cap), _short(ai_telemetry.tokens_today(r.guide))))
		items.append({"id": r.guide, "title": r.name, "badge": _("{0} tokens").format(_short(r.tokens)), "tone": "warning" if cap and ai_telemetry.over_cap(r.guide) else "success", "lines": lines, "actions": []})
	return {"items": items}


@frappe.whitelist(methods=["POST"])
def weekly() -> dict:
	"""A record for each of the last eight weeks: sessions with people, chats with AI guides, tokens and cost."""
	_team()
	ai = {str(w.week): w for w in ai_telemetry.by_week(8)}
	people = {str(r.week): r for r in frappe.db.sql("""select date_sub(date(slot_start), interval weekday(slot_start) day) as week, count(*) as n from `tabBooking`
		where workflow_state = 'Delivered' and slot_start >= %s group by week""", f"{add_days(today(), -56)} 00:00:00", as_dict=True)}
	items = []
	for week in sorted(set(ai) | set(people), reverse=True):
		a, p = ai.get(week), people.get(week)
		lines = [_("{0} sessions with people").format(cint(p.n) if p else 0), _("{0} chats with AI guides").format(cint(a.chats) if a else 0)]
		if a and cint(a.tokens):
			lines.append(_("{0} tokens").format(_short(a.tokens)) + (f" · {_rupees(a.cost)}" if flt(a.cost) else ""))
		items.append({"id": week, "title": _("Week of {0}").format(frappe.utils.formatdate(week, "d MMM")), "badge": "", "tone": "success", "lines": lines, "actions": []})
	return {"items": items}
