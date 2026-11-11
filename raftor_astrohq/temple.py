"""The digital temple: a person's own photo of the deity they worship, and the pooja they perform before it, one offering after another.

    from raftor_astrohq import temple
    temple.view()                  # what the Offering Stage Card draws: the photo, the offerings in order, the card for the next one
    temple.offer("pushpa")         # the person makes the next offering (or repeats one already made)

The pooja is data, not code: a Pooja Kind (Panchopchar, made from pooja.json on install) holds its steps in order, each with its name, its mantra line, what it means and the offering the card draws for it
(Pooja Step.effect). Staff correct or add a pooja in Desk. The card holds no wording and no rules: every word on it and every step it may take is answered here, and a step out of order is refused here.

A person's deity is their photo (Temple Deity, a private file only they can open). A round of the pooja is kept for the day (Pooja Session): the steps made so far, and how many rounds were completed.
A finished round is counted for the stats of the plans (the meter temple_pooja, always free).
"""
import os

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, today

KIND = "Pooja Kind"
DEITY = "Temple Deity"
SESSION = "Pooja Session"
METER = "temple_pooja"
PHOTO_TYPES = ("jpg", "jpeg", "png", "webp")
PHOTO_MAX_MB = 8
TILAK = (50, 42)  # where the sandal tilak is first put (percent across and down the photo): the forehead of a deity seated in the middle


def _user() -> str:
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in first."), frappe.PermissionError)
	return frappe.session.user


def _kind():
	"""The pooja offered now: the first one that is on, in the order staff gave. None when there is none."""
	name = frappe.db.get_value(KIND, {"enabled": 1}, "name", order_by="sequence asc, creation asc")
	return frappe.get_doc(KIND, name) if name else None


def _deity(user: str, name: str = ""):
	"""The person's deity: the one asked for if it is theirs, else their main one. Never someone else's."""
	filters = {"user": user}
	if name:
		filters["name"] = name
	found = frappe.db.get_value(DEITY, filters, "name", order_by="is_main desc, creation asc")
	return frappe.get_doc(DEITY, found) if found else None


def _session(user: str, deity, kind, create: bool = False, lock: bool = False):
	"""Today's round of this pooja before this deity; made when asked to."""
	found = frappe.db.get_value(SESSION, {"user": user, "deity": deity.name, "kind": kind.name, "session_date": today()}, "name", for_update=lock)
	if found:
		return frappe.get_doc(SESSION, found)
	if not create:
		return None
	return frappe.get_doc({"doctype": SESSION, "user": user, "deity": deity.name, "kind": kind.name, "session_date": today(), "steps_done": 0, "status": "Open"}).insert(ignore_permissions=True)


def words(kind) -> dict:
	"""Every word the card shows besides the pooja's own (its steps, mantras and meanings come from the Pooja Kind)."""
	return {
		"upload": _("Upload photo"), "change": _("Change photo"), "photo_alt": _("Your deity"), "uploading": _("Uploading…"),
		"upload_label": _("Upload a photo of your deity"), "tilak_label": _("Place the sandal tilak on the forehead"),
		"begin": _("Add your deity's photo to begin."), "aarti": _("Perform Aarti"), "aarti_end": _("Aarti in progress · tap to end"), "again": _("Again"),
		"next": _("Next"), "done_aria": _("Done: {0}"), "next_aria": _("Offer next: {0}"), "locked_aria": _("Locked until the earlier offerings: {0}"),
		"tilak_hint": _("Tap the photo to place the tilak where you wish."),
		"not_image": _("Choose a photo (JPG, PNG or WebP)."), "too_big": _("The photo must be smaller than {0} MB.").format(PHOTO_MAX_MB), "failed": _("The photo could not be saved. Please try again."),
		"title": _("Your Digital Temple"),
	}


def _payload(user: str, deity, played: str = "") -> dict:
	kind = _kind()
	if not kind:
		return {"empty": _("The pooja is not available yet.")}
	session = _session(user, deity, kind) if deity else None
	has_photo = bool(deity and deity.photo)
	total = len(kind.steps)
	done = min(cint(session.steps_done), total) if session and has_photo else 0
	finished = has_photo and done >= total
	w = words(kind)
	steps = []
	for i, step in enumerate(kind.steps):
		state = "done" if i < done else ("next" if i == done and has_photo else "locked")
		aria = {"done": w["done_aria"], "next": w["next_aria"], "locked": w["locked_aria"]}[state].format(step.label)
		steps.append({"key": step.step_key, "label": step.label, "deva": step.devanagari or "", "effect": step.effect, "state": state, "aria": aria})
	if finished:
		card = {"title": _("{0} complete").format(kind.title), "deva": "सम्पन्न", "mantra": "", "meaning": _("All {0} offerings are made. You can now do the aarti.").format(total)}
	else:
		step = kind.steps[min(done, total - 1)]
		card = {"title": f"{w['next']} · {step.label}", "deva": step.devanagari or "", "mantra": step.mantra or "", "meaning": step.meaning or ""}
		if step.effect == "sandal":
			card["hint"] = w["tilak_hint"]
	tilak = {"x": cint(deity.tilak_x) if deity else TILAK[0], "y": cint(deity.tilak_y) if deity else TILAK[1]}
	return {"title": (deity.title if deity else "") or _("Your deity"), "subtitle": _("{0} Pooja · {1} offerings").format(kind.title, total), "photo": (deity.photo if has_photo else ""),
			"steps": steps, "done": done, "total": total, "finished": finished, "card": card, "tilak": tilak, "played": played, "rounds": cint(session.rounds) if session else 0,
			"words": w, "upload": {"accept": list(PHOTO_TYPES), "max_mb": PHOTO_MAX_MB}}


