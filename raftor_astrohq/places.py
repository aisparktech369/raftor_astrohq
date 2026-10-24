"""Places: from the town a person writes or picks to its latitude, longitude and the time zone offset on the day of birth (a chart needs all three).

AstroHQ keeps no list of towns. The astrology service holds the one list (GeoNames' "cities500", 236,000 places with their state, district, population and time zone) and answers for it through
four opcodes, so that every app that uses the service has the same towns, in the same order, with the same time zones (the service's README, "the places"):

    PLACE_SEARCH   the towns whose name starts with what has been typed, best first (the dropdown)
    PLACE_GET      one town by its id, with the time zone offset in force on a date (the date of birth)
    PLACE_FIND     a town written out ("Pune, Maharashtra"); a name that more than one town carries is not guessed but asked about
    PLACE_NEAR     the town nearest to a point

The functions here keep the names and the answers they always had, so nothing that asks for a place has changed: `lookup`, `by_id`, `suggest`, `near`, `problem`. What was asked is kept for a little while
(a town by its id for a day, the first letters typed for an hour), so that a page that names a town does not ask the service again and again.

The data is GeoNames', licensed CC BY 4.0 (https://www.geonames.org): whatever shows a town says so (`ATTRIBUTION`).
"""
import datetime
import re
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import frappe
from frappe import _

from raftor_astrohq import astrology

ATTRIBUTION = "Place data: GeoNames (geonames.org), licensed CC BY 4.0."
KEEP_BY_ID, KEEP_TYPED = 24 * 3600, 3600  # seconds


class PlaceNotFound(frappe.ValidationError):
	"""The place could not be found, or the qualifiers given do not fit it; the message says what to try."""


class PlaceAmbiguous(PlaceNotFound):
	"""More than one place has this name; the message lists them and asks for the state."""


class PlacesNotReady(frappe.ValidationError):
	"""The service that holds the list of towns cannot be asked, or has not got the list yet."""

	http_status_code = 503


def normal(text: str) -> str:
	"""Lower case, no accents, letters and digits only, one space between words."""
	text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
	return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _ask(opcode: str, place: dict) -> dict:
	"""The service's answer for one of its place opcodes. A town it will not give is PlaceNotFound (its words say what to try), a service that cannot be asked is PlacesNotReady."""
	try:
		return astrology._ask({"opcode": opcode, "place": place}, must_be_on=False)
	except astrology.AstrologyRefused as error:
		raise (PlaceAmbiguous if "More than one place" in str(error) else PlaceNotFound)(str(error)) from None
	except astrology.AstrologyUnavailable as error:
		raise PlacesNotReady(str(error)) from None


def _kept(key: str, seconds: int, ask):
	cache = frappe.cache()
	known = cache.get_value(key, expires=True)
	if known is not None:
		return known
	made = ask()
	cache.set_value(key, made, expires_in_sec=seconds)
	return made


def _at(on: datetime.datetime | datetime.date | str) -> str:
	"""The local date (and time) the offset is wanted for, as the service reads it."""
	if isinstance(on, str):
		on = frappe.utils.get_datetime(on)
	if isinstance(on, datetime.datetime):
		return on.replace(tzinfo=None, second=0, microsecond=0).isoformat(timespec="minutes")
	return on.isoformat()


def ready() -> bool:
	"""Whether the service can give towns just now."""
	try:
		_kept("astro_places:ready", 60, lambda: bool(_ask("PLACE_SEARCH", {"text": "de", "limit": 1}) is not None))
		return True
	except PlacesNotReady:
		return False


def offset_hours(tz: str, on: datetime.datetime) -> float:
	"""Hours east of Greenwich in force in this time zone at this local date and time."""
	try:
		delta = ZoneInfo(tz).utcoffset(on)
	except (ZoneInfoNotFoundError, KeyError, ValueError):
		delta = None
	if delta is None:
		raise PlaceNotFound(_("The time zone of that place is not known."))
	return delta.total_seconds() / 3600.0


def lookup(text: str, on: datetime.datetime | datetime.date | str) -> dict:
	"""{"id", "name", "latitude", "longitude", "timezone", "timezone_offset", "population"} for the place written in `text`, with the time zone offset in force on `on` (the local date and time of
	birth). Raises PlaceNotFound (nothing fits, with what to try), PlaceAmbiguous (it lists the choices) or PlacesNotReady (the service cannot give towns)."""
	at = _at(on)
	return _kept(f"astro_places:f:{normal(text)}:{at}", KEEP_TYPED, lambda: _ask("PLACE_FIND", {"text": str(text or ""), "at": at})["place"])


def by_id(place_id, on: datetime.datetime | datetime.date | str) -> dict:
	"""The place with this id in the list (the `id` that `lookup` and `suggest` give), as `lookup` gives it. Raises PlaceNotFound when there is none."""
	try:
		number = int(place_id)
	except (TypeError, ValueError):
		raise PlaceNotFound(_("That place is not in the list.")) from None
	at = _at(on)
	return _kept(f"astro_places:g:{number}:{at}", KEEP_BY_ID, lambda: _ask("PLACE_GET", {"id": number, "at": at})["place"])


def suggest(text: str, limit: int = 6) -> list[dict]:
	"""The places whose name starts with what has been typed so far, best first: [{"id", "name", "region"}] ("Mumbai", "Maharashtra, India"). Nothing for less than two letters, or when the service cannot be asked."""
	typed = normal(text)
	if len(typed) < 2:
		return []
	try:
		return _kept(f"astro_places:s:{typed}:{limit}", KEEP_TYPED, lambda: _ask("PLACE_SEARCH", {"text": typed, "limit": limit})["places"])
	except PlacesNotReady:
		return []


def near(latitude: float, longitude: float, on: datetime.datetime | datetime.date | str) -> dict | None:
	"""The town nearest to a point, as `lookup` gives it, or None (none within reach, a point that is not on the earth, or a service that cannot be asked)."""
	try:
		lat, lon = float(latitude), float(longitude)
	except (TypeError, ValueError):
		return None
	if not (-90 <= lat <= 90 and -180 <= lon <= 180):
		return None
	try:
		return _ask("PLACE_NEAR", {"latitude": lat, "longitude": lon, "at": _at(on)})["place"]
	except PlacesNotReady:
		return None


def problem(text: str, on: datetime.datetime | datetime.date | str) -> str:
	"""A sentence saying what is wrong with this place, or "" when it is found (or when the service cannot give towns, so that a sale is never refused for it)."""
	try:
		lookup(text, on)
	except PlacesNotReady:
		return ""
	except PlaceNotFound as error:
		return str(error)
	return ""
