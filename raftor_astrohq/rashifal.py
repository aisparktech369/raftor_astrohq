"""The daily rashifal: a short reading for each of the twelve signs, every morning, shown as twelve cards at the top of the Consult page.

Where the words come from, in three steps, so that the writer is never asked to invent the sky:

1. The astrology engine says where the nine planets stand at sunrise (CORE_BASIC for a moment: `sky`). Nothing is worked out by an AI.
2. For each sign, here: the house each planet is in counted from that sign, whether that is a good house for it by the traditional rule of transits from the Moon sign (gochar: GOOD below),
   and from them how each part of life leans (love, money, work, health: positive, mixed or careful), the lucky colour and the lucky number (`facts`).
3. The hub's text-to-text puts those facts into plain words in English and in Hindi (`write`). It is told to use nothing else, and what it sends back is checked (`clean`) before it is kept.

A reading is kept as a Daily Rashifal record, a Draft until staff publish it (Daily Rashifal Settings can publish at once). Only Published readings are shown (`cards`).

One reading per sign for the whole country: the sky at sunrise at the town of the Panchang (Delhi when none is set). The Moon changes sign during a day, so the reading says what the day looks like from sunrise.
Written by a program from traditional rules: it is guidance, not a promise, and an astrologer should read a few days against a printed rashifal before it is published."""
import datetime
import json
import re

import frappe
import requests
from frappe import _
from frappe.utils import now_datetime, strip_html_tags

from raftor_astrohq import astrology, panchang, places

SETTINGS, DOCTYPE = "Daily Rashifal Settings", "Daily Rashifal"
GATEWAY = "/api/method/raftor_apimanager.gateway.call"
DELHI = {"latitude": 28.6139, "longitude": 77.209, "timezone": "Asia/Kolkata", "name": "Delhi"}
# the twelve signs: number, English, Sanskrit name, Hindi, mark
RASHIS = [
	(1, "Aries", "Mesha", "मेष", "♈"), (2, "Taurus", "Vrishabha", "वृषभ", "♉"), (3, "Gemini", "Mithuna", "मिथुन", "♊"), (4, "Cancer", "Karka", "कर्क", "♋"),
	(5, "Leo", "Simha", "सिंह", "♌"), (6, "Virgo", "Kanya", "कन्या", "♍"), (7, "Libra", "Tula", "तुला", "♎"), (8, "Scorpio", "Vrishchika", "वृश्चिक", "♏"),
	(9, "Sagittarius", "Dhanu", "धनु", "♐"), (10, "Capricorn", "Makara", "मकर", "♑"), (11, "Aquarius", "Kumbha", "कुंभ", "♒"), (12, "Pisces", "Meena", "मीन", "♓"),
]
# the engine's two-letter start of a planet's name, the planet, and the houses (counted from the sign) that are good for it in a transit
PLANETS = [("Su", "Sun"), ("Mo", "Moon"), ("Ma", "Mars"), ("Me", "Mercury"), ("Ju", "Jupiter"), ("Ve", "Venus"), ("Sa", "Saturn"), ("Ra", "Rahu"), ("Ke", "Ketu")]
GOOD = {"Sun": (3, 6, 10, 11), "Moon": (1, 3, 6, 7, 10, 11), "Mars": (3, 6, 11), "Mercury": (2, 4, 6, 8, 10, 11), "Jupiter": (2, 5, 7, 9, 11),
		"Venus": (1, 2, 3, 4, 5, 8, 9, 11, 12), "Saturn": (3, 6, 11), "Rahu": (3, 6, 10, 11), "Ketu": (3, 6, 11)}
# each sign's element and ruling planet (they give each reading its own flavour)
CHARACTER = {1: ("fire", "Mars"), 2: ("earth", "Venus"), 3: ("air", "Mercury"), 4: ("water", "Moon"), 5: ("fire", "Sun"), 6: ("earth", "Mercury"),
			 7: ("air", "Venus"), 8: ("water", "Mars"), 9: ("fire", "Jupiter"), 10: ("earth", "Saturn"), 11: ("air", "Saturn"), 12: ("water", "Jupiter")}
