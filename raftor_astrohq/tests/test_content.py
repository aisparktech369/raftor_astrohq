"""The written content: one file per article, read by the blog and by RAG. A duplicated shared section or a repeated id must fail."""
import tempfile
from pathlib import Path
from unittest import TestCase

import frappe

from raftor_astrohq import content

HEAD = "---\nid: {id}\ncategory: rudraksha\ntitle: {title}\nintro: x.\npublish: true\n---\n\n"


class TestContent(TestCase):
	def test_every_article_is_one_file(self):
		items = content.load()
		self.assertEqual(len(items), 93)
		self.assertEqual(len({i["id"] for i in items}), 93)

	def test_single_mukhi_articles_do_not_repeat_the_guide(self):
		for item in content.load():
			if item["id"].endswith("-guide"):
				continue
			for section in content.SHARED_SECTIONS:
				self.assertNotIn(section, item["body"], item["file"])

	def test_astrologer_mentions_lead_to_the_consult_page(self):
		"""An article that tells the reader to ask an astrologer links that to /consult: a chance to book one."""
		for item in content.load():
			body = item["body"]
			if "astrologer" in body.replace("astrologers", ""):
				self.assertTrue("(/consult)" in body or 'href="/consult"' in body, item["file"])

	def test_every_article_is_tabular(self):
		"""Agreed with the owner: facts are tables across the series (at a glance, meaning, mantra), questions are the site's accordion."""
		for item in content.load():
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
		chunks = content.rag_chunks(published_only=False)
		self.assertTrue(chunks)
		for chunk in chunks:
			self.assertTrue(chunk["text"].startswith(chunk["title"]), chunk["article"])
			self.assertNotIn("[[product", chunk["text"])
		self.assertTrue(any(c["products"] == "RUD001" for c in chunks))
		self.assertTrue(all(c["series"] and c["article"] and c["section"] for c in chunks))
		self.assertTrue(any(c["series"] == "Gemstones" and c["group"] == "The nine gems (Navaratna)" for c in chunks))

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
