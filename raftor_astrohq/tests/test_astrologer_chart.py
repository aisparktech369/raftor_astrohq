"""The astrologer's page of a customer's chart (report_view.py): only the astrologer of the customer's booking and the team, only a birth profile the customer shares, every pane with the unchecked ones marked Draft,
and what is kept is kept for the customer.

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_astrologer_chart
"""
import html
import re
from unittest import mock

import frappe

from raftor_astrohq import answers, astrology, page_definitions, places, report_view, vocabulary
from raftor_astrohq.tests.helpers import FAMILY, GOOD, TABLE, AstroTestCase, make_user
from raftor_astrohq.tests.test_arrange import MODES
from raftor_astrohq.tests.test_kundli_reports import DELHI
from raftor_astrohq.tests.test_report_view import DRISHTI, shape
from raftor_websitehq.website_hq import report_html

BOOKING = "BK-TEST-1"


class Chart(AstroTestCase):
	def setUp(self):
		super().setUp()
		self.asked = []
		advanced = {**MODES["CORE_ADVANCED"], "drishti": DRISHTI}

		def chart(birth, opcode="SUPER_BASIC", partner=None):
			self.asked.append((opcode, birth["year"]))
			return advanced if opcode == "CORE_ADVANCED" else MODES[opcode]

		self.customer = make_user(**{TABLE: [FAMILY, GOOD]}).name  # (their own comes first whatever the order they were written in)
		self.astrologer, self.stranger = make_user().name, make_user().name
		self.booking = {"name": BOOKING, "provider_user": self.astrologer, "customer_user": self.customer, "workflow_state": "Confirmed", "slot_start": None}
		real = frappe.db.get_value

		def get_value(doctype, filters=None, fieldname="name", *args, **kwargs):
			if doctype == "Booking":
				return frappe._dict(self.booking) if filters == BOOKING else None
			return real(doctype, filters, fieldname, *args, **kwargs)

		for patcher in (mock.patch.object(astrology, "chart", chart), mock.patch.object(places, "lookup", lambda text, on: dict(DELHI)), mock.patch.object(frappe.db, "get_value", get_value)):
			patcher.start()
			self.addCleanup(patcher.stop)
		frappe.cache().delete_keys("astro_sky:*")
		self.addCleanup(lambda: frappe.cache().delete_keys("astro_sky:*"))

	def as_user(self, user):
		frappe.set_user(user)

	def rows(self):
		return {row.full_name: row for row in frappe.get_doc("User", self.customer).get(TABLE)}


class TestWhoMayOpenIt(Chart):
	def test_the_astrologer_of_the_booking_and_the_team_may_and_nobody_else(self):
		self.as_user(self.astrologer)
		self.assertEqual(report_view.booking_of(BOOKING).customer_user, self.customer)
		self.as_user("Administrator")
		self.assertEqual(report_view.booking_of(BOOKING).name, BOOKING)
		self.as_user(self.stranger)
		for call in (report_view.booking_of, report_view.chart_view):
			with self.assertRaises(frappe.DoesNotExistError, msg=call.__name__):
				call(BOOKING)
		self.as_user("Guest")
		with self.assertRaises(frappe.DoesNotExistError):
			report_view.chart_view(BOOKING)
		self.assertEqual(self.asked, [])  # the engine is never asked for someone who may not see the chart

	def test_only_a_booking_that_is_still_to_be_run_or_has_been_run_gives_a_chart(self):
		self.as_user(self.astrologer)
		for state in ("Requested", "Confirmed", "Delivered"):
			self.booking["workflow_state"] = state
			self.assertEqual(report_view.booking_of(BOOKING).workflow_state, state)
		for state in ("Declined", "Expired", "Cancelled", "No-show"):
			self.booking["workflow_state"] = state
			with self.assertRaises(frappe.DoesNotExistError, msg=state):
				report_view.booking_of(BOOKING)

	def test_a_booking_that_is_not_there_or_has_no_customer_gives_nothing_and_says_the_same(self):
		self.as_user(self.astrologer)
		for booking in (None, "", "BK-NOT-THERE"):
			with self.assertRaises(frappe.DoesNotExistError):
				report_view.booking_of(booking)
		self.booking["customer_user"] = None
		with self.assertRaises(frappe.DoesNotExistError):
			report_view.booking_of(BOOKING)

	def test_their_own_profile_comes_first_then_the_family_they_may_share(self):
		shared = report_view.shared_profiles(self.customer)
		self.assertEqual([r.full_name for r in shared], ["Asha Rao", "Ravi Rao"])
		self.assertEqual(report_view.chosen_profile(shared, None).full_name, "Asha Rao")
		self.assertEqual(report_view.chosen_profile(shared, shared[1].name).full_name, "Ravi Rao")
		self.assertEqual(report_view.chosen_profile(shared, "not-a-row").full_name, "Asha Rao")  # a name that is not one of those shared is not opened
		self.assertIsNone(report_view.chosen_profile([], None))
		self.assertEqual(report_view.shared_profiles(self.stranger), [])

	def test_a_family_members_profile_the_customer_did_not_confirm_they_may_share_is_never_opened(self):
		rows = [frappe._dict(name="r1", relationship="Spouse", permission_given=0, full_name="No"), frappe._dict(name="r2", relationship="You", permission_given=0, full_name="Own"),
				frappe._dict(name="r3", relationship="Child", permission_given=1, full_name="Yes")]
		user = mock.Mock()
		user.get = lambda field: rows if field == TABLE else []
		real = frappe.get_doc
		with mock.patch.object(frappe, "get_doc", lambda *args, **kwargs: user if args[:1] == ("User",) else real(*args, **kwargs)):
			self.assertEqual([r.full_name for r in report_view.shared_profiles("someone")], ["Own", "Yes"])  # (the form does not let one be kept without it: this is a second lock)


