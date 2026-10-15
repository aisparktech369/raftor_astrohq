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


def topics() -> list[str]:
	"""What can be troubling someone who comes for a reading. Every astrologer can answer every one, so it is not a way to filter them; it starts the question."""
	return [_("Career"), _("Marriage"), _("Love"), _("Money"), _("Health"), _("Children"), _("Auspicious date")]


def wishes() -> list[str]:
	"""What someone can wish for when they book a blessing. Staff tag each event with the ones it serves (event_filters.py)."""
	return [_("Prosperity"), _("Health"), _("Family"), _("Protection"), _("Peace"), _("Success")]


def question() -> dict:
	return {"name": "question", "label": _("What would you like to ask?"), "type": "textarea", "placeholder": _("Optional")}


def consultation_rules(values: dict, user: str) -> dict:
	"""A reading needs birth details on the customer's account: any profile will do, their own or a family member's (has_birth_profile)."""
	if not profiles.has_birth_profile(user):
		return {"_form": _("Please add your birth details first, then book.")}
	return {}
