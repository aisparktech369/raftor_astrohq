"""What the AI guides remember about a person and the people in their profiles, and what the site knows of them (the hook `agent_person`, called by AgentsHQ).

A note is a dated line tied to a birth profile (the account holder, "You", or a family member): "Tara (daughter): worried about exams". Notes are kept in Profile Note, never overwritten (a corrected or dropped note is
kept as Replaced), and each profile carries a short read-only summary of its current notes ("What We Know"). When a person speaks of someone who has no profile yet, the guide adds one, marked "Added From Chat", with only
what was said; the account holder completes the birth details on the website; until the birth details are complete, and the person has said they have that person's permission, the profile is not used for reports. A family member added from the chat starts without permission (permission_given 0): the guide asks once ("do you have their permission, or are you their parent or guardian?") and saves the answer with add_profile (has_permission), or the account holder ticks it on the website.

	read(user)                        {"notes": [...], "card": text}: the current notes and what the site knows of the person, for the guide at the start of a turn
	write(user, payload, guide, ...)  keeps the notes (and new family members) the note-taker returned after a reply
	member(user, who)                 one profile with its summary, notes, chart headline and numerology headline, for the guide's tool
	read_report(user, who, kind, guide)  what a guide may say from one person's report, in the guide's own area only, as a summary for the chat (the report is made and kept if it was not)
	forget(user, name)                removes one note for good
"""
import re

import frappe
from frappe.utils import cint, formatdate, today

from raftor_astrohq import answers, plan_rules, profiles, report_view
from raftor_astrohq import report_pdf as rp

LAST = 3
LIMIT = 40
SUMMARY_CHARS = 600
KINDRED = {"daughter": "Child", "son": "Child", "child": "Child", "kid": "Child", "mother": "Parent", "father": "Parent", "mom": "Parent", "dad": "Parent", "parent": "Parent",
		"wife": "Spouse", "husband": "Spouse", "spouse": "Spouse", "partner": "Spouse", "brother": "Sibling", "sister": "Sibling", "sibling": "Sibling"}


def _rows(user: str) -> list:
	return frappe.get_all("Astro Birth Profile", filters={"parent": user, "parenttype": "User", "parentfield": profiles.TABLE}, fields=["name", "relationship", "full_name", "date_of_birth", "time_of_birth", "time_unknown", "place_of_birth", "permission_given", "from_chat", "summary", "creation"], order_by="idx")


def _label(row) -> str:
	return "You" if row.relationship == profiles.SELF else row.full_name


def _word(about: str) -> tuple[str, str]:
	"""('Tara', 'daughter') from 'Tara (daughter)'; ('daughter', '') from 'my daughter'."""
	match = re.match(r"^\s*(.*?)\s*(?:\(([^)]*)\))?\s*$", about or "")
	name, relation = (match.group(1), (match.group(2) or "").strip().lower()) if match else (about, "")
	name = re.sub(r"^(my|the)\s+", "", name.strip(), flags=re.I)
	return name, relation


def _find(rows: list, about: str):
	"""The profile a name or a family word ('Tara', 'Tara (daughter)', 'my daughter') points to, or None. A word like 'daughter' matches only when exactly one profile has that relationship."""
	name, relation = _word(about)
	if not name or name.lower() in ("you", "me", "myself", "self"):
		return next((r for r in rows if r.relationship == profiles.SELF), None)
	named = [r for r in rows if r.relationship != profiles.SELF and (r.full_name or "").strip().lower().split(" ")[0] == name.lower().split(" ")[0] or (r.full_name or "").strip().lower() == name.lower()]
	if named:
		return named[0]
	for word in (name.lower(), relation):
		kind = KINDRED.get(word)
		same = [r for r in rows if kind and r.relationship == kind]
		if len(same) == 1:
			return same[0]
	return None


def _relationship(about: str, given: str = "") -> str:
	_, relation = _word(about)
	for word in (given.lower(), relation, _word(about)[0].lower()):
		if KINDRED.get(word):
			return KINDRED[word]
	return "Other"


