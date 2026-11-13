"""The tarot deck and its spreads, read from the knowledge base: the Markdown articles of the Tarot category in the astrohq domain. They are the one source: the Academy shows them, the guides search them,
and this page and the guides' draw tool draw from them, so every one of them says the same thing about a card. Nothing about a card or a spread is worded here.

A card is the article `tarot-card-<name>`: `00-fool` ... `21-world` for the twenty-two major cards, `<suit>-<rank>` (`wands-ace` ... `pentacles-king`) for the fifty-six minor cards. That name is the card's id
everywhere (a stored reading, a picture, a tool call): the picture of a card is `public/tarot/<id>.webp` (see docs/tarot.md). A spread is the article `tarot-spread-<name>`, its places listed under `## Positions`.

What this file does hold is not wording: the order of the deck, the numeral on a card face, and which symbol of the site's icon set stands for a card or a suit."""
import os
import re
import secrets
import time

import frappe

from raftor_astrohq import content

CATEGORY = "tarot"
CARD = "tarot-card-"
SPREAD = "tarot-spread-"
PRACTICE = "tarot-method-practice-notes"
CONDUCT = "tarot-method-conducting-a-session"  # the ceremony: how a session is conducted, from the opening to the close
KEEP_SECONDS = 300  # how long the parsed deck is kept before the files are read again
REVERSED_ONE_IN = 4  # a card comes out reversed one time in four

