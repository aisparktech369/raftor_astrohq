"""The days a person of astrohq follows, for servicehq's day reminders (servicehq/day_reminders.py does the rest: the records, the page, the schedule, the message).

This is only the domain: what a day is (the Panchang's tithi at sunrise, the weekday, a special day such as Ravi Pushya) and how a day matches what a person follows, in words. servicehq reads it through the hook
`servicehq_day_reminders` (`definition`).

A reminder holds when ANY thing it names holds on the day (it can name tithis, weekdays and special days: it is told on each of them):
  tithi (and the fortnight, unless Both)   the tithi at sunrise, as the Panchang says it and as a person keeps a vrat; the message also says when it begins and ends
  weekday                                  the day of the week
  special day                              Ravi Pushya (Sunday with Pushya), Guru Pushya (Thursday with Pushya), Sarvartha Siddhi and Amrit Siddhi (a weekday with its nakshatras); the nakshatra counts
                                           when it holds at sunrise or begins before the next sunrise
The day comes from the Panchang's engine answer at the Panchang's town (`panchang.day`); nothing is worked out by an AI. The rules of the special days are the commonly printed ones: an astrologer should
confirm them before this goes live."""
import datetime

import frappe
from frappe import _

from raftor_astrohq import panchang
from raftor_astrohq.panchang_panes import moment, when

