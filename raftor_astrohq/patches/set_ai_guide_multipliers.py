"""Gives each AI guide made from a factory person that person's multiplier (AI minutes used per minute), as the factory carries it. The owner changes it in Desk (AI Guide Persona > AI Minutes Used per Minute); this runs once."""
import frappe


def execute():
	frappe.reload_doc("raftor_astro_hq", "doctype", "ai_guide_persona")
	from raftor_astrohq import ai_profiles

	by_id = {p["profile_id"]: p.get("minute_factor") or 1 for p in ai_profiles.persons()}
	for row in frappe.get_all("AI Guide Persona", fields=["name", "profile_id"]):
		frappe.db.set_value("AI Guide Persona", row.name, "minute_factor", by_id.get(row.profile_id, 1), update_modified=False)
