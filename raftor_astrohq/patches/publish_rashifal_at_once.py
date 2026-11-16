"""The daily rashifal is shown as soon as it is written (the owner's choice, 2026-11-15: nobody was publishing the Drafts, so the cards were empty). A site made before keeps the old
switch (off): turn it on once. Staff can turn it off again in Daily Rashifal Settings; this patch runs only once."""
import frappe


def execute():
	if frappe.db.exists("DocType", "Daily Rashifal Settings"):
		frappe.db.set_single_value("Daily Rashifal Settings", "publish_at_once", 1)
