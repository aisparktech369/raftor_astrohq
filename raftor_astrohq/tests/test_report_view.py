"""The panes of a report view (panes.py), the board they sit on (report_view.py, views/*.json) and what reaches a page (websitehq cleans it).

The panes are tried on the engine's own answers for one invented birth (tests/fixtures/engine_answers_all_modes.json.gz).

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_report_view
"""
import datetime
import re
from html.parser import HTMLParser
from unittest import mock

import frappe

from raftor_astrohq import answers, astrology, panes, places, report_view, reports
from raftor_astrohq.tests.helpers import AstroTestCase, make_user
from raftor_astrohq.tests.test_arrange import MODES, words
from raftor_astrohq.tests.test_kundli_reports import DELHI, KUNDLI_DETAILS
from raftor_websitehq.website_hq import report_html

TODAY = datetime.date(2026, 10, 23)
DRISHTI = {"planets": ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"],
		   "matrix": [[0, 0.2, 40.7, 0, 30.2, 0, 43.6, 20.8, 27.1], [15.4, 0, 3.9, 38.8, 14.4, 26.2, 6.3, 23.8, 0], [12.8, 58.1, 0, 1.2, 0, 7.4, 0, 0, 20.2], [0, 11.9, 17.3, 0, 10.9, 0, 24.4, 6.2, 38.8],
				  [7.6, 37.8, 0, 0, 0, 2.2, 0, 0, 41.1], [0, 5.6, 29.9, 0, 19.4, 0, 37.0, 12.5, 32.5], [16.4, 46.6, 0, 49.7, 0, 56.0, 0, 0, 6.0], [2.9, 33.1, 0, 0, 0, 0, 0, 0, 60], [32.9, 11.9, 50.1, 12.4, 55.3, 25.0, 46.5, 60, 0]]}


def answers_of(drishti=True) -> dict:
	advanced = {**MODES["CORE_ADVANCED"], **({"drishti": DRISHTI} if drishti else {})}
	return {"CORE_ADVANCED": advanced, "KP_SYSTEM": MODES["KP_SYSTEM"]}


CTX = {"today": TODAY, "sky": MODES["SUPER_BASIC"]}  # (the birth's own sky stands in for today's)


def shape(html: str) -> list:
	"""Every tag with the names of its attributes, in order: two markups of the same shape lost nothing."""
	found = []

	class Parser(HTMLParser):
		def handle_starttag(self, tag, attrs):
			found.append((tag, tuple(sorted(name for name, _ in attrs))))

	Parser().feed(html)
	return found