class TestThePage(Chart):
	def test_it_says_whose_chart_it_is_and_offers_the_other_people_the_customer_shares_and_the_way_back(self):
		self.as_user(self.astrologer)
		(item,) = report_view.chart_view(BOOKING)["items"]
		head = item["body_html"].split('<div class="rv-board', 1)[0]
		self.assertIn('<h1 class="rv-name">Asha Rao</h1><span class="rv-badge">Themselves</span><span class="rv-born">14 August 1990, 06:42 · Pune, India</span>', head)
		links = re.findall(r'<a class="rv-link" href="([^"]*)">([^<]*)</a>', head)
		self.assertEqual([html.unescape(label) for _href, label in links], ["Back to your bookings", "See Ravi Rao's chart"])
		self.assertEqual(html.unescape(links[0][0]).rstrip("/").split("/")[-2:], ["provider", "bookings"])  # (the page is wide: it has no left menu to go back by)
		self.assertIn(f"booking={BOOKING}", html.unescape(links[1][0]))
		self.assertIn(f"profile={self.rows()['Ravi Rao'].name}", html.unescape(links[1][0]))
		self.assertEqual(len(re.findall(r"<a [^>]*href=", report_html.clean(head))), 2)  # both are pages of this site, so websitehq lets both through
		self.assertIn('<h1 class="rv-name">Asha Rao</h1>', report_html.clean(head))  # (and the name stays the page's main heading)
		self.assertIn(f"booking={BOOKING}&amp;profile=", head)  # (an address is written as an attribute value should be)

	def test_the_other_person_the_customer_shares_has_their_own_page_and_the_way_back_to_the_first(self):
		self.as_user(self.astrologer)
		(item,) = report_view.chart_view(BOOKING, self.rows()["Ravi Rao"].name)["items"]
		head = item["body_html"]
		self.assertIn('<h1 class="rv-name">Ravi Rao</h1><span class="rv-badge">Spouse</span><span class="rv-born">2 March 1988 · Jaipur, India</span>', head)
		self.assertEqual([html.unescape(label) for _href, label in re.findall(r'<a class="rv-link" href="([^"]*)">([^<]*)</a>', head)], ["Back to your bookings", "See Asha Rao's chart"])

	def test_it_is_the_wide_board_with_every_pane_and_what_nobody_checked_is_marked_draft(self):
		self.as_user(self.astrologer)
		(item,) = report_view.chart_view(BOOKING)["items"]
		markup = item["body_html"]
		self.assertTrue(markup.startswith('<div class="rv-who">'))
		self.assertIn('<div class="rv-board rv-board-wide"', markup)
		self.assertEqual(markup.count("<details"), 14)
		self.assertEqual(markup.count('class="rv-draft"'), 10)
		for title in ("Birth chart · D1", "Drishti · planet looks at planet", "Shad bala", "Karakas · special lagnas", "Today from lagna", "Houses"):
			self.assertIn(title, markup)
		self.assertIn("Su 24°06′", markup)

	def test_a_profile_without_a_birth_time_is_said_so_in_words_and_the_people_the_customer_shares_are_still_there(self):
		self.as_user(self.astrologer)
		(item,) = report_view.chart_view(BOOKING, self.rows()["Ravi Rao"].name)["items"]
		self.assertIn("The time of birth is not known, so a chart cannot be drawn.", item["body_html"])
		self.assertNotIn("rv-board", item["body_html"])
		self.assertIn("See Asha Rao", html.unescape(item["body_html"]))
		self.assertEqual(self.asked, [])

	def test_what_the_engine_answers_is_kept_for_the_customer_never_for_the_astrologer(self):
		self.as_user(self.astrologer)
		report_view.chart_view(BOOKING)
		report_view.chart_view(BOOKING)
		self.assertEqual(sorted(opcode for opcode, _year in self.asked), ["CORE_ADVANCED", "KP_SYSTEM", "SUPER_BASIC"])  # asked once: the second look reads what is kept (and the sky, kept a day)
		self.assertEqual(frappe.db.count(answers.DOCTYPE, {"user": self.customer}), 2)
		self.assertEqual(frappe.db.count(answers.DOCTYPE, {"user": self.astrologer}), 0)

	def test_a_customer_who_shares_nothing_has_no_chart(self):
		self.as_user(self.astrologer)
		self.booking["customer_user"] = self.stranger
		self.assertEqual(report_view.chart_view(BOOKING), {"items": []})

	def test_a_name_that_is_markup_never_reaches_a_page_as_markup(self):
		self.as_user("Administrator")
		rows = self.rows()
		frappe.db.set_value("Astro Birth Profile", rows["Asha Rao"].name, {"full_name": "<script>alert(1)</script>Asha", "place_of_birth": "<b>Pune</b>"})
		frappe.db.set_value("Astro Birth Profile", rows["Ravi Rao"].name, "full_name", '"><img src=x onerror=alert(1)>')
		html_out = report_html.clean(report_view.chart_view(BOOKING)["items"][0]["body_html"])
		tags = shape(html_out)
		self.assertFalse({tag for tag, _names in tags} & {"script", "img"})
		self.assertFalse([name for _tag, names in tags for name in names if name.startswith("on")])
		self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;Asha", html_out)  # (the words stay, as words)
		self.assertIn("&lt;b&gt;Pune&lt;/b&gt;", html_out)  # (so does the place of birth)


