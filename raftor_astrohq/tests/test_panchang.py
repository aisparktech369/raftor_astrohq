"""The Panchang (panchang.py, panchang_panes.py): any day at any town, kept once, what is running now, and the page's markup.

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

from raftor_astrohq import astrology, page_definitions, panchang, panchang_panes, panchang_widget, places, report_view
from raftor_websitehq.website_hq import components
from raftor_websitehq.website_hq import report_html
from raftor_astrohq.tests.places_fake import PlacesCase

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
		frappe.db.set_single_value(SETTINGS, {"panchang_place": town, "panchang_muhurat_persona": "", "panchang_muhurat_topic": "", **more})  # (what the live site chose for the muhurat is not what a test is about)

	def delhi(self, on="2026-10-24"):
		return places.lookup("Delhi", datetime.date.fromisoformat(on))

	def at(self, text):
		return datetime.datetime.fromisoformat(text)

	def guides(self, live=None, listed=None):
		"""The guides servicehq lists (card_feeds.providers): `live` those online now, `listed` everyone who can be booked."""
		self.guide_calls = []

		def providers(persona=None, online=None, limit=12, **choices):
			self.guide_calls.append({"persona": persona, "online": online, "topic": choices.get("topic")})
			return {"items": (live if online == "1" else listed) or []}

		return mock.patch("raftor_servicehq.card_feeds.providers", providers)

	TALK = {"full_name": "Ravi", "status": "Online", "button_label": "Talk now · free", "button_url": "/consult/online/start?offering=SVC-1&topic=Auspicious+date&offer=OFF-1"}
	BOOK = {"full_name": "Ravi", "button_label": "Book", "button_url": "/consult/slots?offering=SVC-1"}


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
		self.assertEqual(set(numbers), {"year", "month", "day", "hour", "minute", "second", "latitude", "longitude", "timezone_offset", "chal", "rise"})
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
		self.assertEqual([call.kwargs["expires_in_sec"] for call in kept.call_args_list if str(call.args[0]).startswith("astro_panchang:")], [8 * 24 * 3600, 24 * 3600])  # (the days; the towns kept beside them are the client's)

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
		self.assertEqual(panchang.date_of("1700-01-01", delhi), datetime.date(1800, 1, 1))
		self.assertEqual(panchang.date_of("2500-01-01", delhi), datetime.date(2399, 12, 31))
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
						 "Yamaganda 1:28–2:52 pm avoid", "Abhijit muhurat 11:42 am–12:27 pm good", "Moonset 5:20 am next day", "Waxing · 94% lit", "The day's tithi and nakshatra are the ones at sunrise (6:31 am)", "Place data: GeoNames (geonames.org), licensed CC BY 4.0."):
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

	def test_the_muhurat_button_connects_to_a_pandit_ji_who_is_live_and_has_nothing_without_one_named_in_the_settings(self):
		with self.guides(live=[self.TALK], listed=[self.BOOK]):
			self.assertNotIn("rv-cta", self.page(date="2026-10-24")["body_html"])  # no kind of guide in the settings
			self.assertEqual(self.guide_calls, [])
			frappe.db.set_single_value(SETTINGS, {"panchang_muhurat_persona": "Pandit ji", "panchang_muhurat_topic": "Auspicious date"})
			self.forget_kept()
			body = self.page(date="2026-10-24")["body_html"]
		self.assertIn("A Pandit ji is live now.", body)
		self.assertIn('<a class="rv-cta" href="/consult/online/start?offering=SVC-1&amp;topic=Auspicious+date&amp;offer=OFF-1">Talk now · free →</a>', body)
		self.assertEqual(self.guide_calls[0], {"persona": "Pandit ji", "online": "1", "topic": "Auspicious date"})  # the kind of guide and what the visitor is troubled by go to the listing

	def test_with_none_live_the_button_opens_the_list_of_those_who_can_be_booked_and_with_none_at_all_there_is_no_button(self):
		frappe.db.set_single_value(SETTINGS, {"panchang_muhurat_persona": "Pandit ji", "panchang_muhurat_topic": "Auspicious date"})
		for live, listed, expected in (([], [self.BOOK], "list"), ([self.BOOK], [self.BOOK], "list"), ([], [], None), ([self.BOOK], [], None)):  # (a live guide with nothing to start at once is not one to connect to)
			self.forget_kept()
			with self.guides(live=live, listed=listed):
				body = self.page(date="2026-10-24")["body_html"]
			self.assertEqual("rv-cta" in body, expected is not None, (live, listed))
			if expected:
				self.assertIn('href="/consult?persona=Pandit+ji&amp;topic=Auspicious+date"', body)
				self.assertIn("ask a Pandit ji for a muhurat made for you", body)
				self.assertNotIn("is live now", body)

	def test_what_the_listing_said_is_kept_a_few_seconds_so_that_a_page_does_not_ask_for_every_visitor_again(self):
		frappe.db.set_single_value(SETTINGS, {"panchang_muhurat_persona": "Pandit ji"})
		self.forget_kept()
		with self.guides(live=[self.TALK]):
			panchang.muhurat_offer()
			panchang.muhurat_offer()
		self.assertEqual(len(self.guide_calls), 1)

	def test_the_endpoints_may_be_asked_by_a_visitor_who_is_not_signed_in(self):
		for method in (panchang.page, panchang.places_found, panchang.place_near, panchang.widget_cards):
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


class TestTheCardOverTheBanner(Stood):
	"""What the pop-over section draws is a list of library cards, each with only its own fields; AstroHQ writes no markup (see panchang_widget.py)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		components.sync()

	def items(self, **args):
		return panchang.widget_cards(**args)["items"]

	def page(self, **args):
		(item,) = panchang.page(**args)["items"]
		return item

	def card(self, name, label=None, **args):
		found = [i for i in self.items(**args) if i["card"] == name and (label is None or i.get("label") == label)]
		self.assertEqual(len(found), 1, (name, label, [i["card"] for i in self.items(**args)]))
		return found[0]

	def at(self, text):
		self.now = datetime.datetime.fromisoformat(text).replace(tzinfo=KOLKATA)

	def test_the_first_card_is_a_pill_with_the_moon_the_tithi_and_the_chaugharia_running_now(self):
		first = self.items()[0]
		self.assertEqual(first, {"card": "Pill Card", "icon": "🌔", "title": "Shukla Trayodashi", "body": "Chaugharia: Shubh · good", "tone": "success"})  # 94% lit and waxing; 7:54 to 9:18 is Shubh
		self.at("2026-10-24T10:00")
		self.assertEqual(self.items()[0]["body"], "Chaugharia: Rog · avoid")
		self.assertEqual(self.items()[0]["tone"], "danger")

	def test_when_the_tithi_has_ended_the_next_one_is_the_one_running_and_what_follows_it_is_named(self):
		self.at("2026-10-24T15:00")  # Trayodashi ended at 1:38 pm
		head = self.card("Feature Card")
		self.assertEqual(head["title"], "Shukla Chaturdashi")
		self.assertEqual(head["body"], "till 11:57 am next day · then Purnima")
		self.assertEqual(self.items()[0]["title"], "Shukla Chaturdashi")
		self.at("2026-10-24T08:00")
		head = self.card("Feature Card")
		self.assertEqual((head["title"], head["body"], head["layout"]), ("Shukla Trayodashi", "till 1:38 pm · then Shukla Chaturdashi", "Icon Left"))
		self.assertEqual(head["tag"], "Today · Saturday 24 Oct · Delhi, India")
		self.assertEqual(head["icon"], "🌔")

	def test_at_the_very_moment_a_tithi_changes_the_new_one_is_running(self):
		self.now = datetime.datetime(2026, 10, 24, 13, 38, 1, tzinfo=KOLKATA)  # Trayodashi ends and Chaturdashi begins at 13:38:01
		self.assertEqual(self.items()[0]["title"], "Shukla Chaturdashi")
		self.now = datetime.datetime(2026, 10, 24, 13, 38, 0, tzinfo=KOLKATA)
		self.assertEqual(self.items()[0]["title"], "Shukla Trayodashi")

	def test_before_sunrise_the_sun_and_the_times_are_those_of_the_calendar_day_while_the_night_of_the_day_before_runs(self):
		self.at("2026-10-25T05:00")  # the day that holds this moment is the 24th; the calendar day is the 25th (the sun rises at 6:32 there)
		self.assertTrue(self.card("Stat Card", "Sun")["value"].startswith("↑ 6:32 am"), self.card("Stat Card", "Sun")["value"])
		self.assertEqual(self.card("Stat Card", "Rahu Kaal")["description"].split(" in ")[0], "starts")  # still to come today
		self.assertEqual(self.card("Parts Bar")["start_label"], "Sunset 5:38 pm the day before")

	def test_the_nakshatra_the_yoga_and_the_karana_are_the_ones_running_now(self):
		self.assertEqual(self.card("Stat Card", "Nakshatra")["value"], "Uttara Bhadrapada")
		self.assertEqual(self.card("Stat Card", "Nakshatra")["description"], "till 8:32 pm")
		self.assertEqual((self.card("Fact Card", "Yoga")["value"], self.card("Fact Card", "Yoga")["description"]), ("Vyaghata", "till 8:00 pm"))
		self.assertEqual(self.card("Fact Card", "Karana")["value"], "Taitila")
		self.at("2026-10-24T21:00")  # the next ones have begun
		self.assertEqual(self.card("Stat Card", "Nakshatra")["value"], "Revati")
		self.assertEqual(self.card("Fact Card", "Yoga")["value"], "Harshana")
		self.assertEqual(self.card("Fact Card", "Karana")["value"], "Gara")

	def test_a_karana_the_answers_do_not_list_is_left_out_not_guessed(self):
		held, after = self.days["delhi:2026-10-24"], self.days["delhi:2026-10-25"]
		held["karana"] = {"number": 1, "name": "Bava", "begins": "2026-10-24T05:00:00+05:30", "ends": "2026-10-24T07:00:00+05:30", "next": {"number": 2, "name": "Balava", "begins": "2026-10-24T07:00:00+05:30", "ends": "2026-10-24T17:00:00+05:30"}}
		after["karana"] = {"number": 4, "name": "Vanija", "begins": "2026-10-24T23:00:00+05:30", "ends": "2026-10-25T10:00:00+05:30", "next": {"number": 5, "name": "Vishti", "begins": "2026-10-25T10:00:00+05:30", "ends": "2026-10-25T21:00:00+05:30"}}
		self.at("2026-10-24T20:00")  # Kaulava would be running: neither answer says so
		self.assertEqual([i for i in self.items() if i.get("label") == "Karana"], [])
		self.assertEqual(self.card("Fact Card", "Yoga")["value"], "Vyaghata")  # the rest is not touched
		self.at("2026-10-24T12:00")
		self.assertEqual(self.card("Fact Card", "Karana")["value"], "Balava")

	def test_the_chaugharia_is_a_bar_of_the_eight_parts_with_the_tone_of_each_and_the_one_running_marked(self):
		bar = self.card("Parts Bar")
		self.assertEqual(bar["steps"].split("\n"), ["Kaal", "Shubh", "Rog", "Udveg", "Chal", "Labh", "Amrit", "Kaal"])
		self.assertEqual(bar["tones"].split("\n"), ["danger", "success", "danger", "danger", "success", "success", "success", "danger"])
		self.assertEqual(bar["current"], 2)
		self.assertEqual((bar["heading"], bar["heading_note"], bar["heading_tone"]), ("Chaugharia", "Shubh · good · till 9:18 am", "success"))
		self.assertEqual((bar["start_label"], bar["end_label"]), ("Sunrise 6:31 am", "Sunset 5:38 pm"))
		self.assertEqual(bar["note"], "Good for 1 h 18 min more · then Rog avoid")

	def test_an_avoid_part_says_which_good_one_comes_next_and_in_how_long(self):
		self.at("2026-10-24T10:00")
		bar = self.card("Parts Bar")
		self.assertEqual((bar["current"], bar["heading_tone"], bar["heading_note"]), (3, "danger", "Rog · avoid · till 10:41 am"))
		self.assertEqual(bar["note"], "Next good: Chal 12:05–1:28 pm · in 2 h 5 min")

	def test_at_night_it_is_the_night_with_the_sunset_and_the_next_sunrise_named_and_after_midnight_the_night_of_the_day_before(self):
		self.at("2026-10-24T22:00")
		bar = self.card("Parts Bar")
		self.assertEqual(bar["steps"].split("\n")[:3], ["Labh", "Udveg", "Shubh"])
		self.assertEqual((bar["start_label"], bar["end_label"]), ("Sunset 5:38 pm", "Sunrise 6:32 am next day"))
		self.assertEqual(bar["current"], 3)  # 8:52 to 10:28 pm is the third
		self.at("2026-10-25T00:30")
		bar = self.card("Parts Bar")
		self.assertEqual((bar["start_label"], bar["end_label"]), ("Sunset 5:38 pm the day before", "Sunrise 6:32 am"))
		self.assertEqual(self.card("Feature Card")["tag"], "Today · Sunday 25 Oct · Delhi, India")

	def test_the_last_part_of_the_night_is_followed_by_the_first_of_the_day_after(self):
		self.at("2026-10-25T06:00")
		bar = self.card("Parts Bar")
		first_of_the_day = self.days["delhi:2026-10-25"]["chaugharia"]["day"][0]
		self.assertEqual(bar["current"], 8)
		self.assertTrue(bar["note"].endswith(f"then {first_of_the_day['name']} {'good' if first_of_the_day['quality'] == 'good' else 'avoid'}"), bar["note"])

	def test_rahu_kaal_and_abhijit_say_when_they_start_are_on_or_are_over(self):
		def tiles():
			return {i["label"]: i for i in self.items() if i["card"] == "Stat Card" and i["label"] in ("Rahu Kaal", "Abhijit")}
		got = tiles()
		self.assertEqual((got["Rahu Kaal"]["value"], got["Rahu Kaal"]["description"], got["Rahu Kaal"]["tone"]), ("9:18–10:41 am", "starts in 1 h 18 min", "danger"))
		self.assertEqual((got["Abhijit"]["value"], got["Abhijit"]["description"], got["Abhijit"]["tone"]), ("11:42 am–12:27 pm", "the day's best time", "success"))
		self.at("2026-10-24T10:00")
		self.assertEqual(tiles()["Rahu Kaal"]["description"], "on now · till 10:41 am")
		self.at("2026-10-24T11:50")
		self.assertEqual(tiles()["Abhijit"]["description"], "on now · till 12:27 pm")
		self.at("2026-10-24T15:00")
		self.assertEqual((tiles()["Rahu Kaal"]["description"], tiles()["Rahu Kaal"]["tone"]), ("over for today", ""))
		self.assertEqual((tiles()["Abhijit"]["description"], tiles()["Abhijit"]["tone"]), ("over for today", ""))

	def test_the_sun_tile_says_when_the_sun_rises_and_sets_and_when_the_moon_rises(self):
		sun = self.card("Stat Card", "Sun")
		self.assertEqual((sun["value"], sun["description"]), ("↑ 6:31 am · ↓ 5:38 pm", "Moonrise 4:33 pm"))

	def test_the_muhurat_card_says_a_pandit_ji_is_live_and_connects_or_opens_the_list_and_is_not_there_without_either(self):
		self.assertEqual([i for i in self.items() if i["card"] == "Focus Card"], [])  # no kind of guide in the settings
		frappe.db.set_single_value(SETTINGS, {"panchang_muhurat_persona": "Pandit ji", "panchang_muhurat_topic": "Auspicious date"})
		self.forget_kept()
		with self.guides(live=[self.TALK], listed=[self.BOOK]):
			live = self.items()[-1]
		self.assertEqual(live, {"card": "Focus Card", "tag": "A Pandit ji is live now", "title": "Talk to one about a muhurat", "body": "A wedding, a new home, a vehicle, a new business",
								"link_url": "/consult/online/start?offering=SVC-1&topic=Auspicious+date&offer=OFF-1", "link_label": "Talk now · free"})
		self.forget_kept()
		with self.guides(live=[], listed=[self.BOOK]):
			listed = self.items()[-1]
		self.assertEqual(listed, {"card": "Focus Card", "tag": "Important work?", "title": "Ask a Pandit ji for a muhurat", "body": "A wedding, a new home, a vehicle, a new business",
								  "link_url": "/consult?persona=Pandit+ji&topic=Auspicious+date", "link_label": "Ask for a muhurat"})
		self.forget_kept()
		with self.guides(live=[], listed=[]):
			self.assertEqual([i for i in self.items() if i["card"] == "Focus Card"], [])

	def test_every_item_names_a_card_of_the_library_and_only_fields_that_card_has(self):
		frappe.db.set_single_value(SETTINGS, {"panchang_muhurat_persona": "Pandit ji"})
		self.forget_kept()
		with self.guides(live=[self.TALK]):
			items = self.items()
		self.assertEqual({i["card"] for i in items}, {"Pill Card", "Feature Card", "Parts Bar", "Stat Card", "Fact Card", "Focus Card"})
		for item in items:
			template = frappe.db.get_value("RFHQ Component", item["card"], "web_template")
			self.assertTrue(template, item["card"])
			fields = {f.fieldname for f in frappe.get_cached_doc("Web Template", template).fields}
			self.assertFalse(set(item) - fields - {"card"}, (item["card"], set(item) - fields))

	def test_the_card_comes_with_the_control_for_its_town_and_it_is_the_one_of_the_page(self):
		answer = panchang.widget_cards()
		(control,) = answer["toolbar"]["controls"]
		self.assertEqual((control["type"], control["arg"], control["value"], control["label"]), ("lookup", "place", "19", "Delhi, India"))
		self.assertEqual((control["search"], control["near"]), ("raftor_astrohq.panchang.places_found", "raftor_astrohq.panchang.place_near"))
		page_town = self.page(date="2026-10-24")["toolbar"]["controls"][1]
		self.assertEqual(control, page_town)  # one control, drawn by the same script on both
		self.assertEqual(panchang.widget_cards(place="9999")["toolbar"]["controls"][0]["label"], "Delhi, India")  # a town that is not in the list gives the default one
		self.at("2026-11-08T08:00")
		self.assertEqual(panchang.widget_cards(place="22")["toolbar"]["controls"][0]["label"], "Mumbai, India")
		self.assertIn("raftor_astrohq.panchang.widget_cards", frappe.get_hooks("rfhq_trusted_html_sources", app_name="raftor_astrohq"))  # only a trusted source's control reaches the page

	def test_what_comes_out_is_text_and_nothing_else(self):
		for item in self.items():
			for key, value in item.items():
				self.assertIsInstance(value, str | int, (item["card"], key))
				if isinstance(value, str):
					self.assertNotIn("<", value, (item["card"], key))

	def test_the_town_the_visitor_kept_is_the_one_asked_for_and_said(self):
		self.assertTrue(self.items(place="9999")[1]["tag"].endswith("· Delhi, India"))  # (a town that is not in the list: the default one)
		self.at("2026-11-08T08:00")
		mumbai = self.items(place="22")
		self.assertTrue(mumbai[1]["tag"].endswith("· Mumbai, India"), mumbai[1]["tag"])
		self.assertTrue(self.asked[-1][1]["latitude"] < 25)

	def test_nothing_when_the_panchang_is_off_or_the_engine_cannot_be_asked(self):
		self.engine_error = astrology.AstrologyUnavailable("down")
		self.assertEqual(panchang.widget_cards(), {"items": []})
		self.engine_error = astrology.AstrologyRefused("no")
		self.assertEqual(panchang.widget_cards(), {"items": []})
		self.engine_error = None
		self.switch_on("")
		self.assertEqual(panchang.widget_cards(), {"items": []})


