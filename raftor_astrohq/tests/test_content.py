import json
"""The written content: one file per article, read by the blog and by RAG. A duplicated shared section or a repeated id must fail."""
import re
import tempfile
from pathlib import Path
from unittest import TestCase

import frappe

from raftor_astrohq import content

HEAD = "---\nid: {id}\ncategory: rudraksha\ntitle: {title}\nintro: x.\npublish: true\n---\n\n"


class TestContent(TestCase):
	def test_every_article_is_one_file(self):
		items = [i for i in content.load() if not content.rag_only(i)]
		self.assertEqual(len(items), 236)  # 145 and the Tarot series: 78 cards, 7 spreads, 5 methodology pages and the overview
		self.assertEqual(len({i["id"] for i in items}), 236)
		self.assertEqual(len([i for i in items if i["category"] == "tarot"]), 91)

	def test_the_files_for_the_guides_only_are_the_consult_kinds_and_the_services(self):
		only = [i for i in content.load() if content.rag_only(i)]
		self.assertEqual({i["category"] for i in only}, {"consult", "services"})
		self.assertEqual(len([i for i in only if i["category"] == "consult"]), 8)  # one kind.md for each kind of consultant the site has
		self.assertTrue(all(not i["publish"] for i in only))

	def test_single_mukhi_articles_do_not_repeat_the_guide(self):
		for item in content.load():
			if item["id"].endswith("-guide"):
				continue
			for section in content.SHARED_SECTIONS:
				self.assertNotIn(section, item["body"], item["file"])

	def test_astrologer_mentions_lead_to_the_consult_page(self):
		"""An article that tells the reader to ask an astrologer links that to /consult: a chance to book one."""
		for item in [i for i in content.load() if not content.rag_only(i)]:
			body = item["body"]
			if "astrologer" in body.replace("astrologers", ""):
				self.assertTrue("(/consult)" in body or 'href="/consult"' in body, item["file"])

	def test_a_blog_carries_no_policy_or_commercial_promise(self):
		"""The blog only teaches and sells softly (a card, a link). Guarantees, grades, refunds and certificates belong to the shop's pages and the policies, never to an article."""
		for item in content.load():
			text = item["body"].lower()
			for phrase in ("astrohq guarantee", "astrohq certificate", "we guarantee", "money back", "refund", "money-back", "backed by astrohq", "astrohq grades"):
				self.assertNotIn(phrase, text, f"{item['file']}: {phrase}")

	def test_every_link_between_articles_leads_to_a_live_article(self):
		"""The articles are read together: each links onward (Related reading), and every such link must reach an article that is published."""
		items = content.load()
		live = {content.route_of(i) for i in items if i["publish"]}
		for item in items:
			for link in re.findall(r"\]\((/blog/[^)#\s]+)\)|href=\"(/blog/[^\"#]+)\"", item["body"]):
				target = (link[0] or link[1]).rstrip("/")
				if target.count("/") >= 3:  # an article, not a series page
					self.assertIn(target, live, f"{item['file']}: {target}")
			if item["publish"]:
				self.assertIn("## Related reading", item["body"], item["file"])

	def test_every_article_is_tabular(self):
		"""Agreed with the owner: facts are tables across the series (at a glance, meaning, mantra), questions are the site's accordion."""
		for item in [i for i in content.load() if not content.rag_only(i)]:
			if item["id"] in ("gem-which-for-which-need", "gem-planets-gems-beads-poojas"):
				continue  # the need-to-remedy guides are tables of their own kind
			if item["category"] in ("numerology", "dreams", "tarot"):
				continue  # the numerology, dream and tarot series keep their own shape: prose and a few tables (a card page is its sections: picture, meaning, upright, reversed; the tarot deck and spreads are read from them, tarot_deck.py)
			if item["id"].endswith("-guide"):
				self.assertGreaterEqual(item["body"].count("|---|"), 4, item["file"])
				continue
			if item["id"].startswith("puj-"):
				for section in ("## At a glance", "## Story and meaning", "## When to perform", "## Items (samagri)", "## Steps"):
					self.assertIn(section, item["body"], item["file"])
				self.assertIn("<details><summary>", item["body"], item["file"])
				self.assertIn("(/services/events)", item["body"], item["file"])  # the way to book it
				if not item["id"].endswith("-guide") and item["id"] != "puj-havan":
					self.assertIn("[[product ", item["body"], item["file"])  # the service's own card
					self.assertTrue(item.get("services"), item["file"])
				continue
			if item["id"].startswith("gem-"):
				self.assertIn("| Topic | Detail |", item["body"], item["file"])
				self.assertIn("## Where it comes from\n\n| Origin | What to know |", item["body"], item["file"])
				self.assertIn("## Natural, treated, or made", item["body"], item["file"])
				for section in ("## Mythology and lore", "## Astrology at a glance", "## How astrologers decide"):
					self.assertIn(section, item["body"], item["file"])
				self.assertIn("<details><summary>", item["body"], item["file"])
				continue
			self.assertIn("| Topic | Detail |", item["body"], item["file"])
			self.assertEqual(item["body"].count("| Point | Detail |"), 2, item["file"])  # meaning, mantra
			self.assertIn("<details><summary>", item["body"], item["file"])

	def test_duplicate_id_is_refused(self):
		with tempfile.TemporaryDirectory() as folder:
			for name in ("a.md", "b.md"):
				Path(folder, name).write_text(HEAD.format(id="same", title=name) + "Text.\n", encoding="utf-8")
			with self.assertRaises(ValueError):
				content.load(Path(folder))

	def test_repeated_shared_section_is_refused(self):
		with tempfile.TemporaryDirectory() as folder:
			Path(folder, "a.md").write_text(HEAD.format(id="one", title="One") + "## Care and cleaning\n\nDust.\n", encoding="utf-8")
			with self.assertRaises(ValueError):
				content.load(Path(folder))

	def test_rag_sections_are_self_contained_and_hide_markers(self):
		from raftor_agentshq import domain_rag

		rows, _ = domain_rag._built(content.DOMAIN)
		pieces = [r for rs in rows.values() for r in rs]
		self.assertTrue(pieces)
		for row in pieces:
			meta = json.loads(row["meta"])
			self.assertNotIn("[[product", row["text"])
			self.assertIn(meta["title"], row["text"].split("\n", 1)[0] if meta["section"] == "Introduction" else row["text"], meta["article"])
			self.assertTrue(meta["series"] and meta["article"] and meta["section"])
		self.assertTrue(any(json.loads(r["meta"])["products"] == ["RUD001"] for r in pieces))
		self.assertTrue(any(json.loads(r["meta"])["group"] == "The nine gems (Navaratna)" and r["text"].startswith("Gemstones > ") for r in pieces))

	def test_the_blog_is_named_once_and_staff_names_stay(self):
		try:
			site = frappe.get_single("Website Settings")
			for row in [r for r in site.top_bar_items if r.url == content.ACADEMY_LINK]:
				site.remove(row)
			site.save(ignore_permissions=True)
			frappe.db.set_single_value("Blog Settings", "blog_title", "")
			content.name_the_blog()
			content.name_the_blog()  # a second run adds nothing
			self.assertEqual(frappe.db.get_single_value("Blog Settings", "blog_title"), content.ACADEMY)
			self.assertEqual(len([r for r in frappe.get_single("Website Settings").top_bar_items if r.url == content.ACADEMY_LINK]), 1)
			frappe.db.set_single_value("Blog Settings", "blog_title", "Library")
			content.name_the_blog()
			self.assertEqual(frappe.db.get_single_value("Blog Settings", "blog_title"), "Library")
		finally:
			frappe.db.rollback()

	def test_a_product_gets_one_tab_that_leads_to_its_live_article(self):
		try:
			code = "RUD001"
			name = frappe.db.get_value("Website Item", {"item_code": code}, "name")
			if not name:
				self.skipTest("no RUD001 shop item on this site")
			content.sync_blog()
			content.link_products()
			self.assertEqual(content.link_products(), 0)  # a second run changes nothing
			tabs = [r for r in frappe.get_doc("Website Item", name).tabs if r.label == content.LEARN_TAB]
			self.assertEqual(len(tabs), 1)
			self.assertIn("/blog/", tabs[0].content)
			self.assertEqual(frappe.db.get_value("Website Item", name, "show_tabbed_section"), 1)
		finally:
			frappe.db.rollback()


