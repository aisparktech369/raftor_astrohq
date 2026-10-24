"""The Panchang (panchang.py, panchang_panes.py, places.suggest/near/by_id): any day at any town, kept once, what is running now, and the page's markup.

The engine is stood in for by its own answers for Delhi and Mumbai (tests/fixtures/panchang_days.json.gz, recorded from engine 1.3.0 with the small list of places the tests use).

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_panchang
"""
import datetime
import gzip
import html
import json
import math
import re
import zlib
from pathlib import Path
from unittest import TestCase, mock
from zoneinfo import ZoneInfo

import frappe

from raftor_astrohq import astrology, page_definitions, panchang, panchang_panes, places, report_view
from raftor_websitehq.website_hq import report_html
from raftor_astrohq.tests.test_places import PlacesCase

FIXTURE = Path(__file__).parent / "fixtures" / "panchang_days.json.gz"
KOLKATA = ZoneInfo("Asia/Kolkata")
SETTINGS = "Astrology API Settings"


def recorded() -> dict:
	with gzip.open(FIXTURE, "rt", encoding="utf-8") as f:
		return json.load(f)


class Stood(PlacesCase):
	"""The small list of places, a stand-in for the engine that answers from the recorded days (and writes down what it was asked), and a clean cache."""

	def setUp(self):
		super().setUp()
		self.days = recorded()
		self.asked = []
		self.engine_error = None
		self.now = datetime.datetime(2026, 10, 24, 8, 0, tzinfo=KOLKATA)  # the moment "now" is, in every town
		clock = mock.patch.object(panchang, "local_now", lambda place: self.now.astimezone(ZoneInfo(place["timezone"])))
		clock.start()
		self.addCleanup(clock.stop)

		def chart(numbers, mode="SUPER_BASIC", partner=None):
			self.asked.append((mode, dict(numbers)))
			if self.engine_error:
				raise self.engine_error
			town = "delhi" if numbers["latitude"] > 25 else "mumbai"
			key = f"{town}:{numbers['year']:04d}-{numbers['month']:02d}-{numbers['day']:02d}"
			if key not in self.days:
				raise astrology.AstrologyRefused("not recorded")
			return json.loads(json.dumps(self.days[key]))

		patcher = mock.patch.object(astrology, "chart", chart)
		patcher.start()
		self.addCleanup(patcher.stop)
		self.forget_kept()
		self.addCleanup(self.forget_kept)
		self.switch_on("Delhi")

	def forget_kept(self):
		cache = frappe.cache()
		cache.delete_keys("astro_panchang")
		cache.delete_keys("astro_panchang_new")
		cache.delete_keys("astro_panchang_muhurat")

	def switch_on(self, town="Delhi", **more):
		frappe.db.set_single_value(SETTINGS, {"panchang_place": town, **more})

	def delhi(self, on="2026-10-24"):
		return places.lookup("Delhi", datetime.date.fromisoformat(on))

	def at(self, text):
		return datetime.datetime.fromisoformat(text)


