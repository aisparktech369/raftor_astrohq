import json
from unittest import TestCase

import frappe

from raftor_astrohq import content, knowledge


def built():
	"""What AgentsHQ would write to the store for the astrohq domain: the rows by file, and their fingerprints."""
	from raftor_agentshq import domain_rag

	return domain_rag._built(content.DOMAIN)


class TestKnowledge(TestCase):
	def test_every_published_or_rag_only_file_is_in_the_pieces_with_its_place_and_labels(self):
		rows, wanted = built()
		indexed = {item["id"] for item in content.load() if item["publish"] or item.get("rag")}
		self.assertEqual(set(rows), indexed)
		row = rows["rud-5-mukhi"][0]
		meta = json.loads(row["meta"])
		self.assertTrue(row["text"].startswith("Rudraksha > Beads by number of faces > "))
		self.assertEqual((meta["series"], meta["article"], meta["audience"]), ("rudraksha", "rud-5-mukhi", "public"))
		self.assertTrue(meta["route"].startswith("/blog/rudraksha/"))
		self.assertEqual(row["category"], "rudraksha")

	def test_the_ids_are_unique_and_the_fingerprints_are_steady(self):
		rows, wanted = built()
		ids = [r["id"] for rs in rows.values() for r in rs]
		self.assertEqual(len(ids), len(set(ids)))
		self.assertEqual(wanted, built()[1])

	def test_a_file_for_the_guides_only_points_at_the_site_page_it_is_about(self):
		rows, _ = built()
		routes = {json.loads(rs[0]["meta"])["route"] for name, rs in rows.items() if rs[0]["category"] in ("consult", "services")}
		self.assertTrue(routes and routes <= {"/consult", "/services"})
		self.assertTrue(all(item["category"] in ("consult", "services") for item in content.load() if item.get("rag") and not item["publish"]))

	def test_the_questions_name_files_that_exist(self):
		from raftor_agents_factory.rag import manager

		ids = {item["id"] for item in content.load()}
		for item in json.loads((manager.domain_dir(content.DOMAIN) / "evals" / "rag_questions.json").read_text()):
			self.assertTrue(set(item["expect"]) <= ids, item["q"])

	def test_a_piece_carries_the_products_and_services_of_the_article_and_of_those_it_points_to(self):
		rows, _ = built()
		meta = {name: json.loads(rs[0]["meta"]) for name, rs in rows.items()}
		self.assertEqual(meta["gem-emerald"]["products"], ["GEM012"])
		self.assertNotIn("GEM012", meta["gem-emerald"]["related_products"])  # its own is not repeated
		self.assertIn("Rudrabhishek Personal Pooja Blessings", meta["puj-rudrabhishek"]["services"])
		for m in meta.values():
			self.assertLessEqual(len(m["related_products"]), knowledge.RELATED_MAX)
			self.assertLessEqual(len(m["related_services"]), knowledge.RELATED_MAX)
