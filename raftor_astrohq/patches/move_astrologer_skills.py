"""The Vedic and KP astrology skills now belong to the Vedic astrologer guide and the KP astrologer guide (they were Pandit ji's). A site made before keeps the records as they are (skills and guides are seeded once, then
kept in Desk): move each skill to its guide's area, and each guide made from it (ASTRO-VED-*, ASTRO-KP-*) with it, listed under the new area's word. Only the area and the shelves are written; the switches stay as staff have them
(the KP skill stays off until the KP guide's keys are in use and a person switches it on)."""
import frappe

MOVES = {"vedic_astrology": "vedic_astrologer", "kp_astrology": "kp_astrologer"}


def execute():
	from raftor_astrohq import ai_guides

	for skill, area in MOVES.items():
		if not frappe.db.exists("AI Guide Skill", skill):
			continue
		frappe.db.set_value("AI Guide Skill", skill, {"area": area, "shelves": "consult"})
		for name in frappe.get_all("AI Guide Persona Skill", filters={"skill": skill, "parenttype": "AI Guide Persona"}, pluck="parent"):
			if frappe.db.get_value("AI Guide Persona", name, "area") in ("pandit_ji", "", None):
				frappe.db.set_value("AI Guide Persona", name, "area", area)
				ai_guides.sync_persona(frappe.get_doc("AI Guide Persona", name))