class TestFindingATown(PlacesCase):
	def test_a_place_has_an_id_and_is_found_again_by_it_with_the_offset_of_the_day(self):
		found = places.lookup("Delhi", datetime.date(2026, 10, 24))
		self.assertEqual(found["id"], 19)
		again = places.by_id(19, datetime.date(2026, 10, 24))
		self.assertEqual((again["name"], again["timezone_offset"], again["latitude"]), (found["name"], 5.5, found["latitude"]))
		self.assertEqual(places.by_id("21", datetime.date(1990, 1, 1))["timezone_offset"], 5.75)  # an id may come as text from an address (Kathmandu, whose clock has been +5:45 since 1986)
		for bad in (None, "", "x", 9999, -1):
			with self.assertRaises(places.PlaceNotFound):
				places.by_id(bad, datetime.date(2026, 10, 24))

	def test_the_first_letters_find_the_town_and_a_name_written_whole_comes_first(self):
		self.assertEqual([(r["name"], r["region"]) for r in places.suggest("Pun")][:1], [("Pune", "Maharashtra, India")])
		self.assertEqual(places.suggest("poo")[0]["name"], "Pune")  # another name of the town (Poona)
		self.assertEqual(places.suggest("Mumb")[0], {"id": 22, "name": "Mumbai", "region": "Maharashtra, India"})
		self.assertEqual(places.suggest("bombay")[0]["name"], "Mumbai")
		everything = [r["id"] for r in places.suggest("pune")]
		self.assertEqual(len(everything), len(set(everything)))
		pune = [(r["name"], r["region"]) for r in places.suggest("pune")]
		self.assertEqual(pune.count(("Pune", "Maharashtra, India")), 1)  # the same town listed twice is shown once
		self.assertIn(("Pune", "Bagmati, Nepal"), pune)
		hyderabad = places.suggest("hyderabad")
		self.assertEqual([r["region"] for r in hyderabad], ["Telangana, India", "Sindh, Pakistan"])  # the bigger town first

	def test_a_name_written_whole_comes_before_a_bigger_town_that_only_starts_with_it(self):
		from raftor_astrohq.tests.test_places import ADMIN1, ADMIN2, CITIES, COUNTRIES, city

		bigger = city(30, "Punekar Nagar", 19.0, 74.0, "IN", "16", "521", 9000000, "Asia/Kolkata")
		places.build_from_text(CITIES + "\n" + bigger, ADMIN1, ADMIN2, COUNTRIES, self.file)
		self.assertEqual([r["name"] for r in places.suggest("pune")][:2], ["Pune", "Pune"])  # the two that are called Pune, the bigger one of the other name after them
		self.assertEqual(places.suggest("pune")[-1]["name"], "Punekar Nagar")
		self.assertEqual(places.suggest("punek")[0]["name"], "Punekar Nagar")

	def test_a_short_nickname_of_a_small_place_does_not_come_before_a_big_town_but_a_longer_other_name_does(self):
		from raftor_astrohq.tests.test_places import ADMIN1, ADMIN2, CITIES, COUNTRIES, city

		small = city(31, "Muli", 2.9, 73.5, "IN", "16", "519", 900, "Asia/Kolkata", "Mum,Bombayy")
		places.build_from_text(CITIES + "\n" + small, ADMIN1, ADMIN2, COUNTRIES, self.file)
		found = [r["name"] for r in places.suggest("mum")]
		self.assertEqual(found[0], "Mumbai")  # Mumbai begins with it and is far bigger: Muli is only known as Mum to a few
		self.assertIn("Muli", found)
		self.assertEqual(places.suggest("muli")[0]["name"], "Muli")  # its own name written whole
		self.assertEqual(places.suggest("bombay")[0]["name"], "Mumbai")  # another name of 4 letters or more is a name: the bigger town first
		self.assertEqual([r["name"] for r in places.suggest("bombayy")][:1], ["Muli"])
		more = city(32, "Bombay", -37.0, 174.9, "IN", "16", "519", 2000, "Pacific/Auckland") + "\n" + city(33, "Goa", 15.5, 73.8, "IN", "16", "519", 500, "Asia/Kolkata") + "\n" + city(34, "Goalpara", 26.2, 90.6, "IN", "16", "519", 50000, "Asia/Kolkata")
		places.build_from_text(CITIES + "\n" + small + "\n" + more, ADMIN1, ADMIN2, COUNTRIES, self.file)
		self.assertEqual([r["name"] for r in places.suggest("bombay")][:2], ["Mumbai", "Bombay"])  # Bombay is a name of Mumbai and of a small place: the bigger town first
		self.assertEqual([r["name"] for r in places.suggest("goa")][:2], ["Goa", "Goalpara"])  # a place called Goa is written whole, though a bigger one starts with it

	def test_a_few_letters_that_many_places_start_with_still_find_the_biggest_town(self):
		from raftor_astrohq.tests.test_places import ADMIN1, ADMIN2, CITIES, COUNTRIES, city

		crowd = "\n".join(city(1000 + n, f"Lonaly{n:04d}", 20.0 + n / 1000, 75.0, "IN", "16", "519", 100 + n % 50, "Asia/Kolkata") for n in range(900))  # nine hundred small places that start with \"lon\" and come before London in the list and in its order of names, more than the search reads
		places.build_from_text(crowd + "\n" + CITIES, ADMIN1, ADMIN2, COUNTRIES, self.file)
		self.assertEqual(places.suggest("lon")[0]["name"], "London")  # the biggest of them all, though the crowd came before it in the list
		self.assertEqual([r["region"] for r in places.suggest("lon")][:2], ["England, United Kingdom", "Ontario, Canada"])

	def test_one_letter_or_nothing_finds_nothing_and_the_most_is_asked_for(self):
		for text in ("", "p", " ", None, "zzzz"):
			self.assertEqual(places.suggest(text), [])
		rampur = places.suggest("ramp")
		self.assertEqual([r["region"] for r in rampur], ["Moradabad, Uttar Pradesh, India", "Jaunpur, Uttar Pradesh, India", "Hardoi, Uttar Pradesh, India"])  # three towns of one name: the district says which
		self.assertEqual(len(places.suggest("ramp", limit=2)), 2)

	def test_where_someone_is_gives_the_town_nearest_and_a_bigger_town_beats_a_nearer_village(self):
		self.assertEqual(places.near(18.52, 73.85, datetime.date(2026, 10, 24))["name"].split(",")[0], "Pune")
		self.assertEqual(places.near(28.70, 77.10, datetime.date(2026, 10, 24))["id"], 19)
		self.assertEqual(places.near(18.54, 73.80, datetime.date(2026, 10, 24))["id"], 1)  # standing on the village of 5,000 listed beside Pune: the town of 3 million is meant
		self.assertIsNone(places.near(0.0, -30.0, datetime.date(2026, 10, 24)))  # mid-Atlantic
		self.assertIsNone(places.near(19.2, 74.6, datetime.date(2026, 10, 24)))  # half way between Pune and Aurangabad: neither is within 60 km
		self.assertIsNone(places.near(19.7, 74.0, datetime.date(2026, 10, 24)))  # Aurangabad is in the square looked at, but 104 km off
		for bad in (("x", "y"), (None, None), (91, 0), (0, 181)):
			self.assertIsNone(places.near(*bad, datetime.date(2026, 10, 24)))


