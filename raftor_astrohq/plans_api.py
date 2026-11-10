"""The pages of the AI plans: the person's own page (/my/ai-plan), the line on the plans page that says which plan they are on (/plans), and the page that confirms the plan they chose (/plans/choose).

The person's page is a list of cards (website_hq's App Records): one for the plan they have, then one for each plan. Taking a plan sends the person to PaymentHQ's page to agree to monthly auto-pay; the plan is theirs when the first
payment arrives (plan_billing.py). Everything it says about limits comes from the plans themselves (AI Plan). The three boxes of the plans page are websitehq's Service Card, made from the plans by plan_site.py.
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


def _badge(now: dict) -> str:
	"""When the person's plan renews or ends; a plan that costs nothing says so."""
	if not now["taken"]:
		return _("No cost")
	return _("Renews on {0}").format(formatdate(add_days(now["paid_through"], 1), "d MMM")) if now["renews"] else _("Ends on {0}").format(formatdate(now["paid_through"], "d MMM"))


def _is_mine(plan, now: dict) -> bool:
	return plan.plan_name == now["plan"] and bool(now.get("taken") or cint(plan.monthly_price) == 0)


def _current_card(user: str, now: dict) -> dict:
	if now.get("staff"):
		return {"id": "now", "title": _("Your plan: staff"), "badge": _("No limits"), "tone": "success", "lines": [_("Staff are not limited or counted.")], "actions": []}
	badge = _badge(now)
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
		mine = _is_mine(plan, now)
		card = {"id": plan.plan_name, "title": plan.plan_name if price == 0 else f"{plan.plan_name} · " + _("₹{0} a month").format(price), "badge": _("Your plan") if mine else "",
				"tone": "success" if mine else "", "lines": [plan.tagline, *plans.limit_lines(plan)], "actions": []}
		if price > 0 and not mine and not now.get("staff"):
			change = bool(now.get("taken"))
			card["actions"].append({"label": _("Change to {0}").format(plan.plan_name) if change else _("Choose {0}").format(plan.plan_name), "call": API + "start", "args": {"plan": plan.plan_name}, "kind": "primary",
									**({"confirm": _("Your new month begins today and takes the place of the rest of this one. ₹{0} is charged now, and then each month. Stop any time.").format(price),
										"confirm_label": _("Change plan")} if change else {})})
		items.append(card)
	return {"items": items}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def strip() -> dict:
	"""The line above the boxes of the plans page: the plan the signed-in person is on and where to see what they have used. Nothing for a visitor who has not signed in, or for staff."""
	if frappe.session.user == "Guest":
		return {"items": []}
	now = plans.quota(frappe.session.user)
	if now.get("staff"):
		return {"items": []}
	used, limit = now["replies"]
	return {"items": [{"id": "now", "title": _("You are on the {0} plan").format(now["plan"]), "badge": _badge(now), "tone": "success",
					   "lines": [_("{0} of {1} AI replies used this month").format(used, limit)],
					   "actions": [{"label": _("See what you have used"), "href": plans.MY_PLAN_PAGE, "kind": "outline"}]}]}


@frappe.whitelist(methods=["POST"])
def choose_card(plan: str = "") -> dict:
	"""The page that confirms the plan the person chose on the plans page: what it gives, what it costs, and the button that sends them to agree to monthly auto-pay. A plan that cannot be taken gives no card."""
	user = _user()
	row = frappe.db.get_value("AI Plan", {"name": plan, "enabled": 1}, plans.FIELDS, as_dict=True) if plan else None
	if not row or cint(row.monthly_price) <= 0:
		return {"items": []}
	plan_row, now, price = frappe._dict(row), plans.quota(user), cint(row.monthly_price)
	card = {"id": plan_row.plan_name, "title": _("{0} · ₹{1} a month").format(plan_row.plan_name, price), "badge": "", "tone": "", "lines": [plan_row.tagline, *plans.limit_lines(plan_row)], "actions": []}
	if _is_mine(plan_row, now):
		card.update(badge=_("Your plan"), tone="success")
		card["lines"].append(_("This is your plan. {0}.").format(_badge(now)))
	elif not now.get("staff"):
		change = bool(now.get("taken"))
		card["lines"].append(_("Your new month begins today and takes the place of the rest of this one. ₹{0} is charged now, and then each month. Stop any time.").format(price) if change
							 else _("₹{0} is charged now, and then each month. You agree to monthly auto-pay on the next page. Stop any time.").format(price))
		card["actions"].append({"label": _("Change to {0} and pay ₹{1}").format(plan_row.plan_name, price) if change else _("Agree and pay ₹{0}").format(price), "call": API + "start", "args": {"plan": plan_row.plan_name}, "kind": "primary"})
	return {"items": [card]}


@frappe.whitelist(methods=["POST"])
def start(plan: str) -> dict:
	"""The person chooses a paid plan: they are sent to agree to monthly auto-pay."""
	return plan_billing.start(_user(), plan)


@frappe.whitelist(methods=["POST"])
def stop() -> dict:
	"""The person stops renewing; the plan stays to the end of the month they have paid for."""
	return plan_billing.stop(_user())
