"""The tarot guides made before the Tarot skill had an area (ASTRO-TAR-001 and the others) have a blank area. A guide takes the area of its skills, so each that has the tarot skill and no area gets `tarot`.
Only the area is set (a plain write, no save): the guides stay switched off, and nothing is listed or shown until staff switch the tarot guide on (docs/ai-guides.md). An area staff have set is left."""
import frappe


def execute():
	for name in frappe.get_all("AI Guide Persona Skill", filters={"skill": "tarot", "parenttype": "AI Guide Persona"}, pluck="parent"):
		if not (frappe.db.get_value("AI Guide Persona", name, "area") or "").strip():
			frappe.db.set_value("AI Guide Persona", name, "area", "tarot")
