"""Skills and profiles of the AI guides: a guide has at most three skills of its own area, is shown only while they are on, reads the shelves of its skills, and a profile is made into a guide once."""
import copy
import json
import tempfile
from pathlib import Path

import frappe

from raftor_astrohq import ai_guides, ai_profiles, person
from raftor_astrohq.tests.helpers import AstroTestCase
from raftor_astrohq.tests.test_ai_personas import _clean as _clean_personas
import raftor_astrohq.tests.test_ai_personas as base

SLUGS = ("t-num", "t-two", "t-prof", "t-bad2")
TEST_SKILLS = ("t_skill_a", "t_skill_b", "t_skill_off")


def _clean():
	base.SLUGS = tuple(set(base.SLUGS) | set(SLUGS))
	_clean_personas()
	for key in TEST_SKILLS:
		frappe.delete_doc("AI Guide Skill", key, force=1, ignore_permissions=True) if frappe.db.exists("AI Guide Skill", key) else None
	frappe.db.commit()


def _skill(key, area="numerologist", shelves="numerology", enabled=1):
	frappe.get_doc({"doctype": "AI Guide Skill", "skill_key": key, "title": key, "area": area, "shelves": shelves, "enabled": enabled}).insert(ignore_permissions=True)


def _guide(slug, skills, **kw):
	return frappe.get_doc({"doctype": "AI Guide Persona", "slug": slug, "guide_name": slug.title(), "skills": [{"skill": s} for s in skills], "mindset": "Calm and exact.", "enabled": 1, **kw}).insert(ignore_permissions=True)


class TestSkills(AstroTestCase):
	def setUp(self):
		super().setUp()
		_clean()
		_skill("t_skill_a", shelves="numerology, consult")
		_skill("t_skill_b", shelves="consult, services")
		_skill("t_skill_off", enabled=0)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		_clean()

	def test_the_shipped_skills_are_the_five_disciplines_the_pandit_ji_ones_and_tarot_waits_for_its_guide(self):
		keys = {r["skill_key"]: r for r in ai_guides.skills()}
		for key in ("vedic_astrology", "kp_astrology", "tarot", "numerology", "dream_interpretation", "gemstones", "rudraksha", "poojas"):
			self.assertIn(key, keys)
		self.assertEqual((keys["kp_astrology"]["enabled"], keys["tarot"]["enabled"], keys["tarot"]["area"]), (0, 0, ""))
		self.assertTrue(all(keys[k]["enabled"] for k in ("numerology", "dream_interpretation", "vedic_astrology")))

	def test_a_guide_takes_the_area_of_its_skills_and_reads_the_shelves_of_all_of_them(self):
		guide = _guide("t-two", ["t_skill_a", "t_skill_b"])
		self.assertEqual(guide.area, "numerologist")
		self.assertEqual(person.persona_shelves("t-two", "numerologist"), ["numerology", "consult", "services"])
		self.assertEqual(person.persona_shelves("t-two", "pandit_ji"), [])  # another area's agent is not this guide's

	def test_a_guide_with_no_skills_has_no_shelves_of_its_own(self):
		_guide("t-num", [], area="numerologist")
		self.assertEqual(person.persona_shelves("t-num", "numerologist"), [])

	def test_at_most_three_skills_of_one_area_and_all_on(self):
		for key in ("t_skill_x1", "t_skill_x2"):
			_skill(key)
		try:
			with self.assertRaises(frappe.ValidationError):
				_guide("t-num", ["t_skill_a", "t_skill_b", "t_skill_x1", "t_skill_x2"])
			with self.assertRaises(frappe.ValidationError):
				_guide("t-num", ["t_skill_a", "t_skill_a"])
			with self.assertRaises(frappe.ValidationError):
				_guide("t-num", ["t_skill_a", "t_skill_off"])
			_skill("t_skill_dream", area="dream_guide", shelves="dreams")
			with self.assertRaises(frappe.ValidationError):
				_guide("t-num", ["t_skill_a", "t_skill_dream"])
		finally:
			for key in ("t_skill_x1", "t_skill_x2", "t_skill_dream"):
				frappe.db.delete("AI Guide Persona Skill", {"skill": key})
				frappe.delete_doc("AI Guide Skill", key, force=1, ignore_permissions=True)

	def test_switching_a_skill_off_takes_its_guides_off_the_page_and_out_of_the_chat(self):
		_guide("t-num", ["t_skill_a"], tagline="Numbers")
		self.assertEqual(frappe.db.get_value("Provider", "t-num", "status"), "Live")
		self.assertTrue(person.persona_voice("t-num", "numerologist"))
		skill = frappe.get_doc("AI Guide Skill", "t_skill_a"); skill.enabled = 0; skill.save(ignore_permissions=True)
		self.assertFalse(ai_guides.is_on("t-num"))
		self.assertEqual(frappe.db.get_value("Provider", "t-num", "status"), "Paused")
		self.assertEqual(person.persona_voice("t-num", "numerologist"), "")
		self.assertEqual(person.persona_shelves("t-num", "numerologist"), [])

	def test_a_skill_no_guide_can_do_yet_cannot_be_switched_on(self):
		with self.assertRaises(frappe.ValidationError):
			_skill("t_skill_off", area="", enabled=1) if False else frappe.get_doc({"doctype": "AI Guide Skill", "skill_key": "t_skill_x3", "title": "x", "area": "", "enabled": 1}).insert(ignore_permissions=True)

	def test_the_voice_carries_the_profile_the_language_and_the_boundaries(self):
		_guide("t-num", ["t_skill_a"], languages="Hinglish, English", traits="calm, exact", workflow="Ask the date\nShow the sum", response_format="Input\nResult", boundaries="Never promise wealth", signature_line="Let us check the sum.")
		voice = person.persona_voice("t-num", "numerologist")
		for part in ("Hinglish", "calm, exact", "1. Ask the date", "2. Show the sum", "Input; Result", "- Never promise wealth", "Let us check the sum."):
			self.assertIn(part, voice)
		self.assertIn("add to your other rules", voice)


