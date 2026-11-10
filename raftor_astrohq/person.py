"""What the site knows of a person, for the AI guides (hook `agent_person_context`, read by AgentsHQ at the start of every turn): their saved birth profiles, the reports they have made, what they bought and
what they booked. Short lines in plain words; only the person's own records. The guides get this beside the notes they have kept from earlier chats, so a person is known as one person across every guide."""
import frappe
from frappe.utils import formatdate

LAST = 3


def _profiles(user: str) -> list[str]:
	from raftor_astrohq import profiles

	out = []
	for row in frappe.get_all("Astro Birth Profile", filters={"parent": user, "parenttype": "User", "parentfield": profiles.TABLE}, fields=["relationship", "full_name", "date_of_birth", "time_of_birth", "time_unknown", "place_of_birth", "permission_given"], order_by="idx"):
		if row.relationship != profiles.SELF and not row.permission_given:
			continue
		born = formatdate(row.date_of_birth, "d MMM yyyy") if row.date_of_birth else "birth date not given"
		clock = "birth time not known" if row.time_unknown else (f"at {row.time_of_birth}" if row.time_of_birth else "birth time not given")
		place = f", {row.place_of_birth}" if row.place_of_birth else ""
		who = row.relationship if row.relationship == profiles.SELF else f"{row.full_name} ({row.relationship.lower()})"
		out.append(f"- Profile {who}: {row.full_name}, born {born}, {clock}{place}")
	return out


def _reports(user: str) -> list[str]:
	rows = frappe.get_all("Astro Answer", filters={"user": user}, fields=["mode", "made_on"], order_by="made_on desc", limit=LAST)
	return [f"- Saved report ({r.mode.replace('_', ' ').title()}) made on {formatdate(r.made_on, 'd MMM yyyy')}" for r in rows]


def _customer(user: str) -> str:
	return (frappe.db.get_value("Portal User", {"user": user, "parenttype": "Customer"}, "parent") or frappe.db.get_value("Customer", {"email_id": user}, "name") or "")


def _orders(user: str) -> list[str]:
	customer = _customer(user)
	if not customer:
		return []
	out = []
	for order in frappe.get_all("Sales Order", filters={"customer": customer, "docstatus": 1}, fields=["name", "transaction_date"], order_by="transaction_date desc", limit=LAST):
		items = frappe.get_all("Sales Order Item", filters={"parent": order.name}, pluck="item_name", limit=3)
		out.append(f"- Bought on {formatdate(order.transaction_date, 'd MMM yyyy')}: {', '.join(items)}")
	return out


def _bookings(user: str) -> list[str]:
	if not frappe.db.exists("DocType", "Booking"):
		return []
	rows = frappe.get_all("Booking", filters={"customer_user": user}, fields=["offering", "slot_start", "workflow_state"], order_by="creation desc", limit=LAST)
	def name(offering):
		return (frappe.db.get_value("Item", offering, "item_name") if offering and frappe.db.exists("Item", offering) else offering) or "a session"

	return [f"- Booked {name(r.offering)}{' on ' + formatdate(r.slot_start, 'd MMM yyyy') if r.slot_start else ''} ({(r.workflow_state or '').lower()})" for r in rows]


def context(user: str) -> str:
	"""The person's card: '' when the site knows nothing of them yet."""
	lines = []
	for part in (_profiles, _reports, _orders, _bookings):
		try:
			lines += part(user)
		except Exception:
			frappe.log_error(title=f"person card: {part.__name__}")
	return "\n".join(lines)
