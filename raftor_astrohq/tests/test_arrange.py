"""The arranger (arrange.py, layouts/*.json, engine_words.json): what the astrology API answers, laid out as tables and charts, in words people read.

The ten layouts are tried on the engine's own answers for one invented birth (tests/fixtures/engine_answers_all_modes.json.gz, one answer for each mode); the small pieces on small made-up answers.

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_arrange
"""
import datetime
import gzip
import json
import re
from html import unescape
from pathlib import Path

from raftor_astrohq import arrange
from raftor_astrohq import report_pdf as rp
from raftor_astrohq.tests.helpers import AstroTestCase

TODAY = datetime.date(2026, 10, 23)
MODES = json.loads(gzip.open(Path(__file__).parent / "fixtures" / "engine_answers_all_modes.json.gz", "rt", encoding="utf-8").read())["modes"]
LAYOUT_OF = {"SUPER_BASIC": "basic", "CORE_BASIC": "basic", "CORE_STANDARD": "standard", "CORE_ADVANCED": "advanced", "MATCH_CALC": "match", "DASHA_CALC": "dasha", "ANNUAL_CALC": "annual",
			 "TRANSIT_CALC": "transit", "PANCHANGA": "panchang", "KP_SYSTEM": "kp"}
STRANGE = (r"\bNone\b", r"\bnan\b", r"\bTrue\b", r"\bFalse\b", r"[{}]", r"\[object", "Traceback", "undefined", "_")  # what a page must never show: a value left raw


def words(html: str) -> str:
	"""The text of a page, one line for each row and heading."""
	text = re.sub(r"<style.*?</style>", "", html, flags=re.S)
	text = re.sub(r"<svg.*?</svg>", "[chart]", text, flags=re.S)
	text = re.sub(r"</(tr|h1|h2|h3|p|caption)>", "\n", text)
	text = re.sub(r"</t[dh]>", " | ", text)
	return unescape(re.sub(r"<[^>]+>", "", text))


def page(mode: str, layout: str | None = None) -> str:
	return arrange.html(MODES[mode], layout or LAYOUT_OF[mode], today=TODAY, subject="Sample")


class TestTheEnginesWords(AstroTestCase):
	def test_planets_and_signs_are_written_by_name(self):
		self.assertEqual(arrange.clean("Su☉"), "Sun")
		self.assertEqual(arrange.clean("Raagu☊"), "Rahu")
		self.assertEqual(arrange.clean("♍︎Virgo"), "Virgo (Kanya)")
		self.assertEqual(arrange.clean("Venus♀℞"), "Venus (retrograde)")
		self.assertEqual(arrange.clean("♍︎Virgo 14° 12’ 56\""), "Virgo (Kanya) 14°12′56″")

	def test_the_librarys_tamil_spellings_become_ours_and_only_whole_words_do(self):
		self.assertEqual(arrange.clean("Revathi"), "Revati")
		self.assertEqual(arrange.clean("Sadhayam"), "Shatabhisha")
		self.assertEqual(arrange.clean("Krishna Paksha Dhasami (Nithya)"), "Krishna Paksha Dashami (Nithya)")
		self.assertEqual(arrange.clean("Soubhagya (Ve♀/Ju♃)"), "Saubhagya (Venus/Jupiter)")
		self.assertEqual(arrange.clean("Revathi  (Me☿) Quarter-3"), "Revati (Mercury) pada 3")
		self.assertEqual(arrange.clean("Sivakasi"), "Sivakasi")  # Siva alone is a yoga's name; a longer word is not

	def test_the_word_list_gives_every_nakshatra_its_name_in_the_order_the_library_has_them(self):
		data = json.loads(arrange.WORDS.read_text(encoding="utf-8"))
		self.assertEqual(len(data["nakshatras"]), 28)
		for number, name in enumerate(data["nakshatras"]):
			self.assertEqual(arrange.clean(name), rp.NAKSHATRAS[number] if number < 27 else "Abhijit", name)
		self.assertTrue(all(new and old != new for old, new in data["words"].items()))

	def test_a_sign_is_named_with_its_hindi_name_however_it_comes(self):
		for written in ("Virgo", "♍︎Virgo", "Virgo (Kanya)"):
			self.assertEqual(arrange.sign_name(written), "Virgo (Kanya)", written)
		self.assertEqual(arrange.sign_name("Virgo 14°"), "Virgo 14°")  # more than a sign: left as it is

	def test_values_are_written_the_way_the_layout_says(self):
		self.assertEqual(arrange.fmt(True), "Yes")
		self.assertEqual(arrange.fmt(0.5), "0.5")
		self.assertEqual(arrange.fmt("2031-06-28"), "28 Jun 2031")
		self.assertEqual(arrange.fmt("05:26:45", "time"), "05:26")
		self.assertEqual(arrange.fmt(27, "nakshatra"), "Revati")
		self.assertEqual(arrange.fmt("L", "planet"), "Lagna")
		self.assertEqual(arrange.fmt(5, "sign_index"), "Virgo (Kanya)")
		self.assertEqual(arrange.fmt([5, 14.21], "signdeg"), "Virgo (Kanya) 14°12′")
		self.assertEqual(arrange.fmt("054-12-11", "dms_lon"), "Taurus (Vrishabha) 24°12′")
		self.assertEqual(arrange.fmt(None), "")

	def test_a_place_the_library_wrote_as_a_sign_and_degrees_is_split_from_what_is_said_of_it(self):
		self.assertEqual(arrange.place("♉︎Taurus 24° 6’ 21\" (Amatya Karaka)"), ("Taurus (Vrishabha) 24°06′", "Amatya Karaka"))
		self.assertEqual(arrange.place("♍︎Virgo"), ("Virgo (Kanya)", ""))


