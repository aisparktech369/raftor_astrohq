"""What the AI guides use and cost: chats, turns, tokens and rupees for each guide, from the log every AI turn already writes (AgentsHQ's Agent Run Log), and a daily token cap for a guide.

A turn is tied to its guide through the chat it belongs to (the guide's name is in the chat's request). Cost is what the rate card in AgentsHQ Settings says (rupees for a million tokens read and written); it is
nothing until a rate is set. Nothing here is typed in."""
import frappe
from frappe.utils import add_days, cint, flt, now_datetime, today

TURN = "turn_complete"


def _guide_of_chat() -> str:
	"""The chats of the named guides: {chat: the guide's name}, as a table to join."""
	return "(select session, min(json_value(payload, '$.profile.persona')) as persona from `tabAgent Queue` group by session)"


def per_guide(days: int = 7) -> list[dict]:
	"""For each guide with turns in the last `days` days: chats, turns, tokens read and written, cost. Busiest first."""
	since = add_days(today(), -max(cint(days), 1) + 1)
	rows = frappe.db.sql(f"""select q.persona as guide, count(distinct l.session) as chats, count(*) as turns, coalesce(sum(l.tokens_in), 0) as tokens_in, coalesce(sum(l.tokens_out), 0) as tokens_out, coalesce(sum(l.cost), 0) as cost
		from `tabAgent Run Log` l join {_guide_of_chat()} q on q.session = l.session
		where l.event_type = %s and l.timestamp >= %s and q.persona is not null and q.persona <> '' group by q.persona order by tokens_in + tokens_out desc""", (TURN, since), as_dict=True)
	names = {r.slug: r.guide_name for r in frappe.get_all("AI Guide Persona", fields=["slug", "guide_name"])}
	for r in rows:
		r["name"] = names.get(r.guide) or r.guide
		r["tokens"] = cint(r.tokens_in) + cint(r.tokens_out)
		r["cost"] = round(flt(r.cost), 2)
		r["per_chat"] = round(r["cost"] / r.chats, 2) if r.chats else 0.0
	return rows


def totals(days: int = 7) -> dict:
	rows = per_guide(days)
	return {"chats": sum(r.chats for r in rows), "turns": sum(r.turns for r in rows), "tokens": sum(r.tokens for r in rows), "cost": round(sum(r.cost for r in rows), 2)}


def by_week(weeks: int = 8) -> list[dict]:
	"""A week at a time (Monday first), newest last: chats and tokens and cost, for the trend."""
	since = add_days(today(), -7 * max(cint(weeks), 1))
	return frappe.db.sql(f"""select date_sub(date(l.timestamp), interval weekday(l.timestamp) day) as week, count(distinct l.session) as chats, count(*) as turns, coalesce(sum(l.tokens_in + l.tokens_out), 0) as tokens, coalesce(sum(l.cost), 0) as cost
		from `tabAgent Run Log` l join {_guide_of_chat()} q on q.session = l.session
		where l.event_type = %s and l.timestamp >= %s and q.persona is not null and q.persona <> '' group by week order by week""", (TURN, since), as_dict=True)


def tokens_today(guide: str) -> int:
	"""Tokens a guide has used since midnight."""
	row = frappe.db.sql(f"""select coalesce(sum(l.tokens_in + l.tokens_out), 0) from `tabAgent Run Log` l join {_guide_of_chat()} q on q.session = l.session
		where l.event_type = %s and l.timestamp >= %s and q.persona = %s""", (TURN, f"{today()} 00:00:00", guide))
	return cint(row[0][0]) if row else 0


def over_cap(guide: str) -> bool:
	"""Whether a guide has used up its tokens for today (its cap in Desk; 0 or blank means no cap)."""
	cap = cint(frappe.db.get_value("AI Guide Persona", {"slug": guide}, "daily_token_cap"))
	return bool(cap) and tokens_today(guide) >= cap
