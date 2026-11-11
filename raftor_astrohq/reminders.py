"""My reminders: a person says which days they follow (a tithi such as Ashtami or Amavasya in either fortnight, a weekday, a special day such as Ravi Pushya, or a mix such as Ashtami on a Tuesday)
and is told before each one, by the evening before and/or the morning of, through Notification HQ (the bell in the app and email today; SMS and WhatsApp when they are switched on there).

Nothing is sent that a person did not add. A reminder holds when ANY thing it names holds on the day (it can name a tithi, a weekday and a special day: it is told on each of them):
  tithi (and the fortnight, unless Both)   the tithi at sunrise, as the Panchang says it and as a person keeps a vrat; the message also says when it begins and ends
  weekday                                  the day of the week
  special day                              Ravi Pushya (Sunday with Pushya), Guru Pushya (Thursday with Pushya), Sarvartha Siddhi and Amrit Siddhi (a weekday with its nakshatras); the nakshatra counts
                                           when it holds at sunrise or begins before the next sunrise
The days come from the Panchang's engine answer for the day at the Panchang's town (`panchang.day`); nothing is worked out by an AI. The rules of the special days are the commonly printed ones: an
astrologer should confirm them before this goes live."""
import datetime

import frappe
from frappe import _

from raftor_astrohq import astrology, panchang
from raftor_astrohq.panchang_panes import clock, moment, when

