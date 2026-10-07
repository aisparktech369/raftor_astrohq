"""AstroHQ's pages as data for websitehq to build (hook rfhq_page_definitions): which sections and cards, in what order, fed by which
endpoint. The endpoints and the rules stay in api.py, astrologer_api.py and profiles.py; no HTML, CSS or JavaScript here. Their look is the
site's. Addresses are `<group>/<page>`: a person's own birth details under `my`, the first-time steps under `onboarding`."""
import frappe
from frappe import _

from raftor_astrohq import profiles
from raftor_websitehq.website_hq.page_groups import page_url

API = "raftor_astrohq.api."
ASTRO = "raftor_astrohq.astrologer_api."
TIGHT = {"padding": "Small", "gap": "Small"}


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


def _my(page="", **query):
	return page_url("my", page, **query)


def _start(page="", **query):
	return page_url("onboarding", page, **query)


def _form(route, title, subtitle, form: dict, note: str = "", menu=None) -> dict:
	sections = [{"key": "head", "title": title, "subtitle": subtitle, "look": TIGHT},
				{"key": "form", "cards": [{"type": "App Form Card", "values": form}], "look": TIGHT}]
	if note:
		sections.append({"key": "note", "subtitle": note, "look": TIGHT})
	page = {"route": route, "title": title, "login_required": True, "sections": sections}
	if menu:
		page["menu"] = menu
	return page


def _list(route, title, subtitle, source: dict, menu=None) -> dict:
	page = {"route": route, "title": title, "login_required": True, "sections": [
		{"key": "head", "title": title, "subtitle": subtitle, "look": TIGHT}, {"key": "list", "source": source, "look": TIGHT}]}
	if menu:
		page["menu"] = menu
	return page


def definitions() -> list[dict]:
	profile_list = _my("birth-profiles")
	you = {"relationship": profiles.SELF}
	return [
		_form("onboarding/birth-details", _("Your birth details"), _("Step 1 of 2. We use this to calculate your chart. You can add family members afterwards."), {
			"load": API + "get_profile", "save": API + "save_profile", "static_args": you, "fields": _you_fields(), "submit_label": _("Save and continue"),
			"success_redirect": _start("birth-details/done")}, note=_("Your details are private and used only for your chart.")),
		_list("onboarding/birth-details/done", _("You're all set"), _("Step 2 of 2. Your birth details are saved."), {
			"method": API + "list_profiles", "args": {"who": "you"}, "links": [
				{"label": _("Add a family member"), "href": _my("birth-profiles/new"), "kind": "outline", "where": "bottom"},
				{"label": _("Continue"), "href": "/", "kind": "primary", "where": "bottom"}]}),
		_list("my/birth-profiles", _("Birth profiles"), _("Keep details for the people you care about, all under your one account."), {
			"method": API + "list_profiles", "empty": _("No profiles yet."),
			"links": [{"label": _("Add a person"), "href": _my("birth-profiles/new"), "kind": "primary", "where": "top"}]},
			menu={"label": _("Birth profiles"), "summary": _("Your details and your family's, for charts."), "order": 15}),
		_form("my/birth-profiles/new", _("Add a person"), _("Their details are private to your account."), {
			"save": API + "save_profile", "fields": _person_fields(), "submit_label": _("Save"), "cancel_label": _("Cancel"), "cancel_url": profile_list,
			"success_redirect": profile_list}),
		_form("my/birth-profiles/edit", _("Edit details"), "", {
			"fields_source": API + "profile_form_fields", "save": API + "save_profile", "url_args": "id", "submit_label": _("Save"), "cancel_label": _("Cancel"),
			"cancel_url": profile_list, "success_redirect": profile_list}),
		_form("onboarding/astrologer-personas", _("What you do"), _("Choose everything that applies. Our team approves it with your application."), {
			"fields_source": ASTRO + "personas_form_fields", "save": ASTRO + "save_personas", "submit_label": _("Save and continue"),
			"success_redirect": _start("astrologer-details")}),
		_form("onboarding/astrologer-details", _("Your astrologer details"), _("Customers see this on your page."), {
			"load": ASTRO + "get_details", "save": ASTRO + "save_details", "submit_label": _("Save and continue"),
			"fields": [
				{"name": "expertise", "label": _("Your methods and skills"), "required": True, "placeholder": _("e.g. Vedic, KP, Nadi, Lal Kitab")},
				{"name": "languages", "label": _("Languages"), "required": True, "placeholder": _("e.g. English, Hindi")},
				{"name": "years_of_practice", "label": _("Years of practice"), "required": True, "placeholder": "0"}],
			"success_redirect": _start("astrologer-credentials")}),
		_list("onboarding/astrologer-credentials", _("Your credentials"), _("Courses, certificates or lineage. Our team checks them to verify you."), {
			"method": ASTRO + "list_credentials", "empty": _("No credentials added yet."), "links": [
				{"label": _("Add a credential"), "href": _start("astrologer-credentials/new"), "kind": "outline", "where": "top"},
				{"label": _("Continue"), "href": page_url("provider"), "kind": "primary", "where": "bottom"}]}),
		_form("onboarding/astrologer-credentials/new", _("Add a credential"), "", {
			"save": ASTRO + "add_credential", "submit_label": _("Save"), "cancel_label": _("Cancel"), "cancel_url": _start("astrologer-credentials"),
			"fields": [
				{"name": "title", "label": _("Credential"), "required": True, "placeholder": _("e.g. Jyotish Visharad")},
				{"name": "issued_by", "label": _("Issued by"), "placeholder": _("School or teacher")},
				{"name": "year", "label": _("Year"), "placeholder": "YYYY"}],
			"success_redirect": _start("astrologer-credentials")}),
	]
