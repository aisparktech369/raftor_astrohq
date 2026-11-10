"""Website endpoints for birth profiles. Signed-in people only, and only ever their own rows.

These do not depend on Desk permissions: every call works on the caller's own User record, applies the
shared rules (profiles.py), and answers in the shapes websitehq's page kit expects."""
import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import formatdate

from raftor_astrohq import panchang, places, plans, profiles
from raftor_astrohq.journey import APP_KEY
from raftor_websitehq.website_hq.page_groups import page_url

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
	actions = [{"label": _("Edit"), "href": page_url("my", "birth-profiles/edit", id=row.name)}]
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
	items = [_item(r) for r in rows]
	if who != "you" and not any(r.relationship == profiles.SELF for r in rows):  # the account holder always has a place in the list, to fill in
		items.insert(0, {"id": "you", "title": frappe.utils.get_fullname(frappe.session.user), "badge": profiles.SELF, "lines": [_("Add your own date, time and place of birth.")],
						 "actions": [{"label": _("Add your details"), "href": page_url("my", "birth-profiles/you")}]})
	match = _match_card(rows) if who != "you" else None
	return {"items": items + ([match] if match else [])}


def _match_card(rows) -> dict | None:
	"""Once two people are saved, one more card on the list: check how well any two of them match (the free match making report, where each is chosen from the saved people)."""
	from raftor_servicehq import free_reports, links

	if len(rows) < 2:
		return None
	code = frappe.db.get_value("Item", {"custom_report_kind": "match"}, "name")
	if not code or not free_reports.on_sale(code):
		return None
	return {"id": "match", "title": _("Check compatibility"), "badge": _("Free"), "tone": "success", "lines": [_("Match any two of the people you have saved, by the eight kootas out of 36.")],
			"actions": [{"label": _("Match two people"), "href": links.free_report(code)}]}


@frappe.whitelist(methods=["POST"])
def get_profile(id=None, relationship=None):
	"""Values to prefill a form: the "You" profile, or one row by id. Empty for a new person."""
	user_doc = _user_doc()
	row = profiles.you_row(user_doc) if relationship == profiles.SELF else _find(user_doc, id)
	return {"values": profiles.row_values(row) if row else {}}


@frappe.whitelist(methods=["POST"])
def profile_form_fields(id=None):
	"""The edit form: the short one for the account holder's own profile, the full one for a family member, with their values filled in."""
	from raftor_astrohq.page_definitions import _person_fields, _you_fields

	row = _find(_user_doc(), id)
	if not row:
		frappe.throw(_("That profile was not found."), frappe.DoesNotExistError)
	is_self = row.relationship == profiles.SELF
	return {"title": _("Your details") if is_self else _("Edit a person"), "fields": _you_fields() if is_self else _person_fields(), "values": profiles.row_values(row)}


@frappe.whitelist(methods=["POST"])
def save_profile(id=None, values=None, relationship=None):
	"""Adds or changes one person. Rule problems come back per field, not as an error page."""
	user_doc = _user_doc()
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if relationship:  # the onboarding form fixes this to "You"
		values["relationship"] = relationship
	existing = _find(user_doc, id)
	if existing and existing.relationship == profiles.SELF and not values.get("relationship"):
		values["relationship"] = profiles.SELF  # the short form for the account holder has no relationship field
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

	if not row and not is_self and plans.family_room(frappe.session.user) < 1:  # the person's plan holds no more people
		return {"ok": False, "errors": {"full_name": plans.family_words(frappe.session.user)}}

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


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=panchang._per_visitor, seconds=60)
def place_options(query=None) -> list[dict]:
	"""For the place-of-birth box of a form (websitehq's lookup field): the towns that start with what was typed, as {"value", "label"}, the label being the town written the way the form reads it back
	("Pune, Maharashtra, India"). The towns are the astrology service's (places.suggest); the limit a visitor may ask at is the Panchang's town search's."""
	return [{"value": text, "label": text} for text in (f"{p['name']}, {p['region']}" for p in places.suggest(str(query or "")[:60], 8))]
