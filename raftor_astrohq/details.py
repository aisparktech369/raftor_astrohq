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


VISIT_TIMES = ("7:00 AM", "9:00 AM", "11:00 AM", "2:00 PM", "4:00 PM", "6:00 PM")  # the times a pandit can come, until each pandit's own free times are kept


def visit_fields() -> list[dict]:
	"""Where, on which day and at what time, for a pooja done at the customer's place. The names are servicehq's contract ("visit_date" is the day)."""
	return [{"name": "address", "label": _("Where should the pandit come?"), "type": "textarea", "required": True, "placeholder": _("Flat, street, city, PIN")},
			{"name": "visit_date", "label": _("Day"), "type": "date", "required": True},
			{"name": "visit_time", "label": _("Time"), "type": "select", "required": True, "options": [{"value": t, "label": t} for t in VISIT_TIMES]}]


def wish() -> dict:
	return {"name": "wish", "label": _("Your wish or purpose"), "type": "textarea", "placeholder": _("Optional")}


PLACE_SOURCE = "raftor_astrohq.api.place_options"  # the method that answers the towns that start with what was typed (websitehq's lookup field)


def place_field(name: str, label: str) -> dict:
	"""The place of birth as a form asks for it: type the town and choose it from the list (the astrology service's towns); what is typed and not on the list is read as written, so that it can be told what to try."""
	return {"name": name, "label": label, "icon": "pin", "type": "lookup", "source": PLACE_SOURCE, "free_text": True, "required": True, "placeholder": _("Start typing the town"),
			"hint": _("Choose your town from the list, with its state. If it is not there, write the town and its state, or choose the nearest bigger town.")}


def time_fields() -> list[dict]:
	"""The time of birth as a form asks for it: the time, or that it is not known."""
	return [
		{"name": "time_of_birth", "label": _("Time of birth"), "type": "time_text", "placeholder": "HH:MM",
		 "hint": _("As on your birth record."), "disabled_when": "time_unknown"},
		{"name": "time_unknown", "label": _("I don't know my birth time"), "type": "checkbox", "switch": True},
	]


def you_fields() -> list[dict]:
	"""A person's own birth details as "Your birth details" asks for them (the onboarding page, and a booking form for someone who has none yet)."""
	return [
		{"name": "full_name", "label": _("Full name"), "required": True, "placeholder": _("e.g. Asha Rao"), "hint": _("Shown on your chart.")},
		{"name": "date_of_birth", "label": _("Date of birth"), "type": "date", "required": True},
		*time_fields(),
		place_field("place_of_birth", _("Place of birth")),
	]


def birth_details() -> list[dict]:
	"""What a report made from someone's birth asks: who, the day, the time and the place."""
	return [
		{"name": "report_name", "label": _("Name"), "required": True, "placeholder": _("Full name for the report")},
		{"name": "birth_date", "label": _("Date of birth"), "type": "date", "required": True},
		{"name": "birth_time", "label": _("Time of birth"), "type": "time_text", "required": True, "placeholder": "HH:MM", "hint": _("If you do not know it, write 12:00.")},
		place_field("birth_place", _("Place of birth")),
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
		{"name": k["name"], "label": own(_("name")), "icon": "user", "required": True, "placeholder": _("Full name in English letters")},
		{"name": k["date"], "label": own(_("date of birth")), "icon": "calendar", "type": "date", "required": True},
		{"name": k["time"], "label": own(_("time of birth")), "icon": "clock", "type": "time_text", "required": True, "placeholder": "HH:MM",
		 "hint": _("The exact time matters: the lagna and the dasha change with it. If you do not know it, ask your family or look at the birth certificate.")},
		place_field(k["place"], own(_("place of birth"))),
	]


def kundli_fields() -> list[dict]:
	return person_fields()


def numerology_fields() -> list[dict]:
	"""What the numerology report asks for: the name and the day of birth (no time and no place: the numbers come from the day and the letters)."""
	k = person_keys()
	return [{"name": k["name"], "label": _("Name"), "required": True, "placeholder": _("The name you are best known by, in English letters"),
			 "hint": _("The same name can give another number if it is spelled another way: write it the way you want it counted.")},
			{"name": k["date"], "label": _("Date of birth"), "type": "date", "required": True}]


