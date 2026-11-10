"""Written content, one source: the Markdown files of the astrohq domain (rag/products, rag/consult, rag/services), read through AgentsHQ. The blog and the RAG index both read them, so nothing is typed twice.

	load()          every article file, checked (unique ids and titles, no shared section pasted into a single-mukhi article)
	sync_blog()     creates or updates the Blog Post for each file. The file is the truth: the body, the description and whether it is published
	                all come from the file. Desk edits to these posts are overwritten on the next migrate.

A file has a header between two lines of ---: id, series, category, title, intro, products, texts, publish, and optionally group and order (the heading it is listed under in its series, and its place there). The body follows.
"""

import json
import re
from pathlib import Path

import frappe
import yaml

HEADER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
PRODUCT_MARKER = re.compile(r"^\[\[product\s+[^\]\n]+\]\]\s*$", re.M)
# Topics that belong to the shared guide only: a single-mukhi article must not repeat them.
SHARED_SECTIONS = ("Identifying a genuine", "How to spot a genuine", "How to wear it", "Care and cleaning")
REQUIRED = ("id", "category", "title", "intro", "publish")
BLOGGER = {"short_name": "astrohq-team", "full_name": "AstroHQ Team", "bio": "Written and checked by the AstroHQ Team, from the traditional texts."}
CATEGORIES = {"rudraksha": "Rudraksha", "gemstones": "Gemstones", "pooja": "Pooja", "numerology": "Numerology", "dreams": "Dreams", "consult": "Consult", "services": "Services"}
CATEGORY_NOTES = {
	"rudraksha": "The beads by number of faces: meaning, mantra, the traditions around each, and how to choose one.",
	"gemstones": "Origin, treatments, the planets and stories behind each stone, and how to choose one.",
	"numerology": "The birth number, the name number and the compound numbers, and how to read them with care. A traditional doctrine, calculated by rules, never a prediction.",
	"dreams": "Dreams read as personal stories: the DREAM method, common scenarios, symbol notes, and what the Indian traditions are said to hold, each labelled by how well its source is known.",
	"pooja": "Rituals explained: what each pooja is, when it is done, the items and steps, and what to ask before you book one.",
}
ACADEMY = "Academy"
ACADEMY_INTRO = "Explained from the traditional texts, with sources."
LEARN_TAB = "Learn about this bead"
ACADEMY_LINK = "/blog"  # Frappe's own address for the blog; /academy redirects to it (websitehq hooks)
META_LENGTH = 140  # the search description field holds this much; the full intro stays in blog_intro
SERIES_COVERS = {"pooja": "/assets/raftor_astrohq/images/academy-pooja.png"}
GROUP_COVERS = {  # a pooja article takes the picture of its shelf (drawn for the site, kept in this app)
	"Kamna purti": "/assets/raftor_astrohq/images/academy-lotus.png", "Samasya samadhan": "/assets/raftor_astrohq/images/academy-kalash.png",
	"Graha shanti, the planets": "/assets/raftor_astrohq/images/academy-planets.png", "Graha shanti, doshas and yogas": "/assets/raftor_astrohq/images/academy-planets.png",
	"The rites explained": "/assets/raftor_astrohq/images/academy-fire.png",
}  # a series that sells no goods has its own picture
COVER = "/files/Detailed Brown Rudraksha Seed on Cream Background60cba8.png"  # used when an article has no product picture


DOMAIN = "astrohq"


def load(folder: Path | None = None) -> list[dict]:
	"""Every article file, checked. The files live in the agents factory's astrohq domain, which AgentsHQ (the one contact with the factory) reads; a folder can be given instead (the tests do)."""
	if folder is None:
		from raftor_agentshq import domain_rag

		items = domain_rag.domain_files(DOMAIN)
	else:
		items = _read(folder)
	check(items)
	return items


def _read(folder: Path) -> list[dict]:
	items = []
	for path in sorted(folder.rglob("*.md")):
		text = path.read_text(encoding="utf-8")
		match = HEADER.match(text)
		if not match:
			raise ValueError(f"{path.name}: no header")
		head = yaml.safe_load(match.group(1)) or {}
		missing = [key for key in REQUIRED if key not in head]
		if missing:
			raise ValueError(f"{path.name}: header lacks {', '.join(missing)}")
		head["body"] = text[match.end():].strip() + "\n"
		head["file"] = path.name
		items.append(head)
	return items