class TestADay(Stood):
	def test_a_day_is_asked_for_once_and_then_read_back(self):
		first = panchang.day(datetime.date(2026, 10, 24), self.delhi())
		again = panchang.day(datetime.date(2026, 10, 24), self.delhi())
		self.assertEqual(first, again)
		self.assertEqual(first["tithi"]["name"], "Trayodashi")
		self.assertEqual(len(self.asked), 1)
		panchang.day(datetime.date(2026, 10, 25), self.delhi())
		self.assertEqual(len(self.asked), 2)  # another day is another question
		panchang.day(datetime.date(2026, 11, 8), places.lookup("Mumbai", datetime.date(2026, 11, 8)))
		self.assertEqual(len(self.asked), 3)  # so is another town

	def test_only_the_numbers_a_calculation_needs_go_to_the_engine_and_noon_is_the_time_asked(self):
		panchang.day(datetime.date(2026, 10, 24), self.delhi())
		(mode, numbers), = self.asked
		self.assertEqual(mode, "PANCHANGA_DAY")
		self.assertEqual(set(numbers), {"year", "month", "day", "hour", "minute", "second", "latitude", "longitude", "timezone_offset"})
		self.assertEqual((numbers["hour"], numbers["timezone_offset"]), (12, 5.5))

	def test_the_offset_is_that_of_the_day_asked_for(self):
		london = places.lookup("London, England", datetime.date(2026, 8, 15))
		for on, expected in ((datetime.date(2026, 8, 15), 1.0), (datetime.date(2026, 12, 15), 0.0)):
			self.days[f"delhi:{on.isoformat()}"] = self.days["delhi:2026-10-24"]
			panchang.day(on, london)
			self.assertEqual(self.asked[-1][1]["timezone_offset"], expected)

	def test_what_is_kept_is_asked_for_again_after_the_date_the_settings_say_answers_are_good_from(self):
		panchang.day(datetime.date(2026, 10, 24), self.delhi())
		frappe.db.set_single_value(SETTINGS, "answers_valid_from", frappe.utils.add_days(frappe.utils.today(), -1))
		panchang.day(datetime.date(2026, 10, 24), self.delhi())
		self.assertEqual(len(self.asked), 1)  # made today, good from yesterday
		frappe.db.set_single_value(SETTINGS, "answers_valid_from", frappe.utils.add_days(frappe.utils.today(), 1))
		panchang.day(datetime.date(2026, 10, 24), self.delhi())
		self.assertEqual(len(self.asked), 2)

	def test_the_default_town_is_kept_for_a_week_and_any_other_for_a_day(self):
		with mock.patch.object(frappe.cache(), "set_value", wraps=frappe.cache().set_value) as kept:
			panchang.day(datetime.date(2026, 10, 24), self.delhi())
			panchang.day(datetime.date(2026, 11, 8), places.lookup("Mumbai", datetime.date(2026, 11, 8)))
		self.assertEqual([call.kwargs["expires_in_sec"] for call in kept.call_args_list], [panchang.KEEP_DEFAULT, panchang.KEEP_OTHER])

	def test_only_so_many_new_days_are_worked_out_in_a_minute_and_what_is_kept_is_always_shown(self):
		self.switch_on("Delhi", panchang_new_per_minute=2)
		panchang.day(datetime.date(2026, 10, 24), self.delhi())
		panchang.day(datetime.date(2026, 10, 25), self.delhi())
		with self.assertRaises(panchang.PanchangBusy):
			panchang.day(datetime.date(2026, 10, 26), self.delhi())
		self.assertEqual(len(self.asked), 2)  # the third was never asked for
		self.assertEqual(panchang.day(datetime.date(2026, 10, 24), self.delhi())["tithi"]["name"], "Trayodashi")  # one kept is still shown

	def test_when_the_engine_cannot_be_asked_nothing_is_kept_and_the_error_is_the_engines(self):
		self.engine_error = astrology.AstrologyUnavailable("down")
		with self.assertRaises(astrology.AstrologyUnavailable):
			panchang.day(datetime.date(2026, 10, 24), self.delhi())
		self.engine_error = None
		self.assertEqual(panchang.day(datetime.date(2026, 10, 24), self.delhi())["weekday"], "Saturday")

	def test_a_week_is_seven_days_from_the_first_and_stops_at_the_last_year(self):
		self.assertEqual([d["date"] for d in panchang.week(datetime.date(2026, 10, 24), self.delhi())], [f"2026-10-{n}" for n in range(24, 31)])
		self.days["delhi:2399-12-31"] = self.days["delhi:2026-10-24"]
		self.assertEqual(len(panchang.week(datetime.date(2399, 12, 31), self.delhi())), 1)

	def test_the_dates_are_read_from_the_address_and_never_outside_the_years_the_engine_answers_for(self):
		delhi = self.delhi()
		self.assertEqual(panchang.date_of("2026-11-08", delhi), datetime.date(2026, 11, 8))
		self.assertEqual(panchang.date_of("1700-01-01", delhi), panchang.FIRST)
		self.assertEqual(panchang.date_of("2500-01-01", delhi), panchang.LAST)
		for text in (None, "", "not a date", "2026-13-45"):
			self.assertEqual(panchang.date_of(text, delhi), panchang.today(delhi))

	def test_the_town_is_the_one_asked_for_by_its_id_else_the_default_one(self):
		on = datetime.date(2026, 10, 24)
		self.assertEqual(panchang.place_of("22", on)["name"].split(",")[0], "Mumbai")
		for bad in (None, "", "x", "9999"):
			self.assertEqual(panchang.place_of(bad, on)["id"], 19)
		self.switch_on("")
		self.assertIsNone(panchang.default_place())
		self.assertFalse(panchang.on())


