"""The digital temple: a person's own photo of the deity they worship, and the pooja they perform before it, one offering after another.

    from raftor_astrohq import temple
    temple.view()                  # what the Offering Stage Card draws: the photo, the offerings in order, the card for the next one
    temple.offer("pushpa")         # the person makes the next offering (or repeats one already made)

The pooja is data, not code (and so are its sounds: a recording of the conch, the bell, the aarti and of each mantra, any of which may be left blank, and then the card makes a bell, a conch and a chime of its own): a Pooja Kind (Panchopchar, made from pooja.json on install) holds its steps in order, each with its name, its mantra line, what it means and the offering the card draws for it
(Pooja Step.effect). Staff correct or add a pooja in Desk. The card holds no wording and no rules: every word on it and every step it may take is answered here, and a step out of order is refused here.

A person's deity is their photo (Temple Deity, a private file only they can open). A round of the pooja is kept for the day (Pooja Session): the steps made so far, and how many rounds were completed.
A finished round is counted for the stats of the plans (the meter temple_pooja, always free).
"""
import json
import os
import re

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, today

GALLERY = "Mandir Image"
KIND = "Pooja Kind"
DEITY = "Temple Deity"
SESSION = "Pooja Session"
METER = "temple_pooja"
PHOTO_TYPES = ("jpg", "jpeg", "png", "webp")
PHOTO_MAX_MB = 8
CHANNEL = re.compile(r"^UC[A-Za-z0-9_-]{22}$")  # a YouTube channel id
VIDEO = re.compile(r"^[A-Za-z0-9_-]{11}$")  # a YouTube video id
MANDIRS_MAX = 12  # the mandirs a person may keep for their daily setup
TILAKS_MAX = 12  # the marks of sandal a person may leave in a round: a deity or several


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


def _live(deity):
	"""The live darshan this mandir stands for, if it is one: the page of the channel's current stream, played by YouTube's own player (muted, so the temple's own sounds are heard), and whose it is. None for a mandir made of a picture."""
	if not (deity and deity.mandir_image):
		return None
	row = frappe.db.get_value(GALLERY, deity.mandir_image, ["title", "live_channel", "live_video", "channel_name", "official", "aarti_times", "donate_url"], as_dict=True)
	if not (row and CHANNEL.match(row.live_channel or "")):
		return None
	name = row.channel_name or row.title
	video = row.live_video if VIDEO.match(row.live_video or "") else ""
	play = "autoplay=1&mute=1&controls=0&playsinline=1&rel=0&modestbranding=1&enablejsapi=1&iv_load_policy=3"
	return {"url": f"https://www.youtube-nocookie.com/embed/{video}?{play}" if video else f"https://www.youtube-nocookie.com/embed/live_stream?channel={row.live_channel}&{play}",
			"watch": f"https://www.youtube.com/watch?v={video}" if video else f"https://www.youtube.com/channel/{row.live_channel}/live",
			"credit": (_("Live from {0}") if cint(row.official) else _("Relayed from {0}")).format(name), "times": row.aarti_times or "", "official": bool(cint(row.official))}


def _tilaks(session) -> list:
	"""Where the person left the sandal in this round: [{"x", "y"}] in percent across and down the photo."""
	try:
		marks = json.loads(session.tilaks or "[]") if session else []
	except ValueError:
		marks = []
	return [{"x": cint(m.get("x")), "y": cint(m.get("y"))} for m in marks if isinstance(m, dict)][:TILAKS_MAX]


def words(kind) -> dict:
	"""Every word the card shows besides the pooja's own (its steps, mantras and meanings come from the Pooja Kind)."""
	return {
		"upload": _("Upload photo"), "change": _("Change photo"), "photo_alt": _("Your deity"), "uploading": _("Uploading…"),
		"upload_label": _("Upload a photo of your deity"), "tilak_label": _("Place the sandal tilak on the forehead"),
		"begin": _("Add your deity's photo to begin."), "aarti": _("Perform Aarti"), "aarti_end": _("Aarti in progress · tap to end"), "again": _("Again"),
		"next": _("Next"), "done_aria": _("Done: {0}"), "next_aria": _("Offer next: {0}"), "locked_aria": _("Locked until the earlier offerings: {0}"),
		"prompts": {
			"apply": _("Tap each deity's forehead to leave the sandal there. Tap Done when you have offered it to all."),
			"circle": _("Move your finger in a circle, clockwise, to wave it before the deity."),
			"carry": _("Drag the sweet from the thali to the deity's mouth. Tap Done when you have offered it to all."),
		},
		"done": _("Done"), "auto": _("Do it for me"), "cancel": _("Cancel"), "turn_of": _("Turn {0} of {1}"), "marks": _("{0} placed"), "fed": _("{0} offered"),
		"not_image": _("Choose a photo (JPG, PNG or WebP)."), "too_big": _("The photo must be smaller than {0} MB.").format(PHOTO_MAX_MB), "failed": _("The photo could not be saved. Please try again."),
		"live": _("Live"), "watch": _("Watch on YouTube"), "stream_on": _("Hear the stream"), "stream_off": _("Mute the stream"),
		"mandirs": _("My mandirs"), "choose": _("Choose a mandir"), "upload_own": _("Upload your own"), "close": _("Close"), "current": _("Open now"), "remove": _("Remove"), "credit": _("Photo: {0} · {1}"), "gallery_title": _("Popular mandirs"), "mine_title": _("Your mandirs"),
		"title": _("Your Digital Temple"), "enter": _("Enter"), "ring_bell": _("Ring the bell"), "sound_on": _("Turn the sound on"), "sound_off": _("Turn the sound off"),
		"close_doors": _("Close the temple doors"), "leave": _("Leave the temple"),
	}


