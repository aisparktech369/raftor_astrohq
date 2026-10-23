"""The kundli report and the match making report (reports.py, report_pdf.py, details.py, the vocabulary's "reports").

Most tests run on the engine's own answers for two invented births, kept in tests/fixtures/engine_answers.json, with the place finder and the astrology client
stood in for, so they need neither the astrology service nor the list of places. The last class asks the real service and the real list and is skipped where
they are not set up. Nothing here makes or keeps a record.

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_kundli_reports
"""
import datetime
import io
import json
import os
import re
import xml.etree.ElementTree as ET
from unittest import mock

import frappe
from pypdf import PdfReader

from raftor_astrohq import astrology, details, places, report_pdf as rp, reports, vocabulary
from raftor_astrohq.tests.helpers import AstroTestCase

ANSWERS = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "engine_answers.json"), encoding="utf-8"))
ON = datetime.date(2026, 10, 23)
DELHI = {"name": "Delhi, Delhi, India", "latitude": 28.65195, "longitude": 77.23149, "timezone": "Asia/Kolkata", "timezone_offset": 5.5, "population": 11034555}  # as GeoNames lists them
MUMBAI = {"name": "Mumbai, Maharashtra, India", "latitude": 19.07283, "longitude": 72.88261, "timezone": "Asia/Kolkata", "timezone_offset": 5.5, "population": 12691836}
KUNDLI_DETAILS = {"report_name": "Asha Rao", "birth_date": "1980-06-08", "birth_time": "13:49", "birth_place": "Delhi"}
MATCH_DETAILS = {"boy_name": "Vikram Mehta", "boy_birth_date": "1980-06-08", "boy_birth_time": "13:49", "boy_birth_place": "Delhi",
				 "girl_name": "Priya Shah", "girl_birth_date": "1983-02-14", "girl_birth_time": "09:30", "girl_birth_place": "Mumbai"}


REAL_LOOKUP = places.lookup  # kept before any test stands in for it


def fake_chart(birth, opcode="SUPER_BASIC", partner=None):
	"""The engine's answers for the two invented births: the boy's (born in 1980) and the girl's."""
	boy = birth["year"] == 1980
	if opcode == "SUPER_BASIC":
		return ANSWERS["boy_super_basic" if boy else "girl_super_basic"]
	if opcode == "PANCHANGA":
		return ANSWERS["boy_panchanga"]
	if opcode == "MATCH_CALC":
		return ANSWERS["match"]
	raise AssertionError(opcode)


def fake_lookup(text, on):
	return dict(MUMBAI if "mumbai" in text.lower() else DELHI)


def plain(html: str) -> str:
	"""The words of a page, tags gone and spaces tidied."""
	return re.sub(r"\s+", " ", frappe.utils.strip_html_tags(html.replace("</td>", " </td>").replace("</tr>", " </tr>").replace("</h2>", " </h2>")))


def pdf_text(content: bytes) -> tuple[int, str]:
	reader = PdfReader(io.BytesIO(content))
	return len(reader.pages), re.sub(r"\s+", " ", " ".join(page.extract_text() for page in reader.pages))


class Stood(AstroTestCase):
	"""The engine and the place finder stood in for, and the day fixed at 23 October 2026."""

	def setUp(self):
		super().setUp()
		self.engine = mock.Mock(side_effect=fake_chart)
		for patcher in (mock.patch.object(astrology, "chart", self.engine), mock.patch.object(places, "lookup", fake_lookup),
						mock.patch("raftor_astrohq.reports.today", lambda: str(ON))):
			patcher.start()
			self.addCleanup(patcher.stop)

	def kundli_context(self, **changes):
		person = {"name": "Asha Rao", "born": datetime.datetime(1980, 6, 8, 13, 49), "place_text": "Delhi"}
		context = reports.kundli_context(person, DELHI, ANSWERS["boy_super_basic"], ANSWERS["boy_panchanga"]["panchanga"], ON)
		context.update(changes)
		return context

	def match_context(self):
		boy = {"name": "Vikram Mehta", "born": datetime.datetime(1980, 6, 8, 13, 49), "place_text": "Delhi"}
		girl = {"name": "Priya Shah", "born": datetime.datetime(1983, 2, 14, 9, 30), "place_text": "Mumbai"}
		return reports.match_context(boy, girl, DELHI, MUMBAI, ANSWERS["match"], ANSWERS["boy_super_basic"], ANSWERS["girl_super_basic"], ON)