def _add_member(user: str, about: str, details: dict | None = None):
	"""A profile for someone the person spoke of: the name and how they are related, and whatever birth details were said. Marked as added from the chat; the account holder completes it on the website."""
	name, relation = _word(about)
	name = (details or {}).get("name") or name
	if len(name) < 2 or KINDRED.get(name.lower()) or name.lower() in ("you", "me", "myself", "self"):
		return None  # 'my daughter' with no name cannot be a profile yet
	if plan_rules.family_room(user) < 1:
		return None  # the person's plan holds no more people (plan_rules.py); the notes about them are still kept
	doc = frappe.get_doc("User", user)
	row = {"relationship": _relationship(about, (details or {}).get("relationship") or ""), "full_name": name.title() if name.islower() else name, "from_chat": 1, "permission_given": 1 if (details or {}).get("has_permission") else 0}  # (a person is added without permission until it is asked and answered; see save_profile) gles come later and will start from the "Added From Chat" mark
	for key in ("date_of_birth", "time_of_birth", "place_of_birth"):
		if (details or {}).get(key):
			row[key] = str(details[key]).strip()
	if row.get("date_of_birth"):
		try:
			frappe.utils.getdate(row["date_of_birth"])
		except Exception:
			row.pop("date_of_birth")
	doc.append(profiles.TABLE, row)
	doc.save(ignore_permissions=True)
	added = doc.get(profiles.TABLE)[-1]
	return frappe._dict(name=added.name, relationship=added.relationship, full_name=added.full_name, from_chat=1, summary="")


def current(user: str, limit: int = LIMIT, kinds: list | None = None) -> list:
	"""The person's current notes, oldest first; `kinds` limits them to those kinds (None = all)."""
	filters = {"user": user, "is_current": 1}
	if kinds is not None:
		filters["kind"] = ["in", kinds or [""]]
	rows = frappe.get_all("Profile Note", filters=filters, fields=["noted_on", "about", "kind", "point", "guide"], order_by="noted_on desc, creation desc", limit=limit)
	return [{"on": str(r.noted_on or ""), "about": r.about or "", "kind": r.kind or "", "guide": r.guide or "", "point": r.point} for r in reversed(rows)]


def _summarise(user: str, row_name: str) -> None:
	points = frappe.get_all("Profile Note", filters={"user": user, "profile": row_name, "is_current": 1}, pluck="point", order_by="noted_on asc, creation asc")
	text = "; ".join(p.rstrip(".") for p in points)
	frappe.db.set_value("Astro Birth Profile", row_name, "summary", text[:SUMMARY_CHARS], update_modified=False)


def write(user: str, payload: dict, guide: str, session: str) -> dict:
	"""Makes the person's current notes those given: a new one is added with its date and the guide that heard it, one no longer there is kept as Replaced, an unchanged one is left alone. People named in the notes
	or listed under "people" who have no profile get one (from the chat). Each touched profile's summary is rewritten."""
	rows = _rows(user)
	made = 0
	for person in payload.get("people") or []:
		label = f"{person.get('name', '')} ({person.get('relationship', '')})" if person.get("relationship") else str(person.get("name") or "")
		if person.get("name") and not _find(rows, label):
			row = _add_member(user, label, person)
			if row:
				rows.append(row)
				made += 1
	mine = {(r.about or "You", r.point): r for r in frappe.get_all("Profile Note", filters={"user": user, "is_current": 1}, fields=["name", "about", "point", "profile"])}
	wanted = {}
	for n in payload.get("notes") or []:
		point = str(n.get("point") or "").strip()
		if point:
			wanted[(str(n.get("about") or "You").strip() or "You", point)] = n
	touched, added, replaced = set(), 0, 0
	for key, n in wanted.items():
		if key in mine:
			continue
		row = _find(rows, key[0])
		if row is None and _word(key[0])[0].lower() not in ("you", "me", "myself", "self", ""):
			row = _add_member(user, key[0])
			if row:
				rows.append(row)
				made += 1
		frappe.get_doc({"doctype": "Profile Note", "user": user, "profile": row.name if row else "", "about": key[0], "kind": str(n.get("kind") or "")[:30], "point": key[1][:400],
						"noted_on": n.get("on") or today(), "is_current": 1, "guide": guide, "session": session}).insert(ignore_permissions=True)
		touched.add(row.name if row else "")
		added += 1
	for key, row in mine.items():
		if key not in wanted:
			frappe.db.set_value("Profile Note", row.name, {"is_current": 0, "replaced_on": today()}, update_modified=False)
			touched.add(row.profile or "")
			replaced += 1
	for name in touched - {""}:
		_summarise(user, name)
	return {"added": added, "replaced": replaced, "people_added": made}


def forget(user: str, name: str) -> bool:
	if frappe.db.get_value("Profile Note", name, "user") != user:
		return False
	profile = frappe.db.get_value("Profile Note", name, "profile")
	frappe.delete_doc("Profile Note", name, ignore_permissions=True)
	if profile:
		_summarise(user, profile)
	return True