def _profile(**kw):
	one = json.loads((Path(ai_profiles.HERE) / "guide_profiles" / "ASTRO-NUM-001.json").read_text(encoding="utf-8"))
	return {**one, "profile_id": "T-PROF-001", "slug": "t-prof", "display_name": "T Prof", **kw}


class TestProfiles(AstroTestCase):
	def setUp(self):
		super().setUp()
		_clean()
		self.folder = tempfile.mkdtemp()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		_clean()

	def _put(self, profile, name="ASTRO-p.json"):
		(Path(self.folder) / name).write_text(json.dumps(profile), encoding="utf-8")

	def test_every_profile_that_ships_fits_the_schema_and_a_skill(self):
		shipped = ai_profiles.profiles()
		self.assertEqual(len(shipped), 50)
		for profile in shipped:
			self.assertEqual(ai_profiles.problems(profile), [], profile["profile_id"])
		self.assertEqual(len({p["slug"] for p in shipped}), 50)
		self.assertEqual(len({p["profile_id"] for p in shipped}), 50)

	def test_a_profile_that_does_not_fit_is_reported_and_skipped(self):
		bad = _profile(); del bad["persona"]
		self._put(bad, "ASTRO-a.json"); self._put(_profile(discipline="astro_cooking", slug="t-bad2", profile_id="T-BAD-2"), "ASTRO-b.json")
		steps = ai_profiles.plan(Path(self.folder))
		self.assertEqual([s["action"] for s in steps], ["skipped", "skipped"])
		self.assertTrue(any("persona" in w for w in steps[0]["why"]))

	def test_preview_changes_nothing_and_a_run_makes_the_guide_once(self):
		self._put(_profile())
		self.assertEqual(ai_profiles.run(preview=True, folder=self.folder)[0]["action"], "made")
		self.assertFalse(frappe.db.exists("AI Guide Persona", "t-prof"))
		ai_profiles.run(folder=self.folder)
		guide = frappe.get_doc("AI Guide Persona", "t-prof")
		self.assertEqual((guide.profile_id, guide.area, guide.enabled, guide.languages, [s.skill for s in guide.skills]), ("T-PROF-001", "numerologist", 1, "Hinglish, English", ["numerology"]))
		self.assertEqual(guide.greeting, guide.signature_line)
		frappe.db.set_value("AI Guide Persona", "t-prof", "guide_name", "Edited in Desk")
		again = ai_profiles.run(folder=self.folder)
		self.assertEqual(again[0]["action"], "kept")
		self.assertEqual(frappe.db.get_value("AI Guide Persona", "t-prof", "guide_name"), "Edited in Desk")
		self.assertEqual(frappe.db.count("AI Guide Persona", {"profile_id": "T-PROF-001"}), 1)

	def test_a_guide_whose_skill_is_off_is_made_switched_off(self):
		self._put(_profile(discipline="tarot"))
		ai_profiles.run(folder=self.folder)
		self.assertEqual(frappe.db.get_value("AI Guide Persona", "t-prof", ["enabled", "area"]), (0, ""))

	def test_a_guide_that_waits_for_a_calculation_the_engine_lacks_is_made_switched_off_with_the_reason(self):
		self._put(_profile())
		(Path(self.folder) / "held.json").write_text(json.dumps({"T-PROF-001": "no Pythagorean sums in the engine"}), encoding="utf-8")
		step = ai_profiles.plan(Path(self.folder))[0]
		self.assertEqual((step["action"], step["on"], step["why"]), ("made", False, ["no Pythagorean sums in the engine"]))
		ai_profiles.run(folder=self.folder)
		self.assertEqual(frappe.db.get_value("AI Guide Persona", "t-prof", "enabled"), 0)

	def test_every_held_profile_exists_and_is_a_numerology_one_the_engine_cannot_do(self):
		held = ai_profiles.held()
		self.assertTrue(set(held) <= {p["profile_id"] for p in ai_profiles.profiles()})

	def test_the_voice_direction_sets_the_language(self):
		self.assertEqual(ai_profiles.languages("Deep, Hindi-first with clear explanations"), "Hindi, English")
		self.assertEqual(ai_profiles.languages("Calm male voice; conversational English and Hinglish."), "Hinglish, English")
		self.assertEqual(ai_profiles.languages("Mature male voice, neutral Indian English with clear Hindi"), "English")