class TestTheWordsOfAstrology(AstroTestCase):
	def test_tithi_yoga_and_karana_from_the_longitudes_of_the_sun_and_the_moon(self):
		# (sun, moon) -> (tithi, yoga, karana), worked out by hand from the usual rules: 12 degrees to a tithi, 6 to a karana, 13 degrees 20 minutes to a yoga
		cases = {
			(0, 0): ("Shukla paksha Pratipada", "Vishkambha", "Kimstughna"),
			(0, 100): ("Shukla paksha Navami", "Dhriti", "Balava"),
			(0, 180): ("Krishna paksha Pratipada", "Harshana", "Balava"),
			(10, 178): ("Shukla paksha Purnima", "Vajra", "Vishti"),
			(0, 342): ("Krishna paksha Chaturdashi", "Indra", "Shakuni"),
			(0, 348): ("Krishna paksha Amavasya", "Vaidhriti", "Chatushpada"),
			(0, 354): ("Krishna paksha Amavasya", "Vaidhriti", "Naga"),
			(350, 10): ("Shukla paksha Dwitiya", "Vishkambha", "Kaulava"),  # the Moon is 20 degrees ahead of the Sun, round the end of the circle
			(200, 170): ("Krishna paksha Trayodashi", "Vishkambha", "Vanija"),  # 330 degrees ahead; the two longitudes add up to 370, which is 10
		}
		for (sun, moon), (tithi, yoga, karana) in cases.items():
			with self.subTest(f"sun {sun}, moon {moon}"):
				got = rp.panchang_of(sun, moon)
				self.assertEqual((got["tithi"], got["yoga"], got["karana"]), (tithi, yoga, karana))

	def test_a_planet_and_a_sign_are_found_in_the_engines_words(self):
		for text, code in (("Mercury☿", "Me"), ("Venus♀℞", "Ve"), ("Me☿", "Me"), ("Raagu☊", "Ra"), ("Rahu", "Ra"), ("Kethu☋", "Ke"), ("Ke☋", "Ke"), ("Moon☾", "Mo"), ("Mo☾", "Mo"), ("Sun☉", "Su"),
						   ("Ascendant", "Asc"), ("", None), ("Pluto", None)):
			with self.subTest(text):
				self.assertEqual(rp.planet_code(text), code)
		self.assertEqual(rp.sign_index("♍︎Virgo 14° 11’ 53"), 5)
		self.assertEqual(rp.sign_index("Pisces"), 11)
		self.assertIsNone(rp.sign_index("nothing"))

	def test_degrees_time_zones_dates_and_nakshatras_read_as_people_write_them(self):
		self.assertEqual(rp.degrees(14.2), "14°12′")
		self.assertEqual(rp.degrees(0.0), "0°00′")
		self.assertEqual(rp.offset_text(5.5), "UTC+05:30")
		self.assertEqual(rp.offset_text(-4.0), "UTC-04:00")
		self.assertEqual(rp.offset_text(5.75), "UTC+05:45")
		self.assertEqual(rp.long_date(datetime.date(2026, 10, 3)), "03 October 2026")
		self.assertEqual(rp.nakshatra_label(27, 3), "Revati, pada 3")
		self.assertEqual(rp.nakshatra_label(1), "Ashwini")
		self.assertEqual(rp.sign_label(5), "Virgo (Kanya)")


def house_layout(svg: str) -> dict[int, dict]:
	"""For each of the twelve houses of a drawn chart: the sign number written in it and the planet lines written in it, found by where the texts sit in the drawing."""
	root = ET.fromstring(svg)
	ns = "{http://www.w3.org/2000/svg}"
	polygons = [[tuple(float(n) for n in pair.split(",")) for pair in p.get("points").split()] for p in root.iter(ns + "polygon")]

	def inside(point, shape):
		x, y, hit = point[0], point[1], False
		for (x1, y1), (x2, y2) in zip(shape, shape[1:] + shape[:1]):
			if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
				hit = not hit
		return hit

	layout = {n: {"sign": None, "planets": []} for n in range(1, 13)}
	for text in root.iter(ns + "text"):
		if not text.text or float(text.get("y")) > 300:  # a house with no planet has an empty line; the title is under the drawing
			continue
		point = (float(text.get("x")), float(text.get("y")) - 3)
		house = next(n for n, shape in enumerate(polygons, start=1) if inside(point, shape))
		if text.get("font-weight") == "bold":
			layout[house]["planets"].append(text.text)
		else:
			layout[house]["sign"] = text.text
	return layout


