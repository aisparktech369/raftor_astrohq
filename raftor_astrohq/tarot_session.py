"""A tarot session in a chat: the page's draw (tarot.py), taken one card at a time, so a guide can conduct it.

    start(user, spread, question, topic)    shuffles the whole deck once, face down, and keeps it for the person (a Tarot Reading with source "chat"); no spread: the offered spreads are listed to choose from
    deal(user, pick, clarifier, session)    turns over one card into the next place of the spread: the card the person pointed to (`pick`, a number among the cards still face down), else the top card
    state(user, session)                    the cards so far, the places still empty, whether the spread is full and, when it is, the Academy's words on how to read it

It is the same deck and the same draw as the page: the shuffle is tarot_deck.shuffled() (`secrets`), the words of a card and of a spread are the Academy's (tarot_deck.py), and the card's picture is public/tarot/<card id>.webp.
The guide never names a card and never draws by itself: every card it speaks of came out of `deal`. The person is never named by the model: the server puts the signed-in person into `user` (the blueprint's guardrails.session_user_tools),
so a guide can only open the session of the person it is talking to. A session is open for a day; with no `session` given, the person's latest one is meant, so the guide has no token to carry.
After the spread is full the guide gives its reading in the chat, and may turn over up to two clarifier cards if something is unclear: the conversation goes on from the same cards."""
import json
import secrets

import frappe
from frappe.utils import add_to_date, now_datetime, strip_html_tags

from raftor_astrohq import tarot
from raftor_astrohq import tarot_deck as deck

DOCTYPE = tarot.DOCTYPE
OPEN_HOURS = 24
CLARIFIERS_MAX = 2
CLARIFIER = {"label": "Clarifier", "hint": "A second look at what was unclear"}
GUIDANCE_LENGTH = 1800


PACE_SECONDS = 6  # a second card is not turned over within this many seconds of the last: one card for each reply, so the person answers before the next (tests set it to 0)


def _refused(message: str, **more) -> dict:
	return {"ok": False, "message": message, **more}


def _signed_in(user) -> bool:
	return bool(user) and str(user).strip() not in ("", "Guest")


def _spread_of(doc) -> dict | None:
	return deck.spread(doc.spread or deck.DEFAULT_SPREAD)


def _extras(cards: list[dict]) -> int:
	return sum(1 for c in cards if c.get("extra"))


def _places(spread: dict, extras: int) -> list[dict]:
	"""The places of the spread, then one for each clarifier turned over."""
	return [*spread["positions"], *([CLARIFIER] * extras)]


def _full(spread: dict, cards: list[dict]) -> bool:
	return len(cards) - _extras(cards) >= len(spread["positions"])


def _sessions(user: str, token: str | None = None) -> list:
	"""The person's chat sessions of the last day, the latest first (the one named, when a token is given)."""
	filters = {"user": user, "source": "chat", "creation": [">", add_to_date(now_datetime(), hours=-OPEN_HOURS)]}
	if token:
		filters["name"] = str(token).strip()[:64]
	return [frappe.get_doc(DOCTYPE, name) for name in frappe.get_all(DOCTYPE, filters=filters, order_by="creation desc", pluck="name", limit=10)]


def _latest(user: str, token: str | None, open_only: bool):
	for doc in _sessions(user, token):
		spread = _spread_of(doc)
		if spread and (not open_only or not _full(spread, json.loads(doc.cards or "[]"))):
			return doc
	return None


def _card_out(entry: dict, spread: dict, extras: int, place: int) -> dict:
	"""A card as the guide is given it: where it lies, what it is, and what the Academy says of it."""
	views = {**spread, "positions": _places(spread, extras)}
	card = tarot._card(entry, views, place)
	return {"place": place + 1, "where": card["label"], "where_hint": card["hint"], "card": card["name"], "id": card["id"], "arcana": card["arcana"], "suit": card["suit"], "orientation": card["orientation"],
			"what_it_means": card["keywords"], "what_it_says": card["meaning"], "also_said": card["extra"], "picture": (deck.card(card["id"]) or {}).get("picture", ""), "image": card["image"], "link": card["link"]}


def _method(full: bool) -> dict:
	"""The part of the Academy's methodology for conducting a session that the guide needs next: how to turn over the cards while places are left, how to read, go deeper and close once the spread is full."""
	return deck.conduct("giving the reading", "going deeper", "closing", "care") if full else deck.conduct("choosing the cards", "turning over the cards", "care")


def _guidance(spread: dict) -> dict:
	return {"how_to_read_this_spread": spread.get("read") or "", "practice_notes": deck.practice_notes()[:GUIDANCE_LENGTH]}


def _shape(doc) -> dict:
	"""The session as it stands: the cards turned over, the places still empty, and (once the spread is full) how to read it."""
	spread = _spread_of(doc)
	cards = json.loads(doc.cards or "[]")
	extras = _extras(cards)
	places = _places(spread, extras)
	shown = [_card_out(entry, spread, extras, n) for n, entry in enumerate(cards)]
	full = _full(spread, cards)
	out = {"ok": True, "session": doc.name, "spread": {"key": spread["key"], "title": spread["title"], "cards": len(spread["positions"])}, "question": doc.question or "", "topic": doc.topic or "",
		   "cards_turned_over": shown, "places_left": [p["label"] for p in places[len(cards):]] if not full else [], "face_down": len(json.loads(doc.fan or "[]")),
		   "spread_full": full, "clarifiers_used": extras, "clarifiers_left": max(CLARIFIERS_MAX - extras, 0) if full else 0, "how_to_conduct": _method(full)}
	if full:
		out["reading_guide"] = _guidance(spread)
	return out