class TestTimes(AstroTestCase):
	def test_a_time_before_midnight_is_turned_back_into_the_time_it_is(self):
		# the library writes 17:08 of the day before as how far it is from midnight, with (-1) after it
		self.assertEqual(arrange.clock("06:51:18", "-1"), "17:08 (the day before)")
		self.assertEqual(arrange.clock("00:19:48", "+1"), "00:19 (the next day)")
		self.assertEqual(arrange.clock("14:34:12"), "14:34")
		self.assertEqual(arrange.clock("01:00:00", "+2"), "01:00 (2 days later)")

	def test_a_stretch_of_time_the_library_wrote_in_words_is_read_as_what_it_is_from_when_until_when(self):
		span = arrange.timed("Krishna Paksha Dhasami (Nithya) 06:51:18 (-1) from 14:34:12 ends (2.38% Balance )")
		self.assertEqual(span, {"name": "Krishna Paksha Dashami (Nithya)", "begins": "17:08 (the day before)", "ends": "14:34"})
		span = arrange.timed("Revathi  (Me☿) Quarter-3 02:05:50 from 00:19:48 (+1) ends (47.29% Balance )")
		self.assertEqual(span, {"name": "Revati (Mercury) pada 3", "begins": "02:05", "ends": "00:19 (the next day)"})
		self.assertEqual(arrange.timed("♓︎Pisces 00:19:48 (+1) ends (10.05% Balance )"), {"name": "Pisces (Meena)", "begins": "", "ends": "00:19 (the next day)"})
		self.assertEqual(arrange.timed("11:52:32 from 12:47:39 ends"), {"name": "", "begins": "11:52", "ends": "12:47"})
		self.assertIsNone(arrange.timed("Sunday"))
		self.assertIsNone(arrange.timed(None))

	def test_the_librarys_percent_balance_is_not_shown(self):
		self.assertNotIn("Balance", words(page("PANCHANGA")))  # it works it out from the wrong start for a tithi that began the day before