def _age(row) -> int | None:
	"""Whole years since the birth date, or None when it is not given."""
	if not row.date_of_birth:
		return None
	born, on = frappe.utils.getdate(row.date_of_birth), frappe.utils.getdate(today())
	return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def _details(row) -> str:
	"""What is on file of the birth, said as present or missing. The date, time and place themselves are not given to the AI: it gets the chart's facts from the tools, and the engine reads the details."""
	gaps = [word for word, ok in (("date", bool(row.date_of_birth)), ("time", bool(row.time_unknown or row.time_of_birth)), ("place", bool(row.place_of_birth))) if not ok]
	return "birth details complete" if not gaps else "birth " + " and ".join(gaps) + " not given"


def _line(row) -> str:
	age = _age(row)
	born = f"about {age} years old" if age is not None else "age not given"
	clock, place = _details(row), ""
	who = "You" if row.relationship == profiles.SELF else f"{row.full_name} ({row.relationship.lower()})"
	fresh = row.from_chat and row.creation and (frappe.utils.now_datetime() - frappe.utils.get_datetime(row.creation)).total_seconds() < 1800
	status = (" [saved from this chat a moment ago: tell them once, in a few words, that you saved " + row.full_name + " and they can complete or remove it in their profiles]" if fresh
			  else " [added from chat, details to be completed by the person]" if row.from_chat else "")
	line = f"- {who}: {row.full_name}, {born}, {clock}{place}{status}"
	return line + (f"\n  What we know: {row.summary}" if row.summary else "")


def _reports(user: str) -> list[str]:
	rows = frappe.get_all("Astro Answer", filters={"user": user}, fields=["mode", "made_on"], order_by="made_on desc", limit=LAST)
	return [f"- Saved report ({r.mode.replace('_', ' ').title()}) made on {formatdate(r.made_on, 'd MMM yyyy')}" for r in rows]


def _customer(user: str) -> str:
	return frappe.db.get_value("Portal User", {"user": user, "parenttype": "Customer"}, "parent") or frappe.db.get_value("Customer", {"email_id": user}, "name") or ""


def _orders(user: str) -> list[str]:
	customer = _customer(user)
	if not customer:
		return []
	out = []
	for order in frappe.get_all("Sales Order", filters={"customer": customer, "docstatus": 1}, fields=["name", "transaction_date"], order_by="transaction_date desc", limit=LAST):
		items = frappe.get_all("Sales Order Item", filters={"parent": order.name}, pluck="item_name", limit=3)
		out.append(f"- Bought on {formatdate(order.transaction_date, 'd MMM yyyy')}: {', '.join(items)}")
	return out


def _bookings(user: str) -> list[str]:
	if not frappe.db.exists("DocType", "Booking"):
		return []

	def name(offering):
		return (frappe.db.get_value("Item", offering, "item_name") if offering and frappe.db.exists("Item", offering) else offering) or "a session"

	rows = frappe.get_all("Booking", filters={"customer_user": user}, fields=["offering", "slot_start", "workflow_state"], order_by="creation desc", limit=LAST)
	return [f"- Booked {name(r.offering)}{' on ' + formatdate(r.slot_start, 'd MMM yyyy') if r.slot_start else ''} ({(r.workflow_state or '').lower()})" for r in rows]


def names(user: str) -> list[dict]:
	"""The names the AI must not see (AgentsHQ swaps each for a stand-in, pseudonyms.py): the person's and their family's, as the profiles have them. `key` stays the same for a profile, so its stand-in does too."""
	out = [{"key": r.name, "name": r.full_name, "self": r.relationship == profiles.SELF} for r in _rows(user) if (r.full_name or "").strip()]
	account = " ".join(x for x in (frappe.db.get_value("User", user, "first_name"), frappe.db.get_value("User", user, "last_name")) if x)
	if account and sum(c.isdigit() for c in account) < 5:  # a phone-number sign-up has the number as its name: that is removed as a number, not swapped
		out.append({"key": "account", "name": account, "self": True})
	return [r for r in out if sum(c.isdigit() for c in r["name"]) < 5]


def real(user: str, text: str) -> str:
	"""A name the AI used for a tool, with its stand-in turned back to the real one ('Meera' -> 'Tara'). Unchanged when AgentsHQ is not there."""
	try:
		from raftor_agentshq import pseudonyms

		return pseudonyms.real(user, text)
	except Exception:
		return text


