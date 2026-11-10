"""Pandit ji, the AI guide that answers customers from the Academy and points them to products and services.

What it may reach is fixed here, in one place: its site user, the role that user has, the few records the role may read, and the tools the tool server lets it call.
The agent's own definition (persona, rules) is a blueprint file in the agent factory; this is the site's side of it.
"""

import frappe

ROLE = "Pandit Ji Agent"
USER = "pandit-ji-agent@agents.astrohq.in"
BLUEPRINT = "pandit_ji"
TOOLS = ["search_webshop_products", "get_webshop_product", "find_services", "get_service", "search_knowledge", "get_family_member", "make_report"]  # read-only, or free: the agent never books or charges, it hands the customer to the booking page
READS = {doctype: ["read"] for doctype in ("Website Item", "Item", "Item Price", "Item Group", "Brand", "Price List", "Pricing Rule", "Website Item Group")}


# The numerology guide (classical numerology, from the Academy's Numerology series; the numbers come from the engine through calculate_numerology). Same kind of agent, its own user and its own tools.
NUMEROLOGIST = {"role": "Numerology Guide Agent", "user": "numerology-guide-agent@agents.astrohq.in", "blueprint": "numerologist", "title": "Numerology guide (AI)",
				"tools": ["search_knowledge", "calculate_numerology", "find_services", "get_service", "search_webshop_products", "get_webshop_product", "get_family_member", "make_report"], "reads": READS}
# The dream guide (dreams read as personal stories, from the Academy's Dreams series; each source labelled). Its tools: the Academy search and the person's own family profiles.
DREAM_GUIDE = {"role": "Dream Guide Agent", "user": "dream-guide-agent@agents.astrohq.in", "blueprint": "dream_guide", "title": "Dream guide (AI)", "tools": ["search_knowledge", "get_family_member"], "reads": {}}
AGENTS = {BLUEPRINT: {"role": ROLE, "user": USER, "blueprint": BLUEPRINT, "title": "Pandit ji (AI guide)", "tools": TOOLS, "reads": READS}, NUMEROLOGIST["blueprint"]: NUMEROLOGIST, DREAM_GUIDE["blueprint"]: DREAM_GUIDE}


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
										  (DREAM_GUIDE["blueprint"], DREAM_GUIDE["title"], "Explores a dream as a personal story from the Academy's Dreams series, each source labelled. Read-only; never predicts, books or charges.")):
		if frappe.db.exists("Blueprint Reference", blueprint):
			continue
		frappe.get_doc({"doctype": "Blueprint Reference", "blueprint_id": blueprint, "title": title, "is_active": 1, "is_public": 0, "agent_role": "Customer",
						"lifecycle_mode": "persistent", "description": description}).insert(ignore_permissions=True)