def check(items: list[dict]) -> None:
	for key in ("id", "title"):
		values = [item[key] for item in items]
		if len(values) != len(set(values)):
			raise ValueError(f"two articles share the same {key}")
	for item in items:
		if item["id"].endswith("-guide"):
			continue
		if any(section in item["body"] for section in SHARED_SECTIONS):
			raise ValueError(f"{item['file']}: a shared section is repeated here. Link to the guide instead")


def name_the_blog() -> None:
	"""The blog is called Academy for visitors: its heading, a top menu item and a line in the footer's Explore column.
	Fills in only what is missing, so a name or menu staff have changed is never put back."""
	settings = frappe.get_single("Blog Settings")
	if not settings.blog_title:
		settings.blog_title = ACADEMY
		settings.blog_introduction = settings.blog_introduction or ACADEMY_INTRO
		settings.save(ignore_permissions=True)
	site = frappe.get_single("Website Settings")
	if not any(row.url == ACADEMY_LINK for row in site.top_bar_items):
		site.append("top_bar_items", {"label": ACADEMY, "url": ACADEMY_LINK})
		site.save(ignore_permissions=True)
	if frappe.db.exists("RFHQ Card", "Footer: explore"):
		card = frappe.get_doc("RFHQ Card", "Footer: explore")
		values = json.loads(card.card_values or "{}")
		line = f"{ACADEMY} | {ACADEMY_LINK}"
		if line not in values.get("links", ""):
			values["links"] = (values.get("links", "") + "\n" + line).strip()
			card.card_values = json.dumps(values)
			card.save(ignore_permissions=True)


def link_products() -> int:
	"""Each product a live article names gets a tab on its page, "Learn about this bead", that leads to the article; a product whose article is not live loses it.
	One source: the articles' own product lists. Returns how many products were changed."""
	wanted = {}
	for item in load():
		route = frappe.db.get_value("Blog Post", {"title": item["title"], "published": 1}, "route") if item["publish"] else None
		for code in (item.get("products") or "").split(","):
			if route and code.strip():
				wanted.setdefault(code.strip(), (item["title"], route))
	changed = 0
	for code in {c.strip() for i in load() for c in (i.get("products") or "").split(",") if c.strip()}:
		name = frappe.db.get_value("Website Item", {"item_code": code}, "name")
		if not name:
			continue
		doc = frappe.get_doc("Website Item", name)
		rows = [r for r in doc.tabs if r.label == LEARN_TAB]
		# written straight to the tab rows: saving the whole shop entry runs the shop's picture check, which blanks a picture that has no File record
		if code in wanted:
			title, route = wanted[code]
			html = f'<p><a href="/{route.strip("/")}">{frappe.utils.escape_html(title)}</a></p>'
			if rows and rows[0].content == html and doc.show_tabbed_section:
				continue
			if rows:
				frappe.db.set_value("Website Item Tabbed Section", rows[0].name, "content", html, update_modified=False)
			else:
				frame = frappe.get_doc({"doctype": "Website Item Tabbed Section", "parent": name, "parenttype": "Website Item", "parentfield": "tabs", "idx": len(doc.tabs) + 1, "label": LEARN_TAB, "content": html})
				frame.db_insert()
			frappe.db.set_value("Website Item", name, "show_tabbed_section", 1, update_modified=False)
		elif rows:
			for row in rows:
				frappe.db.delete("Website Item Tabbed Section", {"name": row.name})
		else:
			continue
		frappe.clear_document_cache("Website Item", name)
		changed += 1
	return changed


def fill_pictures() -> int:
	"""A shop entry with no picture takes its item's picture (and its small copy when there is one). The picture needs a File record, which the shop's own check looks for,
	so one is made, with no storage hooks, for a file that is on disk without it. A picture staff have set is never replaced. Returns how many entries were filled."""
	import os

	filled = 0
	for row in frappe.get_all("Website Item", filters={"published": 1}, fields=["name", "item_code", "website_image"]):
		if row.website_image:
			continue
		image = frappe.db.get_value("Item", row.item_code, "image")
		if not image or not image.startswith("/files/") or not os.path.exists(frappe.get_site_path("public", image[1:])):
			continue
		small = image.rsplit(".", 1)[0] + "_small." + image.rsplit(".", 1)[1]
		final = {}
		for url in (image, small):
			if not os.path.exists(frappe.get_site_path("public", url[1:])):
				continue
			if not frappe.db.exists("File", {"file_url": url}):  # the record only, as the file is already there: a File insert would run the storage hooks
				record = frappe.get_doc({"doctype": "File", "file_url": url, "file_name": url.rsplit("/", 1)[1], "is_private": 0, "file_size": os.path.getsize(frappe.get_site_path("public", url[1:]))})
				record.name = frappe.generate_hash(length=10)
				record.db_insert()
			final[url] = url
		frappe.db.set_value("Website Item", row.name, {"website_image": final[image], "thumbnail": final.get(small, final[image])}, update_modified=False)
		frappe.clear_document_cache("Website Item", row.name)
		filled += 1
	return filled