def card(user: str, mode: str = "full") -> str:
	"""The person and their family as the site has them, each with the summary kept from the chats, then their reports, purchases and bookings. '' when the site knows nothing of them yet."""
	if mode == "none":
		return ""
	if mode == "names":  # only who is in the family, so "my daughter" can be understood: no birth details, reports, purchases or summaries
		return "\n".join(f"- {'You' if r.relationship == profiles.SELF else f'{r.full_name} ({r.relationship.lower()})'}: {r.full_name}" for r in _rows(user))
	lines = []
	for part in (lambda u: [_line(r) for r in _rows(u)], _reports, _orders, _bookings):
		try:
			lines += part(user)
		except Exception:
			frappe.log_error(title="person card")
	return "\n".join(lines)


def read(user: str, guide: str = "") -> dict:
	"""What a guide is shown of the person at the start of a turn: the notes and the card, as far as that guide's reads allow (agents.READS_OF_PERSON)."""
	from raftor_astrohq import agents

	allowed = agents.reads_of(guide) if guide else {"notes": None, "card": "full"}
	return {"notes": current(user, limit=LIMIT, kinds=allowed["notes"]), "card": card(user, allowed["card"])}


def allowance(user: str, guide: str, persona: str = "") -> dict:
	"""Whether this guide may answer this person now, on their plan and within the guide's own daily cap (AgentsHQ asks before it queues a message). See plan_rules.py."""
	return plan_rules.allowance(user, guide, persona)


def turn_done(user: str, guide: str, persona: str = "") -> None:
	"""A reply was given: it counts against the person's plan, at the guide's multiplier (AgentsHQ calls this when a turn is complete)."""
	plan_rules.turn_done(user, guide, persona)


def member(user: str, who: str, guide_user: str = "") -> dict:
	"""One profile for the guide's tool: the details, the summary and notes kept from the chats, and the numerology headline of the birth date when it is known. `user` is the signed-in person, set by the server."""
	rows = _rows(user)
	row = _find(rows, real(user, who))
	if row is None:
		return {"found": False, "message": "No profile matches that. Ask the person for the name, or offer to add them.", "profiles": [{"name": _label(r), "relationship": r.relationship} for r in rows]}
	from raftor_astrohq import agents

	reads = agents.reads_of(agents.blueprint_of_user(guide_user)) if guide_user else {"notes": None, "card": "full"}
	if reads["card"] != "full":  # a guide that sees only names: who they are, and the notes of the kinds it may read
		kinds = reads["notes"] or []
		return {"found": True, "name": row.full_name, "relationship": row.relationship, "notes": [{"on": str(n.noted_on or ""), "kind": n.kind, "point": n.point} for n in frappe.get_all(
			"Profile Note", filters={"user": user, "profile": row.name, "is_current": 1, "kind": ["in", kinds or [""]]}, fields=["noted_on", "kind", "point"], order_by="noted_on asc", limit=20)]}
	out = {"found": True, "name": row.full_name, "relationship": row.relationship, "age_years": _age(row), "birth_details": _details(row),
		   "details_complete": not profiles.row_errors(profiles.row_values(row)),
		   "summary": row.summary or "", "notes": [{"on": str(n.noted_on or ""), "kind": n.kind, "point": n.point} for n in frappe.get_all("Profile Note", filters={"user": user, "profile": row.name, "is_current": 1}, fields=["noted_on", "kind", "point"], order_by="noted_on asc", limit=20)]}
	from raftor_astrohq import agents

	areas = agents.report_areas(guide_user) if guide_user else ["kundli", "numerology"]  # a guide reads only the reports of its own area
	try:
		chart = chart_summary(user, row) if {"kundli", "kp"} & set(areas) else None
	except Exception:
		chart = None
	if chart:
		out["chart"] = chart
		if agents.blueprint_of_user(guide_user) in ASTROLOGER_GUIDES:  # the astrologer guides show the chart itself whenever they open a person (once in a chat: the chat does not repeat a card)
			from raftor_astrohq import chart_card

			out["chart_cards"] = [chart_card.card(row.name, row.full_name)]
	if row.date_of_birth and "numerology" in areas:
		try:
			from raftor_astrohq import astrology

			reading = (astrology.numerology(frappe.utils.getdate(row.date_of_birth).day, None, row.full_name).get("reading") or {})
			birth = reading.get("birth") or {}
			out["numerology"] = {"birth_number": birth.get("number"), "headline": birth.get("headline"), "name": reading.get("name")}
		except Exception:
			pass
	return out


def _plain(text) -> str:
	"""A sign or planet as the engine writes it, without its little symbol: '♋︎Cancer' -> 'Cancer'."""
	return re.sub(r"[^A-Za-z ]", "", str(text or "")).strip()