DOCTYPE, SENT, EVENT = "Astro Reminder", "Astro Reminder Sent", "astro.reminder"
TITHIS = ["Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima", "Amavasya"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SPECIALS = ["Ravi Pushya", "Guru Pushya", "Sarvartha Siddhi", "Amrit Siddhi"]
LEADS = ["Evening before", "Morning of", "Both"]
MAX_PER_PERSON = 20
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


# ---- the day ----
def facts(on_date: datetime.date, place: dict) -> dict:
	"""What a reminder is matched against, for one day at one town (raises astrology.AstrologyUnavailable / AstrologyRefused / panchang.PanchangBusy when the engine cannot say)."""
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
	"""A saved choice or several (Ashtami,Amavasya) as a list."""
	return [part.strip() for part in str(value or "").split(",") if part.strip()]


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


def lead_words(lead: str) -> str:
	return {"Evening before": _("the evening before"), "Morning of": _("the morning of the day")}.get(lead, _("the evening before and the morning of the day"))


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


# ---- sending ----
def remind(slot: str) -> int:
	"""Scheduled: tell everyone whose reminder holds for the day (`evening`: tomorrow, `morning`: today). A reminder is sent once for a day and a time of day. How many were sent."""
	place = panchang.default_place()
	if not place:
		return 0
	leads = ["Evening before", "Both"] if slot == "evening" else ["Morning of", "Both"]
	rows = frappe.get_all(DOCTYPE, filters={"enabled": 1, "lead": ["in", leads]}, fields=["name", "user", "tithi", "paksha", "weekday", "special", "lead"])
	if not rows:
		return 0
	date = panchang.today(place) + datetime.timedelta(days=1 if slot == "evening" else 0)
	try:
		day = facts(date, place)
	except (astrology.AstrologyUnavailable, astrology.AstrologyRefused, panchang.PanchangBusy):
		frappe.log_error(title="Reminders: the day could not be had", message=str(date))
		return 0
	from raftor_servicehq import messages

	sent = 0
	for row in rows:
		if not follows(row, day) or not frappe.db.get_value("User", row.user, "enabled"):
			continue
		key = f"{row.name}:{date}:{slot}"
		if frappe.db.exists(SENT, key):
			continue
		frappe.get_doc({"doctype": SENT, "key": key, "reminder": row.name, "for_date": date, "slot": slot}).insert(ignore_permissions=True)
		frappe.db.commit()
		messages.send(EVENT, row.user, {"title": title_of(row), "text": text_for(row, day, slot), "link": _link(date)})
		sent += 1
	return sent


def _link(date: datetime.date) -> str:
	"""The panchang of that day, with the web's usual port left off (https://site:443/... is the same page)."""
	url = frappe.utils.get_url("/panchang?date=" + date.isoformat())
	return url.replace(":443/", "/", 1) if url.startswith("https://") else url.replace(":80/", "/", 1)


def evening() -> int:
	return remind("evening")


def morning() -> int:
	return remind("morning")


# ---- the person's own list (the page /my/reminders) ----
def _me() -> str:
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in."), frappe.PermissionError)
	return frappe.session.user


def _mine(name) -> frappe._dict:
	row = frappe.db.get_value(DOCTYPE, {"name": name, "user": _me()}, ["name", "tithi", "paksha", "weekday", "special", "lead", "enabled"], as_dict=True) if name else None
	if not row:
		frappe.throw(_("That reminder was not found."), frappe.DoesNotExistError)
	return row


@frappe.whitelist(methods=["POST"])
def list_reminders() -> dict:
	rows = frappe.get_all(DOCTYPE, filters={"user": _me()}, fields=["name", "tithi", "paksha", "weekday", "special", "lead", "enabled"], order_by="creation asc")
	items = []
	for row in rows:
		actions = [{"label": _("Delete"), "kind": "danger", "call": "raftor_astrohq.reminders.delete_reminder", "args": {"id": row.name}, "confirm": _("Delete this reminder?"), "confirm_label": _("Yes, delete")}]
		items.append({"id": row.name, "layout": "profile", "mark": "\u263e", "title": title_of(row), "subtitle": _("Reminds you {0}.").format(lead_words(row.lead)),
					  "switch": {"on": bool(row.enabled), "on_label": _("On"), "off_label": _("Paused"), "label": _("Reminder on"), "call": "raftor_astrohq.reminders.toggle_reminder", "args": {"id": row.name}},
					  "actions": actions})
	return {"items": items}


@frappe.whitelist(methods=["POST"])
def save_reminder(values=None) -> dict:
	"""Adds one reminder for the signed-in person. Problems come back per field."""
	user = _me()
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	clean = {key: str(values.get(key) or "").strip() for key in ("tithi", "paksha", "weekday", "special", "lead")}
	errors = {}
	for key, allowed, message in (("tithi", TITHIS, _("Choose tithis from the list.")), ("weekday", WEEKDAYS, _("Choose days from the list.")), ("special", SPECIALS, _("Choose special days from the list."))):
		chosen = [name for name in _set(clean[key]) if name in allowed]  # only what the list has, once each, in the list's order
		if len(chosen) != len(set(_set(clean[key]))):
			errors[key] = message
		clean[key] = ",".join(name for name in allowed if name in chosen)
	if clean["paksha"] and clean["paksha"] not in ("Both", "Shukla", "Krishna"):
		errors["paksha"] = _("Choose Shukla, Krishna or both.")
	if not clean["lead"]:
		clean["lead"] = "Evening before"
	if clean["lead"] not in LEADS:
		errors["lead"] = _("Choose when to remind you.")
	if not (clean["tithi"] or clean["weekday"] or clean["special"]) and not errors:
		errors["tithi"] = _("Choose at least a tithi, a weekday or a special day.")
	if set(_set(clean["tithi"])) <= {"Purnima", "Amavasya"}:
		clean["paksha"] = "Both"
	if errors:
		return {"ok": False, "errors": errors}
	if frappe.db.count(DOCTYPE, {"user": user}) >= MAX_PER_PERSON:
		return {"ok": False, "errors": {"tithi": _("You can keep up to {0} reminders. Delete one first.").format(MAX_PER_PERSON)}}
	same = frappe.db.exists(DOCTYPE, {"user": user, **{k: clean[k] for k in ("tithi", "weekday", "special")}, "paksha": clean["paksha"] or "Both"})
	if same:
		return {"ok": False, "errors": {"tithi": _("You already have this reminder.")}}
	frappe.get_doc({"doctype": DOCTYPE, "user": user, "enabled": 1, **clean, "paksha": clean["paksha"] or "Both"}).insert(ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def toggle_reminder(id=None) -> dict:
	row = _mine(id)
	frappe.db.set_value(DOCTYPE, row.name, "enabled", 0 if row.enabled else 1)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def delete_reminder(id=None) -> dict:
	frappe.delete_doc(DOCTYPE, _mine(id).name, ignore_permissions=True)
	return {"ok": True}
