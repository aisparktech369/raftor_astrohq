"""AstroHQ's pages, described for websitehq to draw (see raftor_websitehq/website_hq/app_pages.py).
Only wording and structure live here: no HTML, CSS or JavaScript."""
import frappe
from frappe import _

from raftor_astrohq import profiles

API = "raftor_astrohq.api."
LIST_PAGE = "/birth-profiles"
ONBOARDING_STEPS = ("Account", "PIN", "Birth details")


def _time_fields():
	return [
		{"name": "time_of_birth", "label": _("Time of birth"), "type": "time_text", "placeholder": "HH:MM",
		 "hint": _("24-hour, as on your birth record."), "disabled_when": "time_unknown"},
		{"name": "time_unknown", "label": _("I don't know my birth time"), "type": "checkbox"},
	]


def _you_fields():
	return [
		{"name": "full_name", "label": _("Full name"), "required": True, "placeholder": _("e.g. Asha Rao"), "hint": _("Shown on your chart.")},
		{"name": "date_of_birth", "label": _("Date of birth"), "type": "date", "required": True},
		*_time_fields(),
		{"name": "place_of_birth", "label": _("Place of birth"), "required": True, "placeholder": _("Town or city, country")},
	]


def _person_fields():
	return [
		{"name": "relationship", "label": _("Relationship"), "type": "select", "required": True, "placeholder": _("Choose"),
		 "options": [r for r in profiles.relationships() if r != profiles.SELF]},
		{"name": "full_name", "label": _("Full name"), "required": True},
		{"name": "date_of_birth", "label": _("Date of birth"), "type": "date", "required": True},
		*_time_fields(),
		{"name": "place_of_birth", "label": _("Place of birth"), "required": True, "placeholder": _("Town or city, country")},
		{"name": "permission_given", "label": _("I have permission to keep this person's details"), "type": "checkbox", "required": True},
	]


def birth_details():
	"""Onboarding: the account holder's own details."""
	return {
		"title": _("Your birth details"),
		"blocks": [
			{"type": "stepper", "steps": [_(s) for s in ONBOARDING_STEPS], "current": 2},
			{"type": "heading", "text": _("Your birth details"), "subtitle": _("We use this to calculate your chart. You can add family members afterwards.")},
			{"type": "form", "id": "you", "load": API + "get_profile", "save": API + "save_profile",
			 "args": {"relationship": profiles.SELF}, "fields": _you_fields(), "submit_label": _("Save and continue"),
			 "success": {"redirect": "/birth-details/done"}},
			{"type": "text", "text": _("Your details are private and used only for your chart.")},
		],
	}


def birth_details_done():
	return {
		"title": _("You're all set"),
		"blocks": [
			{"type": "stepper", "steps": [_(s) for s in ONBOARDING_STEPS], "current": 3},
			{"type": "heading", "text": _("You're all set"), "subtitle": _("Your birth details are saved.")},
			{"type": "record_list", "id": "you", "source": API + "list_profiles", "args": {"who": "you"}},
			{"type": "actions", "links": [
				{"label": _("Add a family member"), "href": LIST_PAGE + "/new", "kind": "outline"},
				{"label": _("Continue"), "href": "/", "kind": "primary"},
			]},
		],
	}


def birth_profiles():
	return {
		"title": _("Birth profiles"),
		"blocks": [
			{"type": "heading", "text": _("Birth profiles"), "subtitle": _("Keep details for the people you care about, all under your one account.")},
			{"type": "record_list", "id": "profiles", "source": API + "list_profiles", "empty": _("No profiles yet."),
			 "add": {"label": _("Add a person"), "href": LIST_PAGE + "/new"}},
		],
	}