class TestWhatIsRunning(Stood):
	def part(self, now, **kw):
		return panchang.current(self.delhi(), self.at(now))

	def test_the_part_that_holds_the_moment_is_the_one_running_and_the_next_good_one_is_named(self):
		got = self.part("2026-10-24T08:00:00+05:30")
		self.assertEqual((got["part"]["name"], got["part"]["quality"], got["part"]["of"]), ("Shubh", "good", "day"))
		self.assertEqual(got["next"]["name"], "Rog")
		self.assertEqual(got["next_good"]["name"], "Chal")  # Rog and Udveg to avoid, then Chal
		got = self.part("2026-10-24T10:00:00+05:30")
		self.assertEqual((got["part"]["name"], got["part"]["quality"], got["next_good"]["name"]), ("Rog", "avoid", "Chal"))

	def test_each_part_begins_at_its_first_moment_and_ends_just_before_the_next(self):
		slots = self.days["delhi:2026-10-24"]["chaugharia"]["day"]
		start = self.at(slots[2]["from"])
		self.assertEqual(self.part(start.isoformat())["part"]["name"], slots[2]["name"])
		self.assertEqual(self.part((start - datetime.timedelta(seconds=1)).isoformat())["part"]["name"], slots[1]["name"])

	def test_after_sunset_it_is_the_night_and_after_midnight_still_the_night_of_the_day_before_until_the_sun_is_up(self):
		self.assertEqual(self.part("2026-10-24T19:00:00+05:30")["part"]["of"], "night")
		before = self.days["delhi:2026-10-23"]["chaugharia"]["night"]
		for moment in ("2026-10-24T00:30:00+05:30", "2026-10-24T03:00:00+05:30", "2026-10-24T06:00:00+05:30"):
			expected = next(p["name"] for p in before if self.at(p["from"]) <= self.at(moment) < self.at(p["to"]))
			got = self.part(moment)
			self.assertEqual((got["part"]["name"], got["part"]["of"]), (expected, "night"), moment)
		self.assertEqual(self.part("2026-10-24T06:32:00+05:30")["part"]["of"], "day")  # the sun is up

	def test_the_last_part_of_the_night_has_the_first_of_the_day_after_it(self):
		last = self.days["delhi:2026-10-23"]["chaugharia"]["night"][7]
		got = self.part((self.at(last["to"]) - datetime.timedelta(minutes=5)).isoformat())
		self.assertEqual((got["part"]["name"], got["part"]["index"]), (last["name"], 15))
		self.assertIsNone(got["next"])  # (the next day's first part comes from that day's answer: the caller asks again when this one ends)


