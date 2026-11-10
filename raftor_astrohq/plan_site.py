"""The plans as boxes on the website: the AI Plans drawn by websitehq's Service Card, the usual pricing box (name, price, what is in it, a button).

The Service Card draws an ERPNext Subscription Plan with its website details (a price of 0 reads the site's word for it, "Free"), so each AI Plan has one of each, made from it here and kept in step whenever the AI Plan is saved (hook doc_events) and on every migrate.
The AI Plan is the only place the numbers are written; this only copies them, so nothing is typed twice. What the business team writes on a plan's website details in Desk (the button's words, a badge, which plan is featured) is
set once and then left alone.
These records are for drawing only. Nobody subscribes to them (the plans are taken through plan_billing.py), and they are not public on servicehq's plans page; the units servicehq asks of a plan are filled with the plan's replies.

    sync(plan=None)         make or update the website records of one AI Plan, or of all of them
    on_plan_saved(doc)      (hook) an AI Plan was saved
    on_plan_removed(doc)    (hook) an AI Plan was deleted: its box is taken off the page
    plan_names()            the plans the page shows, in order
"""
import frappe
from frappe import _
from frappe.utils import cint, flt

from raftor_astrohq import plans

ITEM = "AI plan"  # the one Item every plan record points at (a Subscription Plan needs an Item); disabled, so no shop, order or invoice ever offers it
PLAN, DETAILS = "Subscription Plan", "Subscription Plan Details"
CURRENCY = "INR"  # the currency of AI Plan.monthly_price


def plan_names() -> list[str]:
	"""The enabled plans in order; before the plans exist (a first install), the ones that ship."""
	return frappe.get_all("AI Plan", filters={"enabled": 1}, order_by="sort_order asc, creation asc", pluck="name") or [p["plan_name"] for p in plans.DEFAULT_PLANS]


def _item() -> str:
	if not frappe.db.exists("Item", ITEM):
		frappe.get_doc({"doctype": "Item", "item_code": ITEM, "item_name": ITEM, "item_group": "All Item Groups", "stock_uom": "Nos", "disabled": 1, "is_stock_item": 0, "is_sales_item": 0, "is_purchase_item": 0,
						"description": "The AI guides' plans (the AI Plan list). Only the plans page's boxes point at this; it is never sold."}).insert(ignore_permissions=True)
	return ITEM


def _button(plan) -> tuple[str, str, str]:
	"""The label, address and style of a plan's button: Free goes to the guide, a paid plan to the page that confirms it."""
	from raftor_websitehq.website_hq.page_groups import page_url

	if flt(plan.monthly_price) <= 0:
		return _("Start free"), page_url("ask", "pandit-ji"), "Outline"
	return _("Choose {0}").format(plan.plan_name), page_url("plans", "choose", plan=plan.plan_name), "Primary"


def _plan_record(plan) -> None:
	values = {"currency": CURRENCY, "item": _item(), "price_determination": "Fixed Rate", "cost": flt(plan.monthly_price, 2), "billing_interval": "Month", "billing_interval_count": 1, "is_public": 0,
			  "monthly_quota": max(1, cint(plan.replies_per_month)), "daily_quota": cint(plan.replies_per_day)}
	if frappe.db.exists(PLAN, plan.name):
		doc = frappe.get_doc(PLAN, plan.name)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc({"doctype": PLAN, "plan_name": plan.name, **values}).insert(ignore_permissions=True)


def _details_record(plan) -> None:
	shown = {"show_on_website": 1 if cint(plan.enabled) else 0, "display_order": cint(plan.sort_order), "plan_tagline": plan.tagline or ""}
	features = [{"feature_text": line, "included": 1, "highlight": 1 if n == 0 else 0} for n, line in enumerate(plans.limit_lines(plan))]
	exists = frappe.db.exists(DETAILS, plan.name)
	if exists:
		doc = frappe.get_doc(DETAILS, plan.name)
		doc.update(shown)
	else:  # the words of the button and the note under the price are the business team's to change in Desk once they are made
		label, url, style = _button(plan)
		doc = frappe.get_doc({"doctype": DETAILS, "subscription_plan": plan.name, **shown, "featured": 0, "cta_label": label, "cta_url": url, "cta_style": style, "cta_action": "External URL",
							  "whole_amounts": 1, "price_suffix": _("No payment needed") if flt(plan.monthly_price) <= 0 else _("Renews each month. Stop any time.")})
	doc.set("features", [])
	for row in features:
		doc.append("features", row)
	(doc.save if exists else doc.insert)(ignore_permissions=True)


def sync(plan: str | None = None) -> None:
	"""Makes the website records of one AI Plan (or of every one) from the plan itself. Safe to repeat."""
	for name in [plan] if plan else frappe.get_all("AI Plan", pluck="name"):
		row = frappe.get_doc("AI Plan", name)
		_plan_record(row)
		_details_record(row)


def on_plan_saved(doc, method=None) -> None:
	"""A plan was saved in Desk or made by the install: its box follows. The plan is saved either way; a box that could not be drawn is in the Error Log."""
	try:
		sync(doc.name)
	except Exception:
		frappe.log_error(f"The plans page could not be updated for {doc.name}", frappe.get_traceback())
		frappe.msgprint(_("The plan is saved, but its box on the plans page could not be updated. The Error Log has the reason."), indicator="orange", alert=True)


def on_plan_removed(doc, method=None) -> None:
	"""A plan was deleted: its box is taken off the page (the records stay, hidden, as something may still point at them)."""
	if frappe.db.exists(DETAILS, doc.name):
		frappe.db.set_value(DETAILS, doc.name, "show_on_website", 0)
