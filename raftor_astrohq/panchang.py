"""The panchang of any day at any place, and the chaugharia: what the Panchang page and the card over the Home banner show.

    from raftor_astrohq import panchang
    day = panchang.day(date, place)      # the engine's answer for that day and town (PANCHANGA_DAY), kept for a day (for a week for the default town)
    mine = panchang.current(place)       # the chaugharia running now, what comes next, Rahu Kaal now or to come

Nothing is worked out here: the astrology engine says when each tithi, nakshatra, yoga and karana begins and ends, when the sun rises and Rahu Kaal is, and where the chaugharia fall (the hub's
`PANCHANGA_DAY`); this keeps each answer so that a day is asked for once, finds the town a visitor means (places.py), says which part is running by comparing the clock with the times, and gives the
two pages their markup. Only the numbers a calculation needs go to the engine (the date, and the town's coordinates and time zone), never anything about the visitor.

Switched on by a town in Astrology API Settings (Place for the Panchang); blank, nothing is shown. A visitor may ask for any date from 1800 to 2399 and any town of the list, so the engine is protected
two ways: a visitor may make only so many requests a minute, and only so many days and towns the engine has not worked out yet may be asked for in a minute (what is already kept is always shown).
"""
import datetime
import json
import zlib
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, getdate, now_datetime

from raftor_astrohq import astrology, places

SETTINGS = "Astrology API Settings"
MODE = "PANCHANGA_DAY"
WEEK = 7  # the days of the strip: a week


class PanchangBusy(frappe.ValidationError):
	"""Too many days and towns are being worked out at once; asking again in a moment will do."""

	http_status_code = 429


def _default(fieldname: str) -> str:
	"""What the setting's own definition (its doctype) says it is until someone saves another: one place for it, not a second copy here."""
	return frappe.get_meta(SETTINGS).get_field(fieldname).default or ""


def settings() -> frappe._dict:
	"""The Panchang part of Astrology API Settings, with the defaults a page never saved lacks."""
	doc = frappe.get_single(SETTINGS)
	return frappe._dict(
		place=(doc.get("panchang_place") or "").strip(),
		persona=(doc.get("panchang_muhurat_persona") or "").strip()[:60],
		topic=(doc.get("panchang_muhurat_topic") or _default("panchang_muhurat_topic")).strip(),
		new_per_minute=cint(doc.get("panchang_new_per_minute")) or 60,
		per_visitor=cint(doc.get("panchang_requests_per_minute")) or 40,
		chal=doc.get("panchang_chal") or "good",
		rise=doc.get("panchang_sunrise") or "apparent",
		first_year=cint(doc.get("panchang_first_year")) or 1800,  # the years the engine works a day out for
		last_year=cint(doc.get("panchang_last_year")) or 2399,
		keep_default=(cint(doc.get("panchang_keep_days")) or 8) * 24 * 3600,  # seconds a worked-out day is kept: a week ahead for the default town, a day for any other
		keep_other=(cint(doc.get("panchang_keep_other_days")) or 1) * 24 * 3600,
	)


def first_day() -> datetime.date:
	return datetime.date(settings().first_year, 1, 1)


def last_day() -> datetime.date:
	return datetime.date(settings().last_year, 12, 31)


def on() -> bool:
	"""Whether the Panchang is switched on: a town is named in the settings."""
	return bool(settings().place)


def _per_visitor() -> int:
	return settings().per_visitor


# ---- the town and the date ----
def default_place(on_date: datetime.date | None = None) -> dict | None:
	"""The town in the settings, as places.lookup gives it; None when the Panchang is off or the list of places is not built or does not know the town."""
	text = settings().place
	if not text:
		return None
	try:
		return places.lookup(text, on_date or datetime.date.today())
	except (places.PlaceNotFound, places.PlacesNotReady):
		frappe.log_error(title="The Panchang's default place could not be found", message=text)
		return None


def place_of(value, on_date: datetime.date) -> dict | None:
	"""The town a visitor chose (its id in the list, which the page puts in its address), or the default one when they chose none or the one they named is not there."""
	if value not in (None, ""):
		try:
			return places.by_id(value, on_date)
		except (places.PlaceNotFound, places.PlacesNotReady):
			pass
	return default_place(on_date)


def local_now(place: dict) -> datetime.datetime:
	"""The moment now, on the clock of that town."""
	return datetime.datetime.now(ZoneInfo(place["timezone"]))


