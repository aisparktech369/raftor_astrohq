"""The tarot guide on the site: the skill, the agent (its user, role, tools and keys' names), and its words (agents.py, ai_guides.py, agent_chat.py, ai_skills.json)."""
import json
from pathlib import Path

import frappe

from raftor_astrohq import agent_chat, agents, ai_guides
from raftor_astrohq.tests.helpers import AstroTestCase

SESSION_TOOLS = ["start_tarot_session", "deal_tarot_card", "get_tarot_session"]


class TestTheTarotAgent(AstroTestCase):
	def test_the_tarot_guide_is_an_agent_of_the_site_with_its_own_user_role_and_tools(self):
		tarot = agents.AGENTS["tarot"]
		self.assertEqual((tarot["role"], tarot["user"], tarot["blueprint"]), ("Tarot Guide Agent", "tarot-guide-agent@agents.astrohq.in", "tarot"))
		self.assertEqual(tarot["tools"], ["search_knowledge", *SESSION_TOOLS, "find_services", "get_service", "get_family_member"])
		self.assertEqual(tarot["reads"], {})  # the session tools keep their own records; the guide reads none of the site's
		self.assertEqual(len({a["user"] for a in agents.AGENTS.values()}), len(agents.AGENTS))
		self.assertEqual(agents.blueprint_of_user("tarot-guide-agent@agents.astrohq.in"), "tarot")

	def test_it_reads_no_reports_and_only_the_tarot_notes_and_who_is_in_the_family(self):
		self.assertEqual(agents.report_areas("tarot-guide-agent@agents.astrohq.in"), [])
		self.assertEqual(agents.reads_of("tarot"), {"notes": ["tarot"], "card": "names"})

	def test_every_tool_it_may_call_is_registered_with_the_tool_server(self):
		registered = {path.rsplit(".", 1)[1] for path in frappe.get_hooks("assistant_tools", app_name="raftor_astrohq")}
		for name, cls in (("start_tarot_session", "StartTarotSession"), ("deal_tarot_card", "DealTarotCard"), ("get_tarot_session", "GetTarotSession")):
			self.assertIn(cls, registered, name)

	def test_a_guide_whose_keys_are_not_made_yet_has_its_record_made_switched_off(self):
		self.assertEqual(agents.SWITCHED_OFF_AT_FIRST, {"tarot"})  # the others are made on, as they always were
		if frappe.db.exists("Blueprint Reference", "tarot"):
			self.assertTrue(frappe.db.exists("Blueprint Reference", {"name": "tarot", "agent_role": "Customer"}))


class TestTheTarotSkill(AstroTestCase):
	def skill(self):
		return next(r for r in ai_guides.skills() if r["skill_key"] == "tarot")

	def test_the_skill_has_its_area_and_its_shelves_and_waits_off_for_the_guides_keys(self):
		skill = self.skill()
		self.assertEqual((skill["area"], skill["enabled"]), ("tarot", 0))
		self.assertEqual([s.strip() for s in skill["shelves"].split(",")], ["tarot", "consult"])
		self.assertIn("TAROT_FAC_KEY", skill["about"])

	def test_the_area_is_one_of_the_sites_agents_and_its_guides_are_listed_as_tarot_readers(self):
		self.assertIn(self.skill()["area"], agents.AGENTS)
		self.assertEqual(ai_guides.AREA_WORD["tarot"], "Tarot reader")

	def test_the_record_on_a_site_is_filled_by_the_patch_but_its_switch_is_left_as_staff_have_it(self):
		from raftor_astrohq.patches import set_tarot_skill_area

		original = frappe.db.get_value("AI Guide Skill", "tarot", ["area", "shelves", "about", "enabled"], as_dict=True)
		try:
			frappe.db.set_value("AI Guide Skill", "tarot", {"area": "", "shelves": "consult", "about": "Needs a tarot guide of its own. Not there yet.", "enabled": 1})
			set_tarot_skill_area.execute()
			after = frappe.db.get_value("AI Guide Skill", "tarot", ["area", "shelves", "about", "enabled"], as_dict=True)
			self.assertEqual((after.area, after.shelves, after.enabled), ("tarot", "tarot, consult", 1))  # the switch is untouched
			frappe.db.set_value("AI Guide Skill", "tarot", {"shelves": "my own shelves", "about": "Staff wrote this."})
			set_tarot_skill_area.execute()
			again = frappe.db.get_value("AI Guide Skill", "tarot", ["shelves", "about"], as_dict=True)
			self.assertEqual((again.shelves, again.about), ("my own shelves", "Staff wrote this."))  # what staff wrote is kept
		finally:
			frappe.db.set_value("AI Guide Skill", "tarot", dict(original))

	def test_the_tarot_guides_made_before_the_area_existed_get_it_and_stay_switched_off(self):
		from raftor_astrohq.patches import set_tarot_guides_area

		names = frappe.get_all("AI Guide Persona Skill", filters={"skill": "tarot", "parenttype": "AI Guide Persona"}, pluck="parent")
		if not names:
			self.skipTest("no tarot guide on this site")
		before = frappe.db.get_value("AI Guide Persona", names[0], ["area", "enabled"], as_dict=True)
		try:
			frappe.db.set_value("AI Guide Persona", names[0], "area", "")
			set_tarot_guides_area.execute()
			after = frappe.db.get_value("AI Guide Persona", names[0], ["area", "enabled"], as_dict=True)
			self.assertEqual((after.area, after.enabled), ("tarot", before.enabled))  # the area only: the guide is as it was
			frappe.db.set_value("AI Guide Persona", names[0], "area", "pandit_ji")
			set_tarot_guides_area.execute()
			self.assertEqual(frappe.db.get_value("AI Guide Persona", names[0], "area"), "pandit_ji")  # an area staff set is left
		finally:
			frappe.db.set_value("AI Guide Persona", names[0], dict(before))

	def test_the_patch_is_listed_to_run(self):
		listed = (Path(frappe.get_app_path("raftor_astrohq")) / "patches.txt").read_text(encoding="utf-8")
		for patch in ("set_tarot_skill_area", "set_tarot_guides_area"):
			self.assertIn(f"raftor_astrohq.patches.{patch}", listed)


