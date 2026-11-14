"""Each Tarot reader gets the way of speaking the factory now writes for them (a voice sheet, their own style, signature line, way of working and shape of an answer). Guides that were made before carried the
templated lines (a tagline repeated as the style, one shared script) and an empty voice. Only these fields are written (a plain write, no save: nothing is switched on or off); a reader whose voice
staff have already written in Desk keeps it."""
import frappe

FIELDS = ("voice", "communication_style", "signature_line", "greeting", "workflow", "response_format", "mindset", "traits")


def execute():
	from raftor_agentshq import personas

	for person in personas.catalogue():
		if person.get("discipline") != "tarot":
			continue
		name = frappe.db.get_value("AI Guide Persona", {"profile_id": person["profile_id"]}, "name")
		if not name:
			continue
		have = frappe.db.get_value("AI Guide Persona", name, "voice")
		for field in FIELDS:
			if field == "voice" and have:
				continue  # staff have written this one
			if person.get(field):
				frappe.db.set_value("AI Guide Persona", name, field, person[field])
