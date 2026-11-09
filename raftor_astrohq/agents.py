"""Pandit ji, the AI guide that answers customers from the Academy and points them to products and services.

What it may reach is fixed here, in one place: its site user, the role that user has, the few records the role may read, and the tools the tool server lets it call.
The agent's own definition (persona, rules) is a blueprint file in the agent factory; this is the site's side of it.
"""

import frappe

ROLE = "Pandit Ji Agent"
USER = "pandit-ji-agent@agents.astrohq.in"
TOOLS = ["search_webshop_products", "get_webshop_product", "search_knowledge"]  # read-only; services and booking tools join this list when they exist
READS = {doctype: ["read"] for doctype in ("Website Item", "Item", "Item Price", "Item Group", "Brand", "Price List", "Pricing Rule", "Website Item Group")}


def ensure_access() -> None:
	"""Makes the user, role and tool limits when the agent app and its tool server are both on this site. Safe to repeat."""
	if "raftor_agentshq" not in frappe.get_installed_apps():
		return
	from raftor_agentshq import access

	access.ensure_agent_access(ROLE, USER, TOOLS, READS)