RANK = {"positive": 2, "mixed": 1, "careful": 0}
# which planets speak for which part of life
AREAS = {"love": ("Venus", "Moon", "Jupiter"), "money": ("Jupiter", "Mercury", "Venus"), "work": ("Sun", "Saturn", "Mars", "Rahu"), "health": ("Moon", "Mars", "Saturn", "Sun")}
# the lucky colour and number: those of the first planet in this order that is in a good house
LUCKY = [("Jupiter", "Yellow", "पीला", 3), ("Venus", "White", "सफ़ेद", 6), ("Moon", "Silver white", "चाँदी जैसा सफ़ेद", 2), ("Mercury", "Green", "हरा", 5),
		 ("Sun", "Orange", "नारंगी", 1), ("Mars", "Red", "लाल", 9), ("Saturn", "Blue", "नीला", 8), ("Ketu", "Brown", "भूरा", 7), ("Rahu", "Grey", "स्लेटी", 4)]
SWATCH = {"Yellow": "yellow", "White": "white", "Silver white": "silver", "Green": "green", "Orange": "orange", "Red": "red", "Blue": "blue", "Brown": "brown", "Grey": "grey"}  # the lucky colour by the name websitehq knows it by (its --rfhq-swatch-* tokens): no colour value is kept here
LABELS = {"en": {"love": "Love", "money": "Money", "work": "Work", "health": "Health", "colour": "Lucky colour", "number": "Number", "tap": "Tap to reveal", "good": "A good day", "steady": "A steady day", "slow": "Go slowly"},
		  "hi": {"love": "प्रेम", "money": "धन", "work": "कार्य", "health": "स्वास्थ्य", "colour": "शुभ रंग", "number": "अंक", "tap": "देखने के लिए छुएँ", "good": "शुभ दिन", "steady": "सामान्य दिन", "slow": "धीरे चलें"}}
PARTS = ("summary", "love", "money", "work", "health")
LIMITS = {"summary": 110, "love": 90, "money": 90, "work": 90, "health": 90}
DEVANAGARI = re.compile("[ऀ-ॿ]")
SYSTEM = (
	"You write a short daily rashifal (Vedic horoscope) for one sign, for ordinary readers, in plain, warm, calm words. "
	"You are given the day's facts for the sign as JSON. Use only those facts: say nothing about planets, houses or any detail that is not in them, and do not name planets, houses or numbers. "
	"For each of love, money, work and health, follow its 'lean' (positive: encouraging; mixed: balanced, one thing to go slowly on; careful: gentle caution, never fear). "
	"Never promise, never predict death, illness, accidents, losses or court cases, never give medical, legal or financial advice, and never ask the reader to buy or pay for anything. "
	"Give this sign's reading its own flavour from its element and ruling planet, without naming the planet, begin the summary in its own way (not with \"Today calls for\" or \"Today brings\"), and give one small practical thing to do in at least two parts. Write each part as one sentence: the summary of at most 14 words, every other part of at most 11 words. The Hindi is natural simple Hindi in Devanagari, not a word-for-word copy. "
	'Answer with JSON only, in exactly this shape: {"en": {"summary": "", "love": "", "money": "", "work": "", "health": ""}, "hi": {"summary": "", "love": "", "money": "", "work": "", "health": ""}}'
)


class RashifalUnavailable(frappe.ValidationError):
	pass


def settings() -> frappe._dict:
	doc = frappe.get_single(SETTINGS)
	return frappe._dict(enabled=bool(doc.enabled), publish_at_once=bool(doc.publish_at_once), address=(doc.hub_address or "").strip().rstrip("/"), site=(doc.hub_site or "").strip(),
						key=doc.get_password("hub_key", raise_exception=False) or "", api_name=(doc.api_name or "").strip() or "text-to-text", timeout=int(doc.timeout_seconds or 90))