P = "raftor_astrohq.day_reminders."
TITHIS = ["Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima", "Amavasya"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SPECIALS = ["Ravi Pushya", "Guru Pushya", "Sarvartha Siddhi", "Amrit Siddhi"]
# the nakshatras that make a weekday a Sarvartha Siddhi day, and the one that makes it an Amrit Siddhi day
SARVARTHA = {
	"Sunday": {"Ashwini", "Pushya", "Hasta", "Uttara Phalguni", "Uttara Ashadha", "Uttara Bhadrapada", "Mula"},
	"Monday": {"Rohini", "Mrigashira", "Pushya", "Anuradha", "Shravana"},
	"Tuesday": {"Ashwini", "Krittika", "Ashlesha", "Uttara Bhadrapada"},
	"Wednesday": {"Rohini", "Mrigashira", "Anuradha", "Hasta", "Krittika"},
	"Thursday": {"Ashwini", "Punarvasu", "Pushya", "Anuradha", "Revati"},
	"Friday": {"Ashwini", "Punarvasu", "Anuradha", "Shravana", "Revati"},
	"Saturday": {"Rohini", "Swati", "Shravana"},
}
AMRIT = {"Sunday": "Hasta", "Monday": "Mrigashira", "Tuesday": "Ashwini", "Wednesday": "Anuradha", "Thursday": "Pushya", "Friday": "Revati", "Saturday": "Rohini"}


def definition() -> dict:
	"""What servicehq asks for (hook servicehq_day_reminders): the form's fields and the dotted names of what to call."""
	return {
		"label": _("Days I follow"), "intro": _("Tap what you follow. You are told on each of them: any tithi you tap, any day, any special day."), "avatar": "\u263e",
		"fields": [
			{"name": "tithi", "label": _("Tithis I follow"), "type": "chips", "multiple": True, "grid": True, "options": TITHIS, "hint": _("Tap as many as you follow, for example Ashtami and Amavasya.")},
			{"name": "paksha", "label": _("Which fortnight"), "type": "chips", "segmented": True, "default": "Both", "options": [{"value": "Both", "label": _("Both")}, {"value": "Shukla", "label": _("Shukla")}, {"value": "Krishna", "label": _("Krishna")}],
			 "hint": _("Shukla is the bright half, Krishna the dark half. Purnima and Amavasya need no choice.")},
			{"name": "weekday", "label": _("Days of the week"), "type": "chips", "multiple": True, "options": [{"value": d, "label": _(d)[:3]} for d in WEEKDAYS]},
			{"name": "special", "label": _("Special days"), "type": "chips", "multiple": True, "options": SPECIALS},
		],
		"clean": P + "clean", "facts": P + "facts", "follows": P + "follows", "title": P + "title_of", "text": P + "text_for", "link": P + "link",
	}


def clean(values: dict) -> tuple[dict, dict]:
	"""What the person chose, checked: ({tithi: [...], paksha, weekday: [...], special: [...]}, {field: what is wrong})."""
	errors, rule = {}, {}
	for key, allowed, message in (("tithi", TITHIS, _("Choose tithis from the list.")), ("weekday", WEEKDAYS, _("Choose days from the list.")), ("special", SPECIALS, _("Choose special days from the list."))):
		given = _set(values.get(key))
		chosen = [name for name in allowed if name in given]  # only what the list has, once each, in the list's order
		if len(chosen) != len(set(given)):
			errors[key] = message
		rule[key] = chosen
	paksha = str(values.get("paksha") or "Both").strip()
	if paksha not in ("Both", "Shukla", "Krishna"):
		errors["paksha"] = _("Choose Shukla, Krishna or both.")
	if not any(rule.values()) and not errors:
		errors["tithi"] = _("Choose at least a tithi, a weekday or a special day.")
	rule["paksha"] = "Both" if set(rule["tithi"]) <= {"Purnima", "Amavasya"} else paksha
	return rule, errors


def link(date: datetime.date) -> str:
	"""The panchang of that day, with the web's usual port left off (https://site:443/... is the same page)."""
	url = frappe.utils.get_url("/panchang?date=" + date.isoformat())
	return url.replace(":443/", "/", 1) if url.startswith("https://") else url.replace(":80/", "/", 1)


# ---- the day ----
def facts(on_date: datetime.date) -> dict:
	"""What a reminder is matched against, for one day at the Panchang's town (raises when the engine cannot say: servicehq skips the day and tries again at the next run)."""
	place = panchang.default_place()
	if not place:
		raise panchang.PanchangBusy("The Panchang has no town set.")
	answer = panchang.day(on_date, place)
	next_rise = moment(answer["sun"]["next_rise"])
	nakshatras = {answer["nakshatra"]["name"]}
	following = answer["nakshatra"].get("next") or {}
	if following.get("name") and following.get("begins") and next_rise and moment(following["begins"]) < next_rise:
		nakshatras.add(following["name"])
	tithi = answer["tithi"]
	return {"date": on_date, "weekday": answer["weekday"], "tithi": tithi["name"], "paksha": tithi["paksha"], "tithi_begins": moment(tithi["begins"]), "tithi_ends": moment(tithi["ends"]),
			"nakshatras": nakshatras, "nakshatra": answer["nakshatra"]["name"]}


def specials(day: dict) -> list[str]:
	"""The special days this day is."""
	weekday, nakshatras = day["weekday"], day["nakshatras"]
	out = []
	if weekday == "Sunday" and "Pushya" in nakshatras:
		out.append("Ravi Pushya")
	if weekday == "Thursday" and "Pushya" in nakshatras:
		out.append("Guru Pushya")
	if nakshatras & SARVARTHA.get(weekday, set()):
		out.append("Sarvartha Siddhi")
	if AMRIT.get(weekday) in nakshatras:
		out.append("Amrit Siddhi")
	return out


def _set(value) -> list[str]:
	"""A choice, several as a list or as text (Ashtami,Amavasya), as a list."""
	parts = value if isinstance(value, (list, tuple, set)) else str(value or "").split(",")
	return [str(part).strip() for part in parts if str(part).strip()]


def _tithi_holds(reminder, day: dict) -> bool:
	return day["tithi"] in _set(reminder.get("tithi")) and (reminder.get("paksha") in (None, "", "Both") or day["paksha"] == reminder["paksha"])


def follows(reminder, day: dict) -> bool:
	"""Whether the day is one this reminder names: ANY of the things it names is enough (one of its tithis, one of its weekdays or one of its special days), and it must name at least one. A fortnight only narrows
	the tithis."""
	return _tithi_holds(reminder, day) or day["weekday"] in _set(reminder.get("weekday")) or bool(set(_set(reminder.get("special"))) & set(specials(day)))


def why(reminder, day: dict) -> str:
	"""Every part of the reminder that holds on this day, in words, for the message: Amavasya, a Tuesday, Ashtami (Krishna) and a Tuesday."""
	parts = []
	if _tithi_holds(reminder, day):
		parts.append(title_of({"tithi": day["tithi"], "paksha": reminder.get("paksha")}))
	parts += [name for name in _set(reminder.get("special")) if name in specials(day)]
	if day["weekday"] in _set(reminder.get("weekday")):
		parts.append(_("a {0}").format(_(day["weekday"])))
	return _(" and ").join(parts)


# ---- the words ----
def title_of(reminder) -> str:
	"""Ashtami (Krishna), Amavasya, Every Tuesday: everything the reminder names, one after another"""
	parts = []
	fortnight = reminder.get("paksha")
	for tithi in _set(reminder.get("tithi")):
		parts.append(tithi + (f" ({fortnight})" if fortnight in ("Shukla", "Krishna") and tithi not in ("Purnima", "Amavasya") else ""))
	parts += _set(reminder.get("special"))
	parts += [_("Every {0}").format(_(day)) for day in _set(reminder.get("weekday"))]
	return ", ".join(parts)


def text_for(reminder, day: dict, slot: str) -> str:
	"""What the message says: the day, which of the things you follow it is, and when the tithi begins and ends."""
	date = day["date"]
	label = date.strftime("%A %d %B")
	opening = _("Tomorrow, {0}, is {1}.") if slot == "evening" else _("Today, {0}, is {1}.")
	lines = [opening.format(label, why(reminder, day))]
	tithi = f"{day['tithi']} ({day['paksha']})" if day["tithi"] not in ("Purnima", "Amavasya") else day["tithi"]
	if day["tithi_begins"] and day["tithi_ends"]:
		lines.append(_("The tithi is {0}: it begins {1} and ends {2}.").format(tithi, when(day["tithi_begins"], date), when(day["tithi_ends"], date)))
	if set(_set(reminder.get("special"))) & set(specials(day)):
		lines.append(_("Nakshatra: {0}.").format(day["nakshatra"]))
	return " ".join(lines)