class TestTheTarotChatWords(AstroTestCase):
	def test_the_chat_has_the_tarot_guides_own_words_not_pandit_jis(self):
		words = agent_chat._words("tarot")
		self.assertEqual((words["title"], words["who"]), ("Tarot guide", "the tarot guide"))
		self.assertIn("can't predict", words["notice"])
		self.assertTrue(words["ask"] and words["placeholder"] and words["resting"] and words["sign_in"])
		self.assertNotIn("Pandit", json.dumps(words))


class TestGuideSlugs(AstroTestCase):
	"""A person's key may carry an apostrophe (Rhea D'Souza); a guide's slug is its record name and its listing's name, which accept lowercase letters, numbers and hyphens only."""

	def test_a_slug_drops_apostrophes_and_hyphenates_anything_else_and_a_clean_one_is_unchanged(self):
		from raftor_astrohq import ai_profiles

		for key, slug in (("rhea-d'souza", "rhea-dsouza"), ("Rhea D’Souza", "rhea-dsouza"), ("maya-kapoor", "maya-kapoor"), ("  Tara  Menon ", "tara-menon"), ("a__b", "a-b")):
			self.assertEqual(ai_profiles.slug_of(key), slug, key)

	def test_a_guide_made_from_such_a_person_gets_the_clean_slug(self):
		from raftor_astrohq import ai_profiles

		person = {"key": "rhea-d'souza", "profile_id": "T-1", "name": "Rhea D'Souza", "discipline": "tarot", "tagline": "", "bio": "", "audience": [], "topics": [], "languages": [], "greeting": "", "traits": [], "mindset": "",
				  "communication_style": "", "signature_line": "", "workflow": [], "response_format": "", "boundaries": [], "avatar_prompt": ""}
		self.assertEqual(ai_profiles.persona_values(person, 1)["slug"], "rhea-dsouza")

	def test_the_patch_renames_a_guide_with_an_invalid_slug_and_leaves_clean_ones_alone(self):
		from raftor_astrohq.patches import fix_guide_slugs
		from raftor_astrohq.tests.test_ai_skills import _guide

		_guide("t-source", [], area="numerologist", enabled=0)
		frappe.rename_doc("AI Guide Persona", "t-source", "t-o'neil", force=True)  # (a record cannot be saved with such a slug now: this is how it got there)
		frappe.db.set_value("AI Guide Persona", "t-o'neil", "slug", "t-o'neil")
		_guide("t-clean", [], area="numerologist", enabled=0)
		fix_guide_slugs.execute()
		self.assertFalse(frappe.db.exists("AI Guide Persona", "t-o'neil"))
		self.assertEqual(frappe.db.get_value("AI Guide Persona", "t-oneil", "slug"), "t-oneil")  # the slug field follows the record's name
		self.assertTrue(frappe.db.exists("AI Guide Persona", "t-clean"))
