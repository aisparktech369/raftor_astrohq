"""AstroHQ's way to the astrology API.

The astrology engine (Vedic charts, dasha, panchang, KP, matching) is a program of its own that AstroHQ only asks, over the web, with a key.
Two ways to reach it, chosen in Astrology API Settings: through the hub (the hub's `astrology` API, which passes the call on to wherever the engine
runs) or straight to the astrology API (a small service on this server, or an AWS Lambda function: the same contract). AstroHQ never imports an
astrology library: those are under the AGPL, and keeping them out of AstroHQ keeps AstroHQ a separate program (tests/test_astrology.py checks that).

    from raftor_astrohq import astrology
    born = astrology.birth_data(profile_row, latitude=28.6139, longitude=77.209, timezone_offset=5.5)
    data = astrology.chart(born, "CORE_BASIC")          # the engine's answer; astrology.chart(born, "MATCH_CALC", partner=other) for matching

Where the hub is and AstroHQ's key are in Astrology API Settings (System Manager only). `chart` is server-side code: it checks nobody. Anything
that lets a person ask for a chart over the web must first check that this person may see this other person's birth details (an
astrologer of that booking, the person themselves), because a chart is made from them.

Birth profiles hold the place as text and no coordinates. A chart needs latitude, longitude and the time zone offset on that date: this
module takes them as given and does not look places up.
"""
import json
import re
from urllib.parse import urlsplit

import frappe
import requests
from frappe import _
from frappe.utils import getdate, now_datetime, strip_html_tags

SETTINGS = "Astrology API Settings"
HUB, STRAIGHT = "Through the hub", "Straight to the astrology API"  # the two values of the page's "How AstroHQ Reaches It"
CALL = "/api/method/raftor_apimanager.gateway.call"
USAGE = "/api/method/raftor_apimanager.gateway.usage"
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")  # http is accepted for these only, for trying things on one computer
TIME = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")

# What is sent to the hub: only the numbers a calculation needs, never a name, a place's name or anything else that a caller's dict may hold.
SENT = ("year", "month", "day", "hour", "minute", "second", "latitude", "longitude", "timezone_offset", "gender",
		"ayanamsa_mode", "ayanamsa_value", "dasha_levels", "horary_number", "requested_dasha_systems", "chal", "rise")

# The birth used only to prove the connection: a made-up person, not data.
SAMPLE = {"year": 1980, "month": 6, "day": 8, "hour": 13, "minute": 49, "second": 0, "latitude": 28.6139, "longitude": 77.209, "timezone_offset": 5.5}


class AstrologyUnavailable(frappe.ValidationError):
	"""The astrology engine cannot be reached or will not answer now: switched off, not set up, the hub or the engine is down, the key is
	refused or used up. Trying again later, or having the settings put right, helps."""

	http_status_code = 503


class AstrologyRefused(frappe.ValidationError):
	"""The birth details (or the operation asked for) were not accepted; the message says why. Asking again with the same details will not help."""


def settings() -> frappe._dict:
	"""The saved settings, with defaults for a page never saved. `address` has no trailing slash."""
	doc = frappe.get_single(SETTINGS)
	return frappe._dict(
		enabled=bool(doc.enabled),
		how=doc.how or HUB,
		address=(doc.hub_address or "").strip().rstrip("/"),
		api_key=doc.get_password("api_key", raise_exception=False) or "",
		api_name=(doc.api_name or "").strip(),
		timeout=int(doc.timeout_seconds or 20),
	)


def _filled_in(s: frappe._dict) -> bool:
	"""Address and key, and (only through the hub) the API's name."""
	return bool(s.address and s.api_key and (s.how == STRAIGHT or s.api_name))


def available() -> bool:
	"""Whether charts can be asked for now: switched on, and the address, AstroHQ's key (and, through the hub, the API's name) are filled in."""
	s = settings()
	return bool(s.enabled and _filled_in(s))


def clean_address(text: str) -> str:
	"""The address as `https://host[:port]`, or a plain sentence saying what is wrong with it."""
	address = (text or "").strip().rstrip("/")
	if not address:
		return ""
	parts = urlsplit(address)
	if parts.scheme not in ("https", "http") or not parts.hostname:
		frappe.throw(_("The address must look like https://hub.example.com"))
	if parts.scheme == "http" and parts.hostname not in LOCAL_HOSTS:
		frappe.throw(_("The address must start with https:// so that the key and the birth details travel safely. (An address on this computer may start with http://.)"))
	if parts.username or parts.password or parts.path or parts.query or parts.fragment:
		frappe.throw(_("Give only the address, such as https://hub.example.com: no user name, path or extras."))
	return address