class TestTheMoonMark(TestCase):
	def test_the_moon_is_one_of_the_eight_phases_as_it_is_lit_and_seen_from_india(self):
		mark = panchang_widget.moon_mark
		self.assertEqual([mark(0.0, True), mark(0.02, False)], ["🌑", "🌑"])
		self.assertEqual([mark(0.1, True), mark(0.5, True), mark(0.8, True), mark(0.97, True), mark(1.0, False)], ["🌒", "🌓", "🌔", "🌕", "🌕"])
		self.assertEqual([mark(0.8, False), mark(0.5, False), mark(0.1, False)], ["🌖", "🌗", "🌘"])
		self.assertEqual([mark(0.03, True), mark(0.35, True), mark(0.65, True)], ["🌒", "🌓", "🌔"])  # the edges belong to the phase that begins there
		self.assertEqual([mark(-1, True), mark(7, True)], ["🌑", "🌕"])


class TestWhatTheSettingsDecide(Stood):
	"""Nothing here is fixed in the code: the years, how long a day is kept, and whether Chal is good or neutral are in Astrology API Settings (the defaults are what they always were)."""

	def test_the_defaults_are_what_they_always_were(self):
		got = panchang.settings()
		self.assertEqual((got.chal, got.first_year, got.last_year, got.keep_default, got.keep_other), ("good", 1800, 2399, 8 * 24 * 3600, 24 * 3600))
		self.assertEqual((got.persona, got.topic), ("", "Auspicious date"))  # (no kind of guide named = no muhurat button; the topic is the setting's own default until another is saved)

	def test_the_years_are_the_settings_and_the_bar_and_the_clamp_follow_them(self):
		self.switch_on("Delhi", panchang_first_year=2020, panchang_last_year=2030)
		delhi = self.delhi()
		self.assertEqual(panchang.date_of("1999-05-05", delhi), datetime.date(2020, 1, 1))
		self.assertEqual(panchang.date_of("2500-01-01", delhi), datetime.date(2030, 12, 31))
		date = self.page(date="2026-10-24")["toolbar"]["controls"][0]
		self.assertEqual((date["min"], date["max"]), ("2020-01-01", "2030-12-31"))
		with mock.patch.object(panchang, "day", lambda on, place: {"date": on.isoformat()}):
			self.assertEqual([d["date"] for d in panchang.week(datetime.date(2030, 12, 29), delhi)], ["2030-12-29", "2030-12-30", "2030-12-31"])  # the days that are left of the last year

	def page(self, **args):
		(item,) = panchang.page(**args)["items"]
		return item

	def test_how_long_a_day_is_kept_is_the_settings(self):
		self.switch_on("Delhi", panchang_keep_days=3, panchang_keep_other_days=2)
		with mock.patch.object(frappe.cache(), "set_value", wraps=frappe.cache().set_value) as kept:
			panchang.day(datetime.date(2026, 10, 24), self.delhi())
			panchang.day(datetime.date(2026, 11, 8), places.lookup("Mumbai", datetime.date(2026, 11, 8)))
		self.assertEqual([call.kwargs["expires_in_sec"] for call in kept.call_args_list if str(call.args[0]).startswith("astro_panchang:")], [3 * 24 * 3600, 2 * 24 * 3600])

	def test_the_chal_the_settings_name_is_asked_of_the_engine_and_a_day_is_asked_again_when_it_changes(self):
		panchang.day(datetime.date(2026, 10, 24), self.delhi())
		self.assertEqual(self.asked[-1][1]["chal"], "good")
		self.switch_on("Delhi", panchang_chal="neutral")
		panchang.day(datetime.date(2026, 10, 24), self.delhi())
		self.assertEqual((len(self.asked), self.asked[-1][1]["chal"]), (2, "neutral"))  # not the day kept for the other choice
		panchang.day(datetime.date(2026, 10, 24), self.delhi())
		self.assertEqual(len(self.asked), 2)

	def test_the_rule_of_rising_the_settings_name_is_asked_of_the_engine_and_a_day_is_asked_again_when_it_changes(self):
		self.assertEqual(panchang.settings().rise, "apparent")
		panchang.day(datetime.date(2026, 10, 24), self.delhi())
		self.assertEqual(self.asked[-1][1]["rise"], "apparent")
		self.switch_on("Delhi", panchang_sunrise="centre")
		panchang.day(datetime.date(2026, 10, 24), self.delhi())
		self.assertEqual((len(self.asked), self.asked[-1][1]["rise"]), (2, "centre"))

	def neutral_days(self):
		for answer in (a for a in self.days.values() if isinstance(a, dict)):
			for which in ("day", "night"):
				for part in answer["chaugharia"][which]:
					if part["name"] == "Chal":
						part["quality"] = "neutral"

	def test_a_neutral_chal_is_said_on_the_page_in_its_own_colour_and_in_the_legend(self):
		self.neutral_days()
		body = self.page(date="2026-10-24")["body_html"]
		self.assertRegex(body, r'<tr class="rv-neutral"><th scope="row">Chal</th><td>neutral</td>')
		self.assertIn("Good: Amrit, Labh, Shubh. Neutral: Chal. Avoid: Kaal, Rog, Udveg.", body)
		self.assertNotIn("Chal</th><td>good", body)

	def test_a_neutral_chal_is_a_warning_tone_on_the_card_and_is_not_a_good_part_to_wait_for(self):
		self.neutral_days()
		self.at("2026-10-24T12:30")  # 12:05 to 1:28 pm is Chal
		pill = self.items()[0]
		self.assertEqual((pill["body"], pill["tone"]), ("Chaugharia: Chal · neutral", "warning"))
		bar = self.card("Parts Bar")
		self.assertEqual((bar["heading_tone"], bar["heading_note"]), ("warning", "Chal · neutral · till 1:28 pm"))
		self.assertEqual(bar["tones"].split("\n")[4], "warning")
		self.assertTrue(bar["note"].startswith("Next good: Labh"), bar["note"])  # a neutral part is not one to wait for

	def at(self, text):
		self.now = datetime.datetime.fromisoformat(text).replace(tzinfo=KOLKATA)

	def items(self):
		return panchang.widget_cards()["items"]

	def card(self, name):
		return next(i for i in self.items() if i["card"] == name)