class TestHowTheAstrologerGetsThere(Chart):
	def test_the_booking_has_a_way_to_the_chart_for_its_astrologer_only_and_only_when_something_is_shared(self):
		self.as_user(self.astrologer)
		(action,) = report_view.booking_actions(BOOKING)
		self.assertEqual(action["label"], "View chart")
		self.assertTrue(action["href"].endswith(f"/provider/chart?booking={BOOKING}") or action["href"].endswith(f"provider/chart?booking={BOOKING}"), action["href"])
		self.as_user(self.stranger)
		self.assertEqual(report_view.booking_actions(BOOKING), [])
		self.as_user(self.astrologer)
		self.booking["workflow_state"] = "Declined"
		self.assertEqual(report_view.booking_actions(BOOKING), [])
		self.booking.update(workflow_state="Confirmed", customer_user=self.stranger)
		self.assertEqual(report_view.booking_actions(BOOKING), [])

	def test_the_vertical_says_so_and_websitehq_is_told_the_page_may_send_markup(self):
		self.assertEqual(vocabulary.vocabulary()["booking_actions"], "raftor_astrohq.report_view.booking_actions")
		self.assertTrue(callable(frappe.get_attr(vocabulary.vocabulary()["booking_actions"])))
		self.assertIn("raftor_astrohq.report_view.chart_view", frappe.get_hooks("rfhq_trusted_html_sources"))

	def test_the_page_is_for_providers_it_is_wide_and_asks_for_the_report_view(self):
		page = page_definitions.chart_page()
		self.assertEqual((page["route"], page["roles"], page["otherwise"], page["wide"]), ("provider/chart", ["Service Provider"], "provider/join", True))
		self.assertIn(page, page_definitions.definitions())
		sources = {section["key"]: section["source"] for section in page["sections"]}
		self.assertEqual(sources["chart"]["card"], "Report View")
		self.assertEqual(sources["chart"]["url_args"], "booking,profile")
		for source in sources.values():
			self.assertIn(frappe.get_attr(source["method"]), frappe.whitelisted)  # the page may ask for it; the method itself checks who
