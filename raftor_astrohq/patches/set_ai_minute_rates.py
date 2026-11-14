"""Every AI guide gets the price of a minute that AI minutes bought in a chat cost (AI Guide Persona.minute_rate): 1 for now, changed per guide in Desk. Only a guide with none set is given it."""
import frappe


def execute():
	frappe.reload_doc("raftor_astro_hq", "doctype", "ai_guide_persona")
	frappe.db.sql("update `tabAI Guide Persona` set minute_rate = 1 where minute_rate is null or minute_rate = 0")
