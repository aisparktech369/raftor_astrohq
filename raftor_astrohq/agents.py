"""Pandit ji, the AI guide that answers customers from the Academy and points them to products and services.

What it may reach is fixed here, in one place: its site user, the role that user has, the few records the role may read, and the tools the tool server lets it call.
The agent's own definition (persona, rules) is a blueprint file in the agent factory; this is the site's side of it.
"""

import frappe

ROLE = "Pandit Ji Agent"
USER = "pandit-ji-agent@agents.astrohq.in"
BLUEPRINT = "pandit_ji"
TOOLS = ["search_webshop_products", "get_webshop_product", "find_services", "get_service", "search_knowledge", "get_family_member", "get_report"]  # read-only, or free: the agent never books or charges, it hands the customer to the booking page
READS = {doctype: ["read"] for doctype in ("Website Item", "Item", "Item Price", "Item Group", "Brand", "Price List", "Pricing Rule", "Website Item Group")}


# The numerology guide (classical numerology, from the Academy's Numerology series; the numbers come from the engine through calculate_numerology). Same kind of agent, its own user and its own tools.
# The reports each guide may open and speak from (its own area): the numerologist reads numerology, Pandit ji (who routes to stones, Rudraksha and poojas, which come from a chart and a number) reads both, the dream guide none.
REPORT_AREAS = {"pandit_ji": ["kundli", "numerology"], "numerologist": ["numerology"], "dream_guide": [], "tarot": [], "vedic_astrologer": ["kundli", "match"], "kp_astrologer": ["kp", "match"]}
# What of the person's record each guide is shown: `notes` are the kinds of note it reads (None = all), `card` is how much of the person's details it sees ("full", or "names": only who is in the family, no birth details,
# reports or purchases). The dream guide keeps to the earlier dream talks and nothing else about the person (owner, 2026-11-10).
READS_OF_PERSON = {"pandit_ji": {"notes": None, "card": "full"}, "numerologist": {"notes": None, "card": "full"}, "dream_guide": {"notes": ["dream"], "card": "names"},
				   "tarot": {"notes": ["tarot"], "card": "names"},
				   "vedic_astrologer": {"notes": None, "card": "full"}, "kp_astrologer": {"notes": None, "card": "full"}}  # the tarot guide (owner, 2026-11-10: all the tarot notes, and only those); the key is its blueprint id

NUMEROLOGIST = {"role": "Numerology Guide Agent", "user": "numerology-guide-agent@agents.astrohq.in", "blueprint": "numerologist", "title": "Numerology guide (AI)",
				"tools": ["search_knowledge", "calculate_numerology", "find_services", "get_service", "search_webshop_products", "get_webshop_product", "get_family_member", "get_report"], "reads": READS}
# The dream guide (dreams read as personal stories, from the Academy's Dreams series; each source labelled). Its tools: the Academy search and the person's own family profiles.
DREAM_GUIDE = {"role": "Dream Guide Agent", "user": "dream-guide-agent@agents.astrohq.in", "blueprint": "dream_guide", "title": "Dream guide (AI)", "tools": ["search_knowledge", "get_family_member"], "reads": {}}
# The tarot guide (a tarot reading conducted in the Academy's own methodology: it draws the cards with its three tools, one at a time, and the Academy's words say what each card and spread mean and how a session is conducted).
# Its tools: the Academy search, the three tarot session tools, the services, and the person's own family profiles. It reads no records of the site's (the session tools keep their own), and no reports.
TAROT = {"role": "Tarot Guide Agent", "user": "tarot-guide-agent@agents.astrohq.in", "blueprint": "tarot", "title": "Tarot guide (AI)",
		 "tools": ["search_knowledge", "start_tarot_session", "deal_tarot_card", "get_tarot_session", "find_services", "get_service", "get_family_member"], "reads": {}}
# The two astrologer guides (a chart read from the engine's answer for a saved profile: the Vedic kundli, or the chart the Krishnamurti way, and the ashtakoota match of two saved people). They explain what the chart shows and
# never predict; there is no Academy knowledge for them yet, so they speak from the report only. Their tools: the person's own profiles, the reports of their own area, the services (to hand over to a live astrologer) and the Academy search.
VEDIC = {"role": "Vedic Astrologer Guide Agent", "user": "vedic-astrologer-guide-agent@agents.astrohq.in", "blueprint": "vedic_astrologer", "title": "Vedic astrologer guide (AI)",
		 "tools": ["search_knowledge", "get_family_member", "get_report", "add_profile", "find_services", "get_service"], "reads": {}}