def start(user, spread=None, question=None, topic=None) -> dict:
	"""Begins a session for the signed-in person: the deck shuffled once, face down. Without a spread (or with one the page does not offer) the spreads are listed, to choose from."""
	if not _signed_in(user):
		return _refused("Nobody is signed in, so a tarot session cannot be kept. Ask them to sign in to draw cards.")
	chosen = deck.spread(spread)
	if not chosen or spread != chosen["key"]:  # none given, or one the page does not offer (the deck then answers with its default)
		return {"ok": False, "choose_a_spread": [{"key": s["key"], "title": s["title"], "use_for": s["intro"], "cards": len(s["positions"]), "places": [p["label"] for p in s["positions"]]} for s in deck.spreads()],
				"message": "Choose the spread that fits what the person wants to explore, and start again with its key."}
	fan = deck.shuffled()
	if len(fan) < len(chosen["positions"]):
		return _refused("The tarot deck is not available right now. Say so, and offer a live tarot reader.")
	token = secrets.token_urlsafe(9)
	topics = dict(tarot.TOPICS)
	frappe.get_doc({"doctype": DOCTYPE, "token": token, "user": str(user).strip(), "question": strip_html_tags(str(question or "")).strip()[:tarot.QUESTION_LENGTH], "topic": topic if topic in topics else "",
					"spread": chosen["key"], "cards": "[]", "fan": json.dumps(fan), "source": "chat", "interpretation": "", "model": ""}).insert(ignore_permissions=True)
	out = _shape(frappe.get_doc(DOCTYPE, token))
	out["places"] = [{"n": n + 1, "label": p["label"], "hint": p["hint"]} for n, p in enumerate(chosen["positions"])]
	out["how_to_conduct"] = deck.conduct()  # the whole of the Academy's methodology, from the opening to the care
	out["note"] = (f"The deck is shuffled and lies face down: {out['face_down']} cards. Conduct the session as how_to_conduct says (the Academy's methodology): decide from the conversation whether the person chooses their cards "
				   f"(ask for a number from 1 to {out['face_down']} for each card, and pass it as `pick`) or you deal for them (leave `pick` out). Call deal_tarot_card once for each place, in order.")
	return out


def deal(user, pick=None, clarifier=False, session=None) -> dict:
	"""Turns over one card into the next place: the one the person pointed to (`pick`, 1 to the cards still face down), else the top card. `clarifier` adds one more card once the spread is full."""
	if not _signed_in(user):
		return _refused("Nobody is signed in, so there is no tarot session to draw from.")
	doc = _latest(str(user).strip(), session, open_only=False)
	if not doc:
		return _refused("There is no tarot session from the last day. Call start_tarot_session first.")
	spread = _spread_of(doc)
	cards, fan = json.loads(doc.cards or "[]"), json.loads(doc.fan or "[]")
	full = _full(spread, cards)
	if clarifier and not full:
		return _refused("The spread is not full yet: deal the places in order first.")
	if clarifier and _extras(cards) >= CLARIFIERS_MAX:
		return _refused("Two clarifier cards have been turned over already. Give your reading from the cards on the table.")
	if full and not clarifier:
		return {**_shape(doc), "ok": False, "message": "Every place of the spread is full. Give the reading now, or turn over a clarifier if something is unclear."}
	if not fan:
		return _refused("There are no cards left face down.")
	if cards and PACE_SECONDS and (now_datetime() - doc.modified).total_seconds() < PACE_SECONDS:
		return _refused("A card was turned over a moment ago and the person has not answered yet. Do not turn over another one in this reply: speak of the card on the table, ask what it brings up for them, and wait for their answer.", **{k: v for k, v in _shape(doc).items() if k in ("face_down", "spread_full")})
	index = 0
	if pick not in (None, ""):
		try:
			index = int(pick) - 1
		except (TypeError, ValueError):
			index = -1
		if not 0 <= index < len(fan):
			return _refused(f"Choose a number from 1 to {len(fan)}.", face_down=len(fan))
	entry = fan.pop(index)
	cards.append({"id": entry["id"], "r": bool(entry["r"]), **({"extra": True} if clarifier else {})})
	doc.cards, doc.fan = json.dumps(cards), json.dumps(fan)
	doc.save(ignore_permissions=True)
	extras = _extras(cards)
	out = _shape(doc)
	out["dealt"] = _card_out(cards[-1], spread, extras, len(cards) - 1)
	out["note"] = ("The card is the one that came out: speak of it as it is given here, in its place, in two to four sentences, then ask the person one question about how it lands for them, and STOP. Turn over no other card in this reply. " +
				   ("This was the last place: wait for their answer, then give your reading of the cards together." if out["spread_full"] and not clarifier else
					"The next card is turned over only after they have answered you." if not out["spread_full"] else "Say what it adds to the reading, then ask what it brings up."))
	return out


def state(user, session=None) -> dict:
	"""The person's latest tarot session of the last day (or the one named), as it stands."""
	if not _signed_in(user):
		return _refused("Nobody is signed in, so there is no tarot session to open.")
	doc = _latest(str(user).strip(), session, open_only=False)
	if not doc:
		return _refused("There is no tarot session from the last day. Call start_tarot_session to begin one.")
	return _shape(doc)
