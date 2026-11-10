"""The plans as boxes on the website: made from the AI Plans, kept in step with them, drawn by websitehq's Service Card, and the pages that hold them (/plans, /plans/choose)."""
import frappe

from raftor_astrohq import page_definitions, plan_site, plans
from raftor_astrohq.tests.helpers import AstroTestCase
from raftor_websitehq.website_hq.page_groups import page_url
from raftor_websitehq.website_hq.page_sync import check

DETAILS = "Subscription Plan Details"


def box(name: str) -> str:
	return frappe.get_doc("Web Template", "Service Card").render({"plan_name": name})


def pages() -> dict:
	return {d["route"]: d for d in page_definitions.definitions()}


class TestTheBoxes(AstroTestCase):
	def setUp(self):
		super().setUp()
		plans.ensure_plans()
		plan_site.sync()

	def test_each_plan_has_a_box_made_from_it_and_nothing_is_typed_twice(self):
		for row in frappe.get_all("AI Plan", fields=[*plans.FIELDS, "enabled"]):
			plan = frappe._dict(row)
			record = frappe.db.get_value("Subscription Plan", plan.plan_name, ["cost", "currency", "billing_interval", "billing_interval_count", "is_public"], as_dict=True)
			self.assertEqual((record.cost, record.currency, record.billing_interval, record.billing_interval_count), (plan.monthly_price, "INR", "Month", 1), plan.plan_name)
			self.assertEqual(record.is_public, 0, "servicehq's own plans page must not list these")
			details = frappe.get_doc(DETAILS, plan.plan_name)
			self.assertEqual((details.show_on_website, details.display_order, details.plan_tagline), (plan.enabled, plan.sort_order, plan.tagline))
			self.assertEqual([f.feature_text for f in details.features], plans.limit_lines(plan))
			self.assertEqual([f.highlight for f in details.features], [1] + [0] * (len(details.features) - 1))  # the replies are what the plans differ by

	def test_the_item_the_records_point_at_is_never_sold(self):
		item = frappe.db.get_value("Item", plan_site.ITEM, ["disabled", "is_sales_item", "is_stock_item"], as_dict=True)
		self.assertEqual((item.disabled, item.is_sales_item, item.is_stock_item), (1, 0, 0))

	def test_a_plan_saved_in_desk_changes_its_box(self):
		doc = frappe.get_doc("AI Plan", "Seeker")
		doc.update({"replies_per_month": 777, "monthly_price": 199, "tagline": "Now and then"})
		doc.save()
		self.assertEqual(frappe.db.get_value("Subscription Plan", "Seeker", ["cost", "monthly_quota"]), (199, 777))
		details = frappe.get_doc(DETAILS, "Seeker")
		self.assertEqual(details.plan_tagline, "Now and then")
		self.assertIn("777", details.features[0].feature_text)
		self.assertEqual(len(details.features), len(plans.limit_lines(doc)))  # the old lines are replaced, not added to

	def test_what_the_business_team_wrote_on_a_box_is_kept(self):
		frappe.db.set_value(DETAILS, "Seeker", {"cta_label": "Take Seeker", "featured": 1, "badge_label": "Chosen most", "whole_amounts": 0, "price_suffix": "Every month"})
		plan_site.sync()
		self.assertEqual(frappe.db.get_value(DETAILS, "Seeker", ["cta_label", "featured", "badge_label", "whole_amounts", "price_suffix"]), ("Take Seeker", 1, "Chosen most", 0, "Every month"))

	def test_a_plan_switched_off_or_removed_leaves_the_page(self):
		doc = frappe.get_doc("AI Plan", "Needy")
		doc.enabled = 0
		doc.save()
		self.assertEqual(frappe.db.get_value(DETAILS, "Needy", "show_on_website"), 0)
		self.assertNotIn("Needy", plan_site.plan_names())
		self.assertEqual(box("Needy").strip(), "")  # the card draws nothing for it
		doc.enabled = 1
		doc.save()
		self.assertEqual(frappe.db.get_value(DETAILS, "Needy", "show_on_website"), 1)
		plan_site.on_plan_removed(doc)
		self.assertEqual(frappe.db.get_value(DETAILS, "Needy", "show_on_website"), 0)

	def test_a_box_that_cannot_be_made_does_not_stop_the_plan_being_saved(self):
		from unittest.mock import patch

		with patch.object(plan_site, "sync", side_effect=frappe.ValidationError("no")):
			plan_site.on_plan_saved(frappe._dict(name="Seeker"))  # says so in the Error Log and carries on
		self.assertTrue(frappe.get_all("Error Log", filters={"method": ["like", "The plans page could not be updated for Seeker%"]}, limit=1))

	def test_the_box_reads_the_price_whole_and_a_price_of_0_reads_the_sites_word(self):
		word = frappe.db.get_single_value("Website HQ Settings", "free_price_word")
		self.addCleanup(frappe.db.set_single_value, "Website HQ Settings", "free_price_word", word)
		frappe.db.set_single_value("Website HQ Settings", "free_price_word", "Free")
		self.assertIn("₹ 149", box("Seeker"))
		self.assertNotIn("149.00", box("Seeker"))
		self.assertIn("/month", box("Seeker"))
		self.assertNotIn("/month", box("Free"))
		self.assertIn(">Free<", box("Free"))
		frappe.db.set_single_value("Website HQ Settings", "free_price_word", "")
		self.assertIn("₹ 0", box("Free"))  # blank: as it was