def chart_summary(user: str, row) -> dict | None:
	"""The headline of the person's kundli, from the engine's kept answer for their birth (no new call after the first): the ascendant, the Sun and Moon signs, the Moon's nakshatra and the dasha running now.
	None when the birth time or place is not known, because a chart needs the minute and the place."""
	if row.time_unknown or not row.time_of_birth or not row.place_of_birth or not row.date_of_birth:
		return None
	numbers = report_view.profile_numbers(row)
	if not numbers:
		return None
	chart = answers.get(user, numbers, "SUPER_BASIC")
	by = {rp.planet_code(p["planet"]): p for p in chart["planetary_positions"]}
	on = frappe.utils.getdate(today())
	out = {"ascendant": _plain(chart["lagna"]["sign"]), "ascendant_lord": _plain(chart["lagna"].get("lord")), "sun_sign": _plain(by["Su"]["sign"]), "moon_sign": _plain(by["Mo"]["sign"]),
		   "moon_nakshatra": f"{by['Mo']['nakshatra']}, pada {by['Mo']['pada']}"}
	for period in chart["dasha_sequences"]["vimshottari"]["mahadasha"]:
		if period.get("start_date") and frappe.utils.getdate(period["start_date"]) <= on and (not period.get("end_date") or on <= frappe.utils.getdate(period["end_date"])):
			out["running_mahadasha"] = f"{rp.PLANETS.get(rp.planet_code(period['lord']), _plain(period['lord']))} until {formatdate(period['end_date'], 'd MMM yyyy')}" if period.get("end_date") else rp.PLANETS.get(rp.planet_code(period["lord"]), "")
			for sub in period.get("antardasha") or []:
				if frappe.utils.getdate(sub["start_date"]) <= on <= frappe.utils.getdate(sub["end_date"]):
					out["running_antardasha"] = f"{rp.PLANETS.get(rp.planet_code(sub['lord']), _plain(sub['lord']))} until {formatdate(sub['end_date'], 'd MMM yyyy')}"
			break
	return out


REPORTS = {"kundli": ("kundli", "Kundli report"), "numerology": ("numerology", "Numerology report"), "kp": ("kp", "KP chart report"), "match": ("match", "Match making report")}
AREA_WORDS = {"kundli": "a kundli is read by Pandit ji and the Vedic astrologer guide", "numerology": "numerology is read by the numerology guide and Pandit ji",
			  "kp": "a KP chart is read by the KP astrologer guide", "match": "matching two charts is read by the Vedic and KP astrologer guides"}
GROOM, BRIDE = "groom", "bride"
ASTROLOGER_GUIDES = ("vedic_astrologer", "kp_astrologer")


def _planets(chart: dict) -> list[str]:
	return [f"{rp.PLANETS.get(rp.planet_code(p['planet']), _plain(p['planet']))} in {_plain(p['sign'])}, house {p['house']}" for p in chart["planetary_positions"][:9]]


def _numerology_summary(row) -> dict:
	"""A person's numerology as the engine reads it (never worked out by the guide): the birth number, what it is said to mean, and the name number when a name is known."""
	from raftor_astrohq import astrology
	from raftor_astrohq.assistant_tools.numerology import _part

	born = frappe.utils.getdate(row.date_of_birth)
	reading = astrology.numerology(day=born.day, month=born.month, year=born.year, name=row.full_name).get("reading") or {}
	return {**_part(reading, "birth"), **_part(reading, "name")}


def _kp_summary(user: str, row) -> dict:
	"""A person's chart the KP way, as the engine reads it: the ruling planets at birth, each house cusp with its sign, star and sub lord, and each planet's house with its sign, star and sub lord, with the dasha running now."""
	data = answers.get(user, report_view.profile_numbers(row), "KP_SYSTEM")
	rules = data.get("ruling_planets_at_birth") or {}
	out = {"ruling_planets": {key.replace("_", " "): value for key, value in rules.items()},
		   "cusps": [f"House {h['HouseNr']}: sign lord {h['RasiLord']}, star lord {h['NakshatraLord']}, sub lord {h['SubLord']}" for h in data.get("houses") or []],
		   "planets": [f"{p['Object']}: house {p['HouseNr']}, sign lord {p['RasiLord']}, star lord {p['NakshatraLord']}, sub lord {p['SubLord']}" for p in data.get("planets") or []]}
	headline = chart_summary(user, row) or {}
	return {**out, **{key: headline[key] for key in ("ascendant", "moon_sign", "running_mahadasha", "running_antardasha") if key in headline}}


