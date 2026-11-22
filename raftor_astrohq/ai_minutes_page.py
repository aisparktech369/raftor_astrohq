"""The person's AI minutes page (my/ai-minutes): what they have left (free from their plan and bought), the packs they bought with the invoice of each, and where their minutes went, answer by answer (the ledger, ai_minutes.record).
Every method answers for the signed-in person only."""
import frappe
from frappe import _
from frappe.utils import cint, flt, formatdate, get_datetime

from raftor_astrohq import ai_minutes

LIMIT = 50


def _user() -> str:
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Sign in to see your AI minutes."), frappe.PermissionError)
	return user


def _num(n) -> str:
	n = flt(n)
	return f"{n:,.0f}" if n == int(n) else f"{n:,.1f}"


def _when(value) -> str:
	return get_datetime(value).strftime("%-d %b, %-I:%M %p") if value else ""


@frappe.whitelist(methods=["POST"])
def summary() -> dict:
	"""Fact Card fields: AI minutes left, how many of them are free and how many bought, and the total used."""
	user = _user()
	if not ai_minutes._limited(user) or ai_minutes.plan_left(user) is None:
		return {"items": [{"value": _("No limit"), "label": _("AI minutes"), "description": _("Your plan does not count them.")}]}
	free, bought = ai_minutes.plan_left(user), ai_minutes.bought_left(user)
	used = flt(frappe.db.sql("select coalesce(sum(ai_minutes), 0) from `tabAI Minute Use` where user = %s", user)[0][0])
	cards = [{"value": _num(free + bought), "label": _("AI minutes left"), "description": _("A minute with a guide uses that guide's number of them.")},
			 {"value": _num(free), "label": _("Free with your plan")}, {"value": _num(bought), "label": _("Bought")}]
	if used:
		cards.append({"value": _num(used), "label": _("AI minutes used so far")})
	return {"items": cards}


@frappe.whitelist(methods=["POST"])
def bought() -> dict:
	"""A record for each pack bought: when, how many AI minutes, how many are left, and its invoice."""
	user = _user()
	items = []
	for r in frappe.get_all(ai_minutes.CREDIT, filters={"user": user}, fields=["name", "minutes_bought", "minutes_left", "bought_on", "payment"], order_by="bought_on desc"):
		invoice = frappe.db.get_value("Sales Invoice", {"po_no": r.payment, "docstatus": 1}, "name") if r.payment else None
		lines = [_("{0} bought, {1} left").format(_num(r.minutes_bought), _num(r.minutes_left)), _when(r.bought_on)]
		if invoice:
			lines.append(_("Invoice {0}").format(invoice))
		items.append({"id": r.name, "title": _("{0} AI minutes").format(_num(r.minutes_bought)), "badge": _("Used up") if flt(r.minutes_left) <= 0 else _("{0} left").format(_num(r.minutes_left)),
					  "tone": "neutral" if flt(r.minutes_left) <= 0 else "success", "lines": lines, "actions": []})
	return {"items": items}


@frappe.whitelist(methods=["POST"])
def usage() -> dict:
	"""A record for each answer that used AI minutes, newest first (the last 50): the guide, the time, minutes of talk and AI minutes used, and what was left after."""
	user = _user()
	items = []
	for r in frappe.get_all(ai_minutes.USE, filters={"user": user}, fields=["name", "used_on", "guide_name", "talk_minutes", "ai_minutes", "source", "balance_after"], order_by="used_on desc", limit=LIMIT):
		items.append({"id": r.name, "title": r.guide_name or _("AI guide"), "badge": _("-{0}").format(_num(r.ai_minutes)), "tone": "success" if r.source == "Plan" else "neutral",
					  "lines": [_when(r.used_on), _("{0} min of talk · from {1}").format(_num(r.talk_minutes), _("your plan") if r.source == "Plan" else _("bought minutes")), _("{0} left after").format(_num(r.balance_after))], "actions": []})
	return {"items": items}