class TestThePage(Stood):
	def page(self, **args):
		(item,) = panchang.page(**args)["items"]
		return item

	def test_it_has_the_panes_in_their_order_and_the_bar_to_move_by(self):
		item = self.page(date="2026-10-24")
		titles = re.findall(r'<h3 class="rv-title">([^<]*)', item["body_html"])
		self.assertEqual(titles, ["Panchang", "Chaugharia", "Times to know", "The next 7 days"])  # (a phone reads them in this order; no muhurat pane: nothing for it to lead to)
		self.assertNotIn("rv-draft", item["body_html"])
		self.assertIn('class="rv-board rv-board-lite rv-look-roomy"', item["body_html"])
		date, town = item["toolbar"]["controls"]
		self.assertEqual((date["type"], date["value"], date["label"]), ("date", "2026-10-24", "Saturday, 24 October 2026"))
		self.assertEqual((date["previous"], date["next"]), ("/panchang?date=2026-10-23", "/panchang?date=2026-10-25"))
		self.assertEqual((town["type"], town["value"], town["label"]), ("lookup", "19", "Delhi, India"))
		self.assertEqual((town["search"], town["near"]), ("raftor_astrohq.panchang.places_found", "raftor_astrohq.panchang.place_near"))

	def test_the_panchang_of_the_day_is_in_words_with_when_each_ends_and_what_follows(self):
		body = self.page(date="2026-10-24")["body_html"]
		text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)))
		for expected in ("Tithi Shukla Trayodashi till 1:38 pm, then Shukla Chaturdashi", "Nakshatra Uttara Bhadrapada, pada 2 till 8:32 pm, then Revati", "Yoga Vyaghata till 8:00 pm, then Harshana",
						 "Karana Taitila till 1:38 pm, then Gara", "Weekday Saturday", "Sunrise 6:31 am", "Sunset 5:38 pm", "Moonrise 4:33 pm", "Rahu Kaal 9:18–10:41 am avoid", "Gulika 6:31–7:54 am avoid",
						 "Yamaganda 1:28–2:52 pm avoid", "Abhijit muhurat 11:42 am–12:27 pm good", "Moonset 5:20 am next day", "Waxing · 94% lit", "The day's tithi and nakshatra are the ones at sunrise (6:31 am)"):
			self.assertIn(expected, text)

	def test_the_chaugharia_are_a_table_for_the_day_and_one_for_the_night_with_good_and_avoid(self):
		body = self.page(date="2026-10-24")["body_html"]
		self.assertEqual(body.count('class="rv-good'), 9)  # the day's Shubh, Chal, Labh, Amrit and the night's Labh, Shubh, Amrit, Chal ... counted by the table
		day = re.findall(r'<tr class="(rv-good|rv-avoid)[^"]*"><th scope="row">(\w+)</th>', body)
		self.assertEqual([name for _tone, name in day][:8], ["Kaal", "Shubh", "Rog", "Udveg", "Chal", "Labh", "Amrit", "Kaal"])
		self.assertIn("Good: Amrit, Chal, Labh, Shubh. Avoid: Kaal, Rog, Udveg.", body)
		self.assertIn("sunrise 6:31 am to sunset 5:38 pm", body)
		self.assertIn("1:42 am next day", body)  # the night goes past midnight

	def test_the_running_part_and_time_are_marked_only_on_the_day_that_is_today_there(self):
		today_page = self.page(date="2026-10-24")["body_html"]
		self.assertEqual(len(re.findall(r'<tr class="rv-(?:good|avoid) rv-now">', today_page)), 1)  # at 8 am: Shubh
		self.assertIn("Shubh · good till 9:18 am", today_page)  # the summary a folded pane says on a phone
		self.assertNotIn("rv-now", self.page(date="2026-10-26")["body_html"])  # a day to come has no running part
		self.assertNotIn("rv-now", self.page(date="2026-10-23")["body_html"])
		self.now = datetime.datetime(2026, 10, 24, 10, 0, tzinfo=KOLKATA)  # the middle of Rahu Kaal
		body = self.page(date="2026-10-24")["body_html"]
		self.assertIn('<div class="rv-win rv-avoid rv-now"><span class="rv-k">Rahu Kaal</span><b>9:18–10:41 am</b><span>avoid · on now</span></div>', body)
		self.assertIn('<div class="rv-win rv-good"><span class="rv-k">Abhijit muhurat</span><b>11:42 am–12:27 pm</b><span>good</span></div>', body)
		self.assertEqual(body.count("rv-win rv-"), 4)
		self.assertEqual(body.count("rv-now"), 2)  # (the part of the chaugharia and the window: nothing else)

	def test_the_table_that_holds_the_running_part_is_marked_to_come_first_on_a_phone(self):
		self.assertEqual(self.page(date="2026-10-24")["body_html"].count('<div class="rv-first">'), 1)
		self.assertRegex(self.page(date="2026-10-24")["body_html"], r'<div class="rv-first"><div class="rv-sub"><b>Day</b>')  # at 8 am it is the day's
		self.now = datetime.datetime(2026, 10, 24, 22, 0, tzinfo=KOLKATA)
		night = self.page(date="2026-10-24")["body_html"]
		self.assertRegex(night, r'<div class="rv-first"><div class="rv-sub"><b>Night</b>')
		self.assertEqual(night.count("rv-first"), 1)
		self.assertNotIn("rv-first", self.page(date="2026-10-26")["body_html"])  # a day to come has no running part

	def test_the_moon_is_drawn_as_it_is_lit_and_says_so_in_words(self):
		body = self.page(date="2026-10-24")["body_html"]  # 94% lit and waxing
		self.assertIn('<svg class="rv-moon" viewBox="-11 -11 22 22" role="img" aria-label="Waxing moon, 94% lit">', body)
		self.assertIn('<p class="rv-phase"><b>Waxing</b> · 94% lit</p>', body)
		waning = self.days["delhi:2026-10-24"]
		waning["moon"].update(illumination=0.1, waxing=False)
		self.forget_kept()
		self.assertIn('<p class="rv-phase"><b>Waning</b> · 10% lit</p>', self.page(date="2026-10-24")["body_html"])

	def test_the_next_seven_days_are_links_with_the_shown_day_marked_and_the_town_kept_in_them_only_when_chosen(self):
		body = self.page(date="2026-10-24")["body_html"]
		tiles = re.findall(r'<a class="rv-tile( rv-on)?" href="([^"]*)">', body)
		self.assertEqual(len(tiles), 7)
		self.assertEqual([on for on, _href in tiles], [" rv-on"] + [""] * 6)
		self.assertEqual(tiles[1][1], "/panchang?date=2026-10-25")
		chosen = self.page(date="2026-11-08", place="22")["body_html"]
		self.assertIn('href="/panchang?date=2026-11-09&amp;place=22"', chosen)
		self.assertIn("Krishna Chaturdashi", chosen)  # Mumbai's tithi at sunrise on 8 Nov

	def test_the_town_in_the_address_is_used_and_in_the_bar_and_one_that_is_not_there_gives_the_default(self):
		mumbai = self.page(date="2026-11-08", place="22")
		self.assertEqual(mumbai["toolbar"]["controls"][1]["label"], "Mumbai, India")
		self.assertEqual(mumbai["toolbar"]["controls"][0]["next"], "/panchang?date=2026-11-09&place=22")
		fallback = self.page(date="2026-10-24", place="9999")
		self.assertEqual(fallback["toolbar"]["controls"][1]["value"], "19")
		self.assertNotIn("place=", fallback["toolbar"]["controls"][0]["next"])

	def test_today_is_not_a_link_on_today_and_the_ends_of_time_have_no_previous_or_next(self):
		self.assertIsNone(self.page()["toolbar"]["controls"][0]["today"])  # no date in the address: today
		self.assertIsNone(self.page(date="2026-10-24")["toolbar"]["controls"][0]["today"])
		self.assertEqual(self.page(date="2026-10-26")["toolbar"]["controls"][0]["today"], "/panchang")
		self.days["delhi:1800-01-01"] = self.days["delhi:2026-10-24"]
		self.days["delhi:2399-12-31"] = self.days["delhi:2026-10-24"]
		self.assertIsNone(self.page(date="1800-01-01")["toolbar"]["controls"][0]["previous"])
		self.assertIsNone(self.page(date="2399-12-31")["toolbar"]["controls"][0]["next"])

	def test_switched_off_it_shows_nothing_and_asks_the_engine_nothing(self):
		self.switch_on("")
		self.assertEqual(panchang.page(date="2026-10-24"), {"items": []})
		self.assertEqual(panchang.places_found("Mum"), [])
		self.assertIsNone(panchang.place_near(19.07, 72.88))
		self.assertEqual(self.asked, [])

	def test_when_the_engine_is_down_or_busy_the_page_says_so_in_words_and_keeps_the_bar(self):
		self.engine_error = astrology.AstrologyUnavailable("down")
		item = self.page(date="2026-10-24")
		self.assertIn("cannot be worked out just now", item["body_html"])
		self.assertEqual(len(item["toolbar"]["controls"]), 2)
		self.engine_error = None
		self.switch_on("Delhi", panchang_new_per_minute=1)
		busy = self.page(date="2026-10-24")  # the first day takes the one allowed; the second of the week is over it
		self.assertIn("try again in a minute", busy["body_html"])
		self.assertEqual(len(busy["toolbar"]["controls"]), 2)

	def test_what_the_engine_wrote_never_reaches_the_page_as_markup(self):
		self.days["delhi:2026-10-24"]["tithi"]["name"] = '<script>alert(1)</script>'
		self.days["delhi:2026-10-24"]["nakshatra"]["name"] = '"><img src=x onerror=alert(1)>'
		body = self.page(date="2026-10-24")["body_html"]
		for raw in ("<script", "<img", 'onerror="'):
			self.assertNotIn(raw, body)
		self.assertIn("&lt;script&gt;", body)

	def test_the_full_moon_and_the_new_moon_are_only_purnima_and_amavasya(self):
		full = self.page(date="2026-10-26")["body_html"]
		self.assertIn("<b>Purnima</b>", full)
		self.assertNotIn("Shukla Purnima", full)
		new = self.page(date="2026-11-09", place="22")["body_html"]
		self.assertIn("<b>Amavasya</b>", new)
		self.assertNotIn("Krishna Amavasya", new)

	def test_the_chaugharia_legend_names_every_good_and_every_avoid_name_of_the_day_and_the_night(self):
		for part in self.days["delhi:2026-10-24"]["chaugharia"]["day"]:
			part["quality"] = "avoid"  # none of the day is good, so the good names come from the night
		self.assertIn("Good: Amrit, Chal, Labh, Shubh.", self.page(date="2026-10-24")["body_html"])

	def test_a_tithi_that_ends_before_the_next_sunrise_says_so(self):
		body = self.page(date="2026-10-27")["body_html"]  # Krishna Pratipada at sunrise, and Dwitiya after it comes and goes before the next sunrise
		self.assertIn("which ends before the next sunrise", body)
		self.assertNotIn("which ends before the next sunrise", self.page(date="2026-10-24")["body_html"])

	def test_the_muhurat_button_is_there_only_when_the_service_is_on_and_a_pandit_ji_offers_it(self):
		self.assertNotIn("rv-cta", self.page(date="2026-10-24")["body_html"])  # no service named in the settings
		frappe.db.set_single_value(SETTINGS, {"panchang_muhurat_service": "SVC-MUHURAT", "panchang_muhurat_topic": "Auspicious date"})
		for service, offered, shown in ((None, True, False), ({"enabled": 0, "persona": "Pandit ji"}, True, False), ({"enabled": 1, "persona": ""}, True, False),
										({"enabled": 1, "persona": "Pandit ji"}, False, False), ({"enabled": 1, "persona": "Pandit ji"}, True, True)):
			self.forget_kept()
			with mock.patch.object(panchang, "_service", return_value=frappe._dict(service) if service else None), mock.patch.object(panchang, "_someone_offers", return_value=offered):
				body = self.page(date="2026-10-24")["body_html"]
			self.assertEqual("rv-cta" in body, shown, (service, offered))
		self.assertIn('href="/consult?persona=Pandit+ji&amp;topic=Auspicious+date"', body)
		self.assertIn("ask a Pandit ji for a muhurat made for you", body)

	def test_the_endpoints_may_be_asked_by_a_visitor_who_is_not_signed_in(self):
		for method in (panchang.page, panchang.places_found, panchang.place_near):
			self.assertIn(method, frappe.whitelisted)
			self.assertIn(method, frappe.guest_methods)

	def test_the_page_is_shipped_for_everyone_the_group_is_declared_and_the_method_may_send_markup(self):
		page = page_definitions.panchang_page()
		self.assertEqual((page["route"], page["login_required"]), ("panchang", False))
		self.assertIn(page, page_definitions.definitions())
		self.assertEqual(page["sections"][0]["source"]["card"], "Report View")
		self.assertEqual(page["sections"][0]["source"]["url_args"], "date,place")
		self.assertIn("raftor_astrohq.panchang.page", frappe.get_hooks("rfhq_trusted_html_sources"))
		from raftor_websitehq.website_hq import page_sync

		self.assertEqual(page_sync.groups()["panchang"], "Panchang")
		page_sync.check(page)  # (it says what is wrong, if anything is)