def _read_match(user: str, who: str, partner: str, who_is: str) -> dict:
	"""The ashtakoota match of two of the person's saved profiles (the same engine call and wording as the site's match making report), as facts for the guide to say in its own words."""
	from raftor_astrohq import astrology, reports

	who_is = str(who_is or "").strip().lower()
	if who_is not in (GROOM, BRIDE):
		return {"found": False, "message": "Matching is worked out for a groom and a bride. Ask which of the two is the groom and which the bride, then call again with who_is set to groom or bride for the first person."}
	rows = _rows(user)
	first, second = _find(rows, who), _find(rows, partner)
	if first is None or second is None:
		return {**_no_profile(rows), "message": _no_profile(rows)["message"].replace("No profile matches that.", "One of the two people is not among the saved profiles.") if rows else "No profile is saved yet. Ask for each person's date, time and place of birth."}
	if first.name == second.name:
		return {"found": False, "message": "That is the same person twice. Ask who the other person is."}
	for row in (first, second):
		missing = [label for label, value in (("date of birth", row.date_of_birth), ("time of birth", row.time_of_birth and not row.time_unknown), ("place of birth", row.place_of_birth)) if not value]
		if missing:
			return {"found": False, "message": f"Matching needs {row.full_name}'s {' and '.join(missing)}. Ask for it."}
	boy, girl = (first, second) if who_is == GROOM else (second, first)
	try:
		boy_numbers, girl_numbers = report_view.profile_numbers(boy, "Male"), report_view.profile_numbers(girl, "Female")
		if not boy_numbers or not girl_numbers:
			return {"found": False, "message": "The time of birth is needed for both. Ask for it."}
		match = astrology.chart(boy_numbers, "MATCH_CALC", partner=girl_numbers)
	except Exception:
		frappe.log_error(title="match summary")
		return {"found": False, "message": "The match could not be worked out just now. Say so and offer to try again."}
	score = match.get("compatibility") or {}
	doshas = match.get("doshas") or {}
	total = float(score.get("total_score") or 0)
	from raftor_astrohq import chart_card

	return {"found": True, "report": "match", "groom": boy.full_name, "bride": girl.full_name, "chart_cards": [chart_card.card(boy.name, boy.full_name), chart_card.card(girl.name, girl.full_name)],
			"summary": {"total": f"{total:g} out of {int(score.get('max_score') or 36)}", "how_it_is_read": reports._verdict(total),
						"kootas": [f"{name}: {float(score.get(key) or 0):g} out of {top} ({looks_at})" for name, looks_at, key, top in reports.KOOTAS],
						"manglik": {"groom": bool((doshas.get("person1") or {}).get("manglik")), "bride": bool((doshas.get("person2") or {}).get("manglik"))}},
			"message": f"This is the ashtakoota match of {boy.full_name} (groom) and {girl.full_name} (bride). Say the total and what range it is usually read as, then the one or two kootas that scored lowest and highest, in your own words and as what the tradition reads, "
					   "never as a verdict on the people or the marriage. Never say a match is good or bad for them or advise to marry or not; if they want a decision, point them to a live astrologer."}