def today(place: dict) -> datetime.date:
	"""The date in that town now."""
	return local_now(place).date()


def date_of(text, place: dict) -> datetime.date:
	"""The date written in the address (2026-10-24), else today in that town; never outside the years the engine answers for."""
	try:
		picked = getdate(text) if text else None
	except Exception:
		picked = None
	picked = picked or today(place)
	return min(max(picked, first_day()), last_day())


# ---- one day, kept ----
def _key(place: dict, on_date: datetime.date) -> str:
	return f"astro_panchang:{place['latitude']:.3f}:{place['longitude']:.3f}:{on_date.isoformat()}:{settings().chal}:{settings().rise}"


def _fresh(kept) -> bool:
	"""Kept after the date the settings say answers are good from (Astrology API Settings, Kept Answers Are Good From: put today's date there after the engine is updated)."""
	good_from = frappe.db.get_single_value(SETTINGS, "answers_valid_from")
	return bool(kept) and not (good_from and getdate(kept["made"]) < getdate(good_from))


def _keep_for(place: dict) -> int:
	chosen = default_place()
	same = bool(chosen) and abs(chosen["latitude"] - place["latitude"]) < 0.001 and abs(chosen["longitude"] - place["longitude"]) < 0.001
	return settings().keep_default if same else settings().keep_other


def _allow_new() -> None:
	"""Counts a day the engine has to work out and refuses it when too many have been asked for in this minute."""
	cache = frappe.cache
	key = cache.make_key("astro_panchang_new:" + now_datetime().strftime("%Y%m%d%H%M"))
	if not cache.get(key):
		cache.setex(key, 120, 0)
	if cache.incrby(key, 1) > settings().new_per_minute:
		raise PanchangBusy(_("Many people are asking for the panchang just now. Please try again in a minute."))


def day(on_date: datetime.date, place: dict) -> dict:
	"""The engine's PANCHANGA_DAY answer for this date and town: the one kept, or asked for now and kept. Raises astrology.AstrologyUnavailable when the engine cannot be asked and
	astrology.AstrologyRefused when it will not answer for that date or town."""
	cache, key = frappe.cache(), _key(place, on_date)
	packed = cache.get_value(key, expires=True)
	kept = json.loads(zlib.decompress(packed)) if packed else None
	if _fresh(kept):
		return kept["day"]
	_allow_new()
	offset = places.offset_hours(place["timezone"], datetime.datetime(on_date.year, on_date.month, on_date.day, 12))
	answer = astrology.chart({"year": on_date.year, "month": on_date.month, "day": on_date.day, "hour": 12, "minute": 0, "second": 0,
							  "latitude": place["latitude"], "longitude": place["longitude"], "timezone_offset": offset, "chal": settings().chal, "rise": settings().rise}, MODE)
	cache.set_value(key, zlib.compress(json.dumps({"made": now_datetime().isoformat(), "day": answer}, separators=(",", ":")).encode()), expires_in_sec=_keep_for(place))
	return answer


def week(start: datetime.date, place: dict) -> list[dict]:
	"""The days from `start`, seven of them (the last that can be asked for ends the list)."""
	out = []
	for offset in range(WEEK):
		on_date = start + datetime.timedelta(days=offset)
		if on_date > last_day():
			break
		out.append(day(on_date, place))
	return out


def _moment(text: str) -> datetime.datetime:
	return datetime.datetime.fromisoformat(text)


# ---- what is running now ----
def current(place: dict, now: datetime.datetime | None = None) -> dict | None:
	"""The chaugharia running now and what follows, Rahu Kaal and the day's other times, from the kept answers of the town's day (and the day before's night, until the sun is up).
	{"day": the answer, "part": the running one with its "index" in the 16 and "of" ("day" or "night"), "next": the part after it, "next_good": the next good part or None, "now": the moment}"""
	now = now or local_now(place)
	today_ = now.date()
	todays = day(today_, place)
	if now < _moment(todays["sun"]["rise"]):  # the night of the day before is still running
		before = day(today_ - datetime.timedelta(days=1), place)
		return _running(before, now) or _running(todays, now)
	return _running(todays, now) or _running(day(today_ + datetime.timedelta(days=1), place), now)