class TestShopPictures(TestCase):
	def test_adding_the_tab_leaves_a_picture_that_has_no_file_record(self):
		try:
			name = frappe.db.get_value("Website Item", {"item_code": "RUD001"}, "name")
			if not name:
				self.skipTest("no RUD001 shop item on this site")
			frappe.db.delete("Website Item Tabbed Section", {"parent": name, "label": content.LEARN_TAB})
			frappe.db.set_value("Website Item", name, "website_image", "/files/no-record-for-this.png")
			content.sync_blog()
			content.link_products()
			self.assertEqual(frappe.db.get_value("Website Item", name, "website_image"), "/files/no-record-for-this.png")
		finally:
			frappe.db.rollback()

	def test_an_entry_with_no_picture_takes_its_items_picture(self):
		try:
			row = frappe.db.sql("select wi.name, i.image from `tabWebsite Item` wi join `tabItem` i on i.name = wi.item_code where wi.published = 1 and i.image like '/files/%%' limit 1", as_dict=True)
			if not row:
				self.skipTest("no shop item with a picture on this site")
			frappe.db.set_value("Website Item", row[0].name, {"website_image": "", "thumbnail": ""})
			content.fill_pictures()
			self.assertTrue(frappe.db.get_value("Website Item", row[0].name, "website_image").endswith(row[0].image.rsplit("/", 1)[1]))
			self.assertEqual(content.fill_pictures(), 0)  # a second run changes nothing
		finally:
			frappe.db.rollback()