def save_profile(user: str, who: str, relationship: str = "", date_of_birth: str = "", time_of_birth: str = "", place_of_birth: str = "", time_unknown: bool = False, has_permission: bool = False) -> dict:
	"""Saves (or completes) one person's birth details among the signed-in person's own profiles, from what they said in the chat after agreeing to it: themself, or someone in their family. A profile that is already there
	is completed where it has gaps; details the person entered on the website are never changed from here. Says what is still missing, so the guide asks for exactly that. `user` is the signed-in person, set by the server."""
	who = real(user, str(who or "").strip())  # a stand-in name the AI used for someone already saved is turned back; a new name stays as it is
	given = str(relationship or "").strip()
	is_self = who.lower() in ("", "me", "myself", "self", "you") or given.lower() in ("me", "myself", "self", "you")
	rows = _rows(user)
	if not is_self and not any(r.relationship == profiles.SELF for r in rows) and who and (frappe.db.get_value("User", user, "first_name") or "").strip().lower() == who.split()[0].lower() and not _find(rows, who):
		is_self = True  # their own name, and no profile of their own yet: it is theirs
	row = next((r for r in rows if r.relationship == profiles.SELF), None) if is_self else _find(rows, f"{who} ({given})" if given else who)
	values = {}
	if date_of_birth:
		try:
			born = frappe.utils.getdate(date_of_birth)
		except Exception:
			return {"saved": False, "message": "That date of birth is not a date. Ask for it again as day, month and year."}
		if born > frappe.utils.getdate(today()):
			return {"saved": False, "message": "A date of birth cannot be in the future. Ask for it again."}
		values["date_of_birth"] = str(born)
	if time_unknown and not time_of_birth:
		values["time_unknown"] = 1
	if time_of_birth:
		match = profiles.TIME.match(str(time_of_birth).strip())
		if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
			return {"saved": False, "message": "That is not a 24-hour time such as 06:42. Ask for the time of birth again."}
		values["time_of_birth"], values["time_unknown"] = f"{int(match.group(1)):02d}:{match.group(2)}", 0
	if place_of_birth and len(str(place_of_birth).strip()) >= 2:
		values["place_of_birth"] = str(place_of_birth).strip()
	doc = frappe.get_doc("User", user)
	if row is None:
		if is_self:
			name = who if who.lower() not in ("", "me", "myself", "self", "you") else (frappe.db.get_value("User", user, "full_name") or "")
			if len(name.strip()) < 2:
				return {"saved": False, "message": "Ask for their full name first."}
			doc.append(profiles.TABLE, {"relationship": profiles.SELF, "full_name": name.strip(), "from_chat": 1, "permission_given": 1, **values})
		else:
			if len(who.strip()) < 2 or KINDRED.get(who.lower()):
				return {"saved": False, "message": "Ask for the person's name first (not only 'my daughter')."}
			added = _add_member(user, f"{who} ({given})" if given else who, {"name": who, "relationship": given, **values})
			if added is None:
				return {"saved": False, "message": "The person's plan holds no more people. Say so kindly: they can remove someone on the website, or choose a bigger plan. Their chart cannot be opened until then."}
			doc = frappe.get_doc("User", user)
	else:
		target = next(r for r in doc.get(profiles.TABLE) if r.name == row.name)
		if not target.get("from_chat"):  # entered by the account holder on the website: not changed from the chat
			gaps = {k: v for k, v in values.items() if not target.get(k)}
			if len(gaps) != len(values):
				return {"saved": False, "message": "Those details are already saved for this person on the website, and differ from what was said. Do not change them: say so, and tell them they can edit the profile on the website."}
			values = gaps
		for key, value in values.items():
			target.set(key, value)
	if row is not None or is_self:
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
	fresh = _rows(user)
	saved = next((r for r in fresh if r.relationship == profiles.SELF), None) if is_self else _find(fresh, f"{who} ({given})" if given else who)
	if saved is None:
		return {"saved": False, "message": "The profile could not be saved just now. Say so and offer to try again."}
	if not is_self and has_permission and saved.from_chat and not cint(saved.permission_given):
		frappe.db.set_value("Astro Birth Profile", saved.name, "permission_given", 1, update_modified=False)  # the person said yes when asked
		saved = frappe._dict(saved, permission_given=1)
	missing = [label for label, value in (("date of birth", saved.date_of_birth), ("time of birth", saved.time_of_birth and not saved.time_unknown), ("place of birth", saved.place_of_birth)) if not value]
	out = {"saved": True, "name": saved.full_name, "relationship": saved.relationship, "missing": missing}
	out["message"] = ("Saved " + saved.full_name + ". " + ("Still needed for a chart: " + ", ".join(missing) + ". Ask for exactly that." if missing else "Everything for a chart is there: open the chart now."))
	if saved.time_unknown:
		out["message"] += " Their time of birth is not known, so a chart cannot be drawn: say so kindly."
	if not is_self and not cint(saved.permission_given):
		out["permission_needed"] = True
		out["message"] += f" Ask once: 'Do you have {saved.full_name}'s permission to keep these details, or are you their parent or guardian?' When they say yes, call add_profile again with has_permission true. Until then no report is made for {saved.full_name}."
	return out


def _no_profile(rows: list) -> dict:
	"""No profile matched: say who is saved, so the guide offers those names (a person may have saved only their family, no profile of their own) instead of saying nothing is saved."""
	have = [{"name": _label(r), "relationship": r.relationship} for r in rows]
	return {"found": False, "profiles": have, "message": ("No profile matches that. These are saved: " + ", ".join(f"{p['name']} ({p['relationship']})" for p in have) + ". Offer these names and ask whose chart they mean; if they mean themself, ask for their own date, time and place of birth.")
			if have else "No profile is saved yet. Ask for the date, time and place of birth of the person whose chart they want."}


