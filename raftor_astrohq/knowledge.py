"""The Academy as the knowledge Pandit ji answers from: the same article files that make the blog, cut into sections and put into the agent app's knowledge store.

	index_academy()        puts every published article's sections in the store, each with its labels (series, group, article, section, route, products, services); does nothing when nothing changed
	check(questions)       asks each question of the store and says whether the article that should answer it came back first, or in the top three

A piece of text carries the place it has in the Academy ("Rudraksha > Beads by number of faces > 5 Mukhi Rudraksha > Mantra"), so a search for a mantra finds the right bead and not only a page that mentions mantras.
The store is the agent app's; this module only fills it. One source: nothing here is typed twice, and a change to an article file reaches the store on the next migrate.
"""

import hashlib
import json
import re

import frappe

from raftor_astrohq import content

DOCTYPE = "Academy Article"
DIGEST = "astrohq_academy_rag_digest"
BATCH = 64


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


def pieces() -> list[dict]:
	"""One piece per article section, with its place in the Academy in front of the text and its labels beside it."""
	out = []
	related = related_of(content.load())
	for position, chunk in enumerate(content.rag_chunks()):
		series = content.CATEGORIES[chunk["category"]]
		place = " > ".join(part for part in (series, chunk["group"], chunk["title"], chunk["section"]) if part)
		meta = {"series": chunk["category"], "group": chunk["group"], "article": chunk["article"], "title": chunk["title"], "section": chunk["section"],
				"route": chunk["route"], "products": _list(chunk["products"]), "services": _list(chunk["services"]), "audience": "public", **related[chunk["article"]]}
		body = chunk["text"].split("\n", 2)[2] if chunk["text"].count("\n") >= 2 else chunk["text"]
		out.append({"id": f"{chunk['article']}::{position}", "text": f"{place}\n{body}", "doctype": DOCTYPE, "doc_name": chunk["article"], "category": chunk["category"],
					"chunk_index": position, "meta": json.dumps(meta, ensure_ascii=False)})
	return out


def _list(value) -> list[str]:
	return [part.strip() for part in str(value or "").split(",") if part.strip()]


def digest(rows: list[dict]) -> str:
	return hashlib.sha256(json.dumps([(r["id"], r["text"], r["meta"]) for r in rows], ensure_ascii=False).encode()).hexdigest()


def index_academy(force: bool = False) -> int:
	"""Returns how many pieces were written (0 when the store already holds the current articles)."""
	if "raftor_agentshq" not in frappe.get_installed_apps():
		return 0
	from raftor_agents_factory.rag import store
	from raftor_agents_factory.rag.embedder import DEFAULT_MODEL, embed_batch

	settings = frappe.get_single("Raftor AgentsHQ Settings")
	path = settings.lancedb_path or frappe.get_site_path("lancedb")
	rows = pieces()
	wanted = digest(rows)
	store.ensure_tables(path)
	held = store.get_table(path).count_rows(f"doctype = '{DOCTYPE}'")
	if not force and held == len(rows) and frappe.defaults.get_global_default(DIGEST) == wanted:
		return 0
	store.get_table(path).delete(f"doctype = '{DOCTYPE}'")
	model = settings.embedding_model or DEFAULT_MODEL
	for start in range(0, len(rows), BATCH):
		batch = rows[start:start + BATCH]
		for row, vector in zip(batch, embed_batch([r["text"] for r in batch], model_name=model)):
			row["vector"] = vector
		store.upsert_chunks(path, batch)
	frappe.defaults.set_global_default(DIGEST, wanted)
	frappe.db.commit()
	return len(rows)


def check(questions: list[dict], top_k: int = 3) -> dict:
	"""questions: [{"q": ..., "expect": [article ids that answer it]}]. Says how often an expected article was the first hit, and how often it was in the top `top_k`."""
	from raftor_agents_factory.rag import store
	from raftor_agents_factory.rag.embedder import DEFAULT_MODEL, embed

	settings = frappe.get_single("Raftor AgentsHQ Settings")
	path = settings.lancedb_path or frappe.get_site_path("lancedb")
	model = settings.embedding_model or DEFAULT_MODEL
	first = within = 0
	misses = []
	for item in questions:
		found = []
		for hit in store.search(path, embed(item["q"], model_name=model), top_k=top_k * 4, doctype=DOCTYPE):
			if hit["doc_name"] not in found:
				found.append(hit["doc_name"])
		found = found[:top_k]
		expected = set(item["expect"])
		first += bool(found and found[0] in expected)
		within += bool(expected & set(found))
		if not expected & set(found):
			misses.append({"q": item["q"], "expected": item["expect"], "got": found})
	total = len(questions)
	return {"questions": total, "first": first, "top": within, "first_rate": round(first / total, 2), "top_rate": round(within / total, 2), "misses": misses}