SUITS = ("wands", "cups", "swords", "pentacles")
SUIT_ICON = {"wands": "wand", "cups": "cup", "swords": "sword", "pentacles": "coin"}  # (names of website_hq/icons.py)
RANKS = ("ace", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "page", "knight", "queen", "king")
RANK_MARK = dict(zip(RANKS, ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "P", "Kn", "Q", "K")))
ROMAN = ("0", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI")
MAJOR_ICON = ("child", "hand", "book", "heart", "shield", "bell", "rings", "truck", "flame", "lamp", "wheel", "scales", "return", "hourglass", "cup", "chain", "tower", "star", "moon", "sun", "check", "globe")

# The spreads the page offers, in the order it shows them, and the one it starts on. The rest of the spreads are in the Academy for a reader who lays the cards out by hand.
OFFERED = ("one-card-draw", "three-card-spread", "yes-or-no", "five-card-spread")
DEFAULT_SPREAD = "three-card-spread"

_kept: dict = {"at": 0.0, "data": None}
POSITION = re.compile(r"^\s*\d+\.\s+\*\*(.+?)\*\*\s*[—–-]\s*(.+?)\s*$", re.M)


def slug_of(text: str) -> str:
	return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def _sections(body: str) -> dict[str, str]:
	"""The `## ` sections of an article: {heading in lower case: its text}; the text before the first section is under ""."""
	found, name, lines = {}, "", []
	for line in str(body or "").splitlines():
		if line.startswith("## "):
			found[name] = "\n".join(lines).strip()
			name, lines = line[3:].strip().lower(), []
		elif not line.startswith("# "):
			lines.append(line)
	found[name] = "\n".join(lines).strip()
	return found


def _intro(sections: dict[str, str]) -> str:
	return next((p.strip() for p in sections.get("", "").split("\n\n") if p.strip() and not p.strip().startswith("**Card")), "")


def _card(item: dict) -> dict | None:
	stem = item["id"][len(CARD):]
	parts = _sections(item["body"])
	number = re.match(r"(\d\d)-", stem)
	if number:
		n = int(number.group(1))
		if n >= len(ROMAN):
			return None
		suit, rank, numeral, icon, order = None, None, ROMAN[n], MAJOR_ICON[n], n
	else:
		suit, _, rank = stem.partition("-")
		if suit not in SUITS or rank not in RANKS:
			return None
		numeral, icon, order = RANK_MARK[rank], SUIT_ICON[suit], 100 + SUITS.index(suit) * 20 + RANKS.index(rank)
	return {"id": stem, "name": item["title"], "arcana": "major" if number else "minor", "suit": suit, "rank": rank, "number": order if number else None, "numeral": numeral, "icon": icon, "order": order,
			"picture": parts.get("what the picture shows", ""), "headline": parts.get("what it means", ""), "upright": parts.get("upright", ""), "reversed": parts.get("reversed", ""),
			"extra": parts.get("extra meanings", ""), "link": content.route_of(item)}


def _spread(item: dict) -> dict | None:
	key = item["id"][len(SPREAD):]
	parts = _sections(item["body"])
	places = [{"label": label.strip(), "hint": hint.strip()} for label, hint in POSITION.findall(parts.get("positions", ""))]
	if not places:
		return None
	return {"key": key, "title": item["title"], "intro": _intro(parts), "positions": places, "draw": parts.get("how to draw", ""), "read": parts.get("how to read", ""), "link": content.route_of(item)}


def _build() -> dict:
	items = content.domain_files_of(CATEGORY)
	cards = sorted((c for c in (_card(i) for i in items if i["id"].startswith(CARD)) if c), key=lambda c: c["order"])
	spreads = {s["key"]: s for s in (_spread(i) for i in items if i["id"].startswith(SPREAD)) if s}
	practice = next((_sections(i["body"]) for i in items if i["id"] == PRACTICE), {})
	conduct = next((_sections(i["body"]) for i in items if i["id"] == CONDUCT), {})
	return {"cards": cards, "by_id": {c["id"]: c for c in cards}, "spreads": spreads, "practice": "\n\n".join(f"{name.capitalize()}:\n{text}" for name, text in practice.items() if name and text and name != "related reading"),
			"conduct": {name: text for name, text in conduct.items() if name and text and name != "related reading"}}


def load(force: bool = False) -> dict:
	"""The deck as it stands in the knowledge base, kept for a few minutes (a change to an article reaches the page then, or at once after `load(force=True)`)."""
	if force or _kept["data"] is None or time.time() - _kept["at"] > KEEP_SECONDS:
		_kept["data"], _kept["at"] = _build(), time.time()
	return _kept["data"]


def cards() -> list[dict]:
	"""Every card, in the deck's order: the twenty-two major cards by number, then wands, cups, swords and pentacles from the ace to the king."""
	return load()["cards"]


def card(card_id: str) -> dict | None:
	return load()["by_id"].get(str(card_id or ""))


def spreads() -> list[dict]:
	"""The spreads the page offers, in order."""
	data = load()["spreads"]
	return [data[key] for key in OFFERED if key in data]


def spread(key: str | None) -> dict | None:
	"""The spread of this key if the page offers it, else the default one."""
	data = load()["spreads"]
	return data.get(key) if key in OFFERED and key in data else data.get(DEFAULT_SPREAD)


def practice_notes() -> str:
	"""How a reading is to be given, from the Academy's practice notes: the guides and the page's writer both follow it."""
	return load()["practice"]


def shuffled() -> list[dict]:
	"""The whole deck face down: every card once, in a random order (`secrets`), each upright or reversed. The one draw of the page and of the chat tools: a draw takes cards from the top, or from where the person points."""
	chooser = secrets.SystemRandom()
	ids = [c["id"] for c in cards()]
	chooser.shuffle(ids)
	return [{"id": card_id, "r": chooser.randrange(REVERSED_ONE_IN) == 0} for card_id in ids]


def conduct(*parts: str) -> dict[str, str]:
	"""The Academy's methodology for conducting a session, by section in the order it is written (opening, choosing the spread, choosing the cards, turning over the cards, giving the reading, going deeper, closing, care).
	With names, only those sections. The guides are given it by the tools, so the ceremony they conduct is the one the Academy defines."""
	sections = load()["conduct"]
	return {name: text for name, text in sections.items() if not parts or name in parts}


def image(card_id: str) -> str:
	"""The address of the picture of a card (or "back"), else nothing: the page then draws the card from its symbol. The pictures are the factory's (domains/astrohq/media/tarot/<card id>.webp), delivered once
	by AgentsHQ and shown from the same address by the page, the Academy and the guides' chat. A site that has not had them delivered yet is given what an earlier version kept in public/tarot."""
	from raftor_agentshq import media

	delivered = media.url("astrohq", f"tarot/{card_id}")
	if delivered:
		return delivered
	for ending in ("webp", "jpg", "jpeg", "png"):
		if os.path.exists(frappe.get_app_path("raftor_astrohq", "public", "tarot", f"{card_id}.{ending}")):
			return f"/assets/raftor_astrohq/tarot/{card_id}.{ending}"
	return ""