def _payload(user: str, deity, played: str = "") -> dict:
	kind = _kind()
	if not kind:
		return {"empty": _("The pooja is not available yet.")}
	session = _session(user, deity, kind) if deity else None
	live = _live(deity)
	has_photo = bool(deity and (deity.photo or live))
	total = len(kind.steps)
	done = min(cint(session.steps_done), total) if session and has_photo else 0
	finished = has_photo and done >= total
	w = words(kind)
	steps = []
	for i, step in enumerate(kind.steps):
		state = "done" if i < done else ("next" if i == done and has_photo else "locked")
		aria = {"done": w["done_aria"], "next": w["next_aria"], "locked": w["locked_aria"]}[state].format(step.label)
		steps.append({"key": step.step_key, "label": step.label, "deva": step.devanagari or "", "effect": step.effect, "state": state, "aria": aria, "sound": step.sound or "",
					  "action": step.action or "none", "turns": cint(step.turns) or 3})
	if finished:
		card = {"title": _("{0} complete").format(kind.title), "deva": "सम्पन्न", "mantra": "", "meaning": _("All {0} offerings are made. You can now do the aarti.").format(total)}
	else:
		step = kind.steps[min(done, total - 1)]
		card = {"title": f"{w['next']} · {step.label}", "deva": step.devanagari or "", "mantra": step.mantra or "", "meaning": step.meaning or ""}
	tilaks = _tilaks(session) if has_photo else []
	mine = frappe.get_all(DEITY, filters={"user": user}, fields=["name", "title", "photo", "is_main", "mandir_image"], order_by="creation asc")
	gallery = frappe.get_all(GALLERY, filters={"enabled": 1}, fields=["image_key", "title", "deity", "mandir", "image", "credit", "licence", "live_channel"], order_by="sequence asc, creation asc")
	stock = frappe.db.get_value(GALLERY, deity.mandir_image, ["title", "donate_url", "credit", "licence"], as_dict=True) if deity and deity.mandir_image else None
	return {"title": (deity.title if deity else "") or _("Your deity"), "subtitle": _("{0} Pooja · {1} offerings").format(kind.title, total), "photo": (deity.photo or "") if deity else "", "live": live,
			"steps": steps, "done": done, "total": total, "finished": finished, "card": card, "tilaks": tilaks, "played": played, "rounds": cint(session.rounds) if session else 0,
			"words": w, "upload": {"accept": list(PHOTO_TYPES), "max_mb": PHOTO_MAX_MB}, "deity": deity.name if deity else "",
			"mandirs": [{"id": m.name, "title": m.title or "", "photo": m.photo or "", "current": bool(deity and m.name == deity.name)} for m in mine],
			"gallery": [{"id": g.image_key, "title": g.title, "deity": g.deity or "", "mandir": g.mandir or "", "image": g.image or "", "live": bool(CHANNEL.match(g.live_channel or "")), "credit": w["credit"].format(g.credit or "", g.licence or "") if g.credit else ""} for g in gallery],
			"donate": {"label": _("Donate to {0}").format(stock.title), "url": stock.donate_url} if stock and stock.donate_url else None,
			"can_add": len(mine) < MANDIRS_MAX, "credit": (live["credit"] if live else w["credit"].format(stock.credit, stock.licence or "") if stock and stock.credit else ""), "immersive": True, "haptics": True, "leave_url": "/",
			"sounds": {"open": kind.sound_open or "", "bell": kind.sound_bell or "", "done": kind.sound_done or "", "aarti": kind.sound_aarti or ""}}


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
	if not (found and (found.photo or _live(found))):
		frappe.throw(_("Add your deity's photo first."), frappe.ValidationError)
	keys = [row.step_key for row in kind.steps]
	if step not in keys:
		frappe.throw(_("That is not a step of this pooja."), frappe.ValidationError)
	index, session = keys.index(step), _session(user, found, kind, create=True, lock=True)
	if index > cint(session.steps_done):
		frappe.throw(_("Make the earlier offerings first."), frappe.ValidationError)
	if kind.steps[index].action == "apply" and index == cint(session.steps_done) and not _tilaks(session):
		frappe.throw(_("Leave the sandal on a deity first."), frappe.ValidationError)
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
			session.steps_done, session.status, session.tilaks = 0, "Open", "[]"
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


