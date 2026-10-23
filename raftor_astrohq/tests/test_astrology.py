"""AstroHQ's way to the astrology API, with the hub replaced by a stand-in that answers as the real hub does (the answer shapes were recorded
from the hub's own gateway on 2026-10-23: usage, a good call, a refused call (417), a wrong key (401), an unknown API (404)).

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_astrology
"""
import json
import re
from pathlib import Path
from unittest import mock

import frappe
import requests

from raftor_astrohq import astrology
from raftor_astrohq.tests.helpers import AstroTestCase, make_user

ADDRESS = "https://hub.example.test"
KEY = "key-for-the-tests-only"
PANCHANGA = {"status": "success", "opcode": "PANCHANGA", "processing_time": 0.43, "data": {"panchanga": {"tithi": "Krishna Paksha Dhasami", "vaara": "Sunday"}}}
CHART = {"status": "success", "opcode": "CORE_BASIC", "processing_time": 0.3, "data": {"lagna": {"sign": "Virgo"}}}
BORN = {"year": 1980, "month": 6, "day": 8, "hour": 13, "minute": 49, "second": 0, "latitude": 28.6139, "longitude": 77.209, "timezone_offset": 5.5}
PROFILE = {"relationship": "You", "full_name": "Asha Rao", "date_of_birth": "1990-08-14", "time_of_birth": "06:42", "time_unknown": 0, "place_of_birth": "Pune, India"}


class Reply:
	"""What requests gives back."""

	def __init__(self, status=200, body=None):
		self.status_code, self._body = status, body

	def json(self):
		if self._body is None:
			raise ValueError("this is not JSON")
		return self._body


def good(envelope=CHART):
	return Reply(200, {"success": True, "data": envelope, "request_id": "9f2c"})


def refusal(status, message, exc_type="ValidationError"):
	messages = json.dumps([json.dumps({"message": message, "title": "Message", "indicator": "red", "raise_exception": 1})])
	return Reply(status, {"exc_type": exc_type, "_server_messages": messages})


USAGE = Reply(200, {"subscription": "ACC-SUB-2026-00011", "plan": "Internal", "status": "Active", "calls_used": 0, "calls_limit": 0, "calls_remaining": 0})


def configure(**changes):
	"""Saves the settings (so the page's own rules run). Rolled back with the test."""
	values = {"enabled": 1, "how": astrology.HUB, "hub_address": ADDRESS, "api_key": KEY, "api_name": "astrology", "timeout_seconds": 20}
	values.update(changes)
	doc = frappe.get_single(astrology.SETTINGS)
	doc.update(values)
	doc.save(ignore_permissions=True)
	return doc


def asking(*replies):
	"""Replaces the web with these replies, one for each request."""
	return mock.patch.object(astrology.requests, "request", side_effect=list(replies))


