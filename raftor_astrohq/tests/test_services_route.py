"""Where AstroHQ's words are written (Daily Rashifal Settings: "Old hub" or "AISpark Services"). The old route is untouched and stays the default; the new one goes through IntegrationHQ's AISpark Services
helper. Whatever goes wrong there, the page says what it always said ("could not be written just now") and never shows an error.

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_services_route
"""
import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from raftor_astrohq import hub, rashifal
from raftor_integrationhq.adapters.ai_gateway import aispark_services as svc

GOOD_WORDS = {"en": {k: f"A sentence for {k}." for k in rashifal.PARTS}, "hi": {k: f"{k} के लिए एक वाक्य।" for k in rashifal.PARTS}}


def answer(content="**Words** here", model="openai/gpt-4.1-nano"):
	return {"success": True, "data": {"content": content, "model": model}, "request_id": "sc-1", "units": {"tokens": 30.0}, "replayed": False}


def services(**extra):
	return frappe._dict({"address": "", "site": "", "key": "", "api_name": "text-to-text", "timeout": 5, "route": rashifal.SERVICES, "account": "", **extra})


def old_hub(**extra):
	return frappe._dict({"address": "http://hub", "site": "", "key": "k", "api_name": "text-to-text", "timeout": 5, **extra})


class TestServicesRoute(FrappeTestCase):
	# ---- nothing changes unless it is switched on ----
	def test_the_settings_page_defaults_to_the_old_hub(self):
		meta = frappe.get_meta("Daily Rashifal Settings")
		self.assertEqual((meta.get_field("route").default, meta.get_field("route").options.split("\n")), ("Old hub", ["Old hub", "AISpark Services"]))
		self.assertEqual(rashifal.settings().route, rashifal.OLD_HUB)

	def test_the_old_route_still_posts_to_the_old_hub_and_never_touches_the_new_one(self):
		sent = {}

		class Old:
			status_code = 200

			def json(self):
				return {"data": {"content": "Old words", "model": "m"}}
		with patch("raftor_astrohq.hub.rashifal.settings", return_value=old_hub()), patch("raftor_astrohq.hub.requests.post", lambda url, **kw: sent.update(url=url, **kw) or Old()), \
				patch.object(rashifal, "via_services", side_effect=AssertionError("the new route must not be used")):
			self.assertEqual(hub.write("sys", {"a": 1}), ("Old words", "m"))
		self.assertEqual((sent["url"], sent["headers"]["X-Api-Key"]), ("http://hub" + rashifal.GATEWAY, "k"))

	def test_a_page_with_no_address_or_key_is_still_unavailable_on_the_old_route(self):
		with patch("raftor_astrohq.hub.rashifal.settings", return_value=old_hub(address="", key="")), self.assertRaises(hub.Unavailable):
			hub.write("sys", {})
		self.assertTrue(rashifal.configured(services()))                    # but the new route needs neither: the account holds them

	# ---- the new route ----
	def test_tarot_and_numerology_words_come_from_the_service_with_the_same_request_and_the_same_cleaning(self):
		calls = []
		with patch("raftor_astrohq.hub.rashifal.settings", return_value=services()), patch.object(svc, "call", lambda *a, **kw: calls.append((a, kw)) or answer()), \
				patch("raftor_astrohq.hub.requests.post", side_effect=AssertionError("the old hub must not be asked")):
			text, model = hub.write("be kind", {"cards": ["The Star"]}, max_tokens=300, mode="quick")
		self.assertEqual((text, model), ("Words here", "openai/gpt-4.1-nano"))        # markup and asterisks are cleaned exactly as before
		service, payload = calls[0][0]
		self.assertEqual((service, calls[0][1]), ("text-to-text", {"account": None}))
		self.assertEqual((payload["system"], payload["max_tokens"], payload["mode"], payload["temperature"]), ("be kind", 300, "quick", 0.7))
		self.assertEqual(json.loads(payload["prompt"]), {"cards": ["The Star"]})

	def test_a_named_account_is_used(self):
		calls = []
		with patch.object(svc, "call", lambda *a, **kw: calls.append(kw) or answer()):
			with patch("raftor_astrohq.hub.rashifal.settings", return_value=services(account="AI Gateway-AISpark Services-me")):
				hub.write("s", {})
		self.assertEqual(calls[0]["account"], "AI Gateway-AISpark Services-me")

	def test_the_daily_rashifal_is_written_and_checked_the_same_way(self):
		with patch.object(svc, "call", return_value=answer(json.dumps(GOOD_WORDS, ensure_ascii=False), "m1")):
			words, model = rashifal.write({"sign": "Aries"}, services())
		self.assertEqual((words["en"]["love"], model), ("A sentence for love.", "m1"))
		with patch.object(svc, "call", return_value=answer("not json at all")), self.assertRaises(ValueError):
			rashifal.write({}, services())                                                 # a bad answer is refused by the same checks as before (the daily writer catches this)

	# ---- every way it can fail is the page's usual "could not be written just now" ----
	def test_every_failure_of_the_service_is_the_usual_unavailable_and_not_an_error_on_the_page(self):
		failures = [svc.ServicesUnavailable(), svc.ServicesQuota(429, "quota", "You have used all 100 tokens."), svc.ServicesRefused(422, "refused", "birth_data.year is missing"),
					svc.ServicesError(401, "unauthorized", "The key was not accepted."), svc.ServicesError(409, "still_running", "Still running."),
					frappe.ValidationError("No AISpark Services account is set up on this site.")]
		for failure in failures:
			with patch.object(svc, "call", side_effect=failure), patch.object(frappe, "log_error"), self.subTest(failure=type(failure).__name__):
				with self.assertRaises(hub.Unavailable):
					self._write(hub, services())
				with self.assertRaises(rashifal.RashifalUnavailable):
					rashifal.write({}, services())

	def _write(self, module, s):
		with patch("raftor_astrohq.hub.rashifal.settings", return_value=s):
			return module.write("s", {})

	def test_an_answer_with_no_words_is_unavailable(self):
		for bad in ({"success": True, "data": {}}, {"success": True, "data": {"content": "   "}}, {"success": True}, {}):
			with patch.object(svc, "call", return_value=bad), self.assertRaises(hub.Unavailable):
				self._write(hub, services())

	def test_what_is_logged_is_the_kind_and_the_servers_words_never_a_key_or_an_address(self):
		with patch.object(svc, "call", side_effect=svc.ServicesQuota(429, "quota", "You have used all 100 tokens.")), patch.object(frappe, "log_error") as logged, self.assertRaises(hub.Unavailable):
			self._write(hub, services())
		self.assertEqual(logged.call_args.kwargs["message"], "429 quota: You have used all 100 tokens.")

	def test_a_site_without_integrationhq_degrades_to_unavailable_not_a_crash(self):
		import builtins
		real = builtins.__import__

		def no_integrationhq(name, *a, **kw):
			if name.startswith("raftor_integrationhq"):
				raise ImportError(name)
			return real(name, *a, **kw)
		with patch.object(frappe, "log_error"), patch.object(builtins, "__import__", no_integrationhq):
			self.assertEqual(rashifal.via_services(services(), {"api_name": "t", "payload": {}}), (503, {}))

	def test_a_refusal_status_is_never_accepted_even_if_some_words_came_with_it(self):
		for status in (401, 403, 422, 429, 503):
			with patch.object(rashifal, "via_services", return_value=(status, {"data": {"content": "some words anyway"}})), self.subTest(status=status):
				with self.assertRaises(hub.Unavailable):
					self._write(hub, services())
		with patch.object(rashifal, "via_services", return_value=(429, {"data": {"content": json.dumps(GOOD_WORDS, ensure_ascii=False)}})), self.assertRaises(rashifal.RashifalUnavailable):
			rashifal.write({}, services())
