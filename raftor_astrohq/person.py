"""What the AI guides remember about a person and the people in their profiles, and what the site knows of them (the hook `agent_person`, called by AgentsHQ).

A note is a dated line tied to a birth profile (the account holder, "You", or a family member): "Tara (daughter): worried about exams". Notes are kept in Profile Note, never overwritten (a corrected or dropped note is
kept as Replaced), and each profile carries a short read-only summary of its current notes ("What We Know"). When a person speaks of someone who has no profile yet, the guide adds one, marked "Added From Chat", with only
what was said; the account holder completes the birth details on the website; until the birth details are complete the profile is not used for reports. Consent is not asked yet: the person's consent toggles come later.

	read(user)                        {"notes": [...], "card": text}: the current notes and what the site knows of the person, for the guide at the start of a turn
	write(user, payload, guide, ...)  keeps the notes (and new family members) the note-taker returned after a reply
	member(user, who)                 one profile with its summary, notes and numerology headline, for the guide's tool
	forget(user, name)                removes one note for good
"""
import re

import frappe
from frappe.utils import formatdate, today

from raftor_astrohq import profiles

LAST = 3
LIMIT = 40
SUMMARY_CHARS = 600
KINDRED = {"daughter": "Child", "son": "Child", "child": "Child", "kid": "Child", "mother": "Parent", "father": "Parent", "mom": "Parent", "dad": "Parent", "parent": "Parent",
		"wife": "Spouse", "husband": "Spouse", "spouse": "Spouse", "partner": "Spouse", "brother": "Sibling", "sister": "Sibling", "sibling": "Sibling"}


def _rows(user: str) -> list:
	return frappe.get_all("Astro Birth Profile", filters={"parent": user, "parenttype": "User", "parentfield": profiles.TABLE}, fields=["name", "relationship", "full_name", "date_of_birth", "time_of_birth", "time_unknown", "place_of_birth", "permission_given", "from_chat", "summary"], order_by="idx")


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
	doc = frappe.get_doc("User", user)
	row = {"relationship": _relationship(about, (details or {}).get("relationship") or ""), "full_name": name.title() if name.islower() else name, "from_chat": 1, "permission_given": 1}  # unfiltered for now: the person's consent toggles come later and will start from the "Added From Chat" mark
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


def current(user: str, limit: int = LIMIT) -> list:
	rows = frappe.get_all("Profile Note", filters={"user": user, "is_current": 1}, fields=["noted_on", "about", "kind", "point", "guide"], order_by="noted_on desc, creation desc", limit=limit)
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


def _line(row) -> str:
	born = formatdate(row.date_of_birth, "d MMM yyyy") if row.date_of_birth else "birth date not given"
	clock = "birth time not known" if row.time_unknown else (f"at {row.time_of_birth}" if row.time_of_birth else "birth time not given")
	place = f", {row.place_of_birth}" if row.place_of_birth else ""
	who = "You" if row.relationship == profiles.SELF else f"{row.full_name} ({row.relationship.lower()})"
	status = " [added from chat, details to be completed by the person]" if row.from_chat else ""
	line = f"- {who}: {row.full_name}, born {born}, {clock}{place}{status}"
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


def card(user: str) -> str:
	"""The person and their family as the site has them, each with the summary kept from the chats, then their reports, purchases and bookings. '' when the site knows nothing of them yet."""
	lines = []
	for part in (lambda u: [_line(r) for r in _rows(u)], _reports, _orders, _bookings):
		try:
			lines += part(user)
		except Exception:
			frappe.log_error(title="person card")
	return "\n".join(lines)


def read(user: str) -> dict:
	return {"notes": current(user), "card": card(user)}


def member(user: str, who: str) -> dict:
	"""One profile for the guide's tool: the details, the summary and notes kept from the chats, and the numerology headline of the birth date when it is known. `user` is the signed-in person, set by the server."""
	rows = _rows(user)
	row = _find(rows, who)
	if row is None:
		return {"found": False, "message": "No profile matches that. Ask the person for the name, or offer to add them.", "profiles": [{"name": _label(r), "relationship": r.relationship} for r in rows]}
	out = {"found": True, "name": row.full_name, "relationship": row.relationship, "date_of_birth": str(row.date_of_birth or ""), "time_of_birth": row.time_of_birth or "",
		   "time_unknown": bool(row.time_unknown), "place_of_birth": row.place_of_birth or "", "details_complete": not profiles.row_errors(profiles.row_values(row)),
		   "summary": row.summary or "", "notes": [{"on": str(n.noted_on or ""), "kind": n.kind, "point": n.point} for n in frappe.get_all("Profile Note", filters={"user": user, "profile": row.name, "is_current": 1}, fields=["noted_on", "kind", "point"], order_by="noted_on asc", limit=20)]}
	if row.date_of_birth:
		try:
			from raftor_astrohq import astrology

			reading = (astrology.numerology(frappe.utils.getdate(row.date_of_birth).day, None, row.full_name).get("reading") or {})
			birth = reading.get("birth") or {}
			out["numerology"] = {"birth_number": birth.get("number"), "headline": birth.get("headline"), "name": reading.get("name")}
		except Exception:
			pass
	return out
