"""What the App Chat Card draws for the AI guide: which agent it is, every word, and whether the person has to sign in first (card_methods: the card holds no wording of its own)."""
import frappe
from frappe import _

from raftor_astrohq import agents


@frappe.whitelist(allow_guest=True, methods=["POST"])
def info(**args) -> dict:
	"""A guest is asked to sign in and comes back here. A signed-in person gets the agent's name and words. If the agent is switched off the card says so and draws no chat."""
	if frappe.session.user == "Guest":
		return {"sign_in": {"message": _("Sign in to ask Pandit ji, our AI guide to Rudraksha, gemstones and poojas."), "label": _("Sign in"), "href": "/login?redirect-to=/ask/pandit-ji"}}
	if not frappe.db.get_value("Blueprint Reference", agents.BLUEPRINT, "is_active"):
		return {"notice": _("Pandit ji is resting. Please come back a little later.")}
	return {
		"blueprint": agents.BLUEPRINT, "title": _("Pandit ji"), "subtitle": _("AI guide · Rudraksha, gemstones and poojas"), "avatar": "/files/astrohq-icon.svg",
		"welcome": _("Namaste. I am Pandit ji, an AI guide. Ask me about a bead, a stone or a pooja, and I will explain it from our Academy and show you what we offer. I cannot promise any result."),
		"placeholder": _("Ask Pandit ji"), "send_word": _("Send"), "new_chat_word": _("New chat"),
		"notice": _("An AI guide. It explains from the Academy and cannot predict or promise results."),
	}
