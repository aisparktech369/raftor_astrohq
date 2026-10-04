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


def question() -> dict:
	return {"name": "question", "label": _("What would you like to ask?"), "type": "textarea", "placeholder": _("Optional")}


def consultation_rules(values: dict, user: str) -> dict:
	"""A reading needs the customer's own birth details; they are kept on their account (birth_details_complete)."""
	if not profiles.birth_details_complete(frappe._dict(applicant_user=user)):
		return {"_form": _("Please add your birth details first, then book.")}
	return {}


def dashboard_section(user: str) -> list[dict]:
	"""An extra block on the subscription dashboard: where the customer keeps their birth details."""
	return [{"type": "actions", "links": [{"label": _("Your birth details"), "href": "/birth-profiles", "kind": "outline"}]}]