class TestThePages(AstroTestCase):
	def setUp(self):
		super().setUp()
		plans.ensure_plans()
		plan_site.sync()

	def test_the_plans_page_is_for_everyone_with_a_box_for_each_plan_in_a_row(self):
		page = check(pages()["plans"])
		self.assertFalse(page["login_required"])
		boxes = next(s for s in page["sections"] if s["key"] == "boxes")
		self.assertEqual([c["values"]["plan_name"] for c in boxes["cards"]], plan_site.plan_names())
		self.assertEqual({c["type"] for c in boxes["cards"]}, {"Service Card"})
		self.assertEqual(boxes["columns"], str(len(plan_site.plan_names())))
		for name in plan_site.plan_names():
			self.assertTrue(frappe.db.exists(DETAILS, name), name)  # no box points at a plan that has no record

	def test_the_page_before_the_plans_exist_still_shows_the_plans_that_ship(self):
		self.assertEqual([p["plan_name"] for p in plans.DEFAULT_PLANS], ["Free", "Seeker", "Needy"])
		frappe.db.delete("AI Plan")
		self.assertEqual(plan_site.plan_names(), ["Free", "Seeker", "Needy"])

	def test_the_choose_page_needs_a_sign_in_and_takes_the_plan_from_the_address(self):
		page = check(pages()["plans/choose"])
		self.assertTrue(page["login_required"])
		source = next(s for s in page["sections"] if s["key"] == "plan")["source"]
		self.assertEqual((source["method"], source["url_args"]), ("raftor_astrohq.plans_api.choose_card", "plan"))

	def test_the_buttons_lead_to_the_guide_for_free_and_to_the_confirming_page_for_a_paid_plan(self):
		self.assertEqual(frappe.db.get_value(DETAILS, "Free", "cta_url"), page_url("ask", "pandit-ji"))
		self.assertEqual(frappe.db.get_value(DETAILS, "Seeker", "cta_url"), page_url("plans", "choose", plan="Seeker"))
		self.assertEqual(frappe.db.get_value(DETAILS, "Needy", "cta_action"), "External URL")  # the plans are taken through PaymentHQ, not through the Service Card's own checkout

	def test_the_addresses_the_plans_code_uses_are_the_pages(self):
		self.assertEqual(plans.PLANS_PAGE, page_url("plans"))
		self.assertEqual(plans.MY_PLAN_PAGE, "/" + next(r for r in pages() if r.endswith("ai-plan")))
		self.assertEqual(plans.PLANS_CARD["url"], plans.PLANS_PAGE)
