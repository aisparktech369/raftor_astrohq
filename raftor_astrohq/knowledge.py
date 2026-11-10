"""The Academy as the knowledge the guides answer from: the same article files that make the blog. AgentsHQ (the one contact with the agents factory) cuts them into sections and keeps the store in step, one file at a time.

	enrich(articles)       the labels AstroHQ adds to its files' pieces: place in the Academy, route, related products and services (a hook AgentsHQ calls)
	index_academy()        asks AgentsHQ to sync the domain; only the files that changed are written

A piece of text carries the place it has in the Academy ("Rudraksha > Beads by number of faces > 5 Mukhi Rudraksha > Mantra"), so a search for a mantra finds the right bead and not only a page that mentions mantras.
The store is the agent app's; this module only fills it. One source: nothing here is typed twice, and a change to an article file reaches the store on the next migrate.
"""

import re

import frappe

from raftor_astrohq import content

RELATED_LINK = re.compile(r"\]\((/blog/[^)\s]+)\)")
RELATED_MAX = 3  # how many related products and services travel with a piece


def related_of(items: list[dict]) -> dict[str, dict]:
	"""For each article, the products and services of the articles its Related reading table points to (the same source the reader follows), without its own."""
	by_route = {content.route_of(item): item for item in items}
	found = {}
	for item in items:
		own_products, own_services = set(_list(item.get("products"))), set(_list(item.get("services")))
		products, services = [], []
		for route in dict.fromkeys(RELATED_LINK.findall(item["body"].split("## Related reading")[-1] if "## Related reading" in item["body"] else "")):
			other = by_route.get(route)
			if not other or not other["publish"]:
				continue
			products += [code for code in _list(other.get("products")) if code not in own_products and code not in products]
			services += [name for name in _list(other.get("services")) if name not in own_services and name not in services]
		found[item["id"]] = {"related_products": products[:RELATED_MAX], "related_services": services[:RELATED_MAX]}
	return found


def _list(value) -> list[str]:
	return [part.strip() for part in str(value or "").split(",") if part.strip()]


def enrich(articles: list[dict]) -> dict[str, dict]:
	"""What AgentsHQ asks of AstroHQ when it puts the domain's files in the store (hook agent_rag_enrichers): each file's place in the Academy (series > group > article), its route, and the products and services of its related reading."""
	related = related_of(articles)
	out = {}
	for item in articles:
		place = [part for part in (content.CATEGORIES[item["category"]], item.get("group"), item["title"]) if part]
		out[item["id"]] = {"place": place, "route": content.route_of(item), "extra": related[item["id"]]}
	return out


def index_academy(force: bool = False) -> int:
	"""Asks AgentsHQ to bring the store in step with the domain's files. Only the files that changed are written (force rewrites them all). Returns how many pieces were written."""
	if "raftor_agentshq" not in frappe.get_installed_apps():
		return 0
	from raftor_agentshq import domain_rag

	written = domain_rag.sync(content.DOMAIN, force=force)["written"]
	frappe.db.commit()
	return written
