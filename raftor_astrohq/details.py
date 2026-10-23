"""What astrohq asks for when someone books, and its one real rule (declared in vocabulary.py)."""
import datetime
import unicodedata

import frappe
from frappe import _
from frappe.utils import getdate, today

from raftor_astrohq import places, profiles

def sankalp() -> list[dict]:
	return [
		{"name": "sankalp_name", "label": _("Name for the sankalp"), "required": True, "placeholder": _("Full name as you want it spoken")},
		{"name": "gotra", "label": _("Gotra"), "required": True, "placeholder": _("e.g. Kashyap"), "hint": _("If you do not know it, write Kashyap or ask your family.")},
	]


def wish() -> dict:
	return {"name": "wish", "label": _("Your wish or purpose"), "type": "textarea", "placeholder": _("Optional")}


def birth_details() -> list[dict]:
	"""What a report made from someone's birth asks: who, the day, the time and the place."""
	return [
		{"name": "report_name", "label": _("Name"), "required": True, "placeholder": _("Full name for the report")},
		{"name": "birth_date", "label": _("Date of birth"), "type": "date", "required": True},
		{"name": "birth_time", "label": _("Time of birth"), "type": "time_text", "required": True, "placeholder": "HH:MM", "hint": _("If you do not know it, write 12:00.")},
		{"name": "birth_place", "label": _("Place of birth"), "required": True, "placeholder": _("Town or city")},
	]


# ---- the reports made from birth details (vocabulary.py "reports"; the makers are in reports.py) ----
EARLIEST_YEAR = 1800  # the star-position files cover 1800 to 2400; before that the engine's answers are not checked


def person_keys(prefix: str = "") -> dict[str, str]:
	"""The names of one person's answers in a report's details: a kundli report asks for one person (report_name, birth_date, ...), a match making report
	for two (boy_name, boy_birth_date, ... and girl_name, ...)."""
	return {"name": prefix + "name" if prefix else "report_name", "date": prefix + "birth_date", "time": prefix + "birth_time", "place": prefix + "birth_place"}


def person_fields(prefix: str = "", whose: str = "") -> list[dict]:
	"""One person's birth details as a report asks for them: who, the day, the exact time and the place, as a town and its state. The time is asked for
	and required: the lagna and the dasha change with it, and the Moon moves half a nakshatra between morning and evening, so a report from a guessed
	time can be wrong."""
	k = person_keys(prefix)
	own = (lambda word: f"{whose}{word}") if whose else (lambda word: word[:1].upper() + word[1:])
	return [
		{"name": k["name"], "label": own(_("name")), "required": True, "placeholder": _("Full name in English letters")},
		{"name": k["date"], "label": own(_("date of birth")), "type": "date", "required": True},
		{"name": k["time"], "label": own(_("time of birth")), "type": "time_text", "required": True, "placeholder": "HH:MM",
		 "hint": _("The exact time matters: the lagna and the dasha change with it. If you do not know it, ask your family or look at the birth certificate.")},
		{"name": k["place"], "label": own(_("place of birth")), "required": True, "placeholder": _("Town, State (e.g. Pune, Maharashtra)"),
		 "hint": _("Write the town and its state or country. If you are not sure of the town, the nearest bigger one will do.")},
	]


def kundli_fields() -> list[dict]:
	return person_fields()


def match_fields() -> list[dict]:
	return person_fields("boy_", _("Boy's ")) + person_fields("girl_", _("Girl's "))


def born_at(values: dict, prefix: str = "") -> datetime.datetime:
	"""The local date and time of birth in a report's answers."""
	k = person_keys(prefix)
	day = getdate(values[k["date"]])
	hour, minute = (int(part) for part in values[k["time"]].split(":")[:2])
	return datetime.datetime(day.year, day.month, day.day, hour, minute)


def in_english_letters(text: str) -> bool:
	"""Whether every letter of the text is a Latin one (accents are fine): the reports are printed in a font that has no other script, which would show as boxes."""
	return all(unicodedata.name(ch, "").startswith("LATIN") for ch in str(text or "") if ch.isalpha())


def person_rules(values: dict, prefix: str = "") -> dict[str, str]:
	"""What is wrong with one person's birth details, by field (what is missing or badly written has been found already): the name in English letters, a date
	in the right years, and a place that can be found and is not one of several of that name."""
	k, errors = person_keys(prefix), {}
	if not in_english_letters(values.get(k["name"])):
		errors[k["name"]] = _("Please write the name in English letters, for example Asha Rao.")
	day = getdate(values.get(k["date"]))
	if day > getdate(today()):
		errors[k["date"]] = _("The date of birth cannot be in the future.")
	elif day.year < EARLIEST_YEAR:
		errors[k["date"]] = _("Reports are made for births from the year {0}.").format(EARLIEST_YEAR)
	else:
		problem = places.problem(values.get(k["place"]), born_at(values, prefix))
		if problem:
			errors[k["place"]] = problem
	return errors


def kundli_rules(values: dict, user: str) -> dict:
	return person_rules(values)


def match_rules(values: dict, user: str) -> dict:
	return {**person_rules(values, "boy_"), **person_rules(values, "girl_")}


def topics() -> list[str]:
	"""The topics a visitor can say are troubling them, as staff keep them in Desk (Guidance Topic), in their order. Every astrologer can answer every one, so a topic is not a way to
	filter them; it starts the question."""
	return frappe.get_all("Guidance Topic", filters={"enabled": 1}, order_by="sequence asc, name asc", pluck="name")


def wishes() -> list[str]:
	"""What someone can wish for, as staff keep them in Desk (Blessing Wish), in their order. Staff tag each event with the ones it serves (event_filters.py)."""
	return frappe.get_all("Blessing Wish", filters={"enabled": 1}, order_by="sequence asc, name asc", pluck="name")


def question() -> dict:
	return {"name": "question", "label": _("What would you like to ask?"), "type": "textarea", "placeholder": _("Optional")}


def consultation_rules(values: dict, user: str) -> dict:
	"""A reading needs birth details on the customer's account: any profile will do, their own or a family member's (has_birth_profile)."""
	if not profiles.has_birth_profile(user):
		return {"_form": _("Please add your birth details first, then book.")}
	return {}