@frappe.whitelist(methods=["POST"])
def view(deity: str = "") -> dict:
	"""What the card draws now for the signed-in person."""
	user = _user()
	return _payload(user, _deity(user, deity))


@frappe.whitelist(methods=["POST"])
def offer(step: str, deity: str = "") -> dict:
	"""The person makes an offering: the next one in order, or one already made, which is only shown again. Anything further on is refused."""
	user = _user()
	kind, found = _kind(), _deity(user, deity)
	if not kind:
		frappe.throw(_("The pooja is not available yet."), frappe.ValidationError)
	if not (found and found.photo):
		frappe.throw(_("Add your deity's photo first."), frappe.ValidationError)
	keys = [row.step_key for row in kind.steps]
	if step not in keys:
		frappe.throw(_("That is not a step of this pooja."), frappe.ValidationError)
	index, session = keys.index(step), _session(user, found, kind, create=True, lock=True)
	if index > cint(session.steps_done):
		frappe.throw(_("Make the earlier offerings first."), frappe.ValidationError)
	if index == cint(session.steps_done) and index < len(keys):
		session.steps_done = index + 1
		if session.steps_done == len(keys):
			session.status, session.completed_on, session.rounds = "Completed", now_datetime(), cint(session.rounds) + 1
			_count(user)
		session.save(ignore_permissions=True)
	return _payload(user, found, played=kind.steps[index].effect)


@frappe.whitelist(methods=["POST"])
def again(deity: str = "") -> dict:
	"""Begin a new round of the pooja."""
	user = _user()
	kind, found = _kind(), _deity(user, deity)
	if kind and found:
		session = _session(user, found, kind, lock=True)
		if session:
			session.steps_done, session.status = 0, "Open"
			session.save(ignore_permissions=True)
	return _payload(user, found)


def _count(user: str) -> None:
	"""A finished round is counted for the stats; the temple is always free."""
	from raftor_servicehq import plans

	plans.use(user, METER)


def _checked_image(file_name: str) -> None:
	"""The uploaded file must be a photo of a kind we show, and not too big: its ending, its size and its content are all looked at."""
	from PIL import Image

	record = frappe.get_doc("File", file_name)
	path = record.get_full_path()
	if (record.file_name or "").rsplit(".", 1)[-1].lower() not in PHOTO_TYPES:
		frappe.throw(_("Choose a photo (JPG, PNG or WebP)."), frappe.ValidationError)
	if os.path.getsize(path) > PHOTO_MAX_MB * 1024 * 1024:
		frappe.throw(_("The photo must be smaller than {0} MB.").format(PHOTO_MAX_MB), frappe.ValidationError)
	try:
		with Image.open(path) as image:
			image.verify()
	except Exception:
		frappe.throw(_("Choose a photo (JPG, PNG or WebP)."), frappe.ValidationError)


@frappe.whitelist(methods=["POST"])
def set_photo(file_url: str, deity: str = "") -> dict:
	"""The person's photo of their deity, uploaded as a private file of their own just before. The first photo makes their deity; a later one replaces it and the tilak goes back to its first place."""
	user = _user()
	file_name = frappe.db.get_value("File", {"file_url": file_url, "owner": user, "is_private": 1}, "name")
	if not file_name:
		frappe.throw(_("The photo could not be found."), frappe.ValidationError)
	_checked_image(file_name)
	found = _deity(user, deity)
	if not found:
		found = frappe.get_doc({"doctype": DEITY, "user": user, "title": _("My deity"), "is_main": 1, "photo": file_url, "tilak_x": TILAK[0], "tilak_y": TILAK[1]}).insert(ignore_permissions=True)
	else:
		found.update({"photo": file_url, "tilak_x": TILAK[0], "tilak_y": TILAK[1]})
		found.save(ignore_permissions=True)
	frappe.db.set_value("File", file_name, {"attached_to_doctype": DEITY, "attached_to_name": found.name, "attached_to_field": "photo"}, update_modified=False)
	return _payload(user, found)


@frappe.whitelist(methods=["POST"])
def place_tilak(x, y, deity: str = "") -> dict:
	"""Where on the photo the person wants the sandal tilak (percent across and down); kept for the next time."""
	user = _user()
	found = _deity(user, deity)
	if not found:
		frappe.throw(_("Add your deity's photo first."), frappe.ValidationError)
	found.tilak_x, found.tilak_y = max(0, min(100, cint(x))), max(0, min(100, cint(y)))
	found.save(ignore_permissions=True)
	return {"x": found.tilak_x, "y": found.tilak_y}