class TestTheKindsOfSection(AstroTestCase):
	DATA = {
		"birth": {"day": 8, "month": 6, "year": 1980}, "lagna": {"sign": "♍︎Virgo", "degree": 14.2156},
		"planetary_positions": [{"planet": "Moon☾", "sign": "♓︎Pisces", "house": 7}, {"planet": "Mars♂", "sign": "♌︎Leo", "house": 12}],
		"facts": {"Sun Rise": "05:26:45", "Day": "Sunday"}, "empty": {},
		"rows": [{"name": "Sun", "points": 4}, {"name": "Moon", "points": 6}], "byname": {"Sun": {"a": 1, "b": 2}, "Moon": {"a": 3, "b": 4}},
		"grid": [[1, 2, 3], [4, 5, 6]], "total": [5, 7, 9],
		"info": {"X-Venus♀℞": "♊︎Gemini 4° 53’ 45\" (Jnaati Karaka)", "X-Mars♂": "♌︎Leo 19° 47’ 22\""},
		"many": {"Fact": "yes", "Inner": {"Other": "no"}},
	}

	def section(self, **spec) -> str:
		return arrange.section_html(spec, self.DATA, TODAY)

	def test_lines_read_templates_and_the_small_readings(self):
		text = words(self.section(kind="lines", title="Birth", rows=[["Date", "{birth.day:02d}-{birth.month:02d}-{birth.year}"], ["Lagna", "@lagna"], ["Moon sign", "@moon_sign"], ["Nothing", "{nope.none}"]]))
		self.assertIn("Date | 08-06-1980", text)
		self.assertIn("Lagna | Virgo (Kanya) 14°12′", text)
		self.assertIn("Moon sign | Pisces (Meena)", text)
		self.assertNotIn("Nothing", text)  # a row with nothing to say is left out

	def test_facts_are_read_by_their_keys_even_with_spaces_and_capitals(self):
		text = words(self.section(kind="facts", title="The day", **{"from": "facts"}, rows=[["Weekday", "Day"], ["Sunrise", "Sun Rise", "time"], ["Missing", "Nope"]]))
		self.assertIn("Weekday | Sunday", text)
		self.assertIn("Sunrise | 05:26", text)
		self.assertNotIn("Missing", text)

	def test_places_are_found_by_how_their_key_starts_and_a_retrograde_planet_is_said_to_be(self):
		text = words(self.section(kind="places", title="Planets", **{"from": "info"}, prefix="X-", first="Planet", remark="Karaka", rows=[["Venus", "Venus"], ["Mars", "Mars"], ["Sun", "Sun"]]))
		self.assertIn("Venus | Gemini (Mithuna) 4°53′ | retrograde; Jnaati Karaka", text)
		self.assertIn("Mars | Leo (Simha) 19°47′", text)
		self.assertNotIn("Sun |", text)

	def test_a_table_of_records_a_table_of_named_records_and_a_turned_round_table(self):
		text = words(self.section(kind="table", title="Rows", **{"from": "rows"}, columns=[["Name", "name"], ["Points", "points"]]))
		self.assertIn("Name | Points", text)
		self.assertIn("Moon | 6", text)
		text = words(self.section(kind="table", title="By name", **{"from": "byname"}, key="Planet", columns=[["A", "a"], ["B", "b"]]))
		self.assertIn("Planet | A | B", text)
		self.assertIn("Sun | 1 | 2", text)
		text = words(self.section(kind="pivot", title="Turned", **{"from": "byname"}, row_label="Part", columns=[["Sun", "Sun"], ["Moon", "Moon"]]))
		self.assertIn("Part | Sun | Moon", text)
		self.assertIn("a | 1 | 3", text)

	def test_a_matrix_has_its_totals_and_a_footer_row(self):
		text = words(self.section(kind="matrix", title="Points", **{"from": "grid"}, row_labels=["Sun", "Moon"], col_labels=["a", "b", "c"], total=True, footer={"label": "All", "from": "total"}))
		self.assertIn("Sun | 1 | 2 | 3 | 6", text)
		self.assertIn("All | 5 | 7 | 9 | 21", text)

	def test_a_table_with_nothing_to_show_is_left_out_whole_with_its_heading(self):
		for kind in ("table", "pivot", "facts", "places", "times", "matrix"):
			self.assertEqual(self.section(kind=kind, title="Empty", **{"from": "empty"}, rows=[], columns=[]), "", kind)
		self.assertEqual(self.section(kind="unknown", title="Nothing"), "")

	def test_whatever_is_not_named_is_shown_as_it_comes_with_nothing_left_raw(self):
		html = arrange.auto({"Name": "x", "Nested": {"a": [1, 2], "b": {"c": True}}, "List": [{"p": 1, "q": None}], "Glyph": "Mo☾"})
		text = words(html)
		self.assertIn("Name | x", text)
		self.assertIn("C | Yes", text)
		self.assertIn("Glyph | Moon", text)
		for raw in ("{", "}", "None", "['", "☾"):
			self.assertNotIn(raw, text)

	def test_a_section_of_more_than_one_table_is_kept_whole_with_its_heading_and_a_single_table_carries_its_heading_and_note(self):
		many = self.section(kind="auto", title="Both", **{"from": "many"}, note="A note.")
		self.assertTrue(many.startswith("<table class='sec'><tr><td><h2>Both</h2>"), many[:80])  # a table of one cell: the page never ends inside it
		self.assertIn("<p class='note'>A note.</p>", many)
		one = self.section(kind="table", title="Rows", **{"from": "rows"}, columns=[["Name", "name"]], note="A note.")
		self.assertTrue(one.startswith("<table><caption class='h2'>Rows</caption>"), one[:80])
		self.assertTrue(one.endswith("<tr><td colspan='1' class='note'>A note.</td></tr></table>"), one[-80:])  # the note is the table's last row: it cannot be left alone on the next page

	def test_a_dasha_marks_the_running_period_and_says_when_the_library_gives_no_end(self):
		data = {"d": {"mahadasha": [
			{"lord": "Sun☉", "start_date": "2015-06-28", "end_date": "2021-06-28", "duration_years": 6.0},
			{"lord": "Moon☾", "start_date": "2021-06-28", "end_date": None, "duration_years": 0,
			 "antardasha": [{"lord": "Moon☾", "start_date": "2021-06-28", "end_date": "2022-04-28"}, {"lord": "L", "start_date": "2022-04-28", "end_date": "2031-06-28"}]}]}}
		html = arrange.section_html({"kind": "dasha", "title": "Dasha", "from": "d"}, data, TODAY)
		self.assertRegex(html, r"<tr class=\"now\"><td>Moon</td><td>28 Jun 2021</td><td>—</td><td>—</td></tr>")  # no end given: no end and no years
		self.assertIn("Sub-periods of the running Moon period", html)
		self.assertIn("Moon / Lagna", words(html))  # "L" is how the yearly dashas name the lagna
		self.assertEqual(html.count('class="now"'), 2)  # the main period and its running sub-period

	def test_the_yogas_are_named_cleaned_and_cut_at_the_end_of_a_word(self):
		data = {"yogas": {"general": {"a": ["D1", "guru_mangala_yoga", "224 - The lord of the 5th house should occupy a dusthana. " + "word " * 80, "classical text"]}}}
		html = arrange.section_html({"kind": "yogas", "title": "Yogas", "from": "yogas"}, data, TODAY)
		self.assertIn("Guru Mangala Yoga", html)
		self.assertNotIn("224", html)
		self.assertIn(" …", html)
		self.assertNotIn("classical text", html)  # what a yoga gives is left out unless the layout asks for it
		self.assertIn("classical text", arrange.section_html({"kind": "yogas", "title": "Yogas", "from": "yogas", "effects": True}, data, TODAY))

	def test_whatever_a_customer_could_type_is_escaped_in_every_kind(self):
		hostile = "<script>alert(1)</script>"
		data = {"name": hostile, "lagna": {"sign": hostile, "degree": 1}, "rows": [{"name": hostile}], "facts": {"Day": hostile}, "info": {"X-Sun": hostile},
				"d": {"mahadasha": [{"lord": hostile, "start_date": "2021-06-28", "end_date": "2031-06-28", "duration_years": 10}]}}
		for spec in ({"kind": "lines", "rows": [["a", "{name}"]]}, {"kind": "facts", "from": "facts", "rows": [["a", "Day"]]}, {"kind": "table", "from": "rows", "columns": [["a", "name"]]},
					 {"kind": "places", "from": "info", "prefix": "X-", "rows": [["a", "Sun"]]}, {"kind": "auto", "from": "rows"}, {"kind": "dasha", "from": "d"}, {"kind": "text", "text": hostile}):
			html = arrange.section_html({"title": hostile, **spec}, data, TODAY)
			self.assertTrue(html, spec)
			self.assertNotIn("<script", html, spec)


