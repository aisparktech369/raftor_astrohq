"""What the App Chat Card draws for the AI guide: which agent it is, every word, and what a signed-out visitor goes through first (card_methods: the card holds no wording of its own).

A visitor who is not signed in meets the agent's sign-up conversation, which its blueprint declares (the factory's `gate`, with defaults for any agent that needs a signed-in user); the card plays it
and uses the site's own code sign-in. A signed-in person gets the chat."""
from urllib.parse import quote

import frappe
from frappe import _

from raftor_astrohq import agents


def _gate(blueprint: str | None = None):
	"""The blueprint's sign-up conversation as plain words, or None when the agent is open to everyone or AgentsHQ is not here."""
	try:
		from raftor_agentshq import agent_info
	except ImportError:
		return None
	return agent_info.gate(blueprint or agents.BLUEPRINT)


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
	if blueprint == agents.TAROT["blueprint"]:
		return {"title": _("Tarot guide"), "subtitle": _("AI guide · tarot"), "who": _("the tarot guide"), "placeholder": _("Tell me what is on your mind"), "route": "guide",
				"resting": _("The tarot guide is resting. Please come back a little later."), "notice": _("AI guide. I read the cards as a way to reflect. I can't predict anything or advise on health, money or the law."),
				"sign_in": _("Sign up or sign in to have a tarot reading with the tarot guide. It takes a minute."), "ask": _("What would you like to look at with the cards today?")}
	if blueprint == agents.VEDIC["blueprint"]:
		return {"title": _("Vedic astrologer guide"), "subtitle": _("AI guide · Vedic chart"), "who": _("the Vedic astrologer guide"), "placeholder": _("Ask about a chart"), "route": "vedic-astrologer",
				"resting": _("The Vedic astrologer guide is resting. Please come back a little later."), "notice": _("AI guide. I explain what a chart shows. I can't predict anything or advise on health, money or marriage."),
				"sign_in": _("Sign up or sign in to talk about a chart with the Vedic astrologer guide. It takes a minute."), "ask": _("Whose chart would you like to look at: yours, or someone you have saved?")}
	if blueprint == agents.KP["blueprint"]:
		return {"title": _("KP astrologer guide"), "subtitle": _("AI guide · KP chart"), "who": _("the KP astrologer guide"), "placeholder": _("Ask about a KP chart"), "route": "kp-astrologer",
				"resting": _("The KP astrologer guide is resting. Please come back a little later."), "notice": _("AI guide. I explain what a KP chart shows. I can't predict anything or advise on health, money or marriage."),
				"sign_in": _("Sign up or sign in to talk about a KP chart with the KP astrologer guide. It takes a minute."), "ask": _("Whose chart would you like to look at: yours, or someone you have saved?")}
	return {"title": _("Pandit ji"), "subtitle": _("AI guide · Rudraksha, gemstones and poojas"), "who": _("Pandit ji"), "placeholder": _("Ask Pandit ji"), "route": "pandit-ji",
			"resting": _("Pandit ji is resting. Please come back a little later."), "notice": _("AI guide. I explain from our Academy and can't predict or promise results."),
			"sign_in": _("Sign up or sign in to ask Pandit ji, our AI guide to Rudraksha, gemstones and poojas. It takes a minute, and booking and buying need an account too."), "ask": _("What would you like to know?")}


def _persona(args: dict):
	"""One of the guides of an area, when the page asks for it by name (?persona=kavya): only an enabled guide of one of the site's own agents; anything else is the area's own guide."""
	slug = (args.get("persona") or "").strip()[:80]
	row = frappe.db.get_value("AI Guide Persona", {"slug": slug, "enabled": 1}, ["slug", "guide_name", "area", "tagline", "greeting", "ai_image"], as_dict=True) if slug else None
	from raftor_astrohq import ai_guides

	return row if row and row.area in agents.AGENTS and ai_guides.is_on(row.slug) else None


def _frame(blueprint: str | None = None, persona=None) -> dict:
	w = _words(blueprint)
	if persona:
		photo = frappe.db.get_value("Provider", persona.slug, "photo") or "/files/astrohq-icon.svg"
		sub = _("AI guide") + (" · " + persona.tagline if persona.tagline else "") + (" · " + _("AI-made picture") if persona.ai_image else "")
		return {"title": persona.guide_name, "subtitle": sub, "avatar": photo, "send_word": _("Send"), "new_chat_word": _("New chat")}
	return {"title": w["title"], "subtitle": w["subtitle"], "avatar": "/files/astrohq-icon.svg", "send_word": _("Send"), "new_chat_word": _("New chat")}


def _blueprint_of(args: dict) -> str:
	"""Which agent a card asks for: only the site's own agents (the card's fixed argument `agent`); anything else is Pandit ji."""
	return args.get("agent") if args.get("agent") in agents.AGENTS else agents.BLUEPRINT


@frappe.whitelist(allow_guest=True, methods=["POST"])
def info(**args) -> dict:
	"""A guest gets the sign-up conversation (or, with none, a button to sign in). A signed-in person gets the agent's name and words. If the agent is switched off the card says so and draws no chat."""
	persona = _persona(args)
	blueprint = persona.area if persona else _blueprint_of(args)
	w = _words(blueprint)
	if persona:
		w = {**w, "who": persona.guide_name, "placeholder": _("Ask {0}").format(persona.guide_name), "route": "guide?persona=" + persona.slug, "ask": persona.greeting or w["ask"],
			 "resting": _("{0} is resting. Please come back a little later.").format(persona.guide_name), "sign_in": _("Sign up or sign in to talk to {0}. It takes a minute.").format(persona.guide_name)}
	if not frappe.db.get_value("Blueprint Reference", blueprint, "is_active"):
		return {"notice": w["resting"]}
	if frappe.session.user == "Guest":
		gate = _gate(blueprint)
		if gate:
			return {**_frame(blueprint, persona), "gate": gate, "placeholder": _("Type your answer"), "notice": w["notice"]}
		return {"sign_in": {"message": w["sign_in"], "label": _("Sign up or sign in"), "href": "/login?redirect-to=" + quote("/ask/" + w["route"], safe="/")}}
	name = (frappe.db.get_value("User", frappe.session.user, "first_name") or "").strip()
	return {
		**_frame(blueprint, persona), "blueprint": blueprint, **({"persona": persona.slug} if persona else {}),
		"welcome": (_("Hi {0}, I'm {1}. ").format(name, w["who"]) if name else _("Hi, I'm {0}. ").format(w["who"])) + w["ask"],
		"placeholder": w["placeholder"], "notice": w["notice"],
		"talk": False,  # no talk mode: the guide is text only (owner, 2026-11-09)
	}


def guide() -> dict:
	"""The site's guide, the round button on every page (websitehq's windows, hook rfhq_window_guide): where it opens, who it is, and the pages where it would only be in the way (the guide's own page, the sign-in)."""
	from raftor_astrohq import ai_guides

	pages = ["/" + row["page"].strip("/") for row in ai_guides.rows()]  # the AI guides' chats open in the same drawer from their cards (data: ai_guides.json)
	return {"url": "/ask/pandit-ji", "title": _("Pandit ji"), "label": _("Ask Pandit ji"), "icon": "/files/astrohq-icon.svg", "hide_on": ["/login", "/signup", "/ask/pandit-ji", "/ask/guide", *pages], "pages": pages}