class TestEachPane(AstroTestCase):
	def pane(self, name, **options):
		return panes.PANES[name](answers_of(), CTX, **options)

	def test_every_pane_has_something_to_say_on_the_sample_birth(self):
		for name in panes.PANES:
			made = self.pane(name)
			self.assertTrue(made and made["body"] and made["summary"], name)

	def test_every_pane_is_made_of_what_a_page_may_carry_and_nothing_is_lost_in_the_cleaning(self):
		for name in panes.PANES:
			html = self.pane(name)["body"]
			self.assertEqual(shape(report_html.clean(html)), shape(html), name)  # no tag, no attribute, no class dropped
			self.assertEqual(words(report_html.clean(html)), words(html), name)
			self.assertNotIn("style=", html, name)

	def test_a_pane_has_nothing_to_say_when_the_answer_has_nothing_for_it(self):
		self.assertIsNone(panes.drishti(answers_of(drishti=False), CTX))
		self.assertIsNone(panes.today(answers_of(), {"today": TODAY, "sky": None}))
		self.assertIsNone(panes.varga(answers_of(), CTX, chart_key="D13"))  # a divisional chart the engine does not make
		self.assertIsNone(panes.dasha(answers_of(), {"today": datetime.date(2200, 1, 1), "sky": None}))  # no period running

	def test_the_birth_chart_has_each_planet_with_its_degree_and_the_lagna_in_the_first_house(self):
		body = self.pane("chart", width=540, height=250)["body"]
		for text in ("As 14°12′", "Su 24°06′", "Mo 23°41′", "Ve 4°53′ R", "Ke 29°52′ R"):
			self.assertIn(f">{text}</text>", body)
		self.assertIn('role="img"', body)
		self.assertEqual(body.count("<polygon"), 12)
		self.assertIn("Su 24°</text>", self.pane("chart", minutes=False)["body"])

	def test_the_planets_table_has_the_lords_the_nakshatra_and_the_kp_lords(self):
		text = words(self.pane("planets")["body"])
		for expected in ("Su | 24°06′ | Taurus (Vrishabha) | Ve | 9 | Mrigashira | 1 | Ma | Ra | Ra | Leo", "Mo | 23°41′ | Pisces (Meena) | Ju | 7 | Revati | 3 | Me | Ma | Me | Aqu"):
			self.assertIn(expected, text)
		compact = words(self.pane("planets", compact=True)["body"])
		self.assertIn("Su | 24°06′ | Tau | 9 | Mrigashira 1 | Ma·Ra", compact)

	def test_a_view_that_has_no_kp_answer_has_no_columns_for_the_sub_lords(self):
		without = {"CORE_ADVANCED": answers_of()["CORE_ADVANCED"]}
		self.assertIn("Su | 24°06′ | Taurus (Vrishabha) | Ve | 9 | Mrigashira | 1 | Ma | Leo", words(panes.planets(without, CTX)["body"]))
		self.assertNotIn("Sub", panes.planets(without, CTX)["body"])
		compact = panes.planets(without, CTX, compact=True)["body"]
		self.assertIn("Su | 24°06′ | Tau | 9 | Mrigashira 1 | Ma", words(compact))
		self.assertNotIn("Star·Sub", compact)

	def test_the_running_period_is_marked_and_the_next_main_periods_follow(self):
		made = self.pane("dasha")
		self.assertIn('<div class="rv-run"><b>Mo–Sa</b> running · until 29 Apr 2027</div>', made["body"])
		self.assertEqual(made["body"].count('class="rv-now"'), 1)
		self.assertIn("Ma main", made["body"])
		self.assertEqual(made["summary"], "Mo–Sa until 29 Apr 2027")

	def test_the_drishti_matrix_has_each_planet_in_a_row_and_a_column_and_the_strength_where_they_meet(self):
		made = self.pane("drishti")
		body = made["body"]
		self.assertEqual(body.count("<tr>"), 10)  # the head and nine rows
		self.assertIn('<td class="rv-h9 rv-strong">58</td>', body)  # Mars looks at the Moon: its eighth, 58 of 60
		self.assertEqual(body.count('class="rv-x"'), 9)  # a planet does not look at itself
		self.assertIn('<td class="rv-h3">15</td>', body)
		self.assertEqual(made["summary"], "strongest Ma→Mo 58, Sa→Ve 56, Ke→Ju 55")  # (Rahu and Ketu always look at each other with 60: not worth saying)
		self.assertIn("Row looks at column", body)

	def test_the_strength_bars_are_green_when_a_planet_has_what_it_needs(self):
		body = self.pane("shadbala")["body"]
		self.assertEqual(body.count("rv-bar-good"), 4)
		self.assertEqual(body.count("rv-bar-low"), 3)
		self.assertIn(">9.8</text>", body)
		self.assertEqual(self.pane("shadbala")["summary"], "strong Ju 9.8, Su 9.5 · weak Sa 3.9, Ma 4.4")

	def test_the_karakas_the_special_lagnas_and_the_arudhas(self):
		text = words(self.pane("karakas")["body"])
		self.assertIn("AK | AmK | BK | MK | PiK | PuK | GK | DK", text)
		self.assertIn("Sa | Su | Mo | Ma | Me | Ju | Ve | Ra", text)
		self.assertIn("BL Vir 29°33′", text)
		self.assertIn("UL Sco", text)
		self.assertNotIn("BL", words(self.pane("karakas", lagnas=False, arudhas=False)["body"]))

	def test_the_houses_with_their_signs_lords_and_planets_in_one_list_or_two(self):
		one = words(self.pane("houses")["body"])
		self.assertIn("12 | Leo | Su | Ma, Ju, Sa", one)
		two = self.pane("houses", two=True)
		self.assertIn("1 | Vir | Me |  |  | 7 | Pis | Ju | Mo", words(two["body"]))
		self.assertEqual(two["summary"], "5 Ke · 7 Mo · 9 Su · 10 Me, Ve · 11 Ra · 12 Ma, Ju, Sa")

	def test_the_facts_are_the_lagna_the_moon_the_star_and_with_the_panchang_the_day(self):
		text = words(self.pane("facts")["body"])
		for expected in ("Lagna | Virgo (Kanya) 14°12′", "Moon sign | Pisces (Meena)", "Birth star | Revati, pada 3", "Tithi | Krishna Paksha Dashami (Nithya)", "Weekday | Sunday · rise 05:26, set 19:13",
						 "Running | Moon / Saturn · to 29 Apr 2027", "Manglik | Yes by the usual rule", "Kala sarpa | No"):
			self.assertIn(expected, text)
		plain = words(self.pane("facts", panchang=False)["body"])
		self.assertIn("Birth star", plain)
		for left_out in ("Tithi", "Weekday", "Manglik"):
			self.assertNotIn(left_out, plain)

	def test_today_is_each_planets_sign_counted_from_the_persons_lagna(self):
		made = self.pane("today")
		text = words(made["body"])
		self.assertIn("Su | Tau 24°06′ | house 9", text)  # (the stand-in sky is the birth's own: Taurus, the 9th from Virgo)
		self.assertIn("Sa | Leo 26°51′ | house 12", text)
		self.assertTrue(made["summary"].startswith("today: Su 9"))

	def test_a_divisional_chart_is_drawn_in_the_sites_colours_and_titled_for_a_reader_who_cannot_see_it(self):
		body = self.pane("varga", chart_key="D9", label="Navamsa chart")["body"]
		self.assertIn('aria-label="Navamsa chart"', body)
		self.assertIn("var(--rv-heading)", body)
		self.assertNotIn("#", body.replace("&#", ""))  # no colour is typed into a picture: the page's theme gives them


