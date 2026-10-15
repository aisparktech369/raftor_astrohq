"""The starting topics and wishes, as records staff can change in Desk (Guidance Topic, Blessing Wish). Only when there are none yet, so a list staff have edited is never put back."""
import frappe

TOPICS = ["Career", "Marriage", "Love", "Money", "Health", "Children", "Auspicious date"]
WISHES = ["Prosperity", "Health", "Family", "Protection", "Peace", "Success"]


def execute():
	frappe.reload_doc("raftor_astro_hq", "doctype", "guidance_topic")
	frappe.reload_doc("raftor_astro_hq", "doctype", "blessing_wish")
	for doctype, field, names in (("Guidance Topic", "topic_name", TOPICS), ("Blessing Wish", "wish_name", WISHES)):
		if frappe.db.count(doctype):
			continue
		for n, name in enumerate(names, 1):
			frappe.get_doc({"doctype": doctype, field: name, "enabled": 1, "sequence": n * 10}).insert(ignore_permissions=True)