def rashi(number: int) -> tuple:
	return RASHIS[number - 1]


# ---- the sky and the facts of a sign ----
def place_for(on_date: datetime.date | None = None) -> dict:
	"""The town whose sunrise the sky is taken at: the Panchang's town, else Delhi."""
	return panchang.default_place(on_date) or DELHI


def today() -> datetime.date:
	return panchang.today(place_for()) if panchang.default_place() else datetime.date.today()


def sky(on_date: datetime.date) -> dict:
	"""Where the planets stand at sunrise of this day: {'positions': {planet: {'sign': 1..12, 'retrograde': bool}}, 'nakshatra': the Moon's, 'sunrise': 'HH:MM', 'weekday': 'Wednesday'}.
	Raises astrology.AstrologyUnavailable when the engine cannot be asked."""
	where = place_for(on_date)
	rise = datetime.datetime(on_date.year, on_date.month, on_date.day, 6, 0)
	try:  # the real sunrise when the Panchang can say it, else six in the morning
		rise = panchang._moment(panchang.day(on_date, where)["sun"]["rise"]).replace(tzinfo=None)
	except Exception:
		pass
	offset = places.offset_hours(where["timezone"], rise)
	answer = astrology.chart({"year": rise.year, "month": rise.month, "day": rise.day, "hour": rise.hour, "minute": rise.minute, "second": 0,
							  "latitude": where["latitude"], "longitude": where["longitude"], "timezone_offset": offset}, "CORE_BASIC")
	positions, nakshatra = {}, ""
	names = dict(PLANETS)
	for row in answer.get("planetary_positions") or []:
		planet = names.get(str(row.get("planet", ""))[:2])
		if planet and row.get("sign_index") is not None:
			positions[planet] = {"sign": int(row["sign_index"]) + 1, "retrograde": bool(row.get("is_retrograde"))}
			if planet == "Moon":
				nakshatra = str(row.get("nakshatra") or "")
	if len(positions) != len(PLANETS):
		raise astrology.AstrologyUnavailable(_("The astrology service did not give all nine planets."))
	return {"positions": positions, "nakshatra": nakshatra, "sunrise": rise.strftime("%H:%M"), "weekday": on_date.strftime("%A")}


def house(planet_sign: int, from_sign: int) -> int:
	"""The house a planet is in, counted from a sign (the sign itself is the first)."""
	return (planet_sign - from_sign) % 12 + 1


def score(share: float) -> int:
	"""A share of good planets (0 to 1) as a bar from 35 to 95: never near empty (a bar is a mood, not a verdict) and never full, because a sky is never all one thing."""
	return round(35 + min(max(share, 0.0), 1.0) * 60)


def lean(share: float) -> str:
	return "positive" if share >= 0.67 else "careful" if share <= 0.34 else "mixed"


def facts(sky_: dict, number: int) -> dict:
	"""What the writer is given for one sign: how each part of life leans, the lucky colour and number, and the Moon's nakshatra. Worked out here, from the sky only."""
	good = {}
	for planet, where in sky_["positions"].items():
		good[planet] = house(where["sign"], number) in GOOD[planet]
	shares = {area: sum(good[p] for p in planets) / len(planets) for area, planets in AREAS.items()}
	leans = {area: lean(share) for area, share in shares.items()}
	colour = next(((en, hi, n) for planet, en, hi, n in LUCKY if good.get(planet)), None) or LUCKY[0][1:]
	moon_house = house(sky_["positions"]["Moon"]["sign"], number)
	count, element_ruler = sum(good.values()), CHARACTER[number]
	best, worst = max(leans, key=lambda a: (RANK[leans[a]], -list(AREAS).index(a))), min(leans, key=lambda a: (RANK[leans[a]], list(AREAS).index(a)))
	return {"sign": rashi(number)[1], "element": element_ruler[0], "ruling_planet": element_ruler[1], "weekday": sky_["weekday"], "moon_nakshatra": sky_["nakshatra"],
			"moon_house_from_sign": moon_house, "day": "a good day" if count >= 6 else "a day to go slowly" if count <= 3 else "a steady day", "lean": leans, "scores": {area: score(share) for area, share in shares.items()},
			"best_area": best if leans[best] != "careful" else "", "area_to_handle_gently": worst if leans[worst] != "positive" else "",
			"planets_in_good_houses": count, "lucky_colour": colour[0], "lucky_colour_hindi": colour[1], "lucky_number": colour[2]}


