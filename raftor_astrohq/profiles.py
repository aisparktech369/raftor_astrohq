"""Birth profiles on the existing User: the account holder ("You") and any family members.

Each person is a row of the "Birth Profiles" table on the User. The table is the only place birth
details live; Frappe's own Birth Date and name are left alone. The same rules run when a person saves
on the website (api.py) and whenever a User is saved anywhere (validate_user), so they always agree.

The birth time is plain text on purpose: Frappe fills every empty Time field with the current time,
which would invent a birth time.
"""
import re

import frappe
from frappe import _
from frappe.utils import getdate, nowtime, today

SELF = "You"
TABLE = "astro_birth_profiles"
TIME = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")
TEXT = ("full_name", "time_of_birth", "place_of_birth")

CUSTOM_FIELDS = {
	"User": [
		{
			"fieldname": TABLE,
			"label": "Birth Profiles",
			"fieldtype": "Table",
			"options": "Astro Birth Profile",
			"insert_after": "bio",
			"description": "Birth details for this person and, if they wish, their family. Managed on the website.",
		}
	]
}


def ensure_fields() -> None:
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(CUSTOM_FIELDS, update=True)


def relationships() -> list[str]:
	"""The choices, read from the table's own field so an admin can change them in Customize Form."""
	options = frappe.get_meta("Astro Birth Profile").get_field("relationship").options or ""
	return [o for o in options.split("\n") if o]


def clean(values: dict) -> dict:
	"""Trimmed, with the time in 24-hour HH:MM form. Does not judge; row_errors does."""
	out = {k: (values.get(k) or "") for k in ("relationship", "full_name", "date_of_birth", "time_of_birth", "place_of_birth")}
	for key in TEXT:
		out[key] = str(out[key]).strip()
	out["relationship"] = str(out["relationship"]).strip()
	out["date_of_birth"] = str(out["date_of_birth"] or "").strip()
	out["time_unknown"] = 1 if values.get("time_unknown") in (1, True, "1", "true") else 0
	out["permission_given"] = 1 if values.get("permission_given") in (1, True, "1", "true") else 0
	match = TIME.match(out["time_of_birth"])
	if match:
		out["time_of_birth"] = f"{int(match.group(1)):02d}:{match.group(2)}" + (f":{match.group(3)}" if match.group(3) else "")
	return out


def row_errors(values: dict) -> dict[str, str]:
	"""{field: message} for everything wrong with one person's details; empty when fine."""
	v, errors = clean(values), {}
	is_self = v["relationship"] == SELF
	if v["relationship"] not in relationships():
		errors["relationship"] = _("Choose how this person is related to you.")
	if len(v["full_name"]) < 2:
		errors["full_name"] = _("Enter the full name.")

	born = None
	if not v["date_of_birth"]:
		errors["date_of_birth"] = _("Enter the date of birth.")
	else:
		try:
			born = getdate(v["date_of_birth"])
		except Exception:
			errors["date_of_birth"] = _("Enter a valid date of birth.")
	if born and born > getdate(today()):
		errors["date_of_birth"] = _("Date of birth cannot be in the future.")

	time = v["time_of_birth"]
	if time and v["time_unknown"]:
		errors["time_of_birth"] = _("Give a time or tick the box, not both.")
	elif time:
		m = TIME.match(time)
		if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59 or int(m.group(3) or 0) > 59:
			errors["time_of_birth"] = _("Enter a 24-hour time such as 06:42.")
		elif born and born == getdate(today()) and time > nowtime()[: len(time)]:
			errors["time_of_birth"] = _("Time of birth cannot be in the future.")
	elif not v["time_unknown"]:
		errors["time_of_birth"] = _("Enter the time of birth, or tick that you do not know it.")

	if len(v["place_of_birth"]) < 2:
		errors["place_of_birth"] = _("Enter the place of birth.")
	if not is_self and not v["permission_given"]:
		errors["permission_given"] = _("Please confirm you have permission to keep this person's details.")
	return errors


def row_values(row) -> dict:
	"""A table row (or dict) as plain values for a web form."""
	get = row.get if hasattr(row, "get") else (lambda k: getattr(row, k, None))
	return {
		"relationship": get("relationship") or "",
		"full_name": get("full_name") or "",
		"date_of_birth": str(get("date_of_birth") or ""),
		"time_of_birth": get("time_of_birth") or "",
		"time_unknown": int(get("time_unknown") or 0),
		"place_of_birth": get("place_of_birth") or "",
		"permission_given": int(get("permission_given") or 0),
	}


def validate_user(doc, method=None) -> None:
	"""User.validate: applies the rules to every birth profile, whoever is saving and from wherever."""
	rows = doc.get(TABLE) or []
	if not rows:
		return
	if sum(1 for r in rows if r.relationship == SELF) > 1:
		frappe.throw(_("There can be only one profile marked \"{0}\".").format(SELF))
	for index, row in enumerate(rows, start=1):
		errors = row_errors(row_values(row))
		if errors:
			frappe.throw(_("Birth profile {0}: {1}").format(index, next(iter(errors.values()))))
		cleaned = clean(row_values(row))
		for key in TEXT:
			row.set(key, cleaned[key])
		row.time_unknown = cleaned["time_unknown"]
		row.permission_given = cleaned["permission_given"]


def you_row(user_doc):
	return next((r for r in (user_doc.get(TABLE) or []) if r.relationship == SELF), None)


def birth_details_complete(application) -> bool:
	"""Onboarding completion check: the applicant's own ("You") profile is filled in correctly."""
	user_doc = frappe.get_doc("User", application.applicant_user)
	row = you_row(user_doc)
	return bool(row) and not row_errors(row_values(row))