class TestTheBoard(AstroTestCase):
	def test_a_customers_board_has_the_panes_an_astrologer_checked_and_no_draft_mark(self):
		view = report_view.view_named("customer")
		html = report_view.render(view, answers_of(), CTX, "reviewed")
		titles = re.findall(r'<h3 class="rv-title">([^<]*)', html)
		self.assertEqual(titles, ["Birth chart", "Planets", "At a glance", "Vimshottari", "Navamsa · D9"])
		self.assertNotIn("rv-draft", html)
		self.assertTrue(html.startswith('<div class="rv-board rv-board-lite" role="group" aria-label="Your chart">'))

	def test_an_astrologers_board_has_every_pane_and_marks_what_nobody_checked(self):
		view = report_view.view_named("astrologer")
		html = report_view.render(view, answers_of(), CTX, "all")
		self.assertEqual(html.count("<details"), 14)
		self.assertEqual(html.count('class="rv-draft"'), 10)  # all but the chart, the navamsa, the planets and the dasha, which are checked
		self.assertTrue(html.startswith('<div class="rv-board rv-board-wide"'))
		self.assertIn('data-col="1" data-row="1" data-w="2"', html)

	def test_a_pane_that_the_answers_have_nothing_for_is_left_out_and_so_is_a_board_with_no_panes(self):
		html = report_view.render(report_view.view_named("astrologer"), answers_of(drishti=False), CTX, "all")
		self.assertEqual(html.count("<details"), 13)
		self.assertNotIn("Drishti", html)
		self.assertEqual(report_view.render({"board": "lite", "panes": [{"pane": "drishti", "title": "D", "reviewed": True}]}, answers_of(drishti=False), CTX, "all"), "")

	def test_a_pane_that_cannot_be_drawn_does_not_stop_the_page(self):
		with mock.patch.dict(panes.PANES, {"planets": mock.Mock(side_effect=KeyError("x"))}), mock.patch.object(frappe, "log_error") as logged:
			html = report_view.render(report_view.view_named("customer"), answers_of(), CTX, "reviewed")
		self.assertTrue(logged.called)
		self.assertIn("Birth chart", html)
		self.assertNotIn(">Planets<", html)

	def test_a_board_that_is_not_one_of_ours_is_the_lite_one_and_its_name_is_never_written_into_the_page(self):
		spec = {"pane": "planets", "title": "Planets", "reviewed": True}
		for board in ("", None, "huge", 'wide" onclick="x'):
			html = report_view.render({"board": board, "title": "T", "panes": [spec]}, answers_of(), CTX, "all")
			self.assertTrue(html.startswith('<div class="rv-board rv-board-lite"'), board)
			self.assertNotIn("onclick", html)

	def test_a_look_is_one_of_ours_or_nothing_and_a_board_without_one_is_as_it_was(self):
		spec = {"pane": "planets", "title": "Planets", "reviewed": True}
		self.assertTrue(report_view.render({"board": "lite", "look": "roomy", "title": "T", "panes": [spec]}, answers_of(), CTX, "all").startswith('<div class="rv-board rv-board-lite rv-look-roomy"'))
		for look in ("", None, "huge", 'roomy" onclick="x'):
			html = report_view.render({"board": "lite", "look": look, "title": "T", "panes": [spec]}, answers_of(), CTX, "all")
			self.assertTrue(html.startswith('<div class="rv-board rv-board-lite"'), look)
			self.assertNotIn("onclick", html)
		for name in ("customer", "astrologer"):
			self.assertNotIn("rv-look", report_view.render(report_view.view_named(name), answers_of(), CTX, "all"), name)

	def test_the_panes_that_fold_on_a_phone_are_marked_and_nothing_else_is(self):
		html = report_view.render(report_view.view_named("customer"), answers_of(), CTX, "reviewed")
		shut = re.findall(r'<details class="rv-pane" open[^>]*?( data-shut)?>', html)
		self.assertEqual(len([s for s in shut if s]), 3)  # at a glance, Vimshottari, Navamsa; the chart and the planets stay open

	def test_on_a_phone_an_astrologer_has_the_chart_the_planets_and_the_period_open_and_the_rest_folded_to_a_line(self):
		html = report_view.render(report_view.view_named("astrologer"), answers_of(), CTX, "all")
		shut = re.findall(r'<details class="rv-pane" open[^>]*?( data-shut)?>', html)
		self.assertEqual((len(shut), len([s for s in shut if s])), (14, 11))
		for open_one in ("Birth chart · D1", "Planets", "Vimshottari"):
			self.assertRegex(html, rf'<details class="rv-pane" open data-col="\d" data-row="\d"(?: data-w="\d")?><summary><h3 class="rv-title">{open_one}')

	def test_nothing_a_person_or_the_engine_wrote_reaches_the_page_as_markup(self):
		hostile = answers_of()
		hostile["CORE_ADVANCED"] = {**hostile["CORE_ADVANCED"], "lagna": {**hostile["CORE_ADVANCED"]["lagna"], "sign": "<script>alert(1)</script>Virgo"}}
		html = report_view.render(report_view.view_named("customer"), hostile, CTX, "all")
		self.assertNotIn("<script", html)
		self.assertNotIn("onerror", html)

	def test_the_views_are_valid_and_no_two_panes_sit_in_the_same_place(self):
		for name, columns, rows in (("customer", 3, 4), ("astrologer", 4, 4)):
			view = report_view.view_named(name)
			taken = set()
			for spec in view["panes"]:
				self.assertIn(spec["pane"], panes.PANES, name)
				col, row, wide, tall = (spec["at"] + [1, 1, 1, 1])[:4]
				self.assertTrue(1 <= col and col + wide - 1 <= columns and 1 <= row and row + tall - 1 <= rows, f"{name}: {spec['title']}")
				cells = {(c, r) for c in range(col, col + wide) for r in range(row, row + tall)}
				self.assertFalse(cells & taken, f"{name}: {spec['title']} sits on another pane")
				taken |= cells
				self.assertTrue(spec.get("title"))
			self.assertIn(view["board"], report_view.BOARDS)
			self.assertTrue(not view.get("look") or view["look"] in report_view.LOOKS)
			self.assertTrue(set(view["modes"]) <= set(MODES))