class TestTheBirthChartDrawing(AstroTestCase):
	CELLS = ["Mars♂\nJupiter♃\n", "", "", "", "", "Mercury☿\nVenus♀℞\n", "", "", "", "Kethu☋\nSaturn♄\n", "", "Moon☾\nRaagu☊\n"]  # the engine's list: a cell for each sign from Aries

	def test_the_lagna_is_the_top_diamond_and_the_houses_run_anticlockwise_from_it(self):
		layout = house_layout(rp.diamond_chart_svg(self.CELLS, lagna=5, title="Lagna chart"))
		self.assertEqual({house: info["sign"] for house, info in layout.items()}, {n: str((5 + n - 1) % 12 + 1) for n in range(1, 13)})  # house 1 is Virgo (6), 2 Libra (7) ...
		self.assertEqual(layout[1]["planets"], ["Me Ve(R)"])  # Virgo holds Mercury and Venus going backwards
		self.assertEqual(layout[8]["planets"], ["Ma Ju"])  # Aries is the 8th house from Virgo
		self.assertEqual(layout[5]["planets"], ["Ke Sa"])  # Capricorn
		self.assertEqual(layout[7]["planets"], ["Mo Ra"])  # Pisces
		self.assertEqual([h for h, info in layout.items() if not info["planets"]], [2, 3, 4, 6, 9, 10, 11, 12])

	def test_another_lagna_moves_every_planet_with_it(self):
		layout = house_layout(rp.diamond_chart_svg(self.CELLS, lagna=0))  # Aries rising: house 1 holds Mars and Jupiter
		self.assertEqual(layout[1]["planets"], ["Ma Ju"])
		self.assertEqual(layout[6]["planets"], ["Me Ve(R)"])
		self.assertEqual(layout[10]["planets"], ["Ke Sa"])
		self.assertEqual(layout[12]["planets"], ["Mo Ra"])

	def test_a_crowded_house_is_written_in_rows_of_three(self):
		cells = [""] * 12
		cells[0] = "Sun☉\nMoon☾\nMars♂\nMercury☿\nJupiter♃\n"
		self.assertEqual(house_layout(rp.diamond_chart_svg(cells, lagna=0))[1]["planets"], ["Su Mo Ma", "Me Ju"])

	def test_it_is_a_valid_picture_and_the_title_is_escaped(self):
		svg = rp.diamond_chart_svg([""] * 12, lagna=0, title="A <b>&</b> chart")
		root = ET.fromstring(svg)  # parses: nothing is left open
		self.assertEqual(len(list(root.iter("{http://www.w3.org/2000/svg}polygon"))), 12)
		self.assertIn("A &lt;b&gt;&amp;&lt;/b&gt; chart", svg)