def read_report(user: str, who: str, kind: str, guide_user: str, partner: str = "", who_is: str = "") -> dict:
	"""What a guide may say from one person's report, in its own area only, as facts to put in its own words in the chat (no link). A report that does not exist yet is made now and kept as available among the
	person's reports (a free report, bright on their page); when it cannot be made yet, what is missing is named, so the guide can ask for it."""
	from raftor_astrohq import agents
	from raftor_servicehq import free_reports, intake as intake_rules, workflows

	who, partner = real(user, who), real(user, partner)  # the AI speaks of people by stand-in names
	kind = str(kind or "").strip().lower()
	if kind not in REPORTS:
		return {"found": False, "message": "Say which report: kundli, kp, match or numerology."}
	if kind not in agents.report_areas(guide_user):
		return {"found": False, "message": f"That report is outside your area: {AREA_WORDS[kind]}. Say so kindly and, if useful, point the person to them."}
	if kind == "match":
		return _read_match(user, who, partner, who_is)
	rows = _rows(user)
	row = _find(rows, who)
	if row is None:
		return _no_profile(rows)
	if row.relationship != profiles.SELF and not cint(row.permission_given):
		return {"found": False, "permission_needed": True, "message": f"No report for {row.full_name} yet: their permission is not on file. Ask once: 'Do you have their permission to keep their details, or are you their parent or guardian?' When they say yes, call add_profile again with has_permission true (or they can tick it on their profile on the website)."}
	if not row.date_of_birth:
		return {"found": False, "message": f"{row.full_name}'s date of birth is not saved yet. Ask for it first."}
	item = frappe.db.get_value("Item", {"custom_report_kind": REPORTS[kind][0], "custom_vertical": "astrohq"})
	details = {"report_name": row.full_name, "birth_date": str(row.date_of_birth)}
	if kind in ("kundli", "kp"):
		missing = [label for label, value in (("time of birth", row.time_of_birth and not row.time_unknown), ("place of birth", row.place_of_birth)) if not value]
		if missing:
			return {"found": False, "message": f"A {kind} chart needs {row.full_name}'s {' and '.join(missing)}. Ask for it; the report is made as soon as it is known, and kept under their reports."}
		details.update({"whose": row.relationship, "birth_time": row.time_of_birth, "birth_place": row.place_of_birth})
	made = False
	if item and free_reports.on_sale(item):  # kept as available: the person's own free report, once, for these details
		clean, errors, message = free_reports._check(item, details)
		dumped = intake_rules.dump(clean)
		if not errors and not message and not frappe.db.exists("Free Report", {"user": user, "item": item, "details": dumped}):
			try:
				free_reports.check_limit(user)
				workflows.as_system(lambda: free_reports.create(user, item, clean))
				made = True
			except frappe.ValidationError:
				pass  # the daily limit: the summary below is still given
	out = {"found": True, "report": kind, "for": row.full_name, "newly_made": made}
	try:
		if kind == "numerology":
			out["summary"] = _numerology_summary(row)
		elif kind == "kp":
			out["summary"] = _kp_summary(user, row)
		else:
			chart = chart_summary(user, row) or {}
			by = answers.get(user, report_view.profile_numbers(row), "SUPER_BASIC")
			out["summary"] = {**chart, "planets": _planets(by)}
		if kind in ("kundli", "kp") and report_view.profile_numbers(row):
			from raftor_astrohq import chart_card

			out["chart_cards"] = [chart_card.card(row.name, row.full_name)]
	except Exception:
		frappe.log_error(title="report summary")
		return {"found": False, "message": "The report could not be read just now. Say so and offer to try again."}
	out["message"] = (f"This is {row.full_name}'s {kind} report" + (", just made and kept under their reports" if made else ", kept under their reports") +
					  ". Share what helps the conversation in your own words, in the chat; give no link, and do not read it all out. If they want the full report it is under their reports.")
	return out


def persona_voice(persona: str, guide: str) -> str:
	"""The words that make one guide of an area sound like itself (AgentsHQ asks with the name the chat gives and the area's agent). Only an enabled guide of that very area, with all its skills on, has a voice; any other name gives nothing. The words are built by the factory's person (raftor_agentshq.personas) from the fields staff keep in Desk."""
	from raftor_agentshq import personas
	from raftor_astrohq import ai_guides

	fields = ["guide_name", "voice", "languages", "traits", "mindset", "communication_style", "signature_line", "topics", "workflow", "response_format", "boundaries"]
	row = frappe.db.get_value("AI Guide Persona", {"slug": persona, "area": guide, "enabled": 1}, fields, as_dict=True) if persona else None
	return personas.voice(row.guide_name, row) if row and ai_guides.is_on(persona) else ""


def persona_shelves(persona: str, guide: str) -> list:
	"""The knowledge shelves one guide of an area reads, from its skills (AgentsHQ asks with the name the chat gives and the area's agent). Nothing for a guide that is not on or has no skills."""
	from raftor_astrohq import ai_guides

	return ai_guides.shelves(persona, guide) if persona and frappe.db.exists("AI Guide Persona", persona) and ai_guides.is_on(persona) else []
