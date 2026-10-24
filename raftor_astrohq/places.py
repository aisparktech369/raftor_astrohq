"""Places: from the town a customer writes to its latitude, longitude and the time zone on the day of birth (a chart needs all three).

The list is GeoNames' "cities500" (every populated place of 500 people or more, 236,000 of them, with its state and district, its population
and its time zone), kept in a small database file in the site's private folder (`private/places/places.sqlite`) and built once with
`bench --site <site> execute raftor_astrohq.places.build`. Nothing is asked of the internet when a place is looked up. The data is GeoNames',
licensed CC BY 4.0 (https://www.geonames.org): the reports say so.

How a place is read: "Pune", "Pune, Maharashtra", "Pune, Maharashtra, India", "Sirsa, Haryana", "Houston, TX" and "London, UK" all work. The first part
is the town, the rest must each be a district, a state or a country (or one of their usual short forms), and every one of them must fit the place
found. A name that more than one place in the list carries is not guessed: unless one is by far the biggest town of that name, the customer is told
which ones there are and asked to add the state. A wrong guess would be a wrong chart, so it is better to ask.

The time zone offset is the one in force at the place on that date and time (the zone's own history is used, so a 1972 summer birth in London is +1
and a 1943 birth in India is +6:30).
"""
import datetime
import io
import os
import re
import sqlite3
import unicodedata
import urllib.request
import zipfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import frappe
from frappe import _

BASE = "https://download.geonames.org/export/dump/"
SOURCES = ("cities500.zip", "admin1CodesASCII.txt", "admin2Codes.txt", "countryInfo.txt")
ATTRIBUTION = "Place data: GeoNames (geonames.org), licensed CC BY 4.0."

SAME_PLACE_KM = 25  # places of the same name closer than this are one place (the same town listed twice)
BIG_ENOUGH = 500_000  # a town this big, and 20 times the size of every other of its name, is taken without asking
MUCH_BIGGER = 20
MAX_OPTIONS = 6  # how many of the places that share a name are listed when the customer must choose

# What people write for a country or state that is not its full name in the list. (Short forms of Indian states: GeoNames numbers them.)
COUNTRY_FORMS = {"usa": "US", "us": "US", "united states of america": "US", "america": "US", "uk": "GB", "england": "GB", "scotland": "GB", "wales": "GB", "great britain": "GB",
				 "uae": "AE", "russia": "RU", "south korea": "KR", "korea": "KR"}
INDIA_STATE_FORMS = {"ap": "andhra pradesh", "ar": "arunachal pradesh", "as": "assam", "br": "bihar", "cg": "chhattisgarh", "ga": "goa", "gj": "gujarat", "hr": "haryana",
					 "hp": "himachal pradesh", "jh": "jharkhand", "ka": "karnataka", "kl": "kerala", "mp": "madhya pradesh", "mh": "maharashtra", "mn": "manipur", "ml": "meghalaya",
					 "mz": "mizoram", "nl": "nagaland", "od": "odisha", "or": "odisha", "orissa": "odisha", "pb": "punjab", "rj": "rajasthan", "sk": "sikkim", "tn": "tamil nadu",
					 "ts": "telangana", "tg": "telangana", "tr": "tripura", "up": "uttar pradesh", "uk": "uttarakhand", "ut": "uttarakhand", "uttaranchal": "uttarakhand",
					 "wb": "west bengal", "an": "andaman and nicobar", "ch": "chandigarh", "dl": "delhi", "new delhi": "delhi", "nct": "delhi", "jk": "jammu and kashmir", "la": "ladakh",
					 "ld": "lakshadweep", "py": "puducherry", "pondicherry": "puducherry", "dn": "dadra and nagar haveli and daman and diu", "dd": "dadra and nagar haveli and daman and diu"}


class PlaceNotFound(frappe.ValidationError):
	"""The place could not be found, or the qualifiers given do not fit it; the message says what to try."""


class PlaceAmbiguous(PlaceNotFound):
	"""More than one place has this name; the message lists them and asks for the state."""


class PlacesNotReady(frappe.ValidationError):
	"""The list of places has not been built on this site: run `bench --site <site> execute raftor_astrohq.places.build` once."""

	http_status_code = 503


def path() -> str:
	return frappe.get_site_path("private", "places", "places.sqlite")


def ready() -> bool:
	return os.path.exists(path())


def normal(text: str) -> str:
	"""Lower case, no accents, letters and digits only, one space between words."""
	text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
	return re.sub(r"[^a-z0-9]+", " ", text).strip()


# ---- building the list ----
SCHEMA = """
create table place (id integer primary key, name text, cc text, country text, admin1_code text, admin1 text, admin2 text, lat real, lon real, pop integer, tz text);
create table alias (norm text, place_id integer);
create table meta (key text primary key, value text);
"""