class TestTheKundliPage(Stood):
	def test_it_shows_what_the_engine_said_in_the_usual_words(self):
		text = plain(reports.kundli_html(self.kundli_context()))
		for expected in ("Asha Rao", "Sunday, 08 June 1980, 13:49", "Delhi, Delhi, India (28.65°N, 77.23°E)", "UTC+05:30 (Asia/Kolkata), as it was on that day",
						 "Virgo (Kanya), 14°12′; lord Mercury", "Pisces (Meena)", "Revati, pada 3; lord Mercury", "Taurus (Vrishabha)",
						 "Sunday (lord Sun)", "Krishna paksha Dashami", "Saubhagya", "Vishti", "05:26 and 19:13 (local time)",
						 "Lagna chart (Rasi, D1)", "Navamsa chart (D9)", "Calculated with the Lahiri ayanamsa", "GeoNames", "Made for you on 23 October 2026"):
			self.assertIn(expected, text)

	def test_the_born_row_has_the_weekday_the_customer_knows_and_the_panchang_says_when_its_day_began_earlier(self):
		sunday = plain(reports.kundli_html(self.kundli_context()))
		self.assertIn("Sunday, 08 June 1980, 13:49", sunday)  # born in the afternoon of a Sunday: the same day in both counts
		self.assertNotIn("born before sunrise", sunday)
		person = {"name": "Asha Rao", "born": datetime.datetime(1980, 6, 9, 3, 0), "place_text": "Delhi"}  # 3 in the morning of Monday: the panchang's day is still Sunday's
		before_sunrise = plain(reports.kundli_html(reports.kundli_context(person, DELHI, ANSWERS["boy_super_basic"], ANSWERS["boy_panchanga"]["panchanga"], ON)))
		self.assertIn("Monday, 09 June 1980, 03:00", before_sunrise)
		self.assertIn("Sunday (lord Sun) (the day runs from sunrise to sunrise: you were born before sunrise on Monday)", before_sunrise)

	def test_every_planet_has_its_row_in_the_table(self):
		text = plain(reports.kundli_html(self.kundli_context()))
		for row in ("Sun Taurus (Vrishabha) 24°06′ Mrigashira, pada 1 9", "Moon Pisces (Meena) 23°41′ Revati, pada 3 7", "Venus Gemini (Mithuna) 4°53′ Mrigashira, pada 4 10 Yes",
					"Saturn Leo (Simha) 26°51′ Uttara Phalguni, pada 1 12", "Ketu Capricorn (Makara) 29°52′ Dhanishta, pada 2 5 Yes"):
			self.assertIn(row, text)

	def test_the_dasha_shows_the_balance_at_birth_and_marks_the_period_running_today(self):
		text = plain(reports.kundli_html(self.kundli_context()))
		self.assertIn("At birth the Mercury dasha was running, with 8 years 0 months 19 days still to run.", text)
		self.assertIn("Moon 28 Jun 2021 28 Jun 2031 Running now", text)
		self.assertIn("Moon / Saturn 27 Sep 2025 29 Apr 2027 Running now", text)
		self.assertEqual(text.count("Running now"), 2)
		self.assertIn("The Moon dasha: its antardashas", text)

	def test_the_last_period_has_its_end_and_a_period_with_no_end_is_never_given_todays_date(self):
		html = reports.kundli_html(self.kundli_context())
		self.assertIn("Saturn 28 Jun 2072 29 Jun 2091", plain(html))
		dasha = json.loads(json.dumps(ANSWERS["boy_super_basic"]["dasha_sequences"]["vimshottari"]["mahadasha"]))
		dasha[-1]["end_date"] = None  # an engine that gives no end for the last period (the one before 1.1.1)
		text = plain(reports.kundli_html(self.kundli_context(dasha=dasha)))
		self.assertIn("Saturn 28 Jun 2072 -", text)
		self.assertNotIn("23 Oct 2026", text)  # today, which an empty date once turned into

	def test_the_period_running_follows_the_day_it_is_made(self):
		text = plain(reports.kundli_html(self.kundli_context(on=datetime.date(1990, 1, 1))))
		self.assertIn("Ketu 27 Jun 1988 28 Jun 1995 Running now", text)
		self.assertIn("The Ketu dasha: its antardashas", text)

	def test_what_the_customer_wrote_is_escaped_not_run(self):
		person = {"name": "<script>alert(1)</script> & <b>Co</b>", "born": datetime.datetime(1980, 6, 8, 13, 49), "place_text": "Delhi"}
		context = reports.kundli_context(person, DELHI, ANSWERS["boy_super_basic"], ANSWERS["boy_panchanga"]["panchanga"], ON)
		html = reports.kundli_html(context)
		self.assertNotIn("<script>", html)
		self.assertNotIn("<b>Co</b>", html)
		self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; &lt;b&gt;Co&lt;/b&gt;", html)