# ---- the writer ----
def clean(text: str, limit: int) -> str:
	return re.sub(r"\s+", " ", strip_html_tags(str(text or ""))).strip()[:limit].strip()


def parse(content: str) -> dict:
	"""The writer's answer as {'en': {...}, 'hi': {...}} of clean sentences, or ValueError when it is not what was asked for."""
	text = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(content or "").strip())
	try:
		data = json.loads(text)
	except ValueError:
		raise ValueError("not JSON") from None
	out = {}
	for language in ("en", "hi"):
		part = data.get(language) if isinstance(data, dict) else None
		if not isinstance(part, dict):
			raise ValueError(f"no {language}")
		out[language] = {key: clean(part.get(key), LIMITS[key]) for key in PARTS}
		if not all(out[language].values()):
			raise ValueError(f"{language} is missing a part")
		has_devanagari = [bool(DEVANAGARI.search(value)) for value in out[language].values()]
		if (language == "hi") != all(has_devanagari) or (language == "en" and any(has_devanagari)):
			raise ValueError(f"{language} is in the wrong script")
	return out


def write(facts_: dict, s: frappe._dict | None = None) -> tuple[dict, str]:
	"""The words for one sign, from the hub's text-to-text: ({'en': {...}, 'hi': {...}}, the model's name)."""
	s = s or settings()
	if not (s.address and s.key):
		raise RashifalUnavailable(_("The writer is not set up: see Daily Rashifal Settings."))
	headers = {"X-Api-Key": s.key} | ({"X-Frappe-Site-Name": s.site} if s.site else {})
	body = {"api_name": s.api_name, "payload": {"system": SYSTEM, "prompt": json.dumps(facts_, ensure_ascii=False), "json_mode": True, "temperature": 0.6, "max_tokens": 900}}
	try:
		response = requests.post(s.address + GATEWAY, json=body, headers=headers, timeout=s.timeout)
		answer = response.json()
	except (requests.exceptions.RequestException, ValueError):
		raise RashifalUnavailable(_("The writer did not answer.")) from None
	data = answer.get("data") if isinstance(answer, dict) else None
	if response.status_code >= 400 or not isinstance(data, dict) or not data.get("content"):
		raise RashifalUnavailable(_("The writer refused or gave nothing."))
	return parse(data["content"]), str(data.get("model") or "")


