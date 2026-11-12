"""The reminders a person kept in AstroHQ (Astro Reminder) move to servicehq's Day Reminder, whose rule is the vertical's own words (the lists of tithis, days and special days); the old records, their log and the
old message are removed. A site that never had any reminders has nothing to move."""
import json

import frappe

OLD, OLD_SENT = "Astro Reminder", "Astro Reminder Sent"


def _parts(value) -> list[str]:
	return [p.strip() for p in str(value or "").split(",") if p.strip()]


def execute():
	if frappe.db.table_exists(OLD) and frappe.db.exists("DocType", "Day Reminder"):
		for row in frappe.db.sql(f"select * from `tab{OLD}`", as_dict=True):
			rule = {"tithi": _parts(row.get("tithi")), "paksha": row.get("paksha") or "Both", "weekday": _parts(row.get("weekday")), "special": _parts(row.get("special"))}
			text = json.dumps(rule, sort_keys=True, ensure_ascii=False)
			lead = row.get("lead") or "Evening before"
			if not frappe.db.exists("Day Reminder", {"user": row.get("user"), "kind": "astrohq", "rule": text, "lead": lead}):
				frappe.get_doc({"doctype": "Day Reminder", "user": row.get("user"), "kind": "astrohq", "rule": text, "lead": lead, "enabled": row.get("enabled", 1)}).insert(ignore_permissions=True)
	for name in frappe.get_all("Notification", filters={"rfhq_event": "astro.reminder"}, pluck="name") if frappe.db.has_column("Notification", "rfhq_event") else []:
		frappe.delete_doc("Notification", name, ignore_permissions=True, force=True)
	for doctype in (OLD, OLD_SENT):
		if frappe.db.exists("DocType", doctype):
			try:
				frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True)
			except Exception:
				frappe.db.sql("delete from `tabDocType` where name=%s", doctype)
		frappe.db.sql_ddl(f"drop table if exists `tab{doctype}`")
