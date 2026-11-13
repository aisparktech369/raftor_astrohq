"""Where a person lands after signing in when nothing else sends them (no page they were on, no report to open, no onboarding step): their dashboard."""
import frappe


def default_home(user: str) -> str:
	return "/my" if frappe.db.get_value("User", user, "user_type") == "Website User" else ""
