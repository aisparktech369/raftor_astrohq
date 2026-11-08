"""The written content: one file per article, read by the blog and by RAG. A duplicated shared section or a repeated id must fail."""
import tempfile
from pathlib import Path
from unittest import TestCase

from raftor_astrohq import content

HEAD = "---\nid: {id}\ncategory: rudraksha\ntitle: {title}\nintro: x.\npublish: true\n---\n\n"


class TestContent(TestCase):
	def test_every_article_is_one_file(self):
		items = content.load()
		self.assertEqual(len(items), 16)
		self.assertEqual(len({i["id"] for i in items}), 16)

	def test_single_mukhi_articles_do_not_repeat_the_guide(self):
		for item in content.load():
			if item["id"] == "rud-beginners-guide":
				continue
			for section in content.SHARED_SECTIONS:
				self.assertNotIn(section, item["body"], item["file"])

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