# ---- the day's twelve ----
def write_day(on_date=None, manual: bool = False) -> dict:
	"""Write the readings of a day that have none yet (safe to run again: it keeps what is there). `manual` is a person pressing the button, who is answered even when the writing is switched off.
	Returns {'ok', 'message', 'made', 'failed'}."""
	s = settings()
	if not (s.enabled or manual):
		return {"ok": True, "message": _("Writing is switched off."), "made": 0, "failed": 0}
	on_date = frappe.utils.getdate(on_date) if on_date else today()
	have = set(frappe.get_all(DOCTYPE, filters={"for_date": on_date}, pluck="rashi_no"))
	todo = [n for n in range(1, 13) if n not in have]
	if not todo:
		return {"ok": True, "message": _("All twelve readings are there."), "made": 0, "failed": 0}
	try:
		the_sky = sky(on_date)
	except (astrology.AstrologyUnavailable, astrology.AstrologyRefused) as error:
		frappe.log_error(title="Daily rashifal: the sky could not be had", message=str(error))
		return {"ok": False, "message": _("The astrology service could not say where the planets are."), "made": 0, "failed": len(todo)}
	made = failed = 0
	for number in todo:
		given = facts(the_sky, number)
		try:
			words, model = write(given, s)
		except (RashifalUnavailable, ValueError) as error:
			failed += 1
			frappe.log_error(title=f"Daily rashifal: {rashi(number)[1]} on {on_date} was not written", message=str(error))
			continue
		record = {"doctype": DOCTYPE, "for_date": on_date, "rashi_no": number, "rashi": rashi(number)[1], "status": "Published" if s.publish_at_once else "Draft",
				  "lucky_number": given["lucky_number"], "facts": json.dumps(given, ensure_ascii=False), "model": model, "written_on": now_datetime(),
				  "colour_en": given["lucky_colour"], "colour_hi": given["lucky_colour_hindi"], **{f"{area}_score": value for area, value in given["scores"].items()}}
		for language in ("en", "hi"):
			for part in PARTS:
				record[f"{part}_{language}"] = words[language][part]
		frappe.get_doc(record).insert(ignore_permissions=True)
		frappe.db.commit()
		made += 1
	return {"ok": not failed, "message": _("{0} written, {1} not written.").format(made, failed), "made": made, "failed": failed}


def daily() -> None:
	"""Scheduled (before sunrise, and again later for any that failed): the readings of today, on the long queue so that twelve answers have time."""
	if settings().enabled:
		frappe.enqueue("raftor_astrohq.rashifal.write_day", queue="long", timeout=1500, job_id=f"rashifal-{today()}-{now_datetime().hour}", deduplicate=True)


def publish_day(on_date=None) -> dict:
	"""Publish the Drafts of a day."""
	on_date = frappe.utils.getdate(on_date) if on_date else today()
	names = frappe.get_all(DOCTYPE, filters={"for_date": on_date, "status": "Draft"}, pluck="name")
	for name in names:
		frappe.db.set_value(DOCTYPE, name, "status", "Published")
	return {"ok": True, "message": _("{0} published.").format(len(names)), "published": len(names)}


# ---- what visitors see ----
def _language() -> str:
	return "hi" if str(frappe.local.lang or "en").lower().startswith("hi") else "en"


@frappe.whitelist(allow_guest=True, methods=["POST"])
def cards() -> dict:
	"""The twelve cards of the day as the fields of the Flip Card variant (websitehq gives it its layout and its theme; this gives only words, numbers and the name of a colour): the front is the sign (mark in `number`, name), the back is its reading. The newest Published day that is not older than yesterday;
	none when there is none (the section then shows nothing)."""
	earliest = today() - datetime.timedelta(days=1)
	day = frappe.db.get_value(DOCTYPE, {"status": "Published", "for_date": [">=", earliest]}, "for_date", order_by="for_date desc")
	if not day:
		return {"items": []}
	language = _language()
	other = "en" if language == "hi" else "hi"
	labels = LABELS[language]
	rows = {row.rashi_no: row for row in frappe.get_all(DOCTYPE, filters={"for_date": day, "status": "Published"}, fields=["*"])}
	items = []
	for number in sorted(rows):
		row = rows[number]
		names = {"en": rashi(number)[1], "hi": rashi(number)[3]}
		scores = {area: int(row.get(f"{area}_score") or 0) for area in AREAS}
		average = sum(scores.values()) / len(scores)
		mood = labels["good"] if average >= 66 else labels["slow"] if average <= 52 else labels["steady"]
		items.append({"number": rashi(number)[4] + "\ufe0e", "title": names[language], "meta": names[other],
					  "link_label": labels["tap"], "body": mood, "pills": "\n".join(f"{labels[area]}: {scores[area]}" for area in AREAS), "about": SWATCH.get(row.colour_en or "", ""),
					  "note": f"{labels['colour']}: {row.get(f'colour_{language}') or ''} · {labels['number']}: {row.lucky_number or ''}"})
	return {"items": items}