def new_person():
	return {
		"title": _("Add a person"),
		"blocks": [
			{"type": "heading", "text": _("Add a person"), "subtitle": _("Their details are private to your account.")},
			{"type": "form", "id": "person", "save": API + "save_profile", "fields": _person_fields(),
			 "submit_label": _("Save"), "cancel": {"label": _("Cancel"), "href": LIST_PAGE}, "success": {"redirect": LIST_PAGE}},
		],
	}


def edit_person():
	"""The account holder's own profile gets the short form; family members get the full one."""
	item_id = frappe.form_dict.get("id") or ""
	user_doc = frappe.get_doc("User", frappe.session.user) if frappe.session.user != "Guest" else None
	row = next((r for r in (user_doc.get(profiles.TABLE) or []) if r.name == item_id), None) if user_doc else None
	if user_doc and not row:
		raise frappe.DoesNotExistError
	is_self = bool(row) and row.relationship == profiles.SELF
	form = {"type": "form", "id": "you" if is_self else "person", "load": API + "get_profile", "save": API + "save_profile",
			"args": {"id": item_id, **({"relationship": profiles.SELF} if is_self else {})},
			"fields": _you_fields() if is_self else _person_fields(), "submit_label": _("Save"),
			"cancel": {"label": _("Cancel"), "href": LIST_PAGE}, "success": {"redirect": LIST_PAGE}}
	return {"title": _("Edit details"), "blocks": [{"type": "heading", "text": _("Your details") if is_self else _("Edit a person")}, form]}


# ---- Astrologer: the steps astrohq adds to servicehq's provider journey ----
ASTRO = "raftor_astrohq.astrologer_api."
PROVIDER_STEPS = ("Account", "Profile", "Astrologer details", "Credentials", "Offering")


def astrologer_details():
	return {
		"title": _("Your astrologer details"),
		"blocks": [
			{"type": "stepper", "steps": [_(s) for s in PROVIDER_STEPS], "current": 2},
			{"type": "heading", "text": _("Your astrologer details"), "subtitle": _("Customers see this on your page.")},
			{"type": "form", "id": "astrologer", "load": ASTRO + "get_details", "save": ASTRO + "save_details",
			 "fields": [
				 {"name": "expertise", "label": _("Expertise"), "required": True, "placeholder": _("e.g. Vedic, Tarot, Numerology")},
				 {"name": "languages", "label": _("Languages"), "required": True, "placeholder": _("e.g. English, Hindi")},
				 {"name": "years_of_practice", "label": _("Years of practice"), "required": True, "placeholder": "0"},
			 ], "submit_label": _("Save and continue"), "success": {"redirect": "/astrologer/credentials"}},
		],
	}


def astrologer_credentials():
	return {
		"title": _("Your credentials"),
		"blocks": [
			{"type": "stepper", "steps": [_(s) for s in PROVIDER_STEPS], "current": 3},
			{"type": "heading", "text": _("Your credentials"), "subtitle": _("Courses, certificates or lineage. Our team checks them to verify you.")},
			{"type": "record_list", "id": "credentials", "source": ASTRO + "list_credentials", "empty": _("No credentials added yet."),
			 "add": {"label": _("Add a credential"), "href": "/astrologer/credentials/new"}},
			{"type": "actions", "links": [{"label": _("Continue"), "href": "/provider", "kind": "primary"}]},
		],
	}


def astrologer_credential_new():
	return {
		"title": _("Add a credential"),
		"blocks": [
			{"type": "heading", "text": _("Add a credential")},
			{"type": "form", "id": "credential", "save": ASTRO + "add_credential",
			 "fields": [
				 {"name": "title", "label": _("Credential"), "required": True, "placeholder": _("e.g. Jyotish Visharad")},
				 {"name": "issued_by", "label": _("Issued by"), "placeholder": _("School or teacher")},
				 {"name": "year", "label": _("Year"), "placeholder": "YYYY"},
			 ], "submit_label": _("Save"), "cancel": {"label": _("Cancel"), "href": "/astrologer/credentials"},
			 "success": {"redirect": "/astrologer/credentials"}},
		],
	}