class TestTheMatchPage(Stood):
	def test_each_koota_has_its_row_and_the_total_is_their_sum(self):
		text = plain(reports.match_html(self.match_context()))
		scores = ANSWERS["match"]["compatibility"]
		for name, what, key, best in reports.KOOTAS:
			self.assertIn(f"{name} {what} {scores[key]:g} {best}", text)
		self.assertEqual(sum(scores[key] for _n, _w, key, _b in reports.KOOTAS), scores["total_score"])
		self.assertEqual(sum(best for _n, _w, _k, best in reports.KOOTAS), 36)
		self.assertIn(f"{scores['total_score']:g} out of 36 ({scores['total_score'] / 36 * 100:.0f}%)", text)
		self.assertIn(f"Total {scores['total_score']:g} 36", text)

	def test_it_names_the_two_people_with_their_moon_sign_star_and_lagna(self):
		text = plain(reports.match_html(self.match_context()))
		for expected in ("Vikram Mehta and Priya Shah", "08 June 1980, 13:49", "14 February 1983, 09:30", "Delhi, Delhi, India", "Mumbai, Maharashtra, India", "Pisces (Meena)", "Aquarius (Kumbha)",
						 "Revati, pada 3", "Shatabhisha, pada 3", "Virgo (Kanya)"):
			self.assertIn(expected, text)

	def test_manglik_says_where_mars_is_and_what_is_counted_and_never_calls_an_exception_a_cancellation(self):
		text = plain(reports.match_html(self.match_context()))
		self.assertIn("Mars is in the house 12th from the lagna 12th from the lagna", text)
		self.assertIn("Manglik dosha Present Present", text)
		self.assertIn("Manglik is counted when Mars stands in the 2nd, 4th, 7th, 8th or 12th house from the lagna", text)
		self.assertNotIn("exception also applies", text)

	def test_the_manglik_words_follow_the_engines_flags(self):
		context = self.match_context()
		context["match"] = {**ANSWERS["match"], "doshas": {"person1": {"manglik": False}, "person2": {"manglik": True}}}
		self.assertIn("Manglik dosha Not present Present", plain(reports.match_html(context)))

	def test_the_verdict_follows_the_usual_bands(self):
		for total, words in ((0, "Below 18"), (17.5, "Below 18"), (18, "18 to 24"), (24.5, "18 to 24"), (25, "25 to 32"), (32.5, "25 to 32"), (33, "33 and above"), (36, "33 and above")):
			with self.subTest(total):
				self.assertTrue(reports._verdict(total).startswith(words), reports._verdict(total))

	def test_the_boy_is_the_first_column_and_the_girl_the_second(self):
		text = plain(reports.match_html(self.match_context()))
		self.assertRegex(text, r"Boy Girl Name Vikram Mehta Priya Shah|Name Vikram Mehta Priya Shah")
		self.assertLess(text.index("Vikram Mehta Priya Shah"), text.index("Born"))