def sync_blog() -> int:
	"""Creates or updates the blog posts from the files. Returns how many articles it wrote."""
	from raftor_websitehq.setup.blog_post_fields import create_blog_post_custom_fields

	create_blog_post_custom_fields()  # the heading and place of an article in its series (websitehq owns the fields)
	items = load()
	blogger = _blogger()
	written = 0
	for item in items:
		if rag_only(item):
			continue  # knowledge for the guides only: no blog post
		category = _category(item["category"])
		post = frappe.db.get_value("Blog Post", {"title": item["title"]}, "name")
		doc = frappe.get_doc("Blog Post", post) if post else frappe.new_doc("Blog Post")
		if not post:
			doc.title = item["title"]
		values = {
			"blog_category": category,
			"rfhq_group": item.get("group") or "",
			"rfhq_order": item.get("order") or 0,
			"blogger": blogger,
			"content_type": "Markdown",
			"content_md": item["body"],
			"blog_intro": item["intro"],
				"meta_image": _cover(item, items),
			"meta_description": item["intro"][:META_LENGTH],
			"meta_title": f"{item['title']} | AstroHQ"[:60],
			"published": 1 if item["publish"] else 0,
			"disable_comments": 1,
			"disable_likes": 1,
		}
		if any(doc.get(field) != value for field, value in values.items()):
			doc.update(values)
			doc.save(ignore_permissions=True)
			written += 1
	return written


def rag_only(item: dict) -> bool:
	"""A page that is knowledge for the guides and not a blog post (header `rag: true`, `publish: false`): what the consultant kinds do, what services there are."""
	return bool(item.get("rag")) and not item["publish"]


def slug(text: str) -> str:
	"""A title as Frappe makes its address: lower case, the apostrophe dropped, anything else that is not a letter or digit a hyphen."""
	return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("'", "")).strip("-")


def route_of(item: dict) -> str:
	"""Where an article lives: /blog/<category>/<title>. A page for the guides only points at the site page it is about (its `route`, else /consult or /services)."""
	if rag_only(item):
		return item.get("route") or ("/consult" if item["category"] == "consult" else "/services")
	return f"/blog/{slug(CATEGORIES[item['category']])}/{slug(item['title'])}"


def _blogger():
	name = frappe.db.get_value("Blogger", {"short_name": BLOGGER["short_name"]}, "name")
	if not name:
		name = frappe.get_doc({"doctype": "Blogger", **BLOGGER}).insert(ignore_permissions=True).name
	return name


def _cover(item: dict, items: list[dict]) -> str:
	"""The picture of the article's first product (the shop entry's, else the item's own); a guide with no product borrows the first picture in its own category; else the shared one. The Academy list shows it."""
	same = [item] + [other for other in items if other["category"] == item["category"] and other is not item]
	for article in same:
		for code in (article.get("products") or "").split(","):
			code = code.strip()
			image = (frappe.db.get_value("Website Item", {"item_code": code}, "website_image") or frappe.db.get_value("Item", code, "image")) if code else None
			if image:
				return image
	return GROUP_COVERS.get(item.get("group"), SERIES_COVERS.get(item["category"], COVER)) if item["category"] in SERIES_COVERS else COVER


def _category(key: str) -> str:
	title = CATEGORIES[key]
	name = frappe.db.get_value("Blog Category", {"title": title}, "name")
	if not name:
		name = frappe.get_doc({"doctype": "Blog Category", "title": title, "published": 1, "description": CATEGORY_NOTES.get(key, "")}).insert(ignore_permissions=True).name
	elif not frappe.db.get_value("Blog Category", name, "description") and CATEGORY_NOTES.get(key):
		frappe.db.set_value("Blog Category", name, "description", CATEGORY_NOTES[key])  # only fills a blank one; staff words stay
	return name
