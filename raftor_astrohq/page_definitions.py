"""AstroHQ's pages as data for websitehq to build (hook rfhq_page_definitions): which sections and cards, in what order, fed by which
endpoint. The endpoints and the rules stay in api.py, astrologer_api.py and profiles.py; no HTML, CSS or JavaScript here. Their look is the
site's. Addresses are `<group>/<page>`: a person's own birth details under `my`, the first-time steps under `onboarding`."""
import frappe
from frappe import _

from raftor_astrohq import details, profiles
from raftor_servicehq.roles import SERVICE_PROVIDER_ROLE, STAFF_ROLES
from raftor_websitehq.website_hq.page_groups import page_url

API = "raftor_astrohq.api."
ASTRO = "raftor_astrohq.astrologer_api."
VIEW = "raftor_astrohq.report_view."
TAROT = "raftor_astrohq.tarot."
NUMEROLOGY = "raftor_astrohq.numerology_page."
TEMPLE = "raftor_astrohq.temple."
TIGHT = {"padding": "Small", "gap": "Small"}


def _time_fields():
	return details.time_fields()


def _you_fields():
	return details.you_fields()


def _person_fields():
	return [
		{"name": "relationship", "label": _("Who is this?"), "type": "chips", "grid": True, "required": True, "options": profiles.relationships()},
		{"name": "full_name", "label": _("Full name"), "required": True},
		{"name": "date_of_birth", "label": _("Date of birth"), "type": "date", "required": True},
		*_time_fields(),
		details.place_field("place_of_birth", _("Place of birth")),
		{"name": "permission_given", "label": _("I have permission to keep this person's details"), "type": "checkbox", "switch": True,
		 "hint": _("Needed for anyone but yourself.")},
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


def chart_page() -> dict:
	"""The astrologer's page of a customer's chart (report_view.py): whose it is, the other people the customer shares and the wide board of panes, from one endpoint. Only people who hold the provider role; the endpoint checks
	the booking and what the customer shares.
	A wide page: it has the whole window (no left menu, no container) so that the board of panes can have four columns."""
	return {"route": "provider/chart", "title": _("Chart"), "login_required": True, "roles": [SERVICE_PROVIDER_ROLE], "otherwise": "provider/join", "wide": True, "sections": [
		{"key": "chart", "source": {"method": VIEW + "chart_view", "card": "Report View", "url_args": "booking,profile", "empty": _("There is no chart to show for this booking.")}, "look": TIGHT}]}


def ask_page() -> dict:
	"""Ask Pandit ji: a chat with the AI guide (agent_chat.py), for a signed-in person."""
	return {"route": "ask/pandit-ji", "title": _("Ask Pandit ji"), "meta_title": _("Ask Pandit ji, our AI guide | AstroHQ"),
		"meta_description": _("Ask about Rudraksha, gemstones and poojas. An AI guide that explains from our Academy and shows what we offer."), "login_required": False, "sections": [
		{"key": "head", "title": _("Ask Pandit ji"), "subtitle": _("An AI guide to Rudraksha, gemstones and poojas, explained from our Academy."), "look": TIGHT},
		{"key": "chat", "cards": [{"type": "App Chat Card", "values": {"info": "raftor_astrohq.agent_chat.info"}}], "look": TIGHT}]}


def numerologist_page() -> dict:
	"""Ask the numerology guide: a chat with the second AI guide (agent_chat.py, the card's fixed argument says which agent)."""
	return {"route": "ask/numerologist", "title": _("Ask the numerology guide"), "meta_title": _("Ask the numerology guide | AstroHQ"),
		"meta_description": _("Find your birth number and your name number and see what they are said to mean. An AI guide that explains from our Academy."), "login_required": False, "sections": [
		{"key": "head", "title": _("Ask the numerology guide"), "subtitle": _("Your birth number and your name number, and what they are said to mean."), "look": TIGHT},
		{"key": "chat", "cards": [{"type": "App Chat Card", "values": {"info": "raftor_astrohq.agent_chat.info", "static_args": '{"agent": "numerologist"}'}}], "look": TIGHT}]}


def dream_guide_page() -> dict:
	"""Talk to the dream guide: a chat with the third AI guide (agent_chat.py, the card's fixed argument says which agent)."""
	return {"route": "ask/dream-guide", "title": _("Talk about a dream"), "meta_title": _("Talk about a dream with our dream guide | AstroHQ"),
		"meta_description": _("Tell a dream and explore what it might mean to you, with the traditions labelled. An AI guide that explains from our Academy and predicts nothing."), "login_required": False, "sections": [
		{"key": "head", "title": _("Talk about a dream"), "subtitle": _("Tell a dream and explore what it might mean to you, one question at a time."), "look": TIGHT},
		{"key": "chat", "cards": [{"type": "App Chat Card", "values": {"info": "raftor_astrohq.agent_chat.info", "static_args": '{"agent": "dream_guide"}'}}], "look": TIGHT}]}


def vedic_astrologer_page() -> dict:
	"""Ask the Vedic astrologer guide: a chat that opens a saved person's kundli and matches two saved people (agent_chat.py, the card's fixed argument says which agent)."""
	return {"route": "ask/vedic-astrologer", "title": _("Ask the Vedic astrologer guide"), "meta_title": _("Ask the Vedic astrologer guide | AstroHQ"),
		"meta_description": _("See your birth chart, or a family member's, explained, and match two charts. An AI guide that explains what a chart shows and predicts nothing."), "login_required": False, "sections": [
		{"key": "head", "title": _("Ask the Vedic astrologer guide"), "subtitle": _("Your birth chart, or a family member's, explained; and how two charts match."), "look": TIGHT},
		{"key": "chat", "cards": [{"type": "App Chat Card", "values": {"info": "raftor_astrohq.agent_chat.info", "static_args": '{"agent": "vedic_astrologer"}'}}], "look": TIGHT}]}


def kp_astrologer_page() -> dict:
	"""Ask the KP astrologer guide: a chat that opens a saved person's chart the Krishnamurti way and matches two saved people (agent_chat.py, the card's fixed argument says which agent)."""
	return {"route": "ask/kp-astrologer", "title": _("Ask the KP astrologer guide"), "meta_title": _("Ask the KP astrologer guide | AstroHQ"),
		"meta_description": _("See your chart the KP way, with cusps, star and sub lords, and match two charts. An AI guide that explains what a chart shows and predicts nothing."), "login_required": False, "sections": [
		{"key": "head", "title": _("Ask the KP astrologer guide"), "subtitle": _("Your chart the Krishnamurti way, with its cusps, star lords and sub lords; and how two charts match."), "look": TIGHT},
		{"key": "chat", "cards": [{"type": "App Chat Card", "values": {"info": "raftor_astrohq.agent_chat.info", "static_args": '{"agent": "kp_astrologer"}'}}], "look": TIGHT}]}


def guide_page() -> dict:
	"""Talk to one of the AI guides of an area (?persona=kavya): one chat page for all of them (agent_chat.py reads the name from the address and the card tells the chat which guide it is)."""
	return {"route": "ask/guide", "title": _("Talk to an AI guide"), "meta_title": _("Talk to an AI guide | AstroHQ"),
		"meta_description": _("Choose an AI guide who talks the way you like, in your language, about what matters to you."), "login_required": False, "sections": [
		{"key": "chat", "cards": [{"type": "App Chat Card", "values": {"info": "raftor_astrohq.agent_chat.info", "url_args": "persona"}}], "look": TIGHT}]}


def panchang_page() -> dict:
	"""The Panchang page (panchang.py), public: the panchang and the chaugharia of any day and town, and the next seven days. The address takes ?date=2026-10-24&place=<the town's id>."""
	return {"route": "panchang", "title": _("Panchang"), "meta_title": _("Today's Panchang | AstroHQ"),
		"meta_description": _("Today's tithi, nakshatra, yoga, karana and Rahu Kaal for your town, with sunrise and sunset."), "login_required": False, "sections": [
		{"key": "day", "title": _("Panchang"), "subtitle": _("Today's tithi, nakshatra, Rahu Kaal and chaugharia, for any day and any town."),
		 "source": {"method": "raftor_astrohq.panchang.page", "card": "Report View", "url_args": "date,place", "empty": _("The panchang is not available yet.")}, "look": TIGHT}]}


def temple_page() -> dict:
	"""The person's digital temple (temple.py), signed in: their own photo of the deity they worship and the pooja performed before it, drawn by websitehq's Offering Stage Card."""
	values = {"view": TEMPLE + "view", "offer": TEMPLE + "offer", "photo": TEMPLE + "set_photo", "tilak": TEMPLE + "place_tilak", "again": TEMPLE + "again",
			  "choose": TEMPLE + "choose_mandir", "switch": TEMPLE + "switch_mandir", "remove": TEMPLE + "remove_mandir"}
	return {"route": "my/temple", "title": _("Your Digital Temple"), "login_required": True,
			"menu": {"side": {"label": _("My temple"), "order": 16}},  # in the left menu and the phone's bottom bar; not in the account menu (it has no menu label)
			"sections": [{"key": "temple", "cards": [{"type": "Offering Stage Card", "values": values}], "look": {**TIGHT, "theme": "Temple"}}]}  # (the theme variant made for it: its tones are the room's)


def tarot_page() -> dict:
	"""Three cards, drawn from a small cabinet (websitehq's Tarot Draw Card): open to anyone; the reading of the three together asks for a sign-in (tarot.py)."""
	values = {"view": TAROT + "view", "draw": TAROT + "draw", "interpret": TAROT + "interpret", "url_args": "draw"}
	return {"route": "services/tarot", "title": _("Tarot"), "login_required": False,
			"sections": [{"key": "tarot", "cards": [{"type": "Tarot Draw Card", "values": values}], "look": {**TIGHT, "theme": "Temple"}}]}


def numerology_page() -> dict:
	"""A name and a date of birth, and the numbers come out one by one (websitehq's Number Reveal Card): open to anyone; the reading of the numbers together asks for a sign-in (numerology_page.py)."""
	values = {"view": NUMEROLOGY + "view", "reveal": NUMEROLOGY + "reveal", "interpret": NUMEROLOGY + "interpret", "url_args": "reading"}
	return {"route": "services/numerology", "title": _("Numerology"), "login_required": False,
			"sections": [{"key": "numerology", "cards": [{"type": "Number Reveal Card", "values": values}], "look": {**TIGHT, "theme": "Temple"}}]}


def definitions() -> list[dict]:
	profile_list = _my("birth-profiles")
	you = {"relationship": profiles.SELF}
	stats = "raftor_astrohq.stats_page."
	return [
		{"route": "team/stats", "title": _("Business stats"), "login_required": True, "roles": list(STAFF_ROLES), "otherwise": "my",
		 "menu": {"label": _("Business stats"), "summary": _("Sessions, ratings and what the AI guides use and cost."), "order": 6, "side": {"order": 11}},
		 "sections": [{"key": "head", "title": _("Business stats"), "subtitle": _("The last 30 days, then each AI guide and each week."), "look": TIGHT},
					  {"key": "numbers", "columns": "3", "source": {"method": stats + "summary", "card": "Fact Card", "empty": _("Nothing to count yet.")}, "look": TIGHT},
					  {"key": "guides", "title": _("AI guides"), "source": {"method": stats + "guides", "empty": _("No AI chats in the last 30 days.")}, "look": TIGHT},
					  {"key": "weeks", "title": _("Week by week"), "source": {"method": stats + "weekly", "empty": _("Nothing yet.")}, "look": TIGHT}]},
		_form("onboarding/birth-details", _("Your birth details"), _("We use this to calculate your chart. You can add family members afterwards."), {
			"load": API + "get_profile", "save": API + "save_profile", "static_args": you, "fields": _you_fields(), "submit_label": _("Save and continue"),
			"success_redirect": _start("birth-details/done")}, note=_("Your details are private and used only for your chart.")),
		_list("onboarding/birth-details/done", _("You're all set"), _("Your birth details are saved."), {
			"method": API + "list_profiles", "args": {"who": "you"}, "links": [
				{"label": _("Add a family member"), "href": _my("birth-profiles/new"), "kind": "outline", "where": "bottom"},
				{"label": _("Continue"), "href": "/", "kind": "primary", "where": "bottom"}]}),
		_list("my/birth-profiles", _("Birth profiles"), _("Keep details for the people you care about, all under your one account."), {
			"method": API + "list_profiles", "empty": _("No profiles yet."),
			"links": [{"label": _("Add a person"), "href": _my("birth-profiles/new"), "kind": "primary", "where": "top"}]},
			menu={"label": _("Birth profiles"), "summary": _("Your details and your family's, for charts."), "order": 15, "side": {"order": 30}}),
		_form("my/birth-profiles/you", _("Your birth details"), _("We use this to calculate your chart."), {
			"load": API + "get_profile", "save": API + "save_profile", "static_args": you, "fields": _you_fields(), "submit_label": _("Save"), "cancel_label": _("Cancel"),
			"cancel_url": profile_list, "success_redirect": profile_list}, note=_("Your details are private and used only for your chart.")),
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
		chart_page(),
		panchang_page(),
		ask_page(),
		numerologist_page(),
		dream_guide_page(),
		vedic_astrologer_page(),
		kp_astrologer_page(),
		guide_page(),
		temple_page(),
		tarot_page(),
		numerology_page(),
	]