class TestTheCharts(AstroTestCase):
	CHART = {"chart": ["Mars♂\n"] + [""] * 11, "ascendant_house": 0}

	def test_each_chart_has_its_title_inside_the_picture_and_the_font_can_be_made_small(self):
		html = arrange.section_html({"kind": "charts", "title": "Charts", "from": "c", "which": ["D1"], "titles": {"D1": "Lagna chart (D1)"}, "size": 200, "font": 9}, {"c": {"D1": self.CHART}}, TODAY)
		self.assertIn('width="200" height="222" viewBox="0 0 200 222"', html)
		self.assertIn("Lagna chart (D1)", html)
		self.assertIn('font-size="9" font-weight="bold"', html)

	def test_a_chart_the_engine_does_not_make_is_left_out(self):
		data = {"c": {"D1": self.CHART, "D13": {"chart": [], "ascendant_house": None, "note": "not supported"}}}
		html = arrange.section_html({"kind": "charts", "title": "Charts", "from": "c"}, data, TODAY)
		self.assertEqual(html.count("<svg"), 1)


class TestTheLayouts(AstroTestCase):
	def test_every_layout_file_is_valid_and_names_only_kinds_the_arranger_knows(self):
		known = {"lines", "facts", "times", "places", "table", "pivot", "matrix", "charts", "dasha", "yogas", "dashas", "auto", "text"}
		files = sorted(arrange.LAYOUTS.glob("*.json"))
		self.assertGreaterEqual(len(files), 9)
		for path in files:
			layout = arrange.layout_named(path.stem)
			self.assertTrue(layout.get("title"), path.name)
			for spec in layout["sections"]:
				self.assertIn(spec.get("kind"), known, f"{path.name}: {spec.get('title')}")

	def test_a_fuller_layout_has_everything_of_the_one_it_extends_and_comes_after_it(self):
		basic = [s.get("title") for s in arrange.layout_named("basic")["sections"]]
		standard = [s.get("title") for s in arrange.layout_named("standard")["sections"]]
		advanced = [s.get("title") for s in arrange.layout_named("advanced")["sections"]]
		self.assertEqual(standard[:len(basic)], basic)
		self.assertEqual(advanced[:len(standard)], standard)
		self.assertGreater(len(advanced), len(standard))

	def test_the_ten_modes_each_make_a_page_with_no_value_left_raw(self):
		for mode in MODES:
			text = words(page(mode))
			self.assertGreater(len(text.strip().splitlines()), 15, mode)
			for raw in STRANGE:
				self.assertIsNone(re.search(raw, text), f"{mode}: {raw}")
			for symbol in "☉☾♂☿♃♀♄☊☋♈♉♊♋♌♍♎♏♐♑♒♓℞":
				self.assertNotIn(symbol, text, f"{mode}: {symbol}")


