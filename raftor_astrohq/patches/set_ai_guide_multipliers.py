"""Gives each AI guide its starting multiplier (AI minutes used per minute): the ones that read a chart take 2, the others 1. The owner changes them in Desk (AI Guide Persona > AI Minutes Used per Minute); this runs once."""
import frappe

START = {"vedic_astrologer": 2, "kp_astrologer": 2}


def execute():
	frappe.reload_doc("raftor_astro_hq", "doctype", "ai_guide_persona")
	for row in frappe.get_all("AI Guide Persona", fields=["name", "area"]):
		frappe.db.set_value("AI Guide Persona", row.name, "minute_factor", START.get(row.area, 1), update_modified=False)