def birth_data(profile, latitude, longitude, timezone_offset, gender: str | None = None) -> dict:
	"""The numbers the engine needs, from an Astro Birth Profile row (or its values as a dict) and the place's coordinates.

	`timezone_offset` is hours east of Greenwich on that date and place (+5.5 for India; +1 for London in summer 1972). Refused in words when
	the birth time is not known (a chart has no lagna or houses without it) or the coordinates are not usable."""
	get = profile.get if hasattr(profile, "get") else (lambda key: getattr(profile, key, None))
	if int(get("time_unknown") or 0) or not (get("time_of_birth") or "").strip():
		raise AstrologyRefused(_("The time of birth is not known, so a chart cannot be drawn."))
	match = TIME.match((get("time_of_birth") or "").strip())
	if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59 or int(match.group(3) or 0) > 59:
		raise AstrologyRefused(_("The time of birth is not a 24-hour time such as 06:42."))
	if not get("date_of_birth"):  # (getdate of nothing is today, which would be a birth on the day of asking)
		raise AstrologyRefused(_("The date of birth is missing."))
	try:
		born = getdate(get("date_of_birth"))
	except Exception:
		raise AstrologyRefused(_("The date of birth is not a date.")) from None
	numbers = {}
	for key, value, low, high, name in (("latitude", latitude, -90, 90, _("latitude")), ("longitude", longitude, -180, 180, _("longitude")), ("timezone_offset", timezone_offset, -14, 14, _("time zone"))):
		try:
			number = float(value)
		except (TypeError, ValueError):
			raise AstrologyRefused(_("The place needs a {0}.").format(name)) from None
		if not low <= number <= high:
			raise AstrologyRefused(_("The {0} must be between {1} and {2}.").format(name, low, high))
		numbers[key] = number
	out = {"year": born.year, "month": born.month, "day": born.day, "hour": int(match.group(1)), "minute": int(match.group(2)), "second": int(match.group(3) or 0), **numbers}
	if gender:
		out["gender"] = gender
	return out


def chart(birth: dict, opcode: str = "SUPER_BASIC", partner: dict | None = None) -> dict:
	"""The engine's answer for one birth (and, for `MATCH_CALC`, the partner's birth). Raises AstrologyRefused when the hub or engine says the
	birth details or the operation are not acceptable, and AstrologyUnavailable when it cannot be asked or will not answer."""
	payload = {"opcode": opcode, "birth_data": _sendable(birth)}
	if partner is not None:
		payload["birth_data_2"] = _sendable(partner)
	return _ask(payload)


def numerology(day: int | None = None, month: int | None = None, name: str | None = None) -> dict:
	"""Cheiro's numerology, calculated by the engine (opcode NUMEROLOGY): the birth number from the day, the zodiac period when the month is given, the name number
	from a Latin spelling. It needs no birth time or place. The sums are the engine's: a language model never counts letters. Raises like `chart`."""
	asked = {key: value for key, value in (("day", day), ("month", month), ("name", name)) if value not in (None, "")}
	return _ask({"opcode": "NUMEROLOGY", "numerology": asked})


def _sendable(birth: dict) -> dict:
	if not isinstance(birth, dict):
		raise AstrologyRefused(_("The birth details must be a set of numbers: year, month, day, hour, minute, second, latitude, longitude and time zone."))
	return {key: birth[key] for key in SENT if birth.get(key) is not None}


def _ask(payload: dict, s: frappe._dict | None = None, must_be_on: bool = True) -> dict:
	s = s or settings()
	if not ((s.enabled or not must_be_on) and _filled_in(s)):
		raise AstrologyUnavailable(_("Charts are switched off or not set up yet: see Astrology API Settings."))
	if s.how == STRAIGHT:  # the astrology API's own contract: the payload itself, answered with the engine's envelope
		return _result(_send("POST", s.address + "/", s, payload), straight=True)
	return _result(_send("POST", s.address + CALL, s, {"api_name": s.api_name, "payload": payload}))


def _send(method: str, url: str, s: frappe._dict, body: dict | None = None) -> requests.Response:
	try:
		return requests.request(method, url, json=body, headers={"X-Api-Key": s.api_key}, timeout=s.timeout)
	except requests.exceptions.RequestException:
		raise AstrologyUnavailable(_("The astrology service did not answer. Try again in a little while.")) from None