def _running(answer: dict, now: datetime.datetime) -> dict | None:
	parts = [dict(p, of="day") for p in answer["chaugharia"]["day"]] + [dict(p, of="night") for p in answer["chaugharia"]["night"]]
	for index, part in enumerate(parts):
		if _moment(part["from"]) <= now < _moment(part["to"]):
			after = parts[index + 1] if index + 1 < 16 else None
			good = next((p for p in parts[index + 1:] if p["quality"] == "good"), None)
			return {"day": answer, "part": dict(part, index=index), "next": after, "next_good": good, "now": now}
	return None


def state(place: dict, now: datetime.datetime | None = None) -> dict | None:
	"""What the card over the banner says at this moment: the chaugharia running (`current`), the answer of the day (sunrise to sunrise) that holds it, the answer of the day after it, and the answer
	of the calendar day (for the sun, the moon and Rahu Kaal of today). None when no part is running (the engine's answer has a hole)."""
	now = now or local_now(place)
	running = current(place, now)
	if running is None:
		return None
	held = running["day"]
	after = day(datetime.date.fromisoformat(held["date"]) + datetime.timedelta(days=1), place)
	return {"now": now, "running": running, "held": held, "after": after, "calendar": day(now.date(), place)}


# ---- the page's own endpoints ----
@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=_per_visitor, seconds=60)
def places_found(text=None) -> list[dict]:
	"""The towns whose name starts with what the visitor has typed: [{"id", "name", "region"}]. For the page's place box."""
	return places.suggest(str(text or "")[:60]) if on() else []


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=_per_visitor, seconds=60)
def place_near(latitude=None, longitude=None) -> dict | None:
	"""The town nearest to where the visitor says they are: {"id", "label"} or None. The position is used for this answer and kept nowhere."""
	if not on():
		return None
	found = places.near(latitude, longitude, datetime.date.today())
	return {"id": found["id"], "label": found["name"]} if found else None


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=_per_visitor, seconds=60)
def widget_cards(place=None) -> dict:
	"""The cards of the card over the Home banner, as websitehq's Pop-over section draws them: {"items": [{"card": a card of the library, ... its fields}]}, about this moment and the visitor's town
	(`place`: its id, which the browser kept when the visitor chose a town on the Panchang page; none or one that is not in the list gives the default town). Nothing when the Panchang is off or the engine
	cannot be asked just now: the card is then not there, and nothing else on the page is any the worse."""
	from raftor_astrohq import panchang_widget

	if default_place() is None:
		return {"items": []}
	chosen = place_of(place, datetime.date.today())
	try:
		held = state(chosen)
	except (PanchangBusy, astrology.AstrologyUnavailable, astrology.AstrologyRefused):
		return {"items": []}
	if not held:
		return {"items": []}
	return {"items": panchang_widget.cards(held, {"muhurat": muhurat_offer(), "place": town_label(chosen)}), "toolbar": {"controls": [lookup_control(chosen)]}}  # (the control: the town the card is about, to change)


def warm() -> int:
	"""Run shortly after midnight (scheduled): works out today and the week after for the default town, so that the first visitor of the day waits for nothing. How many days were worked out."""
	first = default_place()
	if not first:
		return 0
	start, worked = today(first), 0
	for offset in range(WEEK + 1):
		try:
			day(start + datetime.timedelta(days=offset), first)
			worked += 1
		except (astrology.AstrologyUnavailable, astrology.AstrologyRefused, PanchangBusy):
			break  # the engine is not there just now: the visitors will find out and the next night tries again
	return worked


# ---- the page ----
def muhurat_offer() -> dict | None:
	"""What the muhurat button connects to, or None when there is to be none. The settings name a kind of guide (a Pandit ji): if one is live now and can be talked to at once, the button starts that talk
	({"live": True, "url": the start, "label": what the guide's card says}); else, if some can be booked, it opens the list of them ({"live": False}); else there is no button. Kept for twenty seconds
	(for each kind of visitor: what a guide offers depends on who asks)."""
	s = settings()
	if not s.persona:
		return None
	cache, key = frappe.cache(), f"astro_panchang_muhurat:{s.persona}:{s.topic}:{frappe.session.user}"
	known = cache.get_value(key, expires=True)
	if known is None:
		known = _muhurat_offer(s.persona, s.topic) or {}
		cache.set_value(key, known, expires_in_sec=20)
	return known or None


