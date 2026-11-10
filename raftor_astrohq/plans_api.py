"""The pages of the plans: the plans page with a box for each plan (/plans), the page that confirms the plan a person chose (/plans/choose), and the person's own page (/my/astro-plan).

The boxes are websitehq's Service Card: this app answers the values (`boxes`), the card is websitehq's (website_hq/feed.py). The person's page is one card (App Records): the plan they have and what they have used. Taking a plan sends the
person to PaymentHQ's page to agree to monthly auto-pay; the plan is theirs when the first payment arrives (plan_billing.py). Everything these pages say about limits comes from the plans themselves (Astro Plan).
"""
import frappe
from frappe import _
from frappe.utils import add_days, cint, formatdate

from raftor_astrohq import plan_billing, plans
from raftor_websitehq.website_hq import free_price
from raftor_websitehq.website_hq.page_groups import page_url

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
	actions = [{"label": _("Change plan") if now["taken"] else _("See the plans"), "href": plans.PLANS_PAGE, "kind": "primary"}]
	if now["taken"] and now["renews"]:
		actions.append({"label": _("Stop renewing"), "call": API + "stop", "kind": "danger", "confirm": _("Stop renewing? Your plan stays until {0}.").format(formatdate(now["paid_through"], "d MMMM")),
						"confirm_label": _("Stop renewing")})
	return {"id": "now", "title": _("Your plan: {0}").format(now["plan"]), "badge": badge, "tone": "success", "lines": lines, "actions": actions}


@frappe.whitelist(methods=["POST"])
def my_plan() -> dict:
	"""The person's own page: the plan they have, what they have used of it, and the way to change it or stop it. The card of the App Records list; the plans to choose from are on the plans page."""
	user = _user()
	return {"items": [_current_card(user, plans.quota(user))]}


def _money(amount) -> str:
	return _("₹{0}").format(f"{cint(amount):,}")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def boxes() -> dict:
	"""The boxes of the plans page, one for each plan on offer, as the values websitehq's Service Card draws. The plan a signed-in person has is marked, and its button leads to what they have used."""
	now = plans.quota(frappe.session.user) if frappe.session.user != "Guest" else {}
	items = []
	for row in frappe.get_all("Astro Plan", filters={"enabled": 1}, fields=plans.FIELDS, order_by="sort_order asc"):
		plan = frappe._dict(row)
		price = cint(plan.monthly_price)
		mine = bool(now) and not now.get("staff") and _is_mine(plan, now)
		lines = plans.limit_lines(plan)
		label = plans._fill(plan.button_label or ("" if price == 0 else _("Choose {plan}")), plan=plan.plan_name)
		url = plan.button_url or ("" if price == 0 else page_url("plans", "choose", plan=plan.plan_name))
		note, badge = plan.price_note or "", plan.badge or ""
		if mine:
			badge, label, url = _("Your plan"), _("See what you have used"), plans.MY_PLAN_PAGE
			note = _badge(now) if now["taken"] else note
		items.append({"title": plan.plan_name, "tagline": plan.tagline or "", "price": (free_price.rfhq_free_price_word() or _("Free")) if price == 0 else _money(price), "interval": "" if price == 0 else _("month"),
					  "price_note": note, "feature_lines": "\n".join(["* " + lines[0], *lines[1:]]), "badge": badge, "button_label": label, "button_url": url,
					  "button_style": "Primary" if price > 0 and not mine else "Outline"})
	return {"items": items}


@frappe.whitelist(methods=["POST"])
def choose_card(plan: str = "") -> dict:
	"""The page that confirms the plan the person chose on the plans page: what it gives, what it costs, and the button that sends them to agree to monthly auto-pay. A plan that cannot be taken gives no card."""
	user = _user()
	row = frappe.db.get_value("Astro Plan", {"name": plan, "enabled": 1}, plans.FIELDS, as_dict=True) if plan else None
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