class TestMakingTheReports(Stood):
	NUMBER_KEYS = {"year", "month", "day", "hour", "minute", "second", "latitude", "longitude", "timezone_offset", "gender"}

	def test_the_kundli_report_is_a_two_page_pdf_with_the_customers_chart(self):
		made = reports.kundli_report("ITEM", KUNDLI_DETAILS, "x@example.com")
		self.assertEqual(made["file_name"], "kundli-report-asha-rao.pdf")
		self.assertTrue(made["content"].startswith(b"%PDF"))
		pages, text = pdf_text(made["content"])
		self.assertEqual(pages, 2)
		for expected in ("Kundli report", "Asha Rao", "Virgo (Kanya)", "Revati, pada 3", "Krishna paksha Dashami", "Vimshottari dasha", "Running now", "Saturn 28 Jun 2072 29 Jun 2091"):
			self.assertIn(expected, text)

	def test_only_numbers_go_to_the_astrology_service_never_the_name_or_the_place(self):
		reports.kundli_report("ITEM", KUNDLI_DETAILS, "x@example.com")
		self.assertEqual([call.args[1] for call in self.engine.call_args_list], ["SUPER_BASIC", "PANCHANGA"])
		for call in self.engine.call_args_list:
			sent = call.args[0]
			self.assertLessEqual(set(sent), self.NUMBER_KEYS)
			self.assertEqual((sent["year"], sent["month"], sent["day"], sent["hour"], sent["minute"], sent["latitude"], sent["longitude"], sent["timezone_offset"]), (1980, 6, 8, 13, 49, 28.65195, 77.23149, 5.5))
			self.assertNotIn("Asha", json.dumps(sent))
			self.assertNotIn("Delhi", json.dumps(sent))

	def test_the_match_report_asks_for_the_boy_first_as_a_man_and_the_girl_as_a_woman(self):
		made = reports.match_report("ITEM", MATCH_DETAILS, "x@example.com")
		self.assertEqual(made["file_name"], "match-making-report-vikram-mehta-priya-shah.pdf")
		match = next(call for call in self.engine.call_args_list if call.args[1] == "MATCH_CALC")
		self.assertEqual((match.args[0]["gender"], match.args[0]["year"], match.kwargs["partner"]["gender"], match.kwargs["partner"]["year"]), ("Male", 1980, "Female", 1983))
		for call in self.engine.call_args_list:
			self.assertLessEqual(set(call.args[0]), self.NUMBER_KEYS)
		pages, text = pdf_text(made["content"])
		self.assertEqual(pages, 1)
		for expected in ("Match making report", "Vikram Mehta and Priya Shah", "Ashtakoota (Guna Milan)", "out of 36", "Manglik dosha", "Mars is in the house"):
			self.assertIn(expected, text)

	def test_the_places_are_looked_up_for_the_day_and_hour_of_birth(self):
		seen = []
		with mock.patch.object(places, "lookup", lambda text, on: seen.append((text, on)) or fake_lookup(text, on)):
			reports.match_report("ITEM", MATCH_DETAILS, "x@example.com")
		self.assertEqual(seen, [("Delhi", datetime.datetime(1980, 6, 8, 13, 49)), ("Mumbai", datetime.datetime(1983, 2, 14, 9, 30))])

	def test_a_place_that_is_not_found_or_a_service_that_is_down_stops_the_report_in_plain_words(self):
		with mock.patch.object(places, "lookup", mock.Mock(side_effect=places.PlaceNotFound("We could not find Xyz. Check the spelling."))):
			with self.assertRaises(places.PlaceNotFound) as caught:
				reports.kundli_report("ITEM", KUNDLI_DETAILS, "x@example.com")
			self.assertEqual(str(caught.exception), "We could not find Xyz. Check the spelling.")
		self.engine.side_effect = astrology.AstrologyUnavailable("The astrology service did not answer.")
		with self.assertRaises(frappe.ValidationError) as caught:  # a Frappe validation error: servicehq writes its words on the order and tries again every hour
			reports.match_report("ITEM", MATCH_DETAILS, "x@example.com")
		self.assertEqual(str(caught.exception), "The astrology service did not answer.")

	def test_the_name_is_part_of_the_file_name_only_as_plain_letters(self):
		for names, expected in ((("Asha Rao",), "kundli-report-asha-rao.pdf"), (("O'Brien",), "kundli-report-o-brien.pdf"), (("José Núñez",), "kundli-report-jose-nunez.pdf"),
								(("../../etc/passwd",), "kundli-report-etc-passwd.pdf"), (("आशा",), "kundli-report-report.pdf"), (("",), "kundli-report-report.pdf"),
								(("<b>x</b>; rm -rf",), "kundli-report-b-x-b-rm-rf.pdf")):
			with self.subTest(names):
				self.assertEqual(reports._file_name("kundli-report", *names), expected)
		long = reports._file_name("kundli-report", "a" * 500)
		self.assertTrue(long.endswith(".pdf") and len(long) < 140, long)

	def test_nothing_the_customer_wrote_becomes_markup_or_reads_a_file_of_the_server(self):
		hostname = open("/etc/hostname").read().strip()
		made = reports.kundli_report("ITEM", {**KUNDLI_DETAILS, "report_name": '<iframe src="file:///etc/hostname" width="500" height="100"></iframe>'}, "x@example.com")
		_pages, text = pdf_text(made["content"])
		self.assertIn("<iframe", text)  # written out as the letters it is made of
		self.assertNotIn(hostname, text)

	def test_a_name_in_another_script_is_refused_at_the_form_and_not_printed_as_boxes(self):
		self.assertEqual(details.person_rules({**KUNDLI_DETAILS, "report_name": "आशा राव"}), {"report_name": "Please write the name in English letters, for example Asha Rao."})


