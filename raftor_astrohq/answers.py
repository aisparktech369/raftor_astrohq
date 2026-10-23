"""What the astrology engine answered, kept for each person so that a report, a page and a second report made from it cost no new call.

    from raftor_astrohq import answers
    data = answers.get(user, numbers, "CORE_ADVANCED")                 # kept after the first time, then read back
    both = answers.bundle(user, numbers, ["CORE_ADVANCED", "KP_SYSTEM"])   # {mode: answer}

An answer is kept under a fingerprint of the person, the mode and the numbers the engine is sent (nothing else: never a name or a place), so the same person asking again for the same birth finds it,
and nobody else ever does. It is packed (gzip) in an `Astro Answer` record only a System Manager can open, goes with the person (their User's deletion removes it, `forget_user`), and is asked for again
when it was made before the date in Astrology API Settings, Kept Answers Are Good From (put today's date there after the engine is updated). `chart` is server-side code: it checks nobody; the caller has already
checked that this person may see this birth (astrology.py says how).

A chart asked for another moment than a birth (today's sky) is a different thing: it is not kept for good, only for a day (`sky`).
"""
import base64
import gzip
import hashlib
import json

import frappe
from frappe.utils import getdate

from raftor_astrohq import astrology

DOCTYPE = "Astro Answer"
SKY_SECONDS = 24 * 60 * 60


def fingerprint(user: str, mode: str, numbers: dict, partner: dict | None = None) -> str:
	"""One fingerprint for who asked, which mode and the numbers sent to the engine (only those it is sent: see astrology.SENT)."""
	text = json.dumps({"user": user, "mode": mode, "birth": astrology._sendable(numbers), "partner": astrology._sendable(partner) if partner else None}, sort_keys=True, separators=(",", ":"))
	return hashlib.sha256(text.encode()).hexdigest()


def pack(data: dict) -> str:
	return base64.b64encode(gzip.compress(json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode(), 6)).decode()


def unpack(text: str) -> dict:
	return json.loads(gzip.decompress(base64.b64decode(text)).decode())


def _good_from():
	return frappe.db.get_single_value("Astrology API Settings", "answers_valid_from")


def found(key: str) -> dict | None:
	"""The kept answer under this fingerprint, unless it was made before the date the settings say answers are good from."""
	row = frappe.db.get_value(DOCTYPE, key, ["answer", "made_on"], as_dict=True)
	if not row or not row.answer:
		return None
	good_from = _good_from()
	if good_from and getdate(row.made_on) < getdate(good_from):
		return None
	return unpack(row.answer)


def keep(user: str, mode: str, key: str, data: dict) -> None:
	"""Keeps (or replaces) the answer under its fingerprint."""
	packed = pack(data)
	values = {"answer": packed, "made_on": frappe.utils.now_datetime(), "size_kb": max(1, len(packed) // 1024)}
	if frappe.db.exists(DOCTYPE, key):
		frappe.db.set_value(DOCTYPE, key, values)
		return
	try:
		frappe.get_doc({"doctype": DOCTYPE, "user": user, "mode": mode, "key": key, **values}).insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:  # two requests for the same birth at once: the other one kept it
		pass


def get(user: str, numbers: dict, mode: str, partner: dict | None = None, kept: bool = True) -> dict:
	"""The engine's answer for this birth in this mode: the kept one, or asked for now and kept (not when `kept` is False or there is no signed-in person to keep it for)."""
	if not kept or not user or user == "Guest":
		return astrology.chart(numbers, mode, partner)
	key = fingerprint(user, mode, numbers, partner)
	data = found(key)
	if data is None:
		data = astrology.chart(numbers, mode, partner)
		keep(user, mode, key, data)
	return data


def bundle(user: str, numbers: dict, modes: list[str], partner: dict | None = None) -> dict[str, dict]:
	"""{mode: answer} for each mode, every one kept."""
	return {mode: get(user, numbers, mode, partner if mode == "MATCH_CALC" else None) for mode in modes}


def sky(numbers: dict, mode: str = "SUPER_BASIC") -> dict:
	"""The sky at another moment than a birth (a "birth" at that moment: today's planets): kept for a day in the cache, for anyone, since it is not about a person."""
	key = "astro_sky:" + hashlib.sha256(json.dumps(astrology._sendable(numbers), sort_keys=True).encode()).hexdigest()[:32] + ":" + mode
	cached = frappe.cache().get_value(key, expires=True)
	if cached:
		return cached
	data = astrology.chart(numbers, mode)
	frappe.cache().set_value(key, data, expires_in_sec=SKY_SECONDS)
	return data


def forget(user: str) -> int:
	"""Removes everything kept for a person; how many."""
	count = frappe.db.count(DOCTYPE, {"user": user})
	if count:
		frappe.db.delete(DOCTYPE, {"user": user})
	return count


def forget_user(doc, method=None) -> None:
	"""A User is being deleted: what was kept for them goes with them (hook `doc_events`)."""
	forget(doc.name)
