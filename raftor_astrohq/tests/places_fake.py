"""A stand-in for the astrology service's places (its four PLACE_ opcodes), for the tests of what only needs a town: a few towns, answered in the shapes the service answers in.
What the service does with its real list (the order of a search, a name that two towns share, a point near a town) is tested in the service: raftor_apimanager.tests.test_astrology_places."""
import datetime
from unittest import mock
from zoneinfo import ZoneInfo

import frappe

from raftor_astrohq import astrology, places
from raftor_astrohq.tests.helpers import AstroTestCase

TOWNS = {  # id: (the name as the service gives it, latitude, longitude, time zone, population)
	1: ("Pune, Maharashtra, India", 18.51957, 73.85535, "Asia/Kolkata", 3124458),
	10: ("London, England, United Kingdom", 51.50853, -0.12574, "Europe/London", 8961989),
	19: ("Delhi, Delhi, India", 28.66667, 77.21667, "Asia/Kolkata", 10927986),
	21: ("Kathmandu, Bagmati, Nepal", 27.70169, 85.3206, "Asia/Kathmandu", 1442271),
	22: ("Mumbai, Maharashtra, India", 19.07283, 72.88261, "Asia/Kolkata", 12691836),
}


def place(number: int, at: str) -> dict:
	label, lat, lon, tz, pop = TOWNS[number]
	moment = datetime.datetime.fromisoformat(at if "T" in at else at + "T12:00")
	return {"id": number, "name": label, "latitude": lat, "longitude": lon, "timezone": tz, "timezone_offset": ZoneInfo(tz).utcoffset(moment).total_seconds() / 3600.0, "population": pop}


def answer(payload: dict, s=None, must_be_on: bool = True) -> dict:
	opcode, query = payload["opcode"], payload["place"]
	at = query.get("at") or "2026-10-24"
	if opcode == "PLACE_GET":
		if int(query["id"]) not in TOWNS:
			raise astrology.AstrologyRefused("That place is not in the list.")
		return {"place": place(int(query["id"]), at)}
	if opcode == "PLACE_FIND":
		town = places.normal(str(query["text"]).split(",")[0])
		found = [n for n, row in TOWNS.items() if places.normal(row[0].split(",")[0]) == town]
		if not found:
			raise astrology.AstrologyRefused(f"We could not find {town.title()}. Check the spelling, write the town and its state (for example Pune, Maharashtra), or use the nearest bigger town.")
		return {"place": place(max(found, key=lambda n: TOWNS[n][4]), at)}
	if opcode == "PLACE_SEARCH":
		typed = places.normal(query["text"])
		return {"places": [{"id": n, "name": row[0].split(",")[0], "region": ", ".join(row[0].split(", ")[-2:])} for n, row in sorted(TOWNS.items(), key=lambda kv: -kv[1][4])
						   if len(typed) >= 2 and places.normal(row[0]).startswith(typed)][: query.get("limit") or 6]}
	if opcode == "PLACE_NEAR":
		close = [n for n, row in TOWNS.items() if abs(row[1] - query["latitude"]) < 0.5 and abs(row[2] - query["longitude"]) < 0.5]
		return {"place": place(close[0], at) if close else None}
	raise AssertionError(f"not a place opcode: {opcode}")


class PlacesCase(AstroTestCase):
	"""A few towns from a stand-in for the service, and a clean cache of what was asked of it."""

	def setUp(self):
		super().setUp()
		self.places_asked = []  # what was asked of the stand-in service

		def spy(payload, s=None, must_be_on=True):
			self.places_asked.append(payload)
			return answer(payload, s, must_be_on)

		patcher = mock.patch.object(astrology, "_ask", spy)
		patcher.start()
		self.addCleanup(patcher.stop)
		frappe.cache().delete_keys("astro_places")
		self.addCleanup(lambda: frappe.cache().delete_keys("astro_places"))
