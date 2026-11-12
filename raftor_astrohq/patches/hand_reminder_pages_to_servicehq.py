"""My reminders and Add a reminder are shipped by servicehq now: the pages astrohq made keep their records and only change hands, so that the page sync lets servicehq's definition take their place."""
import frappe


def execute():
	for route in ("my/reminders", "my/reminders/new"):
		name = frappe.db.get_value("Web Page", {"route": route, "rfhq_definition_owner": "raftor_astrohq"})
		if name:
			frappe.db.set_value("Web Page", name, {"rfhq_definition_owner": "raftor_servicehq", "rfhq_definition_hash": ""})