class TestSettingsPage(AstroTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.delete("Singles", {"doctype": astrology.SETTINGS})  # a page never saved, whatever this site holds (the test is rolled back)
		frappe.db.delete("__Auth", {"doctype": astrology.SETTINGS})
		frappe.clear_document_cache(astrology.SETTINGS, astrology.SETTINGS)

	def test_a_page_never_saved_is_off_and_has_its_defaults(self):
		s = astrology.settings()
		self.assertFalse(s.enabled)
		self.assertEqual((s.api_name, s.timeout, s.address, s.api_key, s.how), ("astrology", 20, "", "", astrology.HUB))
		self.assertFalse(astrology.available())

	def test_available_needs_the_switch_the_address_the_key_and_the_name(self):
		configure()
		self.assertTrue(astrology.available())
		configure(enabled=0)
		self.assertFalse(astrology.available())

	def test_the_key_is_kept_encrypted_and_not_shown_on_the_page(self):
		configure()
		self.assertNotEqual(frappe.get_doc(astrology.SETTINGS).api_key, KEY)
		self.assertNotIn(KEY, json.dumps(frappe.get_doc(astrology.SETTINGS).as_dict(), default=str))
		self.assertEqual(astrology.settings().api_key, KEY)

	def test_switching_on_asks_for_what_is_missing(self):
		for missing, words in (("hub_address", "address"), ("api_key", "key"), ("api_name", "name")):
			with self.subTest(missing):
				with self.assertRaises(frappe.ValidationError) as caught:
					configure(**{missing: ""})
				self.assertIn(words, str(caught.exception))

	def test_it_may_be_saved_half_filled_while_off(self):
		configure(enabled=0, api_key="", hub_address="")

	def test_wait_time_is_between_5_and_60_seconds(self):
		for seconds in (0, 4, 61, 600):
			with self.subTest(seconds):
				with self.assertRaises(frappe.ValidationError):
					configure(timeout_seconds=seconds)
		configure(timeout_seconds=5)
		configure(timeout_seconds=60)

	def test_the_hub_address_rules(self):
		clean = astrology.clean_address
		self.assertEqual(clean(" https://hub.example.test/ "), "https://hub.example.test")
		self.assertEqual(clean("https://hub.example.test:8443"), "https://hub.example.test:8443")
		self.assertEqual(clean("http://127.0.0.1:8800"), "http://127.0.0.1:8800")
		self.assertEqual(clean("http://localhost:8800/"), "http://localhost:8800")
		self.assertEqual(clean(""), "")
		for bad in ("http://hub.example.test", "ftp://hub.example.test", "hub.example.test", "https://", "https://user:pw@hub.example.test",
					"https://hub.example.test/api", "https://hub.example.test?x=1", "https://hub.example.test#top"):
			with self.subTest(bad):
				with self.assertRaises(frappe.ValidationError):
					clean(bad)

	def test_the_saved_address_is_tidied(self):
		configure(hub_address=" https://hub.example.test/ ")
		self.assertEqual(astrology.settings().address, "https://hub.example.test")


class TestAsking(AstroTestCase):
	def setUp(self):
		super().setUp()
		configure()

	def test_the_request_carries_the_key_and_only_the_numbers_of_the_calculation(self):
		with asking(good()) as web:
			astrology.chart({**BORN, "full_name": "Asha Rao", "place_of_birth": "Delhi", "email": "asha@example.com", "gender": "Female"}, "CORE_BASIC")
		(method, url), kwargs = web.call_args.args, web.call_args.kwargs
		self.assertEqual((method, url), ("POST", ADDRESS + "/api/method/raftor_apimanager.gateway.call"))
		self.assertEqual(kwargs["headers"], {"X-Api-Key": KEY})
		self.assertEqual(kwargs["timeout"], 20)
		self.assertEqual(kwargs["json"], {"api_name": "astrology", "payload": {"opcode": "CORE_BASIC", "birth_data": {**BORN, "gender": "Female"}}})
		self.assertNotIn("Asha", json.dumps(kwargs["json"]))

	def test_the_engines_answer_is_what_comes_back(self):
		with asking(good(CHART)):
			self.assertEqual(astrology.chart(BORN, "CORE_BASIC"), {"lagna": {"sign": "Virgo"}})

	def test_matching_sends_the_partner_too(self):
		partner = {**BORN, "year": 1983, "gender": "Female"}
		with asking(good({"status": "success", "opcode": "MATCH_CALC", "data": {"compatibility": {"total_score": 21}}})) as web:
			out = astrology.chart(BORN, "MATCH_CALC", partner=partner)
		self.assertEqual(out["compatibility"]["total_score"], 21)
		self.assertEqual(web.call_args.kwargs["json"]["payload"]["birth_data_2"]["year"], 1983)

	def test_the_operation_defaults_to_the_short_chart(self):
		with asking(good()) as web:
			astrology.chart(BORN)
		self.assertEqual(web.call_args.kwargs["json"]["payload"]["opcode"], "SUPER_BASIC")

	def test_an_answer_that_comes_wrapped_is_still_read(self):
		with asking(Reply(200, {"message": {"success": True, "data": CHART}})):
			self.assertEqual(astrology.chart(BORN), {"lagna": {"sign": "Virgo"}})

	def test_an_answer_without_the_usual_envelope_is_passed_on_as_it_is(self):
		with asking(Reply(200, {"success": True, "data": {"lagna": {"sign": "Virgo"}}})):
			self.assertEqual(astrology.chart(BORN), {"lagna": {"sign": "Virgo"}})

	def test_an_engine_error_inside_a_good_answer_is_not_handed_over_as_a_chart(self):
		with asking(good({"status": "success", "opcode": "MATCH_CALC", "data": {"error": "Unable to compute compatibility: missing nakshatra data"}})):
			with self.assertRaises(astrology.AstrologyUnavailable) as caught:
				astrology.chart(BORN, "MATCH_CALC", partner=BORN)
		self.assertIn("missing nakshatra", str(caught.exception))

	def test_a_refusal_comes_back_as_a_refusal_with_the_reasons_own_words(self):
		for status in (400, 417, 422):
			with self.subTest(status):
				with asking(refusal(status, "birth_data.month must be in [1, 12], got 13")):
					with self.assertRaises(astrology.AstrologyRefused) as caught:
						astrology.chart({**BORN, "month": 13})
				self.assertIn("month must be in [1, 12]", str(caught.exception))

	def test_html_in_a_reason_is_removed(self):
		with asking(refusal(417, "<div class='ql-editor'><p>Unknown opcode &#x27;NOPE&#x27;</p></div>")):
			with self.assertRaises(astrology.AstrologyRefused) as caught:
				astrology.chart(BORN, "NOPE")
		self.assertNotIn("<", str(caught.exception))
		self.assertIn("Unknown opcode", str(caught.exception))

	def test_a_refusal_without_a_reason_still_says_something(self):
		with asking(Reply(417, {})):
			with self.assertRaises(astrology.AstrologyRefused) as caught:
				astrology.chart(BORN)
		self.assertTrue(str(caught.exception))

	def test_each_way_the_hub_can_say_no_has_its_own_plain_sentence(self):
		cases = {
			401: ("AuthenticationError", "API key"),
			403: ("PermissionError", "plan"),
			404: ("DoesNotExistError", "no astrology API"),
			429: ("QuotaExceeded", "used up"),
			500: ("ValidationError", "not working"),
			502: ("ValidationError", "not working"),
			503: ("ValidationError", "not working"),
		}
		for status, (exc_type, words) in cases.items():
			with self.subTest(status):
				with asking(refusal(status, "hub's own words", exc_type)):
					with self.assertRaises(astrology.AstrologyUnavailable) as caught:
						astrology.chart(BORN)
				text = str(caught.exception)
				self.assertIn(words, text)
				self.assertNotIn(KEY, text)
				self.assertNotIn("example.test", text)

	def test_the_web_failing_is_unavailable_not_a_crash(self):
		for failure in (requests.exceptions.ConnectionError("no route"), requests.exceptions.Timeout("slow"), requests.exceptions.SSLError("bad certificate")):
			with self.subTest(type(failure).__name__):
				with mock.patch.object(astrology.requests, "request", side_effect=failure):
					with self.assertRaises(astrology.AstrologyUnavailable) as caught:
						astrology.chart(BORN)
				self.assertNotIn("example.test", str(caught.exception))

	def test_an_answer_that_is_not_json_or_not_a_chart_is_unavailable(self):
		for reply in (Reply(200, None), Reply(200, {"success": True, "data": "text"}), Reply(200, {"success": False}), Reply(200, [1, 2])):
			with self.subTest(str(reply._body)):
				with asking(reply):
					with self.assertRaises(astrology.AstrologyUnavailable):
						astrology.chart(BORN)

	def test_switched_off_it_asks_nothing(self):
		configure(enabled=0)
		with asking() as web:
			with self.assertRaises(astrology.AstrologyUnavailable) as caught:
				astrology.chart(BORN)
		web.assert_not_called()
		self.assertIn("Astrology API Settings", str(caught.exception))

	def test_a_caller_who_passes_something_else_than_numbers_is_told(self):
		with asking() as web:
			with self.assertRaises(astrology.AstrologyRefused):
				astrology.chart("not a dict")
		web.assert_not_called()

	def test_both_kinds_of_trouble_are_frappe_validation_errors_so_a_web_caller_gets_a_message(self):
		self.assertTrue(issubclass(astrology.AstrologyUnavailable, frappe.ValidationError))
		self.assertTrue(issubclass(astrology.AstrologyRefused, frappe.ValidationError))
		self.assertEqual(astrology.AstrologyUnavailable.http_status_code, 503)


class TestBirthData(AstroTestCase):
	def test_numbers_from_a_profile_and_the_place(self):
		self.assertEqual(
			astrology.birth_data(PROFILE, 18.5204, 73.8567, 5.5),
			{"year": 1990, "month": 8, "day": 14, "hour": 6, "minute": 42, "second": 0, "latitude": 18.5204, "longitude": 73.8567, "timezone_offset": 5.5},
		)

	def test_seconds_gender_and_numbers_given_as_text(self):
		out = astrology.birth_data({**PROFILE, "time_of_birth": "06:42:30"}, "18.5204", "73.8567", "5.5", gender="Female")
		self.assertEqual((out["second"], out["gender"], out["latitude"]), (30, "Female", 18.5204))

	def test_a_real_birth_profile_row_works_too(self):
		row = frappe.get_doc({"doctype": "Astro Birth Profile", **PROFILE})
		self.assertEqual(astrology.birth_data(row, 18.5204, 73.8567, 5.5)["hour"], 6)

	def test_no_name_or_place_name_travels_with_the_numbers(self):
		out = astrology.birth_data(PROFILE, 18.5204, 73.8567, 5.5)
		self.assertNotIn("Asha", json.dumps(out))
		self.assertNotIn("Pune", json.dumps(out))

	def test_an_unknown_birth_time_is_refused_in_words(self):
		for profile in ({**PROFILE, "time_unknown": 1, "time_of_birth": ""}, {**PROFILE, "time_of_birth": ""}, {**PROFILE, "time_of_birth": "  "}):
			with self.subTest(str(profile["time_of_birth"])):
				with self.assertRaises(astrology.AstrologyRefused) as caught:
					astrology.birth_data(profile, 18.5, 73.8, 5.5)
				self.assertIn("time of birth", str(caught.exception))

	def test_a_time_that_is_not_a_time_is_refused(self):
		for time in ("25:00", "06:61", "6.42", "noon", "06:42:75"):
			with self.subTest(time):
				with self.assertRaises(astrology.AstrologyRefused):
					astrology.birth_data({**PROFILE, "time_of_birth": time}, 18.5, 73.8, 5.5)

	def test_a_missing_or_wrong_date_is_refused(self):
		for date in ("", None, "not a date"):
			with self.subTest(str(date)):
				with self.assertRaises(astrology.AstrologyRefused):
					astrology.birth_data({**PROFILE, "date_of_birth": date}, 18.5, 73.8, 5.5)

	def test_unusable_coordinates_are_refused_naming_which(self):
		for args, word in (((None, 73.8, 5.5), "latitude"), ((18.5, "x", 5.5), "longitude"), ((18.5, 73.8, None), "time zone"),
						   ((91, 73.8, 5.5), "latitude"), ((18.5, 181, 5.5), "longitude"), ((18.5, 73.8, 15), "time zone")):
			with self.subTest(args):
				with self.assertRaises(astrology.AstrologyRefused) as caught:
					astrology.birth_data(PROFILE, *args)
				self.assertIn(word, str(caught.exception))


class TestCheckingTheConnection(AstroTestCase):
	def test_not_set_up_it_says_so_and_asks_nothing(self):
		frappe.db.delete("Singles", {"doctype": astrology.SETTINGS})
		frappe.db.delete("__Auth", {"doctype": astrology.SETTINGS})
		frappe.clear_document_cache(astrology.SETTINGS, astrology.SETTINGS)
		with asking() as web:
			result = astrology.check_connection()
		web.assert_not_called()
		self.assertFalse(result["ok"])
		self.assertIn("Fill in", result["message"])

	def test_a_good_hub_is_connected_and_names_the_plan(self):
		configure()
		with asking(USAGE, good(PANCHANGA)) as web:
			result = astrology.check_connection()
		self.assertTrue(result["ok"], result)
		self.assertIn("Internal", result["message"])
		(first, second) = web.call_args_list
		self.assertEqual(first.args, ("GET", ADDRESS + "/api/method/raftor_apimanager.gateway.usage"))
		self.assertEqual(second.args[0:2], ("POST", ADDRESS + "/api/method/raftor_apimanager.gateway.call"))
		self.assertEqual(second.kwargs["json"]["payload"]["opcode"], "PANCHANGA")
		self.assertNotIn("name", json.dumps(second.kwargs["json"]["payload"]["birth_data"]))

	def test_it_can_be_tried_before_it_is_switched_on(self):
		configure(enabled=0)
		with asking(USAGE, good(PANCHANGA)):
			self.assertTrue(astrology.check_connection()["ok"])

	def test_a_refused_key_stops_at_the_first_question(self):
		configure()
		with asking(refusal(401, "Invalid or inactive API key", "AuthenticationError")) as web:
			result = astrology.check_connection()
		self.assertFalse(result["ok"])
		self.assertIn("API key", result["message"])
		self.assertEqual(web.call_count, 1)

	def test_a_good_key_but_an_engine_that_does_not_answer(self):
		configure()
		with asking(USAGE, refusal(500, "x")):
			result = astrology.check_connection()
		self.assertFalse(result["ok"])
		self.assertIn("not working", result["message"])

	def test_a_good_key_but_an_empty_answer(self):
		configure()
		with asking(USAGE, good({"status": "success", "data": {}})):
			result = astrology.check_connection()
		self.assertFalse(result["ok"])
		self.assertIn("empty", result["message"])

	def test_a_hub_that_cannot_be_reached(self):
		configure()
		with mock.patch.object(astrology.requests, "request", side_effect=requests.exceptions.ConnectionError("no route")):
			result = astrology.check_connection()
		self.assertFalse(result["ok"])
		self.assertIn("did not answer", result["message"])

	def test_a_usage_answer_that_is_not_json(self):
		configure()
		with asking(Reply(200, None)):
			result = astrology.check_connection()
		self.assertFalse(result["ok"])


ENGINE = "http://127.0.0.1:8795"
ENVELOPE_SAMPLE = {"status": "success", "opcode": "PANCHANGA", "processing_time": 0.4, "data": {"panchanga": {"vaara": "Sunday"}}}
ABOUT = Reply(200, {"service": "astrology", "version": "1.1.0", "ready": True, "operations": ["PANCHANGA"], "libraries": {}, "source": None})


def engine_error(status, code, message):
	return Reply(status, {"status": "error", "error": {"code": code, "message": message, "request_id": "abc123"}})


def straight_settings(**changes):
	values = {"how": astrology.STRAIGHT, "hub_address": ENGINE, "api_name": ""}
	values.update(changes)
	return configure(**values)


class TestStraightToTheAstrologyAPI(AstroTestCase):
	"""AstroHQ asks the astrology API itself (the small service on this server, or an AWS Lambda function): its own contract, no hub."""

	def setUp(self):
		super().setUp()
		straight_settings()

	def test_it_can_be_switched_on_without_the_hubs_api_name_but_not_without_an_address_or_key(self):
		self.assertTrue(astrology.available())
		for missing, words in (("hub_address", "address"), ("api_key", "key")):
			with self.subTest(missing):
				with self.assertRaises(frappe.ValidationError) as caught:
					straight_settings(**{missing: ""})
				self.assertIn(words, str(caught.exception))

	def test_the_request_is_the_payload_itself_with_the_key_and_nothing_of_the_hub(self):
		with asking(Reply(200, ENVELOPE_SAMPLE)) as web:
			astrology.chart({**BORN, "full_name": "Asha Rao"}, "PANCHANGA")
		(method, url), kwargs = web.call_args.args, web.call_args.kwargs
		self.assertEqual((method, url), ("POST", ENGINE + "/"))
		self.assertEqual(kwargs["headers"], {"X-Api-Key": KEY})
		self.assertEqual(kwargs["json"], {"opcode": "PANCHANGA", "birth_data": BORN})
		self.assertNotIn("api_name", kwargs["json"])
		self.assertNotIn("Asha", json.dumps(kwargs["json"]))

	def test_the_engines_answer_is_what_comes_back_and_matching_sends_the_partner(self):
		with asking(Reply(200, {"status": "success", "opcode": "MATCH_CALC", "data": {"compatibility": {"total_score": 21}}})) as web:
			out = astrology.chart(BORN, "MATCH_CALC", partner={**BORN, "year": 1983})
		self.assertEqual(out["compatibility"]["total_score"], 21)
		self.assertEqual(web.call_args.kwargs["json"]["birth_data_2"]["year"], 1983)

	def test_an_engine_error_inside_a_good_answer_is_not_handed_over_as_a_chart(self):
		with asking(Reply(200, {"status": "success", "data": {"error": "Unable to compute compatibility: missing nakshatra data"}})):
			with self.assertRaises(astrology.AstrologyUnavailable) as caught:
				astrology.chart(BORN, "MATCH_CALC", partner=BORN)
		self.assertIn("missing nakshatra", str(caught.exception))

	def test_a_good_status_without_an_envelope_is_unreadable(self):
		for reply in (Reply(200, {"success": True, "data": {"x": 1}}), Reply(200, {"status": "error"}), Reply(200, None), Reply(200, [1])):
			with self.subTest(str(reply._body)):
				with asking(reply):
					with self.assertRaises(astrology.AstrologyUnavailable):
						astrology.chart(BORN)

	def test_a_refusal_comes_back_with_the_services_own_words(self):
		for status, code in ((422, "invalid_request"), (400, "bad_request"), (413, "too_large")):
			with self.subTest(status):
				with asking(engine_error(status, code, "birth_data.month must be in [1, 12], got 13")):
					with self.assertRaises(astrology.AstrologyRefused) as caught:
						astrology.chart({**BORN, "month": 13})
				self.assertIn("month must be in [1, 12]", str(caught.exception))

	def test_each_way_the_service_can_say_no_has_its_own_plain_sentence(self):
		cases = {
			401: (engine_error(401, "unauthorized", "Missing or wrong API key."), "did not accept AstroHQ's API key"),
			404: (Reply(404, None), "Nothing answers as the astrology API"),
			503: (engine_error(503, "engine_not_ready", "The astrology engine is not ready on this server."), "not ready"),
			500: (engine_error(500, "engine_error", "The astrology engine could not complete this request."), "not working"),
			405: (engine_error(405, "method_not_allowed", "Use POST."), "not working"),
		}
		for status, (reply, words) in cases.items():
			with self.subTest(status):
				with asking(reply):
					with self.assertRaises(astrology.AstrologyUnavailable) as caught:
						astrology.chart(BORN)
				self.assertIn(words, str(caught.exception))
				self.assertNotIn(KEY, str(caught.exception))

	def test_the_service_being_down_is_unavailable_not_a_crash(self):
		for failure in (requests.exceptions.ConnectionError("refused"), requests.exceptions.Timeout("slow")):
			with self.subTest(type(failure).__name__):
				with mock.patch.object(astrology.requests, "request", side_effect=failure):
					with self.assertRaises(astrology.AstrologyUnavailable):
						astrology.chart(BORN)

	def test_switched_off_it_asks_nothing(self):
		straight_settings(enabled=0)
		with asking() as web:
			with self.assertRaises(astrology.AstrologyUnavailable):
				astrology.chart(BORN)
		web.assert_not_called()

	def test_the_connection_check_asks_who_it_is_then_for_a_sample_chart(self):
		with asking(ABOUT, Reply(200, ENVELOPE_SAMPLE)) as web:
			result = astrology.check_connection()
		self.assertTrue(result["ok"], result)
		self.assertIn("version 1.1.0", result["message"])
		(first, second) = web.call_args_list
		self.assertEqual(first.args, ("GET", ENGINE + "/"))
		self.assertEqual((second.args[0], second.args[1]), ("POST", ENGINE + "/"))
		self.assertEqual(second.kwargs["json"]["opcode"], "PANCHANGA")

	def test_it_can_be_tried_before_it_is_switched_on(self):
		straight_settings(enabled=0)
		with asking(ABOUT, Reply(200, ENVELOPE_SAMPLE)):
			self.assertTrue(astrology.check_connection()["ok"])

	def test_a_service_that_says_it_is_not_ready_is_not_asked_for_a_chart(self):
		with asking(Reply(200, {"service": "astrology", "version": "1.1.0", "ready": False})) as web:
			result = astrology.check_connection()
		self.assertFalse(result["ok"])
		self.assertIn("not ready", result["message"])
		self.assertEqual(web.call_count, 1)

	def test_a_service_that_answers_503_to_who_are_you(self):
		with asking(Reply(503, {"service": "astrology", "ready": False})) as web:
			result = astrology.check_connection()
		self.assertFalse(result["ok"])
		self.assertEqual(web.call_count, 1)

	def test_a_wrong_key_shows_up_at_the_chart_and_is_said_plainly(self):
		with asking(ABOUT, engine_error(401, "unauthorized", "Missing or wrong API key.")):
			result = astrology.check_connection()
		self.assertFalse(result["ok"])
		self.assertIn("did not accept AstroHQ's API key", result["message"])

	def test_a_service_that_cannot_be_reached(self):
		with mock.patch.object(astrology.requests, "request", side_effect=requests.exceptions.ConnectionError("refused")):
			result = astrology.check_connection()
		self.assertFalse(result["ok"])
		self.assertIn("did not answer", result["message"])

	def test_the_way_defaults_to_the_hub_and_switching_back_needs_the_name(self):
		configure()  # through the hub again, with its API name
		self.assertEqual(astrology.settings().how, astrology.HUB)
		with self.assertRaises(frappe.ValidationError):
			configure(api_name="")


class TestWhoMaySeeAndUseIt(AstroTestCase):
	def setUp(self):
		super().setUp()
		configure()
		self.owner = make_user(user_type="System User", roles=[{"role": "System Manager"}])
		self.team = make_user(user_type="System User", roles=[{"role": "Accounts Manager"}])
		self.customer = make_user()

	def test_only_a_system_manager_may_open_or_change_the_page(self):
		for user, allowed in ((self.owner, True), (self.team, False), (self.customer, False)):
			for right in ("read", "write"):
				with self.subTest(f"{user.name} {right}"):
					self.assertEqual(bool(frappe.has_permission(astrology.SETTINGS, right, user=user.name)), allowed)

	def test_the_check_runs_for_a_system_manager_and_keeps_what_the_hub_said(self):
		frappe.set_user(self.owner.name)
		with asking(USAGE, good(PANCHANGA)):
			result = frappe.get_doc(astrology.SETTINGS).check_connection()
		self.assertTrue(result["ok"])
		frappe.set_user("Administrator")
		self.assertIn("Connected", frappe.db.get_single_value(astrology.SETTINGS, "last_result", cache=False))
		self.assertTrue(frappe.db.get_single_value(astrology.SETTINGS, "last_checked", cache=False))

	def test_the_check_is_refused_to_everyone_else_and_asks_the_hub_nothing(self):
		for user in (self.team, self.customer):
			with self.subTest(user.name):
				frappe.set_user(user.name)
				with asking() as web:
					with self.assertRaises(frappe.PermissionError):
						frappe.get_doc(astrology.SETTINGS).check_connection()
				web.assert_not_called()

	def test_nothing_that_makes_a_chart_can_be_called_from_the_web(self):
		"""`chart` is server-side code that checks nobody: it must stay off the web until a screen checks who may see whose birth details."""
		for function in (astrology.chart, astrology.birth_data, astrology.settings, astrology.available, astrology._ask, astrology.check_connection):
			with self.subTest(function.__name__):
				with self.assertRaises(frappe.PermissionError):
					frappe.is_whitelisted(function)


class TestAstroHQStaysSeparate(AstroTestCase):
	def test_no_astrology_library_is_imported_inside_astrohq(self):
		"""PyJHora and pyswisseph are under the AGPL: AstroHQ must only ever ask the engine over the web (docs/astrology-api.md)."""
		import raftor_astrohq

		root = Path(raftor_astrohq.__file__).parent
		pattern = re.compile(r"^\s*(?:import|from)\s+(?:jhora|swisseph)\b", re.M)
		offenders = [str(path.relative_to(root)) for path in root.rglob("*.py") if pattern.search(path.read_text())]
		self.assertEqual(offenders, [])