def numerology_rules(values: dict, user: str) -> dict:
	k, errors = person_keys(), {}
	if not in_english_letters(values.get(k["name"])):
		errors[k["name"]] = _("Please write the name in English letters, for example Asha Rao.")
	day = getdate(values.get(k["date"]))
	if day > getdate(today()):
		errors[k["date"]] = _("The date of birth cannot be in the future.")
	elif day.year < EARLIEST_YEAR:
		errors[k["date"]] = _("Reports are made for births from the year {0}.").format(EARLIEST_YEAR)
	return errors


def whose() -> dict:
	"""Whose kundli it is, asked only where it is given away (servicehq free_reports.py): the person's own, or someone in the family. The answer is the birth profile's relationship, which
	decides how the details are kept (the person's own profile is "You"; a family member's is kept with the person's confirmation that they may)."""
	words = {profiles.SELF: _("Me"), "Spouse": _("My husband or wife"), "Child": _("My child"), "Parent": _("My mother or father"), "Sibling": _("My brother or sister"), "Other": _("Someone else")}
	marks = {profiles.SELF: "user", "Spouse": "rings", "Child": "child", "Parent": "home", "Sibling": "users", "Other": "star"}
	return {"name": "whose", "label": _("This kundli is for"), "type": "chips", "grid": True, "tiles": True, "required": True, "default": profiles.SELF,
			"options": [{"value": relation, "label": words.get(relation, relation), "icon": marks.get(relation, "user")} for relation in profiles.relationships()]}


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
	errors = {**person_rules(values, "boy_"), **person_rules(values, "girl_")}
	one, other = (person_keys(prefix) for prefix in ("boy_", "girl_"))
	if not errors and all(str(values.get(one[k]) or "").strip().lower() == str(values.get(other[k]) or "").strip().lower() for k in ("name", "date", "time")):
		errors[other["name"]] = _("Choose two different people: these are the same person.")
	return errors


def topics() -> list[str]:
	"""The topics a visitor can say are troubling them, as staff keep them in Desk (Guidance Topic), in their order. Every astrologer can answer every one, so a topic is not a way to
	filter them; it starts the question."""
	return frappe.get_all("Guidance Topic", filters={"enabled": 1}, order_by="sequence asc, name asc", pluck="name")


def wishes() -> list[str]:
	"""What someone can wish for, as staff keep them in Desk (Blessing Wish), in their order. Staff tag each event with the ones it serves (event_filters.py)."""
	return frappe.get_all("Blessing Wish", filters={"enabled": 1}, order_by="sequence asc, name asc", pluck="name")


def question() -> dict:
	return {"name": "question", "label": _("What would you like to ask?"), "type": "textarea", "placeholder": _("Optional")}


BIRTH_KEYS = ("full_name", "date_of_birth", "time_of_birth", "time_unknown", "place_of_birth")


def consultation_fields(user: str) -> list[dict]:
	"""A reading needs birth details on the customer's account. Someone who has none is asked for them right there, once, on the form they are filling in
	(the questions of "Your birth details"); they are kept as their own profile (consultation_rules), so the booking does not keep a second copy."""
	if profiles.has_birth_profile(user):
		return []
	return [{**field, "store": False} for field in you_fields()]


def consultation_rules(values: dict, user: str) -> dict:
	"""A reading needs birth details on the customer's account: any profile will do, their own or a family member's (has_birth_profile). Someone who gave
	theirs in this form (consultation_fields) has them kept now as their own profile; what is wrong with them comes back by field."""
	if profiles.has_birth_profile(user):
		return {}
	given = {key: values.get(key) for key in BIRTH_KEYS if values.get(key) not in (None, "")}
	if not given:
		return {"_form": _("Please add your birth details first, then book.")}
	saved = profiles.save_you(user, given)
	if not saved["ok"]:
		return dict(saved["errors"])
	from raftor_astrohq import api  # (api imports this module)

	api._refresh_onboarding(user)  # the person's own details are in: the first-time steps notice, as when they save them on their own page
	return {}
