"""Website endpoints for birth profiles. Signed-in people only, and only ever their own rows.

These do not depend on Desk permissions: every call works on the caller's own User record, applies the
shared rules (profiles.py), and answers in the shapes websitehq's page kit expects."""
import frappe
from frappe import _
from frappe.utils import formatdate

from raftor_astrohq import profiles
from raftor_astrohq.journey import APP_KEY

EDIT_PAGE = "/birth-profiles/edit?id="
DELETE = "raftor_astrohq.api.delete_profile"


def _user_doc():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in first."), frappe.PermissionError)
	return frappe.get_doc("User", frappe.session.user)


def _rows(user_doc):
	return user_doc.get(profiles.TABLE) or []


def _find(user_doc, id):
	return next((r for r in _rows(user_doc) if r.name == id), None) if id else None


def _line(row) -> str:
	when = row.time_of_birth if row.time_of_birth else _("time not known")
	return f"{formatdate(row.date_of_birth, 'dd MMM yyyy')} · {when} · {row.place_of_birth}"


def _item(row) -> dict:
	actions = [{"label": _("Edit"), "href": EDIT_PAGE + row.name}]
	if row.relationship != profiles.SELF:
		actions.append({"label": _("Delete"), "kind": "danger", "call": DELETE, "args": {"id": row.name},
						"confirm": _("Delete {0}?").format(row.full_name), "confirm_label": _("Yes, delete")})
	return {"id": row.name, "title": row.full_name, "badge": row.relationship, "lines": [_line(row)], "actions": actions}


@frappe.whitelist(methods=["POST"])
def list_profiles(who=None):
	"""Cards for the caller's profiles, "You" first. who="you" returns only that one."""
	rows = sorted(_rows(_user_doc()), key=lambda r: (r.relationship != profiles.SELF, r.idx))
	if who == "you":
		rows = [r for r in rows if r.relationship == profiles.SELF]
	return {"items": [_item(r) for r in rows]}


@frappe.whitelist(methods=["POST"])
def get_profile(id=None, relationship=None):
	"""Values to prefill a form: the "You" profile, or one row by id. Empty for a new person."""
	user_doc = _user_doc()
	row = profiles.you_row(user_doc) if relationship == profiles.SELF else _find(user_doc, id)
	return {"values": profiles.row_values(row) if row else {}}


@frappe.whitelist(methods=["POST"])
def save_profile(id=None, values=None, relationship=None):
	"""Adds or changes one person. Rule problems come back per field, not as an error page."""
	user_doc = _user_doc()
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if relationship:  # the onboarding form fixes this to "You"
		values["relationship"] = relationship
	is_self = values.get("relationship") == profiles.SELF

	only_one = {"relationship": _("There can be only one profile marked \"{0}\".").format(profiles.SELF)}
	if is_self:
		row = profiles.you_row(user_doc)
		other = _find(user_doc, id)
		if other and other.relationship != profiles.SELF:
			return {"ok": False, "errors": only_one}  # a family member cannot be turned into "You"
	else:
		row = _find(user_doc, id)
		if id and not row:
			frappe.throw(_("That profile was not found."), frappe.DoesNotExistError)
		if row and row.relationship == profiles.SELF:
			return {"ok": False, "errors": only_one}  # "You" cannot be turned into a family member

	errors = profiles.row_errors(values)
	if errors:
		return {"ok": False, "errors": errors}

	data = profiles.clean(values)
	if row:
		row.update(data)
	else:
		user_doc.append(profiles.TABLE, data)
	user_doc.save(ignore_permissions=True)
	if is_self:
		_refresh_onboarding(frappe.session.user)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def delete_profile(id):
	"""Removes a family member. The "You" profile cannot be deleted."""
	user_doc = _user_doc()
	row = _find(user_doc, id)
	if not row:
		frappe.throw(_("That profile was not found."), frappe.DoesNotExistError)
	if row.relationship == profiles.SELF:
		frappe.throw(_("Your own profile cannot be deleted."), frappe.PermissionError)
	user_doc.remove(row)
	user_doc.save(ignore_permissions=True)
	return {"message": _("Deleted.")}


def _refresh_onboarding(user: str) -> None:
	"""Lets onboarding notice that the "You" profile is now complete, if this person has an open journey."""
	try:
		from raftor_onboardinghq.applications import open_applications, run_completion_checks
	except ImportError:
		return
	for name in open_applications(user, APP_KEY):
		run_completion_checks(name)