def _read_countries(text: str) -> dict[str, str]:
	out = {}
	for line in text.splitlines():
		if line and not line.startswith("#"):
			cells = line.split("\t")
			if len(cells) > 4:
				out[cells[0]] = cells[4]
	return out


def _read_names(text: str) -> dict[str, str]:
	"""admin1CodesASCII and admin2Codes: {"IN.16": "Maharashtra", "IN.16.521": "Pune"}."""
	out = {}
	for line in text.splitlines():
		cells = line.split("\t")
		if len(cells) > 1:
			out[cells[0]] = cells[1]
	return out


def build_from_text(cities: str, admin1: str, admin2: str, countries: str, target: str, source_note: str = "") -> dict:
	"""Writes the database of places to `target` (atomically) from the text of GeoNames' files. Returns the counts."""
	country_of, region_of, district_of = _read_countries(countries), _read_names(admin1), _read_names(admin2)
	os.makedirs(os.path.dirname(target), exist_ok=True)
	temporary = target + ".part"
	if os.path.exists(temporary):
		os.remove(temporary)
	db = sqlite3.connect(temporary)
	try:
		db.executescript(SCHEMA)
		places, aliases = [], []
		for line in cities.splitlines():
			cells = line.split("\t")
			if len(cells) < 18 or not cells[17]:
				continue
			geo_id, name, ascii_name, others, lat, lon = int(cells[0]), cells[1], cells[2], cells[3], float(cells[4]), float(cells[5])
			cc, a1, a2, population, tz = cells[8], cells[10], cells[11], int(cells[14] or 0), cells[17]
			places.append((geo_id, name, cc, country_of.get(cc, cc), a1, region_of.get(f"{cc}.{a1}", ""), district_of.get(f"{cc}.{a1}.{a2}", ""), lat, lon, population, tz))
			for text in {name, ascii_name, *others.split(",")}:
				norm = normal(text)
				if norm and len(norm) <= 60:
					aliases.append((norm, geo_id))
			if len(places) >= 20000:
				db.executemany("insert into place values (?,?,?,?,?,?,?,?,?,?,?)", places)
				db.executemany("insert into alias values (?,?)", aliases)
				places, aliases = [], []
		db.executemany("insert into place values (?,?,?,?,?,?,?,?,?,?,?)", places)
		db.executemany("insert into alias values (?,?)", aliases)
		db.execute("create index alias_norm on alias (norm)")
		counts = {"places": db.execute("select count(*) from place").fetchone()[0], "aliases": db.execute("select count(*) from alias").fetchone()[0]}
		for key, value in {**counts, "built": datetime.datetime.now().isoformat(timespec="seconds"), "source": source_note or "GeoNames cities500", "attribution": ATTRIBUTION}.items():
			db.execute("insert into meta values (?, ?)", (key, str(value)))
		db.commit()
	except Exception:
		db.close()
		os.remove(temporary)
		raise
	db.close()
	os.replace(temporary, target)
	return counts


def _download(name: str) -> bytes:
	with urllib.request.urlopen(BASE + name, timeout=300) as response:  # noqa: S310 (a fixed https address)
		return response.read()


def build(force: bool = False) -> dict:
	"""Downloads GeoNames' files and builds the list for this site (about a minute, 14 MB down, 50 MB on disk). Does nothing if it is already built, unless `force`."""
	if ready() and not force:
		return {"places": int(_meta().get("places") or 0), "already": True}
	raw = {name: _download(name) for name in SOURCES}
	with zipfile.ZipFile(io.BytesIO(raw["cities500.zip"])) as archive:
		cities = archive.read("cities500.txt").decode("utf-8")
	counts = build_from_text(cities, raw["admin1CodesASCII.txt"].decode("utf-8"), raw["admin2Codes.txt"].decode("utf-8"), raw["countryInfo.txt"].decode("utf-8"), path(),
							 source_note=f"{BASE} ({', '.join(SOURCES)})")
	print(f"Places built: {counts['places']} places, {counts['aliases']} names ({ATTRIBUTION})")
	return counts


def _connect() -> sqlite3.Connection:
	if not ready():
		raise PlacesNotReady(_("The list of places is not set up on this site yet. Ask whoever looks after the site to run: bench --site <site> execute raftor_astrohq.places.build"))
	db = sqlite3.connect(f"file:{path()}?mode=ro", uri=True)
	db.row_factory = sqlite3.Row
	return db


def _meta() -> dict:
	db = _connect()
	try:
		return {row["key"]: row["value"] for row in db.execute("select key, value from meta")}
	finally:
		db.close()


