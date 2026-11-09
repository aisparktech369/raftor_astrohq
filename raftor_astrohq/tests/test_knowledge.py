import json
from pathlib import Path
from unittest import TestCase

import frappe

from raftor_astrohq import content, knowledge


class TestKnowledge(TestCase):
	def test_every_published_article_is_in_the_pieces_with_its_place_and_labels(self):
		rows = knowledge.pieces()
		published = {item["id"] for item in content.load() if item["publish"]}
		self.assertEqual({row["doc_name"] for row in rows}, published)
		row = next(r for r in rows if r["doc_name"] == "rud-5-mukhi")
		meta = json.loads(row["meta"])
		self.assertTrue(row["text"].startswith("Rudraksha > Beads by number of faces > "))
		self.assertEqual((meta["series"], meta["article"], meta["audience"]), ("rudraksha", "rud-5-mukhi", "public"))
		self.assertTrue(meta["route"].startswith("/blog/rudraksha/"))
		self.assertEqual(row["category"], "rudraksha")

	def test_the_ids_are_unique_and_the_digest_follows_the_text(self):
		rows = knowledge.pieces()
		self.assertEqual(len({r["id"] for r in rows}), len(rows))
		changed = [dict(r) for r in rows]
		changed[0]["text"] += " more"
		self.assertNotEqual(knowledge.digest(rows), knowledge.digest(changed))
		self.assertEqual(knowledge.digest(rows), knowledge.digest(knowledge.pieces()))

	def test_the_questions_name_articles_that_exist(self):
		ids = {item["id"] for item in content.load()}
		for item in json.loads((Path(knowledge.__file__).parent / "rag_questions.json").read_text()):
			self.assertTrue(set(item["expect"]) <= ids, item["q"])