def _result(response: requests.Response, straight: bool = False) -> dict:
	"""The chart inside the answer, or the right exception for what went wrong. `straight` is the astrology API's own contract (the answer is the
	engine's envelope), not the hub's (the envelope inside {"success", "data"})."""
	status = response.status_code
	try:
		body = response.json()
	except ValueError:
		body = None
	if not isinstance(body, dict):
		body = {}
	who = _("the astrology API") if straight else _("the hub")
	if status == 200:
		if straight:
			answer = body if body.get("status") == "success" else None
		else:
			if isinstance(body.get("message"), dict) and "data" not in body:  # an answer that came wrapped, as Frappe sometimes does
				body = body["message"]
			answer = body.get("data") if body.get("success") else None
		if isinstance(answer, dict):
			chart = answer["data"] if answer.get("status") == "success" and "data" in answer else answer
			if isinstance(chart, dict) and isinstance(chart.get("error"), str):  # the engine could not finish (it says so inside an otherwise good answer)
				raise AstrologyUnavailable(chart["error"])
			return chart
		raise AstrologyUnavailable(_("The astrology service sent an answer AstroHQ could not read."))
	words = _words(body)
	if status in (400, 413, 417, 422):
		raise AstrologyRefused(words or _("The birth details were not accepted."))
	if status == 401:
		raise AstrologyUnavailable(_("{0} did not accept AstroHQ's API key. Ask whoever runs it for a new one and put it in Astrology API Settings.").format(who[:1].upper() + who[1:]))
	if status == 403:
		raise AstrologyUnavailable(_("AstroHQ's plan at the hub does not include the astrology API, or its subscription is not active."))
	if status == 404:
		raise AstrologyUnavailable(_("Nothing answers as the astrology API at that address. Check the address in Astrology API Settings.") if straight else _("The hub has no astrology API by that name. Check the hub's address and the API's name in Astrology API Settings."))
	if status == 429:
		raise AstrologyUnavailable(_("AstroHQ has used up the calls it may make to the astrology API for now."))
	if status == 503 and straight:
		raise AstrologyUnavailable(_("The astrology API is running but is not ready (its key or its star-position files are not set up). Ask whoever runs it."))
	raise AstrologyUnavailable(_("The astrology service is not working right now. Try again in a little while."))


def _words(body: dict) -> str:
	"""The reason Frappe gave for refusing a request, as plain text."""
	raw = body.get("_server_messages")
	if raw:
		try:
			first = json.loads(raw)[0]
			if isinstance(first, str):
				first = json.loads(first)
			text = strip_html_tags(str(first.get("message") or "")).strip()
			if text:
				return text[:300]
		except (ValueError, IndexError, AttributeError, TypeError):
			pass
	error = body.get("error")
	if isinstance(error, dict) and isinstance(error.get("message"), str):  # the astrology API's own refusal
		return strip_html_tags(error["message"]).strip()[:300]
	message = body.get("message")
	return strip_html_tags(message).strip()[:300] if isinstance(message, str) else ""


def check_connection() -> dict:
	"""Asks whether AstroHQ's key is accepted and the engine answers a sample chart. Through the hub, the hub is asked first about the key (this
	counts no call); straight, the astrology API is asked who it is and whether it is ready. Uses the saved address and key whether or not charts
	are switched on, so it can be tried before switching on. {"ok": bool, "message": str}"""
	s = settings()
	if not _filled_in(s):
		return {"ok": False, "message": _("Fill in the address and AstroHQ's API key (and, through the hub, the API's name) first, and save.")}
	try:
		if s.how == STRAIGHT:
			info = _send("GET", s.address + "/", s)
			if info.status_code != 200:
				_result(info, straight=True)  # raises the right sentence for 503, 404 and the rest
				raise AstrologyUnavailable(_("The astrology API did not say who it is."))
			about = info.json() or {}
			if not about.get("ready"):
				return {"ok": False, "message": _("The astrology API is running but says it is not ready. Ask whoever runs it.")}
			answer = _ask({"opcode": "PANCHANGA", "birth_data": SAMPLE}, s, must_be_on=False)
			named = _("the astrology API (version {0})").format(about.get("version") or "?")
		else:
			usage = _send("GET", s.address + USAGE, s)
			if usage.status_code != 200:
				_result(usage)  # raises the right sentence for 401, 403, 429 and the rest
				raise AstrologyUnavailable(_("The hub did not give the key's usage."))
			plan = (usage.json() or {}).get("plan") or _("an unnamed plan")
			answer = _ask({"opcode": "PANCHANGA", "birth_data": SAMPLE}, s, must_be_on=False)
			named = _("the hub, which knows AstroHQ on the plan {0}").format(plan)
	except (AstrologyUnavailable, AstrologyRefused) as error:
		return {"ok": False, "message": str(error)}
	except ValueError:
		return {"ok": False, "message": _("The answer could not be read.")}
	if not isinstance(answer, dict) or not answer.get("panchanga"):
		return {"ok": False, "message": _("The key was accepted but the engine's answer was empty.")}
	return {"ok": True, "message": _("Connected to {0}: the astrology engine answered a sample chart.").format(named)}


def note_connection(result: dict) -> None:
	"""Keeps what the last check said, without saving the page (so nothing the user is editing is touched)."""
	frappe.db.set_single_value(SETTINGS, {"last_checked": now_datetime(), "last_result": str(result.get("message") or "")[:500]})