KP = {"role": "KP Astrologer Guide Agent", "user": "kp-astrologer-guide-agent@agents.astrohq.in", "blueprint": "kp_astrologer", "title": "KP astrologer guide (AI)",
	  "tools": ["search_knowledge", "get_family_member", "get_report", "add_profile", "find_services", "get_service"], "reads": {}}
# A guide's record is made switched ON, except one whose keys to the tool server are not made yet: its record is made OFF, and staff switch it on (Blueprint Reference, Desk) when they are.
SWITCHED_OFF_AT_FIRST = {"tarot", "vedic_astrologer", "kp_astrologer"}
AGENTS = {BLUEPRINT: {"role": ROLE, "user": USER, "blueprint": BLUEPRINT, "title": "Pandit ji (AI guide)", "tools": TOOLS, "reads": READS}, NUMEROLOGIST["blueprint"]: NUMEROLOGIST, DREAM_GUIDE["blueprint"]: DREAM_GUIDE, TAROT["blueprint"]: TAROT,
		  VEDIC["blueprint"]: VEDIC, KP["blueprint"]: KP}


def ensure_access() -> None:
	"""Makes the user, role and tool limits of each agent when the agent app and its tool server are both on this site. Safe to repeat."""
	if "raftor_agentshq" not in frappe.get_installed_apps():
		return
	from raftor_agentshq import access

	for agent in AGENTS.values():
		access.ensure_agent_access(agent["role"], agent["user"], agent["tools"], agent["reads"])
	ensure_blueprint()


def ensure_blueprint() -> None:
	"""The agent's record on the site: it is switched on here, and a signed-in customer (role Customer) may talk to it. Its definition is the factory's blueprint file `pandit_ji`; no blueprint
	type is set, so the site never writes a copy of that file over the pinned one. Nothing is changed on a record that exists, so a switch or a role staff have set stays."""
	for blueprint, title, description in ((BLUEPRINT, "Pandit ji (AI guide)", "Answers from the Academy and points to products and services. Read-only; never books or charges."),
										  (NUMEROLOGIST["blueprint"], NUMEROLOGIST["title"], "Explains numerology from the Academy, with the numbers worked out by the engine. Read-only; never books or charges."),
										  (DREAM_GUIDE["blueprint"], DREAM_GUIDE["title"], "Explores a dream as a personal story from the Academy's Dreams series, each source labelled. Read-only; never predicts, books or charges."),
										  (TAROT["blueprint"], TAROT["title"], "Conducts a tarot reading in the Academy's methodology, drawing the cards one at a time with its tools. A way to reflect, never a forecast; never books or charges."),
										  (VEDIC["blueprint"], VEDIC["title"], "Explains a person's Vedic chart (kundli) and the match of two saved people from the engine's answer. Never predicts, books or charges."),
										  (KP["blueprint"], KP["title"], "Explains a person's chart the KP way (cusps, star and sub lords) and the match of two saved people from the engine's answer. Never predicts, books or charges.")):
		if frappe.db.exists("Blueprint Reference", blueprint):
			continue
		frappe.get_doc({"doctype": "Blueprint Reference", "blueprint_id": blueprint, "title": title, "is_active": 0 if blueprint in SWITCHED_OFF_AT_FIRST else 1, "is_public": 0, "agent_role": "Customer",
						"lifecycle_mode": "persistent", "description": description}).insert(ignore_permissions=True)


def report_areas(agent_user: str) -> list[str]:
	"""The reports the guide signed in as this site user may read: its own area, nothing else (a person's kundli is not the numerologist's to read, and the other way round)."""
	for agent in AGENTS.values():
		if agent["user"] == agent_user:
			return list(REPORT_AREAS.get(agent["blueprint"], []))
	return []


def reads_of(blueprint: str) -> dict:
	"""What of the person's record this guide is shown (see READS_OF_PERSON); an unknown guide is shown nothing."""
	return READS_OF_PERSON.get(blueprint, {"notes": [], "card": "none"})


def blueprint_of_user(agent_user: str) -> str:
	for agent in AGENTS.values():
		if agent["user"] == agent_user:
			return agent["blueprint"]
	return ""