class TestWhatTheTenPagesSay(AstroTestCase):
	def test_the_birth_chart_has_the_planets_the_charts_and_the_running_dasha(self):
		html = page("SUPER_BASIC")
		text = words(html)
		for expected in ("Virgo (Kanya) 14°12′", "Taurus (Vrishabha) | 24°06′", "Moon | Pisces (Meena) | 23°41′", "Revati", "Moon / Saturn | 27 Sep 2025 | 29 Apr 2027"):
			self.assertIn(expected, text)
		for title in ("Lagna chart (D1)", "Navamsa (D9)"):
			self.assertIn(title, html)  # written inside each drawing
		self.assertEqual(html.count('class="now"'), 2)  # the running main period and the running sub-period
		self.assertNotIn("Planet strength", text)  # this mode has none: the heading goes with the table

	def test_the_standard_answer_has_no_planet_positions_and_still_gives_the_planets_and_the_signs(self):
		self.assertNotIn("planetary_positions", MODES["CORE_STANDARD"])
		text = words(page("CORE_STANDARD"))
		self.assertIn("Moon sign | Pisces (Meena)", text)  # found through the houses
		self.assertIn("Saturn | Leo (Simha) 26°51′ | Atma Karaka", text)
		self.assertIn("Venus | Gemini (Mithuna) 4°53′ | retrograde; Jnaati Karaka", text)
		self.assertIn("Mars in house | 12", text)
		self.assertIn("Manglik by the usual rule (Mars in 2, 4, 7, 8 or 12) | Yes", text)
		self.assertIn("Bhava Lagna | Virgo (Kanya) 29°33′", text)

	def test_the_full_chart_adds_the_birth_star_the_yogas_and_the_panchang_with_the_times_made_right(self):
		text = words(page("CORE_ADVANCED"))
		for expected in ("Nakshatra | Revati", "Guru Mangala Yoga", "Tithi | Krishna Paksha Dashami (Nithya) | 17:08 (the day before) | 14:34",
						 "Nakshatra | Revati (Mercury) pada 3 | 02:05 | 00:19 (the next day)", "Rahu Kalam | 17:30 | 19:13", "Sunrise | 05:26"):
			self.assertIn(expected, text)
		for left_out in ("longevity", "Longevity", "Balance"):
			self.assertNotIn(left_out, text)

	def test_the_match_has_the_kootas_in_order_with_their_total_and_none_of_the_librarys_verdicts(self):
		text = words(page("MATCH_CALC"))
		for expected in ("Varna | 1 | 1", "Nadi | 8 | 8", "Total | 18 | 36", "Birth star | Revati, pada 3 | Shatabhisha, pada 3", "Manglik | Yes | Yes"):
			self.assertIn(expected, text)
		for verdict in ("Not Recommended", "Feasibility", "Harmony", "Dosha risk", "50.0%"):
			self.assertNotIn(verdict, text)

	def test_the_dasha_page_has_each_system_under_its_own_name_and_marks_the_one_running(self):
		html = page("DASHA_CALC")
		self.assertGreaterEqual(html.count("<caption class='h3'>"), 20)
		text = words(html)
		self.assertIn("Vimshottari", text)
		self.assertIn("Sub-periods of the running", text)
		self.assertGreaterEqual(html.count('class="now"'), 20)

	def test_the_yearly_the_tajaka_the_panchang_and_the_kp_pages(self):
		annual = words(page("ANNUAL_CALC"))
		self.assertIn("Mudda Dasha", annual)
		self.assertIn("Lagna |", annual)
		self.assertIn("one fixed year after birth", annual)
		self.assertIn("Annual chart (Tajaka)", words(page("TRANSIT_CALC")))
		panchang = words(page("PANCHANGA"))
		self.assertIn("Weekday | Sunday", panchang)
		self.assertIn("Karana | Vishti (Bhadra) (Saturn) | 03:51 | 14:34", panchang)
		kp = words(page("KP_SYSTEM"))
		for expected in ("Ruling planets at birth", "Day lord", "Lord of the birth day | Sun", "House cusps", "Significators of the houses", "Aspects"):
			self.assertIn(expected, kp)
		self.assertIn("Moon | Jupiter | Mercury | —", kp)  # the engine gives no sub lord of the Moon: it says so

	def test_every_page_is_made_for_a_pdf_with_its_tables_kept_whole(self):
		html = page("CORE_ADVANCED")
		self.assertIn("<caption class='h2'>Planets</caption>", html)  # a heading is the caption of its table: a page can never end between the two
		self.assertIn("table.sec", html)
		self.assertNotIn("<h2>Planets</h2>", html)