class TestWhatItIsMadeFrom(AstroTestCase):
	def test_the_sky_asked_for_is_this_hour_at_the_birth_place_in_the_time_of_that_place(self):
		numbers = {"latitude": 28.65, "longitude": 77.23, "timezone_offset": 5.5, "year": 1980, "month": 6, "day": 8, "hour": 13, "minute": 49, "second": 0}
		now = datetime.datetime(2026, 10, 23, 9, 40, tzinfo=datetime.timezone.utc)
		self.assertEqual(report_view.sky_numbers(numbers, DELHI, now), {"latitude": 28.65, "longitude": 77.23, "timezone_offset": 5.5, "year": 2026, "month": 10, "day": 23, "hour": 15, "minute": 0, "second": 0})
		late = datetime.datetime(2026, 10, 23, 23, 50, tzinfo=datetime.timezone.utc)
		over = report_view.sky_numbers(numbers, DELHI, late)
		self.assertEqual((over["day"], over["hour"]), (24, 5))  # the next day there
		west = report_view.sky_numbers(numbers, {**DELHI, "timezone_offset": -5.0}, now)
		self.assertEqual((west["day"], west["hour"]), (23, 4))

	def test_it_asks_for_the_modes_the_view_names_and_for_the_sky_only_when_a_pane_wants_it(self):
		asked = []

		def chart(birth, opcode="SUPER_BASIC", partner=None):
			asked.append((opcode, birth["year"]))
			return MODES[opcode]

		user = make_user().name
		frappe.cache().delete_keys("astro_sky:*")
		with mock.patch.object(astrology, "chart", chart), mock.patch.object(places, "lookup", lambda text, on: dict(DELHI)):
			data, ctx = report_view.data_for(user, KUNDLI_DETAILS, report_view.view_named("astrologer"), TODAY, show="all")
			self.assertEqual(sorted(data), ["CORE_ADVANCED", "KP_SYSTEM"])
			self.assertTrue(ctx["sky"])
			self.assertEqual(sorted(opcode for opcode, _year in asked), ["CORE_ADVANCED", "KP_SYSTEM", "SUPER_BASIC"])
			self.assertEqual({year for opcode, year in asked if opcode == "SUPER_BASIC"}, {datetime.datetime.now(datetime.timezone.utc).year})  # the sky is of now
			asked.clear()
			plain = {"modes": ["CORE_ADVANCED"], "panes": [{"pane": "chart"}]}
			data, ctx = report_view.data_for(user, KUNDLI_DETAILS, plain, TODAY)
			self.assertEqual(asked, [])  # kept
			self.assertIsNone(ctx["sky"])
			unchecked = {"modes": ["CORE_ADVANCED"], "panes": [{"pane": "today"}]}
			self.assertIsNone(report_view.data_for(user, KUNDLI_DETAILS, unchecked, TODAY)[1]["sky"])  # a customer does not have it: it is not asked for
			self.assertEqual(asked, [])
		frappe.cache().delete_keys("astro_sky:*")

	def test_the_customers_page_is_made_from_the_details_for_the_person_and_nothing_is_asked_twice(self):
		asked = []

		def chart(birth, opcode="SUPER_BASIC", partner=None):
			asked.append(opcode)
			return MODES[opcode]

		user = make_user().name
		with mock.patch.object(astrology, "chart", chart), mock.patch.object(places, "lookup", lambda text, on: dict(DELHI)), mock.patch.object(reports, "shown", lambda: "reviewed"):
			first = report_view.customer_view("ASTROHQ-REPORT-KUNDLI", KUNDLI_DETAILS, user)
			second = report_view.customer_view("ASTROHQ-REPORT-KUNDLI", KUNDLI_DETAILS, user)
		self.assertEqual(first, second)
		self.assertEqual(asked, ["CORE_ADVANCED"])
		self.assertIn("Birth chart", first)
		self.assertNotIn("Drishti", first)  # nobody has checked it, so a customer does not have it

	def test_the_reports_of_one_person_say_which_page_they_have(self):
		from raftor_astrohq import vocabulary

		listed = vocabulary.vocabulary()["reports"]
		for name in ("kundli", "detailed"):
			self.assertEqual(listed[name]["view"], "raftor_astrohq.report_view.customer_view")
			self.assertTrue(callable(frappe.get_attr(listed[name]["view"])))
		for name in ("match", "dasha", "kp", "panchang"):
			self.assertNotIn("view", listed[name])