class TestTheNight(Stood):
	def test_the_nightly_work_keeps_today_and_the_week_ahead_of_the_default_town(self):
		self.assertEqual(panchang.warm(), 8)  # 24 to 31 Oct
		self.assertEqual(len(self.asked), 8)
		panchang.warm()
		self.assertEqual(len(self.asked), 8)  # nothing worked out twice
		self.switch_on("")
		self.assertEqual(panchang.warm(), 0)

	def test_the_nightly_work_stops_quietly_when_the_engine_is_not_there(self):
		self.engine_error = astrology.AstrologyUnavailable("down")
		self.assertEqual(panchang.warm(), 0)


class TestTheMoonPicture(TestCase):
	def points(self, markup):
		(found,) = re.findall(r'<polygon class="rv-moon-lit" points="([^"]*)"(?:/>|></polygon>)', markup)
		return [tuple(float(n) for n in pair.split(",")) for pair in found.split()]

	def area(self, points):
		return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]))) / 2

	def test_the_lit_part_is_as_much_of_the_disc_as_the_engine_says(self):
		for lit in (0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0):
			for waxing in (True, False):
				got = self.area(self.points(panchang_panes.moon_picture(lit, waxing, "x"))) / (math.pi * 10 ** 2)
				self.assertAlmostEqual(got, lit, delta=0.006, msg=(lit, waxing))

	def test_a_waxing_moon_is_lit_on_the_right_a_waning_one_on_the_left_and_a_half_is_cut_straight(self):
		for lit in (0.2, 0.5, 0.8):
			right = self.points(panchang_panes.moon_picture(lit, True, "x"))
			left = self.points(panchang_panes.moon_picture(lit, False, "x"))
			self.assertAlmostEqual(max(x for x, _y in right), 10.0, delta=0.01)
			self.assertAlmostEqual(min(x for x, _y in left), -10.0, delta=0.01)
		half = self.points(panchang_panes.moon_picture(0.5, True, "x"))
		self.assertGreaterEqual(min(x for x, _y in half), -1e-9)  # nothing of the dark half
		crescent = self.points(panchang_panes.moon_picture(0.2, True, "x"))
		self.assertGreaterEqual(min(x for x, _y in crescent), -1e-9)  # a crescent keeps to its own side
		gibbous = self.points(panchang_panes.moon_picture(0.8, True, "x"))
		self.assertAlmostEqual(min(x for x, _y in gibbous), -6.0, delta=0.01)  # a gibbous moon is lit a little past the middle

	def test_the_new_moon_is_a_dark_disc_and_the_full_moon_is_lit_all_over(self):
		self.assertNotIn("<polygon", panchang_panes.moon_picture(0.0, True, "x"))
		self.assertNotIn("<polygon", panchang_panes.moon_picture(0.003, False, "x"))
		full = self.points(panchang_panes.moon_picture(1.0, True, "x"))
		self.assertAlmostEqual(max(x for x, _y in full), 10.0, delta=0.01)
		self.assertAlmostEqual(min(x for x, _y in full), -10.0, delta=0.01)
		for odd in (-3, 7, 1.0000001):
			self.assertTrue(self.area(self.points(panchang_panes.moon_picture(odd, True, "x"))) <= math.pi * 100 + 1e-6 if odd > 0 else "<polygon" not in panchang_panes.moon_picture(odd, True, "x"))

	def test_the_words_of_the_picture_are_text_and_the_whole_picture_survives_the_report_filter(self):
		made = panchang_panes.moon_picture(0.6, True, 'Waxing moon <b>"60%"</b>')
		self.assertNotIn("<b>", made)
		cleaned = report_html.clean(f"<div>{made}</div>")
		self.assertIn('<svg class="rv-moon"', cleaned)
		self.assertIn('<rect class="rv-moon-dark" x="-10" y="-10" width="20" height="20" rx="10" ry="10">', cleaned)
		self.assertEqual(len(self.points(cleaned)), len(self.points(made)))
		self.assertIn('class="rv-moon-lit"', cleaned)