class TestWhatTheFormAsksAndChecks(Stood):
	def test_a_kundli_asks_for_one_person_and_a_match_for_two(self):
		self.assertEqual([f["name"] for f in details.kundli_fields()], ["report_name", "birth_date", "birth_time", "birth_place"])
		self.assertEqual([f["name"] for f in details.match_fields()],
						 ["boy_name", "boy_birth_date", "boy_birth_time", "boy_birth_place", "girl_name", "girl_birth_date", "girl_birth_time", "girl_birth_place"])
		for field in details.kundli_fields() + details.match_fields():
			self.assertTrue(field["required"], field["name"])  # the time too: the lagna and the dasha change with it
		self.assertEqual([f["label"] for f in details.match_fields()][:2], ["Boy's name", "Boy's date of birth"])
		self.assertEqual([f.get("type", "text") for f in details.kundli_fields()], ["text", "date", "time_text", "text"])

	def test_the_makers_read_the_same_names_the_forms_use(self):
		self.assertEqual(set(details.person_keys().values()), {f["name"] for f in details.kundli_fields()})
		self.assertEqual(set(details.person_keys("boy_").values()) | set(details.person_keys("girl_").values()), {f["name"] for f in details.match_fields()})
		self.assertEqual(details.born_at(KUNDLI_DETAILS), datetime.datetime(1980, 6, 8, 13, 49))
		self.assertEqual(details.born_at({**KUNDLI_DETAILS, "birth_time": "6:05"}), datetime.datetime(1980, 6, 8, 6, 5))
		self.assertEqual(details.born_at(MATCH_DETAILS, "girl_"), datetime.datetime(1983, 2, 14, 9, 30))

	def test_the_name_must_be_in_english_letters(self):
		for text, ok in (("Asha Rao", True), ("José Núñez", True), ("O'Brien-Smith Jr.", True), ("Müller", True), ("आशा", False), ("Asha 阿", False), ("Ася", False), ("", True)):
			with self.subTest(text):
				self.assertEqual(details.in_english_letters(text), ok)

	def test_the_date_must_not_be_in_the_future_or_before_the_star_files_begin(self):
		with mock.patch.object(places, "problem", lambda text, on: ""):
			self.assertEqual(details.person_rules(KUNDLI_DETAILS), {})
			tomorrow = str(frappe.utils.add_days(frappe.utils.today(), 1))
			self.assertEqual(list(details.person_rules({**KUNDLI_DETAILS, "birth_date": tomorrow})), ["birth_date"])
			self.assertEqual(details.person_rules({**KUNDLI_DETAILS, "birth_date": "1799-12-31"}), {"birth_date": "Reports are made for births from the year 1800."})
			self.assertEqual(details.person_rules({**KUNDLI_DETAILS, "birth_date": "1800-01-01"}), {})

	def test_a_place_that_cannot_be_found_or_is_not_one_place_is_said_at_the_form(self):
		with mock.patch.object(places, "problem", lambda text, on: "Sirsa is in more than one place: Sirsa, Haryana; Sirsa, Uttar Pradesh. Please add the state."):
			errors = details.kundli_rules(KUNDLI_DETAILS, "x@example.com")
		self.assertEqual(errors, {"birth_place": "Sirsa is in more than one place: Sirsa, Haryana; Sirsa, Uttar Pradesh. Please add the state."})

	def test_a_match_checks_each_person_under_their_own_fields(self):
		bad_girl = {**MATCH_DETAILS, "girl_birth_date": "1700-01-01", "boy_name": "आशा"}
		with mock.patch.object(places, "problem", lambda text, on: ""):
			self.assertEqual(set(details.match_rules(bad_girl, "x@example.com")), {"boy_name", "girl_birth_date"})
			self.assertEqual(details.match_rules(MATCH_DETAILS, "x@example.com"), {})

	def test_with_no_list_of_places_a_sale_is_not_refused_for_it(self):
		with mock.patch.object(places, "lookup", REAL_LOOKUP), mock.patch.object(places, "ready", lambda: False):
			with self.assertRaises(places.PlacesNotReady):
				places.lookup("Delhi", datetime.date(1980, 6, 8))
			self.assertEqual(details.person_rules(KUNDLI_DETAILS), {})  # the maker will say so on the order, and the team sees it


