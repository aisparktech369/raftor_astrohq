"""The tool that lets the numerology guide work out a number: calculate_numerology.

The sums are the engine's (astrology.numerology): the guide never adds numbers or counts letters itself. It only reads, and it gets what the numbers are said to mean (the engine's `reading`), never the working.
The guide asks for one part at a time (its conversation goes step by step), and the part that links a number to its planet also looks up what the shop offers for that planet, so the cards under the answer are real products.
"""

import re
from typing import Any, Dict

from frappe_assistant_core.core.base_tool import BaseTool

PARTS = ("birth", "more", "lucky", "name", "period", "year", "links")


def _part(reading: dict, part: str) -> dict:
	"""Only the part of the reading asked for, so a small model is given one thing to say."""
	birth = reading.get("birth") or {}
	if part == "birth":
		keys = ("number", "day", "compound", "headline", "summary", "strengths", "watch", "care")
		return {"birth": {k: birth.get(k) for k in keys if birth.get(k)}}
	if part == "more":
		return {"more": {"famous": (birth.get("famous") or [])[:4], "music": birth.get("music")}}
	if part == "lucky":
		keys = ("your_dates", "weekdays", "weekday_note", "colours", "avoid_colours", "jewels", "friendly_numbers")
		return {"lucky": {k: birth.get(k) for k in keys if birth.get(k)}}
	if part == "period":
		return {"period": reading.get("period")}
	if part == "year":
		return {"year": reading.get("year")}
	if part == "name":
		return {"name": reading.get("name")}
	return {}


def _shop(links: dict) -> dict:
	"""What the shop offers for the planet's gem and Rudraksha, and the pooja for it: the same shapes the shop and service tools give, so the cards are made from them."""
	out: Dict[str, Any] = {"items": [], "services": []}
	try:
		from frappe_tools.catalog.webshop import SearchWebshopProducts
	except ImportError:
		return out
	search = SearchWebshopProducts()
	gem = links.get("gem") or ""
	alias = re.search(r"\(([^)]+)\)", gem)
	terms = [re.sub(r"\(.*", "", gem).split(",")[0].split(";")[0].strip()] + ([alias.group(1)] if alias else [])
	terms += [f"{n} mukhi" for n in re.findall(r"(\d+)\s*mukhi", links.get("rudraksha") or "")]
	for term in terms:
		if not term:
			continue
		try:
			found = search.execute({"search_term": term, "limit": 2}).get("items") or []
		except Exception:
			found = []
		out["items"] += [i for i in found if i not in out["items"]]
	try:
		from raftor_astrohq.assistant_tools import services

		word = ((links.get("pooja") or "").strip().split() or [""])[0].lower()
		if word:
			out["services"] = [services._card(row) for row in services._everything() if word in f"{row['title']} {row.get('tag', '')}".lower()][:2]
	except Exception:
		pass
	return out


class CalculateNumerology(BaseTool):
	def __init__(self):
		super().__init__()
		self.name = "calculate_numerology"
		self.description = (
			"Numerology by code: give the day of the month for the birth number, and a name in Latin letters for the name number. Ask for one `part` at a time: "
			"'birth' (the birth number, its headline, strengths and what to watch), 'name' (the name number, each word's compound and whether it fits the birth number), "
			"'links' (the planet of the number and the gem, Rudraksha and pooja the tradition links with it, with what the shop offers), 'lucky' (dates, weekdays, colours, stones), "
			"'more' (famous people of the number, music), 'period' (the zodiac period, needs the month too), 'year' (the year number, needs the year). "
			"Only results and their meanings come back. Use it for every number: never add numbers or count letters yourself."
		)
		self.requires_permission = None
		self.annotations = {"module": "astrohq.numerology", "tags": ["read", "calculate"], "tier": "T2"}
		self.inputSchema = {
			"type": "object",
			"properties": {
				"day": {"type": "integer", "minimum": 1, "maximum": 31, "description": "The day of the month the person was born (1-31)"},
				"month": {"type": "integer", "minimum": 1, "maximum": 12, "description": "The month of birth (1-12), only for the zodiac period"},
				"year": {"type": "integer", "minimum": 1800, "maximum": 2200, "description": "The year of birth, only for the year number"},
				"name": {"type": "string", "description": "The name in Latin letters, in the spelling the person chose, for example 'John Smith'"},
				"part": {"type": "string", "enum": list(PARTS), "description": "Which part to return (default 'birth', or 'name' when only a name is given)"},
			},
		}

	def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
		from raftor_astrohq import astrology

		part = arguments.get("part") or ("birth" if arguments.get("day") else "name")
		if part not in PARTS:
			part = "birth"
		try:
			answer = astrology.numerology(arguments.get("day"), arguments.get("month"), arguments.get("name"), arguments.get("year"))
		except astrology.AstrologyRefused as error:
			return {"found": False, "message": str(error)}
		except astrology.AstrologyUnavailable:
			return {"found": False, "message": "The numerology calculator is not available right now. Say so, and offer a live numerologist."}
		reading = answer.get("reading") or {}
		if part == "links":
			birth = reading.get("birth") or {}
			links = birth.get("tradition_links") or {}
			return {"found": True, "links": {"number": birth.get("number"), "planet": birth.get("planet"), "planet_note": birth.get("planet_note"), **links}, **_shop(links),
					"note": "Name the gem, the Rudraksha and the pooja in your reply by the names given here, as what the tradition links with the planet. They are not a fix."}
		return {"found": True, **_part(reading, part), "safeguard": reading.get("safeguard")}
