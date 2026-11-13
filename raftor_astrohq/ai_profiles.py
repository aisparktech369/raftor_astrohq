"""The AI guides made from the agent persons the agents factory carries (AgentsHQ serves them: raftor_agentshq.personas), as AI Guide Personas.

	plan()                   what an import would do with each person (a preview: nothing is touched)
	run(preview=False)       makes the guides that are missing; safe to repeat

The person brings its character, voice, way of working and portrait; AstroHQ attaches the skill it can do for the person's discipline, may give the person another name (pack/guides.json "names": profile_id -> name) and decides whether it is on.
A person is known by its profile_id: a guide already made from it is left exactly as staff have it in Desk. A guide whose skill is not switched on, or that pack/guides.json lists under "held" (profile_id -> why), is made switched off.
`bench --site <site> execute raftor_astrohq.ai_profiles.run --kwargs '{"preview": 1}'` shows the plan."""
import json
import re
from pathlib import Path

import frappe

HERE = Path(__file__).parent
PACK = HERE / "pack" / "guides.json"
PERSONA, SKILL = "AI Guide Persona", "AI Guide Skill"
DISCIPLINE_SKILL = {"vedic_astrology": "vedic_astrology", "kp_astrology": "kp_astrology", "tarot": "tarot", "numerology": "numerology", "dream_interpretation": "dream_interpretation"}


def _pack(source: Path | None = None) -> dict:
	return json.loads((source or PACK).read_text(encoding="utf-8"))


def held(source: Path | None = None) -> dict:
	"""Persons whose guide waits for something the site cannot do yet (profile_id -> why). They are made, switched off."""
	return _pack(source).get("held") or {}


def persons() -> list[dict]:
	"""The factory's persons, as AgentsHQ gives them (none when AgentsHQ or the factory is not here)."""
	try:
		from raftor_agentshq import personas
	except ImportError:
		return []
	return personas.catalogue()


def slug_of(key: str) -> str:
	"""A guide's slug is its record's name, its address (`?persona=`) and its listing's name: lowercase letters, numbers and single hyphens, as the listing requires. A person's key may carry more (an apostrophe in
	Rhea D'Souza): apostrophes are dropped, any other run of characters becomes one hyphen."""
	return re.sub(r"[^a-z0-9]+", "-", re.sub(r"['\u2019`]", "", str(key).lower())).strip("-")


def persona_values(person: dict, sequence: int, name: str | None = None) -> dict:
	"""The fields of the AI Guide Persona a person becomes."""
	keep = ("tagline", "bio", "audience", "topics", "languages", "greeting", "traits", "mindset", "communication_style", "signature_line", "workflow", "response_format", "boundaries", "avatar_prompt")
	return {"doctype": PERSONA, "slug": slug_of(person["key"]), "profile_id": person["profile_id"], "guide_name": name or person["name"], "skills": [{"skill": DISCIPLINE_SKILL[person["discipline"]]}],
			**{k: person[k] for k in keep}, "ai_image": 1, "sequence": sequence}


def plan(source: Path | None = None) -> list[dict]:
	"""For each person: made (new), kept (a guide from it exists) or skipped (with the reasons), and whether the guide would be on."""
	out, wait, names = [], held(source), _pack(source).get("names") or {}
	for person in persons():
		pid = person["profile_id"]
		if person["discipline"] not in DISCIPLINE_SKILL:
			out.append({"profile": pid, "action": "skipped", "why": [f"discipline: no skill for {person['discipline']}"]})
		elif frappe.db.exists(PERSONA, {"profile_id": pid}):
			out.append({"profile": pid, "action": "kept", "why": []})
		elif frappe.db.exists(PERSONA, person["key"]):
			out.append({"profile": pid, "action": "skipped", "why": [f"another guide already uses the key {person['key']}"]})
		else:
			skill = frappe.db.get_value(SKILL, DISCIPLINE_SKILL[person["discipline"]], ["enabled", "area"], as_dict=True)
			out.append({"profile": pid, "action": "made", "why": [wait[pid]] if pid in wait else [], "on": bool(skill and skill.enabled and skill.area and pid not in wait), "name": names.get(pid) or person["name"]})
	return out


def run(preview: bool = False, source: str | None = None) -> list[dict]:
	"""Makes each guide that is missing (nothing at all with preview). Needs the skills to exist first."""
	steps = plan(Path(source) if source else None)
	if preview or not frappe.db.exists("DocType", PERSONA):
		return steps
	by_id = {p["profile_id"]: p for p in persons()}
	made = 0
	for step in steps:
		if step["action"] != "made":
			continue
		values = persona_values(by_id[step["profile"]], 10 + 10 * made, step["name"])
		frappe.get_doc({**values, "enabled": 1 if step["on"] else 0}).insert(ignore_permissions=True)
		made += 1
	frappe.db.commit()
	return steps