# ---- looking a place up ----
def _km(a, b) -> float:
	import math

	dlat, dlon = math.radians(b["lat"] - a["lat"]), math.radians(b["lon"] - a["lon"])
	h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a["lat"])) * math.cos(math.radians(b["lat"])) * math.sin(dlon / 2) ** 2
	return 12742 * math.asin(math.sqrt(h))


def _parts(text: str) -> list[list[str]]:
	"""The ways to read the text as [town, qualifier, qualifier...], best first: split at the commas (and at brackets and dashes); if it has no
	commas, "Pune Maharashtra" is read as the town "Pune" and the qualifier "Maharashtra", trying the town as one word, two, and so on from the longest."""
	cleaned = re.sub(r"[()\[\];|/\-–—]+", ",", str(text or ""))
	comma = [normal(part) for part in cleaned.split(",")]
	comma = [part for part in comma if part]
	if not comma:
		return []
	readings = [comma]
	if len(comma) == 1:
		words = comma[0].split()
		for cut in range(len(words) - 1, 0, -1):
			readings.append([" ".join(words[:cut]), " ".join(words[cut:])])
	return readings


def _matches(qualifier: str, place) -> bool:
	"""Does this qualifier (a district, a state or a country, or a short form of one) fit this place?"""
	if qualifier in (normal(place["country"]), place["cc"].lower(), normal(place["admin1"]), normal(place["admin2"]), place["admin1_code"].lower() if place["admin1_code"].isalpha() else None):
		return True
	if COUNTRY_FORMS.get(qualifier) == place["cc"]:
		return True
	return place["cc"] == "IN" and INDIA_STATE_FORMS.get(qualifier) == normal(place["admin1"])


def _label(place) -> str:
	return ", ".join(part for part in (place["name"], place["admin2"] if place["admin2"] and place["admin2"] != place["name"] else "", place["admin1"], place["country"]) if part)


def _candidates(db, town: str, qualifiers: list[str]) -> list:
	rows = db.execute("select distinct p.* from alias a join place p on p.id = a.place_id where a.norm = ?", (town,)).fetchall()
	return [row for row in rows if all(_matches(q, row) for q in qualifiers)]


def _one_of(candidates: list, town: str):
	"""The place meant among these, or an exception saying which to choose from."""
	groups = []  # places of the same name that are really one place: the biggest of each stands for it
	for place in sorted(candidates, key=lambda p: -(p["pop"] or 0)):
		if not any(_km(place, kept) < SAME_PLACE_KM for kept in groups):
			groups.append(place)
	if len(groups) == 1:
		return groups[0]
	top, second = groups[0], groups[1]
	if (top["pop"] or 0) >= BIG_ENOUGH and (top["pop"] or 0) >= MUCH_BIGGER * max(second["pop"] or 0, 1):
		return top
	shown = [_label(p) for p in groups[:MAX_OPTIONS]]
	raise PlaceAmbiguous(_("More than one place is called {0}: {1}. Please write the town and its state, for example {2}.").format(
		town.title(), "; ".join(shown), shown[0]))


def offset_hours(tz: str, on: datetime.datetime) -> float:
	"""Hours east of Greenwich in force in this time zone at this local date and time."""
	try:
		delta = ZoneInfo(tz).utcoffset(on)
	except (ZoneInfoNotFoundError, KeyError, ValueError):
		delta = None
	if delta is None:
		raise PlaceNotFound(_("The time zone of that place is not known."))
	return delta.total_seconds() / 3600.0


def _moment(on: datetime.datetime | datetime.date | str) -> datetime.datetime:
	if isinstance(on, str):
		on = frappe.utils.get_datetime(on)
	if not isinstance(on, datetime.datetime):
		on = datetime.datetime(on.year, on.month, on.day, 12, 0)
	return on


def _as_place(row, on: datetime.datetime) -> dict:
	return {"id": row["id"], "name": _label(row), "latitude": row["lat"], "longitude": row["lon"], "timezone": row["tz"], "timezone_offset": offset_hours(row["tz"], on), "population": row["pop"]}


def lookup(text: str, on: datetime.datetime | datetime.date | str) -> dict:
	"""{"id", "name", "latitude", "longitude", "timezone", "timezone_offset", "population"} for the place written in `text`, with the time zone offset in force
	on `on` (the local date and time of birth). Raises PlaceNotFound (nothing fits, with what to try), PlaceAmbiguous (it lists the choices) or
	PlacesNotReady (the list has not been built here)."""
	on = _moment(on)
	readings = _parts(text)
	if not readings:
		raise PlaceNotFound(_("Please write the place of birth in English letters, for example Pune, Maharashtra.") if str(text or "").strip() else _("Please write the place of birth."))
	db = _connect()
	try:
		ambiguity = None
		for reading in readings:
			found = _candidates(db, reading[0], reading[1:])
			if not found:
				continue
			try:
				place = _one_of(found, reading[0])
			except PlaceAmbiguous as error:
				ambiguity = ambiguity or error
				continue
			return _as_place(place, on)
		if ambiguity:
			raise ambiguity
		town = readings[0][0]
		if len(readings[0]) > 1 and _candidates(db, town, []):
			raise PlaceNotFound(_("{0} is not found in {1}. Check the spelling of the state or country, or leave it out.").format(town.title(), ", ".join(q.title() for q in readings[0][1:])))
		raise PlaceNotFound(_("We could not find {0}. Check the spelling, write the town and its state (for example Pune, Maharashtra), or use the nearest bigger town.").format(readings[0][0].title() or text))
	finally:
		db.close()


