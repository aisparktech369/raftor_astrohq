"""What the App Chat Card draws for the AI guide: which agent it is, every word, and what a signed-out visitor goes through first (card_methods: the card holds no wording of its own).

A visitor who is not signed in meets the agent's sign-up conversation, which its blueprint declares (the factory's `gate`, with defaults for any agent that needs a signed-in user); the card plays it
and uses the site's own code sign-in. A signed-in person gets the chat."""
import frappe
from frappe import _

from raftor_astrohq import agents


def _gate():
	"""The blueprint's sign-up conversation as plain words, or None when the agent is open to everyone or the factory is not here."""
	try:
		from raftor_agents_factory.blueprints.registry import gate_of, load_blueprint

		gate = gate_of(load_blueprint(agents.BLUEPRINT))
	except Exception:
		return None
	return gate.model_dump() if gate else None


def _frame() -> dict:
	return {"title": _("Pandit ji"), "subtitle": _("AI guide · Rudraksha, gemstones and poojas"), "avatar": "/files/astrohq-icon.svg", "send_word": _("Send"), "new_chat_word": _("New chat")}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def info(**args) -> dict:
	"""A guest gets the sign-up conversation (or, with none, a button to sign in). A signed-in person gets the agent's name and words. If the agent is switched off the card says so and draws no chat."""
	if not frappe.db.get_value("Blueprint Reference", agents.BLUEPRINT, "is_active"):
		return {"notice": _("Pandit ji is resting. Please come back a little later.")}
	if frappe.session.user == "Guest":
		gate = _gate()
		if gate:
			return {**_frame(), "gate": gate, "placeholder": _("Type your answer"), "notice": _("AI guide. I explain from our Academy and can't predict or promise results.")}
		return {"sign_in": {"message": _("Sign up or sign in to ask Pandit ji, our AI guide to Rudraksha, gemstones and poojas. It takes a minute, and booking and buying need an account too."),
							"label": _("Sign up or sign in"), "href": "/login?redirect-to=/ask/pandit-ji"}}
	name = (frappe.db.get_value("User", frappe.session.user, "first_name") or "").strip()
	return {
		**_frame(), "blueprint": agents.BLUEPRINT,
		"welcome": (_("Hi {0}, I'm Pandit ji. ").format(name) if name else _("Hi, I'm Pandit ji. ")) + _("What would you like to know?"),
		"placeholder": _("Ask Pandit ji"), "notice": _("AI guide. I explain from our Academy and can't predict or promise results."),
	}


def guide() -> dict:
	"""The site's guide, the round button on every page (websitehq's windows, hook rfhq_window_guide): where it opens, who it is, and the pages where it would only be in the way (the guide's own page, the sign-in)."""
	return {"url": "/ask/pandit-ji", "title": _("Pandit ji"), "label": _("Ask Pandit ji"), "icon": "/files/astrohq-icon.svg", "hide_on": ["/login", "/signup", "/ask/pandit-ji"]}
