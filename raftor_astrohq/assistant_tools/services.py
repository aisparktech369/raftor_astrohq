"""The two tools that let Pandit ji talk about services: what there is (find_services) and one service in full with the way to book it (get_service).

Both read what the site's own Services page shows (servicehq's card_feeds.by_group), so the agent and the page can never disagree about a price, a shelf, or whether a pooja is "Coming soon". They only read.
Nothing here books or charges: a card carries the link to the booking page, where the customer picks the time, gives the details, and pays under their own sign-in.
"""

from typing import Any, Dict

import frappe
from frappe_assistant_core.core.base_tool import BaseTool

MAX = 12


def _absolute(url: str) -> str:
	return frappe.utils.get_url(url) if url and url.startswith("/") else (url or "")


def _everything() -> list[dict]:
	"""Every service the Services page lists, from every shelf (the page shows one shelf at a time, so each is asked for)."""
	from raftor_servicehq import card_feeds

	first = card_feeds.by_group()
	shelves = [o["value"] for f in first.get("filters", []) if f["name"] == "kind" for o in f["options"]]
	seen, rows = set(), []
	for shelf in shelves or [""]:
		for row in (card_feeds.by_group(kind=shelf) if shelf else first).get("items", []):
			key = (row["title"], row.get("link_url") or "")
			if key not in seen:
				seen.add(key)
				rows.append({"shelf": shelf, **row})
	return rows


def _card(row: dict) -> dict:
	status = row.get("status") or ""
	return {
		"title": row["title"], "shelf": row.get("shelf", ""), "topic": row.get("tag", ""), "status": status or "Bookable now",
		"bookable": not status and bool(row.get("link_url")), "price": row.get("price_line", ""), "price_before_offer": row.get("price_was", ""),
		"book_link": _absolute(row.get("link_url", "")), "button": row.get("link_label", ""),
	}


def _matches(row: dict, words: list[str]) -> bool:
	text = f"{row['title']} {row.get('tag', '')} {row.get('shelf', '')}".lower()
	return all(word in text for word in words)


class FindServices(BaseTool):
	def __init__(self):
		super().__init__()
		self.name = "find_services"
		self.description = (
			"List the blessing services (poojas and rites) AstroHQ offers: personal or samuhik (group), by shelf such as Kamna purti or Samasya samadhan. "
			"Each result says its price, whether it can be booked now or is Coming soon, and gives the link to book it. Use this instead of guessing a service, a price or its availability."
		)
		self.requires_permission = None
		self.annotations = {"module": "astrohq.services", "tags": ["read", "list"], "tier": "T2"}
		self.inputSchema = {
			"type": "object",
			"properties": {
				"search": {"type": "string", "description": "Words from the service name or what it is for, for example 'rudrabhishek' or 'job'"},
				"shelf": {"type": "string", "description": "A shelf of services, for example Kamna purti or Samasya samadhan"},
				"bookable_only": {"type": "boolean", "default": False, "description": "Leave out services that are Coming soon"},
				"limit": {"type": "integer", "default": 6, "maximum": MAX},
			},
		}

	def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
		words = [w for w in str(arguments.get("search") or "").lower().split() if w]
		shelf = str(arguments.get("shelf") or "").lower()
		limit = min(int(arguments.get("limit") or 6), MAX)
		cards = []
		for row in _everything():
			if shelf and shelf not in row["shelf"].lower():
				continue
			if words and not _matches(row, words):
				continue
			card = _card(row)
			if arguments.get("bookable_only") and not card["bookable"]:
				continue
			cards.append(card)
		return {"count": len(cards[:limit]), "services": cards[:limit], "more": max(len(cards) - limit, 0)}


class GetService(BaseTool):
	def __init__(self):
		super().__init__()
		self.name = "get_service"
		self.description = (
			"One service in full: its price, whether it can be booked now or is Coming soon, and the link to book it. Use it when the customer has chosen a service and wants to book. "
			"It never books or charges: the customer books on the page the link opens, under their own sign-in."
		)
		self.requires_permission = None
		self.annotations = {"module": "astrohq.services", "tags": ["read", "inspect"], "tier": "T2"}
		self.inputSchema = {"type": "object", "properties": {"title": {"type": "string", "description": "The service's name as find_services gave it"}}, "required": ["title"]}

	def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
		wanted = str(arguments.get("title") or "").strip().lower()
		rows = [r for r in _everything() if r["title"].lower() == wanted] or [r for r in _everything() if wanted and wanted in r["title"].lower()]
		if not rows:
			return {"found": False, "message": "There is no service with that name. Use find_services to see what is offered."}
		card = _card(rows[0])
		card["found"] = True
		card["how_to_book"] = "Open the link, pick a date or time, give the details asked, and pay." if card["bookable"] else "It cannot be booked yet. It is Coming soon."
		return card