def _muhurat_offer(persona: str, topic: str) -> dict | None:
	from raftor_servicehq import card_feeds
	from raftor_websitehq.website_hq.page_groups import page_url

	live = card_feeds.providers(persona=persona, online="1", limit=1, topic=topic)["items"]
	if live and "/online/start" in (live[0].get("button_url") or ""):  # live, and with something to start at once
		return {"live": True, "url": live[0]["button_url"], "label": live[0].get("button_label") or _("Talk now")}
	if card_feeds.providers(persona=persona, limit=1, topic=topic)["items"]:
		return {"live": False, "url": page_url("consult", persona=persona, topic=topic), "label": _("Ask for a muhurat")}
	return None


def _address(on_date: datetime.date | None, chosen_id) -> str:
	from raftor_websitehq.website_hq.page_groups import page_url

	return page_url("panchang", "", date=on_date.isoformat() if on_date else "", place=chosen_id or "")


def town_label(place: dict) -> str:
	"""Delhi, India: the town and its country, as the bar and the card say it."""
	parts = place["name"].split(",")
	return parts[0] + (", " + parts[-1].strip() if len(parts) > 1 else "")


def lookup_control(place: dict) -> dict:
	"""The control that chooses the town (websitehq's: a search of names and "use my location"), for the Panchang page's bar and for the card over a banner."""
	return {"type": "lookup", "arg": "place", "value": str(place["id"]), "label": town_label(place), "search": "raftor_astrohq.panchang.places_found", "near": "raftor_astrohq.panchang.place_near",
			"labels": {"search": _("Search a town"), "near": _("Use my location"), "none": _("No town of that name is in our list."), "choose": _("Choose a town")}}


def toolbar(on_date: datetime.date, place: dict, explicit) -> dict:
	"""What websitehq's Report View draws above the panes: the day (with the day before, the day after, today, and a calendar) and the town (with a search and a way to use where the visitor is).
	The town is in the addresses only when the visitor chose one."""
	chosen = place["id"] if explicit not in (None, "") else None
	here = today(place)
	return {"controls": [
		{"type": "date", "arg": "date", "value": on_date.isoformat(), "label": f"{_(on_date.strftime('%A'))}, {on_date.day} {_(on_date.strftime('%B'))} {on_date.year}", "min": first_day().isoformat(), "max": last_day().isoformat(),
		 "previous": _address(on_date - datetime.timedelta(days=1), chosen) if on_date > first_day() else None, "next": _address(on_date + datetime.timedelta(days=1), chosen) if on_date < last_day() else None,
		 "today": _address(None, chosen) if on_date != here else None, "labels": {"previous": _("The day before"), "next": _("The day after"), "today": _("Today"), "pick": _("Choose a date")}},
		lookup_control(place),
	]}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=_per_visitor, seconds=60)
def page(date=None, place=None) -> dict:
	"""The Panchang page for a date and a town (the address's `date` and `place`): its panes and the bar to move to another day or town. For websitehq's Report View, which cleans what it sends."""
	from raftor_astrohq import report_view

	if default_place() is None:  # switched off, or the list of places or the town is not there
		return {"items": []}
	chosen = place_of(place, datetime.date.today())
	on_date = date_of(date, chosen)
	explicit = place if place not in (None, "") and str(place) == str(chosen["id"]) else None
	bar = toolbar(on_date, chosen, explicit)
	try:
		shown = day(on_date, chosen)
		days = week(on_date, chosen)
	except PanchangBusy as error:
		return {"items": [{"body_html": f'<p class="rv-note">{frappe.utils.escape_html(str(error))}</p>', "toolbar": bar}]}
	except (astrology.AstrologyUnavailable, astrology.AstrologyRefused):
		return {"items": [{"body_html": f'<p class="rv-note">{frappe.utils.escape_html(_("The panchang cannot be worked out just now. Please try again in a little while."))}</p>', "toolbar": bar}]}
	now = local_now(chosen)
	ctx = {"date": on_date, "today": on_date, "now": now if on_date == now.date() else None, "place": chosen, "link": lambda on: _address(on, explicit), "muhurat": muhurat_offer()}
	markup = report_view.render(report_view.view_named("panchang"), {"day": shown, "week": days}, ctx, "reviewed")
	return {"items": [{"body_html": markup, "toolbar": bar}] if markup else []}
