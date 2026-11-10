"""The AI plan page (/my/ai-plan): the person's plan with what they have used of it, the three plans with their limits, and the buttons to take one or stop renewing.

The page is a list of cards (website_hq's App Records): one for the plan they have, then one for each plan. Taking a plan sends the person to PaymentHQ's page to agree to monthly auto-pay; the plan is theirs when the first
payment arrives (plan_billing.py). Everything it says about limits comes from the plans themselves (AI Plan).
"""
import frappe
from frappe import _
from frappe.utils import add_days, cint, formatdate

from raftor_astrohq import plan_billing, plans

API = "raftor_astrohq.plans_api."
BAR = 10


def _user() -> str:
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in first."), frappe.PermissionError)
	return frappe.session.user


def _bar(used: int, limit: int) -> str:
	"""A small bar of ten cells: '████░░░░░░'."""
	filled = BAR if limit <= 0 else min(BAR, round(BAR * used / limit))
	return "█" * filled + "░" * (BAR - filled)


def _line(label: str, used: int, limit: int) -> str:
	return f"{label}: {_bar(used, limit)} {used} / {limit}"


def _limits(plan) -> list[str]:
	lines = [_("{0} AI replies a month, up to {1} a day").format(plan.replies_per_month, plan.replies_per_day),
			 _("{0} people in your profiles").format(plan.family_profiles),
			 _("{0} free reports a month").format(plan.reports_per_month),
			 _("Your guides remember {0} notes about you").format(plan.notes_read)]
	if plan.guides:
		lines.append(_("Guides: {0}").format(plan.guides))
	return lines


def _current_card(user: str, now: dict) -> dict:
	if now.get("staff"):
		return {"id": "now", "title": _("Your plan: staff"), "badge": _("No limits"), "tone": "success", "lines": [_("Staff are not limited or counted.")], "actions": []}
	if now["taken"]:
		badge = _("Renews on {0}").format(formatdate(add_days(now["paid_through"], 1), "d MMM")) if now["renews"] else _("Ends on {0}").format(formatdate(now["paid_through"], "d MMM"))
	else:
		badge = _("No cost")
	lines = [_line(_("AI replies this month"), *now["replies"]), _line(_("Today"), *now["day"]), _line(_("People saved"), *now["people"]), _line(_("Reports made"), *now["reports"]),
			 _("This month: {0} to {1}").format(formatdate(now["period_start"], "d MMM"), formatdate(now["period_end"], "d MMM"))]
	actions = []
	if now["taken"] and now["renews"]:
		actions.append({"label": _("Stop renewing"), "call": API + "stop", "kind": "danger", "confirm": _("Stop renewing? Your plan stays until {0}.").format(formatdate(now["paid_through"], "d MMMM")),
						"confirm_label": _("Stop renewing")})
	return {"id": "now", "title": _("Your plan: {0}").format(now["plan"]), "badge": badge, "tone": "success", "lines": lines, "actions": actions}


@frappe.whitelist(methods=["POST"])
def plan_cards() -> dict:
	"""The page: the person's plan and use, then each plan. The cards of the App Records list."""
	user = _user()
	now = plans.quota(user)
	items = [_current_card(user, now)]
	for row in frappe.get_all("AI Plan", filters={"enabled": 1}, fields=plans.FIELDS, order_by="sort_order asc"):
		plan = frappe._dict(row)
		price = cint(plan.monthly_price)
		mine = plan.plan_name == now["plan"] and (now.get("taken") or price == 0)
		card = {"id": plan.plan_name, "title": plan.plan_name if price == 0 else f"{plan.plan_name} · " + _("₹{0} a month").format(price), "badge": _("Your plan") if mine else "",
				"tone": "success" if mine else "", "lines": [plan.tagline, *_limits(plan)], "actions": []}
		if price > 0 and not mine and not now.get("staff"):
			change = bool(now.get("taken"))
			card["actions"].append({"label": _("Change to {0}").format(plan.plan_name) if change else _("Choose {0}").format(plan.plan_name), "call": API + "start", "args": {"plan": plan.plan_name}, "kind": "primary",
									**({"confirm": _("Your new month begins today and takes the place of the rest of this one. ₹{0} is charged now, and then each month. Stop any time.").format(price),
										"confirm_label": _("Change plan")} if change else {})})
		items.append(card)
	return {"items": items}


@frappe.whitelist(methods=["POST"])
def start(plan: str) -> dict:
	"""The person chooses a paid plan: they are sent to agree to monthly auto-pay."""
	return plan_billing.start(_user(), plan)


@frappe.whitelist(methods=["POST"])
def stop() -> dict:
	"""The person stops renewing; the plan stays to the end of the month they have paid for."""
	return plan_billing.stop(_user())
