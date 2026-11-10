"""What the App Chat Card draws for the AI guide: which agent it is, every word, and what a signed-out visitor goes through first (card_methods: the card holds no wording of its own).

A visitor who is not signed in meets the agent's sign-up conversation, which its blueprint declares (the factory's `gate`, with defaults for any agent that needs a signed-in user); the card plays it
and uses the site's own code sign-in. A signed-in person gets the chat."""
import frappe
from frappe import _

from raftor_astrohq import agents


def _gate(blueprint: str | None = None):
	"""The blueprint's sign-up conversation as plain words, or None when the agent is open to everyone or the factory is not here."""
	try:
		from raftor_agents_factory.blueprints.registry import gate_of, load_blueprint

		gate = gate_of(load_blueprint(blueprint or agents.BLUEPRINT))
	except Exception:
		return None
	return gate.model_dump() if gate else None


def _words(blueprint: str | None = None) -> dict:
	"""Every word the card shows for one of the site's agents, and where its page is."""
	if blueprint == agents.NUMEROLOGIST["blueprint"]:
		return {"title": _("Numerology guide"), "subtitle": _("AI guide · numerology"), "who": _("the numerology guide"), "placeholder": _("Ask the numerology guide"), "route": "numerologist",
				"resting": _("The numerology guide is resting. Please come back a little later."), "notice": _("AI guide. I explain numerology from our Academy. It is not a prediction or advice."),
				"sign_in": _("Sign up or sign in to ask the numerology guide. It takes a minute."), "ask": _("Give me a birth day or a name and I'll work out the numbers.")}
	if blueprint == agents.DREAM_GUIDE["blueprint"]:
		return {"title": _("Dream guide"), "subtitle": _("AI guide · Exploring your dreams"), "who": _("the dream guide"), "placeholder": _("Tell me a dream"), "route": "dream-guide",
				"resting": _("The dream guide is resting. Please come back a little later."), "notice": _("AI guide. I explore what a dream might mean to you. I can't predict anything or say what a dream shows about your health or others."),
				"sign_in": _("Sign up or sign in to talk about a dream with the dream guide. It takes a minute."), "ask": _("Would you like to tell me a dream?")}
	return {"title": _("Pandit ji"), "subtitle": _("AI guide · Rudraksha, gemstones and poojas"), "who": _("Pandit ji"), "placeholder": _("Ask Pandit ji"), "route": "pandit-ji",
			"resting": _("Pandit ji is resting. Please come back a little later."), "notice": _("AI guide. I explain from our Academy and can't predict or promise results."),
			"sign_in": _("Sign up or sign in to ask Pandit ji, our AI guide to Rudraksha, gemstones and poojas. It takes a minute, and booking and buying need an account too."), "ask": _("What would you like to know?")}


def _frame(blueprint: str | None = None) -> dict:
	w = _words(blueprint)
	return {"title": w["title"], "subtitle": w["subtitle"], "avatar": "/files/astrohq-icon.svg", "send_word": _("Send"), "new_chat_word": _("New chat")}


def _blueprint_of(args: dict) -> str:
	"""Which agent a card asks for: only the site's own agents (the card's fixed argument `agent`); anything else is Pandit ji."""
	return args.get("agent") if args.get("agent") in agents.AGENTS else agents.BLUEPRINT


@frappe.whitelist(allow_guest=True, methods=["POST"])
def info(**args) -> dict:
	"""A guest gets the sign-up conversation (or, with none, a button to sign in). A signed-in person gets the agent's name and words. If the agent is switched off the card says so and draws no chat."""
	blueprint = _blueprint_of(args)
	w = _words(blueprint)
	if not frappe.db.get_value("Blueprint Reference", blueprint, "is_active"):
		return {"notice": w["resting"]}
	if frappe.session.user == "Guest":
		gate = _gate(blueprint)
		if gate:
			return {**_frame(blueprint), "gate": gate, "placeholder": _("Type your answer"), "notice": w["notice"]}
		return {"sign_in": {"message": w["sign_in"], "label": _("Sign up or sign in"), "href": "/login?redirect-to=/ask/" + w["route"]}}
	name = (frappe.db.get_value("User", frappe.session.user, "first_name") or "").strip()
	return {
		**_frame(blueprint), "blueprint": blueprint,
		"welcome": (_("Hi {0}, I'm {1}. ").format(name, w["who"]) if name else _("Hi, I'm {0}. ").format(w["who"])) + w["ask"],
		"placeholder": w["placeholder"], "notice": w["notice"],
		"talk": False,  # no talk mode: the guide is text only (owner, 2026-11-09)
	}


def guide() -> dict:
	"""The site's guide, the round button on every page (websitehq's windows, hook rfhq_window_guide): where it opens, who it is, and the pages where it would only be in the way (the guide's own page, the sign-in)."""
	from raftor_astrohq import ai_guides

	pages = ["/" + row["page"].strip("/") for row in ai_guides.rows()]  # the AI guides' chats open in the same drawer from their cards (data: ai_guides.json)
	return {"url": "/ask/pandit-ji", "title": _("Pandit ji"), "label": _("Ask Pandit ji"), "icon": "/files/astrohq-icon.svg", "hide_on": ["/login", "/signup", "/ask/pandit-ji", *pages], "pages": pages}