def by_id(place_id, on: datetime.datetime | datetime.date | str) -> dict:
	"""The place with this id in the list (the `id` that `lookup` and `suggest` give), as `lookup` gives it. Raises PlaceNotFound when there is none."""
	try:
		number = int(place_id)
	except (TypeError, ValueError):
		raise PlaceNotFound(_("That place is not in the list.")) from None
	db = _connect()
	try:
		row = db.execute("select * from place where id = ?", (number,)).fetchone()
	finally:
		db.close()
	if not row:
		raise PlaceNotFound(_("That place is not in the list."))
	return _as_place(row, _moment(on))


def suggest(text: str, limit: int = 6) -> list[dict]:
	"""The places whose name starts with what has been typed so far, best first: [{"id", "name", "region"}] ("Mumbai", "Maharashtra, India"). A name written exactly comes first, then the places whose
	own name starts with it, then the others, the bigger towns before the smaller. Nothing for less than two letters."""
	typed = normal(text)
	if len(typed) < 2 or not ready():
		return []
	db = _connect()
	try:
		rows = db.execute("select distinct p.* from alias a join place p on p.id = a.place_id where a.norm like ? limit 400", (typed + "%",)).fetchall()
		exact = {r["place_id"] for r in db.execute("select place_id from alias where norm = ? limit 400", (typed,)).fetchall()}
	finally:
		db.close()
	ranked = sorted(rows, key=lambda r: (r["id"] not in exact, not normal(r["name"]).startswith(typed), -(r["pop"] or 0)))
	plain = lambda row: ", ".join(part for part in (row["admin1"], row["country"]) if part)
	same = {}  # the places that would read the same ("Rampur, Uttar Pradesh, India"), to tell apart the ones that are not the one town listed twice
	for row in ranked:
		same.setdefault((normal(row["name"]), plain(row)), []).append(row)
	out = []
	for row in ranked:
		group = same[(normal(row["name"]), plain(row))]
		if any(_km(row, other) > SAME_PLACE_KM for other in group):  # more than one town of this name here: say which district
			region = ", ".join(part for part in (row["admin2"] if row["admin2"] != row["name"] else "", row["admin1"], row["country"]) if part)
		else:
			region = plain(row)
		if any(item["name"] == row["name"] and item["region"] == region for item in out):
			continue  # the same town listed twice (see SAME_PLACE_KM)
		out.append({"id": row["id"], "name": row["name"], "region": region})
		if len(out) >= limit:
			break
	return out


NEAR_KM = 60  # how far from a point to look for a town when someone shares where they are
SMALL_TOWN = 20000  # a town this big or bigger is preferred to a nearer village


def near(latitude: float, longitude: float, on: datetime.datetime | datetime.date | str) -> dict | None:
	"""The town nearest to a point, as `lookup` gives it: the nearest of the places of 20,000 people and more within 60 km, else the nearest place of any size within 60 km, else None."""
	try:
		lat, lon = float(latitude), float(longitude)
	except (TypeError, ValueError):
		return None
	if not (-90 <= lat <= 90 and -180 <= lon <= 180) or not ready():
		return None
	spread = NEAR_KM / 111.0
	db = _connect()
	try:
		rows = db.execute("select * from place where lat between ? and ? and lon between ? and ?", (lat - spread, lat + spread, lon - spread * 3, lon + spread * 3)).fetchall()
	finally:
		db.close()
	here = {"lat": lat, "lon": lon}
	close = sorted(((_km(here, row), row) for row in rows), key=lambda pair: pair[0])
	close = [pair for pair in close if pair[0] <= NEAR_KM]
	big = [pair for pair in close if (pair[1]["pop"] or 0) >= SMALL_TOWN]
	pick = (big or close or [None])[0]
	return _as_place(pick[1], _moment(on)) if pick else None


def problem(text: str, on: datetime.datetime | datetime.date | str) -> str:
	"""A sentence saying what is wrong with this place, or "" when it is found (or when the list is not set up here, so that a sale is never refused for it)."""
	try:
		lookup(text, on)
	except PlacesNotReady:
		return ""
	except PlaceNotFound as error:
		return str(error)
	return ""
