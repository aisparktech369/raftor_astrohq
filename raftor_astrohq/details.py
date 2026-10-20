"""What astrohq asks for when someone books, and its one real rule (declared in vocabulary.py)."""
import frappe
from frappe import _

from raftor_astrohq import profiles

def sankalp() -> list[dict]:
	return [
		{"name": "sankalp_name", "label": _("Name for the sankalp"), "required": True, "placeholder": _("Full name as you want it spoken")},
		{"name": "gotra", "label": _("Gotra"), "required": True, "placeholder": _("e.g. Kashyap"), "hint": _("If you do not know it, write Kashyap or ask your family.")},
	]


def wish() -> dict:
	return {"name": "wish", "label": _("Your wish or purpose"), "type": "textarea", "placeholder": _("Optional")}


def birth_details() -> list[dict]:
	"""What a report made from someone's birth asks: who, the day, the time and the place."""
	return [
		{"name": "report_name", "label": _("Name"), "required": True, "placeholder": _("Full name for the report")},
		{"name": "birth_date", "label": _("Date of birth"), "type": "date", "required": True},
		{"name": "birth_time", "label": _("Time of birth"), "type": "time_text", "required": True, "placeholder": "HH:MM", "hint": _("If you do not know it, write 12:00.")},
		{"name": "birth_place", "label": _("Place of birth"), "required": True, "placeholder": _("Town or city")},
	]


def topics() -> list[str]:
	"""The topics a visitor can say are troubling them, as staff keep them in Desk (Guidance Topic), in their order. Every astrologer can answer every one, so a topic is not a way to
	filter them; it starts the question."""
	return frappe.get_all("Guidance Topic", filters={"enabled": 1}, order_by="sequence asc, name asc", pluck="name")


def wishes() -> list[str]:
	"""What someone can wish for, as staff keep them in Desk (Blessing Wish), in their order. Staff tag each event with the ones it serves (event_filters.py)."""
	return frappe.get_all("Blessing Wish", filters={"enabled": 1}, order_by="sequence asc, name asc", pluck="name")


def question() -> dict:
	return {"name": "question", "label": _("What would you like to ask?"), "type": "textarea", "placeholder": _("Optional")}


def consultation_rules(values: dict, user: str) -> dict:
	"""A reading needs birth details on the customer's account: any profile will do, their own or a family member's (has_birth_profile)."""
	if not profiles.has_birth_profile(user):
		return {"_form": _("Please add your birth details first, then book.")}
	return {}
