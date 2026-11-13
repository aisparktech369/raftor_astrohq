"""The Tarot skill now has an area (the tarot guide). A site made before it keeps the record as it is (skills are seeded once, then kept in Desk): fill the area, the shelves and the note, only where they are blank,
and leave the switch exactly as staff have it (it stays off until the tarot guide's keys are made and a person switches it on)."""
import json
from pathlib import Path

import frappe


def execute():
	if not frappe.db.exists("AI Guide Skill", "tarot"):
		return
	row = next((r for r in json.loads((Path(__file__).parent.parent / "ai_skills.json").read_text(encoding="utf-8")) if r["skill_key"] == "tarot"), None)
	if not row:
		return
	have = frappe.db.get_value("AI Guide Skill", "tarot", ["area", "shelves", "about"], as_dict=True)
	values = {key: row[key] for key in ("area", "shelves", "about") if not (have.get(key) or "").strip() or (key == "shelves" and have.get(key) == "consult") or (key == "about" and "Not there yet" in (have.get(key) or ""))}
	if values:
		frappe.db.set_value("AI Guide Skill", "tarot", values)