class TestWhatAstroHQShips(AstroTestCase):
	def test_the_vocabulary_lists_the_two_reports_with_everything_servicehq_needs(self):
		shipped = vocabulary.vocabulary()["reports"]
		self.assertEqual(sorted(shipped), ["kundli", "match"])
		for name, entry in shipped.items():
			with self.subTest(name):
				self.assertTrue(entry["title"] and entry["blurb"] and entry["description"])
				self.assertTrue(callable(frappe.get_attr(entry["maker"])))
				self.assertTrue(callable(frappe.get_attr(entry["details"]["validate"])))
				self.assertTrue(entry["details"]["fields"])
		self.assertEqual(shipped["kundli"]["title"], "Kundli report")
		self.assertEqual(shipped["match"]["title"], "Match making report")

	def test_servicehq_finds_each_reports_questions_through_the_vocabulary(self):
		from raftor_servicehq import kinds

		self.assertEqual([f["name"] for f in kinds.details("astrohq", "Report:kundli")["fields"]], ["report_name", "birth_date", "birth_time", "birth_place"])
		self.assertEqual(len(kinds.details("astrohq", "Report:match")["fields"]), 8)
		self.assertEqual(kinds.report("astrohq", "match")["maker"], "raftor_astrohq.reports.match_report")

	def test_the_plain_birth_summary_is_still_the_answer_for_a_report_with_no_name(self):
		made = reports.birth_summary("Any Item", {"report_name": "A", "birth_date": "1990-05-17", "birth_time": "06:30", "birth_place": "Pune"}, "x@example.com")
		self.assertTrue(made["content"].startswith(b"%PDF"))

	def test_nothing_that_makes_a_chart_for_a_customer_can_be_called_from_the_web(self):
		for module in (reports, places, details):
			for name in dir(module):
				function = getattr(module, name)
				if callable(function) and getattr(function, "__module__", None) == module.__name__:
					self.assertNotIn(function, frappe.whitelisted, f"{module.__name__}.{name} is on the web")


def real_service_is_set_up() -> bool:
	try:
		return bool(astrology.available() and places.ready())
	except Exception:
		return False


class TestWithTheRealServiceAndPlaces(AstroTestCase):
	"""Asks the astrology service on this server and the real list of places, and is skipped where they are not set up."""

	def setUp(self):
		super().setUp()
		if not real_service_is_set_up():
			self.skipTest("the astrology service or the list of places is not set up here")
		patcher = mock.patch("raftor_astrohq.reports.today", lambda: str(ON))
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_a_kundli_for_a_known_birth(self):
		made = reports.kundli_report("ITEM", KUNDLI_DETAILS, "x@example.com")
		pages, text = pdf_text(made["content"])
		self.assertEqual(pages, 2)
		for expected in ("Sunday, 08 June 1980, 13:49", "Delhi, Delhi, India", "UTC+05:30", "Virgo (Kanya)", "Pisces (Meena)", "Revati, pada 3", "Taurus (Vrishabha)",
						 "8 years 0 months 19 days still to run", "Moon 28 Jun 2021 28 Jun 2031 Running now"):
			self.assertIn(expected, text)
		order = [text.index(f"{lord} ") for lord in ("Mercury 28 Jun 1971", "Ketu 27 Jun 1988", "Venus 28 Jun 1995", "Sun 28 Jun 2015", "Moon 28 Jun 2021", "Mars 28 Jun 2031", "Rahu 28 Jun 2038",
																									 "Jupiter 28 Jun 2056", "Saturn 28 Jun 2072")]
		self.assertEqual(order, sorted(order))
		self.assertRegex(text, r"Saturn 28 Jun 2072 2[89] Jun 2091")

	def test_a_match_for_a_known_pair_adds_up(self):
		made = reports.match_report("ITEM", MATCH_DETAILS, "x@example.com")
		_pages, text = pdf_text(made["content"])
		total = float(re.search(r"([\d.]+) out of 36", text).group(1))
		delhi, mumbai = places.lookup("Delhi", datetime.datetime(1980, 6, 8, 13, 49)), places.lookup("Mumbai", datetime.datetime(1983, 2, 14, 9, 30))
		boy = astrology.birth_data({"date_of_birth": "1980-06-08", "time_of_birth": "13:49", "time_unknown": 0}, delhi["latitude"], delhi["longitude"], delhi["timezone_offset"], "Male")
		girl = astrology.birth_data({"date_of_birth": "1983-02-14", "time_of_birth": "09:30", "time_unknown": 0}, mumbai["latitude"], mumbai["longitude"], mumbai["timezone_offset"], "Female")
		answer = astrology.chart(boy, "MATCH_CALC", partner=girl)["compatibility"]
		self.assertEqual(total, answer["total_score"])
		self.assertEqual(sum(answer[key] for _n, _w, key, _b in reports.KOOTAS), answer["total_score"])
		self.assertIn("Mumbai, Maharashtra, India", text)

	def test_a_place_that_does_not_exist_is_said_in_words_before_anything_is_made(self):
		with self.assertRaises(places.PlaceNotFound):
			reports.kundli_report("ITEM", {**KUNDLI_DETAILS, "birth_place": "Nowhereville, Atlantis"}, "x@example.com")
