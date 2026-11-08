"""Written content, one source: the Markdown files in content/. The blog and the RAG index both read them, so nothing is typed twice.

	load()          every article file, checked (unique ids and titles, no shared section pasted into a single-mukhi article)
	sync_blog()     creates or updates the Blog Post for each file. The file is the truth: the body, the description and whether it is published
	                all come from the file. Desk edits to these posts are overwritten on the next migrate.
	rag_chunks()    the same bodies cut into sections, each one named by its article, with the product and source as fields for filtering

A file has a header between two lines of ---: id, series, category, title, intro, products, texts, publish. The body follows.
"""

import json
import re
from pathlib import Path

import frappe
import yaml

CONTENT = Path(__file__).parent / "content"
HEADER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
PRODUCT_MARKER = re.compile(r"^\[\[product\s+[A-Za-z0-9_\-]+\]\]\s*$", re.M)
# Topics that belong to the shared guide only: a single-mukhi article must not repeat them.
SHARED_SECTIONS = ("Identifying a genuine", "How to spot a genuine", "How to wear it", "Care and cleaning")
REQUIRED = ("id", "category", "title", "intro", "publish")
BLOGGER = {"short_name": "astrohq-team", "full_name": "AstroHQ Team", "bio": "Written and checked by the AstroHQ Team, from the traditional texts."}
CATEGORIES = {"rudraksha": "Rudraksha"}
ACADEMY = "Academy"
ACADEMY_INTRO = "Explained from the traditional texts, with sources."
ACADEMY_LINK = "/blog"  # Frappe's own address for the blog; /academy redirects to it (websitehq hooks)
META_LENGTH = 140  # the search description field holds this much; the full intro stays in blog_intro
COVER = "/files/Detailed Brown Rudraksha Seed on Cream Background60cba8.png"  # used when an article has no product picture


def load(folder: Path = CONTENT) -> list[dict]:
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
	check(items)
	return items


def check(items: list[dict]) -> None:
	for key in ("id", "title"):
		values = [item[key] for item in items]
		if len(values) != len(set(values)):
			raise ValueError(f"two articles share the same {key}")
	for item in items:
		if item["id"] == "rud-beginners-guide":
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


def sync_blog() -> int:
	"""Creates or updates the blog posts from the files. Returns how many articles it wrote."""
	items = load()
	blogger = _blogger()
	written = 0
	for item in items:
		category = _category(item["category"])
		post = frappe.db.get_value("Blog Post", {"title": item["title"]}, "name")
		doc = frappe.get_doc("Blog Post", post) if post else frappe.new_doc("Blog Post")
		if not post:
			doc.title = item["title"]
		values = {
			"blog_category": category,
			"blogger": blogger,
			"content_type": "Markdown",
			"content_md": item["body"],
			"blog_intro": item["intro"],
				"meta_image": _cover(item),
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


def rag_chunks(published_only: bool = True) -> list[dict]:
	"""One entry per section of each article. The text is self-contained: the article's title leads each one."""
	chunks = []
	for item in load():
		if published_only and not item["publish"]:
			continue
		body = PRODUCT_MARKER.sub("", item["body"])
		body = re.sub(r"<details><summary>(.*?)</summary><p>(.*?)</p></details>", r"\n**\1** \2\n", body, flags=re.S)
		intro, *sections = re.split(r"\n(?=## )", "\n" + body.strip())
		pieces = [("Introduction", intro.strip())] + [(s.split("\n", 1)[0][3:].strip(), s.split("\n", 1)[1].strip()) for s in sections if "\n" in s]
		for heading, text in pieces:
			if not text:
				continue
			chunks.append({
				"article": item["id"], "title": item["title"], "section": heading,
				"products": item.get("products") or "", "texts": item.get("texts") or "",
				"text": f"{item['title']}\n{heading}\n{text}",
			})
	return chunks


def _blogger():
	name = frappe.db.get_value("Blogger", {"short_name": BLOGGER["short_name"]}, "name")
	if not name:
		name = frappe.get_doc({"doctype": "Blogger", **BLOGGER}).insert(ignore_permissions=True).name
	return name


def _cover(item: dict) -> str:
	"""The picture of the article's first product, else the shared one. The Academy list shows it."""
	for code in (item.get("products") or "").split(","):
		image = frappe.db.get_value("Website Item", {"item_code": code.strip()}, "website_image") if code.strip() else None
		if image:
			return image
	return COVER


def _category(key: str) -> str:
	title = CATEGORIES[key]
	name = frappe.db.get_value("Blog Category", {"title": title}, "name")
	if not name:
		name = frappe.get_doc({"doctype": "Blog Category", "title": title, "published": 1}).insert(ignore_permissions=True).name
	return name
