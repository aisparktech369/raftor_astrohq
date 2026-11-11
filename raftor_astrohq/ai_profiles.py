"""The AI guide profiles that come with the app (guide_profiles/*.json, written to the AstroHQ expert profile schema) made into AI Guide Personas.

	plan()                   what an import would do with each profile (a preview: nothing is touched)
	run(preview=False)       makes the guides that are missing; safe to repeat

A profile is known by its profile_id: a guide already made from it is left exactly as staff have it in Desk, and a profile that does not fit the schema or names an unknown discipline is reported and skipped. The skills a profile
needs are the AI Guide Skill records (ai_skills.json): a guide whose skill is not switched on is made switched off.
A profile listed in guide_profiles/held.json is made switched off, with the reason in the plan. `bench --site <site> execute raftor_astrohq.ai_profiles.run --kwargs '{"preview": 1}'` shows the plan."""
import json
import re
from pathlib import Path

import frappe

HERE = Path(__file__).parent
PERSONA, SKILL = "AI Guide Persona", "AI Guide Skill"
DISCIPLINE_SKILL = {"vedic_astrology": "vedic_astrology", "kp_astrology": "kp_astrology", "tarot": "tarot", "numerology": "numerology", "dream_interpretation": "dream_interpretation"}
ISSUES_FIRST = 5
NEEDED_PERSONA = ("traits", "mindset", "communication_style", "voice_direction", "signature_line")
NEEDED_METHOD = ("workflow", "response_format")


def profiles(folder: Path | None = None) -> list[dict]:
	return [json.loads(f.read_text(encoding="utf-8")) for f in sorted((folder or HERE / "guide_profiles").glob("ASTRO-*.json"))]


def problems(profile: dict) -> list[str]:
	"""Why a profile cannot be used: what the schema says is wrong with it, or the discipline no skill covers."""
	import jsonschema

	schema = json.loads((HERE / "guide_profiles" / "schema.json").read_text(encoding="utf-8")) if (HERE / "guide_profiles" / "schema.json").exists() else {}
	found = [f"{'/'.join(str(p) for p in e.absolute_path) or 'profile'}: {e.message}" for e in sorted(jsonschema.Draft202012Validator(schema).iter_errors(profile), key=lambda e: list(e.absolute_path))][:ISSUES_FIRST]
	if not found:  # the schema keeps these loose; the guide needs them
		who, method = profile["persona"], profile.get("consultation_method") or {}
		found += [f"persona/{k}: missing" for k in NEEDED_PERSONA if not who.get(k)]
		found += [f"consultation_method/{k}: missing" for k in NEEDED_METHOD if not method.get(k)]
	if not found and DISCIPLINE_SKILL.get(profile.get("discipline")) is None:
		found.append(f"discipline: no skill for {profile.get('discipline')}")
	return found


def languages(voice_direction: str) -> str:
	"""The languages a profile's voice direction implies, first language first (it sets the language of the replies)."""
	text = (voice_direction or "").lower()
	if re.search(r"hindi-first|gentle hindi", text):
		return "Hindi, English"
	if re.search(r"hinglish|hindi-english|hindi and english", text):
		return "Hinglish, English"
	return "English"


def _words(items) -> str:
	if isinstance(items, str):  # a profile may give the audience as one sentence
		return items.strip()
	return ", ".join(str(i).replace("_", " ").strip().capitalize() for i in items or [])


def _lines(items) -> str:
	return "\n".join(str(i).strip() for i in items or [])


def persona_values(profile: dict, sequence: int) -> dict:
	"""The fields of the AI Guide Persona a profile becomes."""
	who, method = profile["persona"], profile.get("consultation_method") or {}
	skill = DISCIPLINE_SKILL[profile["discipline"]]
	return {
		"doctype": PERSONA, "slug": profile["slug"], "profile_id": profile["profile_id"], "guide_name": profile["display_name"], "skills": [{"skill": skill}],
		"tagline": profile["tagline"], "bio": " ".join(x for x in (who["communication_style"], f"Best for: {_words(profile['audience'])[:1].lower() + _words(profile['audience'])[1:].rstrip('.')}." if profile.get("audience") else "") if x),
		"audience": _words(profile.get("audience")), "topics": _words(profile.get("specialisations")), "languages": languages(who.get("voice_direction")), "greeting": who["signature_line"],
		"traits": ", ".join(str(t).replace("_", " ") for t in who.get("traits") or []), "mindset": who["mindset"], "communication_style": who["communication_style"], "signature_line": who["signature_line"],
		"workflow": _lines(method.get("workflow")), "response_format": _lines(method.get("response_format")), "boundaries": _lines(profile.get("boundaries")),
		"avatar_prompt": _avatar_prompt(profile), "ai_image": 1, "sequence": sequence,
	}


def _avatar_prompt(profile: dict) -> str:
	f = HERE / "guide_profiles" / "avatar-prompts" / f"{profile['profile_id']}.txt"
	return f.read_text(encoding="utf-8").strip() if f.exists() else (profile.get("identity") or {}).get("appearance", "")


def held(folder: Path | None = None) -> dict:
	"""Profiles whose guide waits for something the site cannot do yet (guide_profiles/held.json: profile_id -> why). They are made, switched off."""
	f = (folder or HERE / "guide_profiles") / "held.json"
	return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def plan(folder: Path | None = None) -> list[dict]:
	"""For each profile: made (new), kept (a guide from it exists) or skipped (with the reasons), and whether the guide would be on."""
	out = []
	for profile in profiles(folder):
		pid = profile.get("profile_id") or "?"
		bad = problems(profile)
		if bad:
			out.append({"profile": pid, "action": "skipped", "why": bad})
		elif frappe.db.exists(PERSONA, {"profile_id": pid}):
			out.append({"profile": pid, "action": "kept", "why": []})
		elif frappe.db.exists(PERSONA, profile["slug"]):
			out.append({"profile": pid, "action": "skipped", "why": [f"another guide already uses the key {profile['slug']}"]})
		else:
			skill = frappe.db.get_value(SKILL, DISCIPLINE_SKILL[profile["discipline"]], ["enabled", "area"], as_dict=True)
			wait = held(folder).get(pid)
			out.append({"profile": pid, "action": "made", "why": [wait] if wait else [], "on": bool(skill and skill.enabled and skill.area and not wait)})
	return out


def run(preview: bool = False, folder: str | None = None) -> list[dict]:
	"""Makes each guide that is missing (nothing at all with preview). Needs the skills to exist first."""
	steps = plan(Path(folder) if folder else None)
	if preview or not frappe.db.exists("DocType", PERSONA):
		return steps
	by_id = {p.get("profile_id"): p for p in profiles(Path(folder) if folder else None)}
	made = 0
	for step in steps:
		if step["action"] != "made":
			continue
		values = persona_values(by_id[step["profile"]], 10 + 10 * made)
		frappe.get_doc({**values, "enabled": 1 if step["on"] else 0}).insert(ignore_permissions=True)
		made += 1
	frappe.db.commit()
	return steps