def _make_main(user: str, deity) -> None:
	"""This mandir is the one open now; the person's others are put by."""
	for other in frappe.get_all(DEITY, filters={"user": user, "name": ["!=", deity.name], "is_main": 1}, pluck="name"):
		frappe.db.set_value(DEITY, other, "is_main", 0, update_modified=False)
	if not deity.is_main:
		deity.is_main = 1
		deity.save(ignore_permissions=True)


def _new_mandir(user: str, title: str, photo: str, stock: str = ""):
	if frappe.db.count(DEITY, {"user": user}) >= MANDIRS_MAX:
		frappe.throw(_("You have kept as many mandirs as you can. Remove one first."), frappe.ValidationError)
	deity = frappe.get_doc({"doctype": DEITY, "user": user, "title": title, "photo": photo, "mandir_image": stock or None, "is_main": 0}).insert(ignore_permissions=True)
	_make_main(user, deity)
	return deity


@frappe.whitelist(methods=["POST"])
def set_photo(file_url: str, deity: str = "", new: int = 0) -> dict:
	"""The person's own photo of a mandir, uploaded as a private file of their own just before. It becomes a mandir of theirs and the one open now (`new`), or replaces the picture of the deity named; either way today's round begins again."""
	user = _user()
	file_name = frappe.db.get_value("File", {"file_url": file_url, "owner": user, "is_private": 1}, "name")
	if not file_name:
		frappe.throw(_("The photo could not be found."), frappe.ValidationError)
	_checked_image(file_name)
	found = None if cint(new) else _deity(user, deity)
	if not found:
		count = frappe.db.count(DEITY, {"user": user})
		found = _new_mandir(user, _("My mandir") if not count else _("My mandir {0}").format(count + 1), file_url)
	else:
		found.photo, found.mandir_image = file_url, None
		found.save(ignore_permissions=True)
		kind = _kind()
		session = _session(user, found, kind, lock=True) if kind else None
		if session:  # a different photo is a different deity: today's round begins again
			session.steps_done, session.status, session.tilaks = 0, "Open", "[]"
			session.save(ignore_permissions=True)
	frappe.db.set_value("File", file_name, {"attached_to_doctype": DEITY, "attached_to_name": found.name, "attached_to_field": "photo"}, update_modified=False)
	return _payload(user, found)


@frappe.whitelist(methods=["POST"])
def choose_mandir(image: str) -> dict:
	"""The person picks a mandir from the gallery: it becomes one of theirs and the one open now. Picking one they already keep only opens it."""
	user = _user()
	stock = frappe.db.get_value(GALLERY, {"image_key": image, "enabled": 1}, ["name", "title", "image"], as_dict=True)
	if not stock:
		frappe.throw(_("That mandir is not in the gallery."), frappe.ValidationError)
	have = frappe.db.get_value(DEITY, {"user": user, "mandir_image": stock.name}, "name")
	found = frappe.get_doc(DEITY, have) if have else _new_mandir(user, stock.title, stock.image or "", stock.name)
	_make_main(user, found)
	return _payload(user, found)


@frappe.whitelist(methods=["POST"])
def switch_mandir(deity: str) -> dict:
	"""The person opens another of their mandirs."""
	user = _user()
	found = _deity(user, deity) if deity else None
	if not (found and found.name == deity):
		frappe.throw(_("That mandir is not yours."), frappe.ValidationError)
	_make_main(user, found)
	return _payload(user, found)


@frappe.whitelist(methods=["POST"])
def remove_mandir(deity: str) -> dict:
	"""The person puts one of their mandirs away, with its rounds."""
	user = _user()
	found = _deity(user, deity) if deity else None
	if not (found and found.name == deity):
		frappe.throw(_("That mandir is not yours."), frappe.ValidationError)
	frappe.db.delete(SESSION, {"user": user, "deity": found.name})
	frappe.delete_doc(DEITY, found.name, ignore_permissions=True, force=True)
	return _payload(user, _deity(user))


@frappe.whitelist(methods=["POST"])
def place_tilak(x, y, deity: str = "") -> dict:
	"""The person leaves a mark of sandal on a deity of their photo (percent across and down); it stays for the round, and another mark may be left for another deity."""
	user = _user()
	kind, found = _kind(), _deity(user, deity)
	if not (kind and found and (found.photo or _live(found))):
		frappe.throw(_("Add your deity's photo first."), frappe.ValidationError)
	session = _session(user, found, kind, create=True, lock=True)
	marks = _tilaks(session)
	if len(marks) >= TILAKS_MAX:
		frappe.throw(_("That is enough sandal for one round."), frappe.ValidationError)
	marks.append({"x": max(0, min(100, cint(x))), "y": max(0, min(100, cint(y)))})
	session.tilaks = json.dumps(marks)
	session.save(ignore_permissions=True)
	return _payload(user, found)
