"""What an astrologer adds to servicehq's general Provider: their own table (Astrologer Profile) pointing at it.
The Provider is never changed. The same rules run on every save (api.py) and in the onboarding checks.
"""
import re

import frappe
from frappe import _
from frappe.utils import cint, getdate, today

DOCTYPE = "Astrologer Profile"
MAX_YEARS = 80  # a sanity limit on the number typed, not a business rule


def provider_of(user: str) -> str | None:
	return frappe.db.get_value("Provider", {"user": user}, "name")


def profile_of(provider: str):
	return frappe.get_doc(DOCTYPE, provider) if frappe.db.exists(DOCTYPE, provider) else None


def clean(values: dict) -> dict:
	years = str(values.get("years_of_practice") if values.get("years_of_practice") is not None else "").strip()
	return {
		"expertise": str(values.get("expertise") or "").strip(),
		"languages": str(values.get("languages") or "").strip(),
		"years_of_practice": years,
	}


def details_errors(values: dict) -> dict[str, str]:
	v, errors = clean(values), {}
	if len(v["expertise"]) < 2:
		errors["expertise"] = _("Enter what you read or practise.")
	if len(v["languages"]) < 2:
		errors["languages"] = _("Enter the languages you consult in.")
	years = v["years_of_practice"]
	if not years.isdigit() or int(years) > MAX_YEARS:
		errors["years_of_practice"] = _("Enter a whole number of years, from 0 to {0}.").format(MAX_YEARS)
	return errors


def credential_errors(values: dict) -> dict[str, str]:
	errors = {}
	if len(str(values.get("title") or "").strip()) < 2:
		errors["title"] = _("Enter the name of the credential.")
	year = str(values.get("year") or "").strip()
	if year and (not year.isdigit() or not 1900 <= int(year) <= getdate(today()).year):
		errors["year"] = _("Enter a valid year, or leave it empty.")
	return errors


def details_complete(application) -> bool:
	"""Onboarding completion check: expertise, languages and years are filled in correctly."""
	provider = provider_of(application.applicant_user)
	row = profile_of(provider) if provider else None
	return bool(row) and not details_errors({k: row.get(k) for k in ("expertise", "languages", "years_of_practice")})


def credentials_complete(application) -> bool:
	"""Onboarding completion check: at least one credential is listed."""
	provider = provider_of(application.applicant_user)
	row = profile_of(provider) if provider else None
	return bool(row) and bool(row.credentials)


def credential_year(value) -> int | None:
	return cint(value) or None


def persona_fields() -> list[dict]:
	"""One tick box per persona the vertical lists, in its own words."""
	from raftor_servicehq import kinds

	return [{"name": "p_" + re.sub(r"\W+", "_", name.lower()), "label": kinds.upfirst(name), "type": "checkbox", "persona": name} for name in kinds.personas()]


def personas_complete(application) -> bool:
	"""Onboarding completion check: at least one persona is chosen."""
	provider = provider_of(application.applicant_user)
	return bool(provider) and bool(frappe.db.exists("Provider Persona", {"parent": provider, "parenttype": "Provider"}))


def card_lines(provider: str) -> list[str]:
	"""What a provider card says about an astrologer in public: years of practice, and the languages they consult in."""
	row = frappe.db.get_value(DOCTYPE, provider, ["years_of_practice", "languages"], as_dict=True)
	if not row:
		return []
	if frappe.db.get_value("Provider", provider, "ai_guide_page"):
		return []  # an AI guide has no years of practice, and its one line says what it is
	return [_("{0} years").format(row.years_of_practice) if row.years_of_practice is not None else "", (row.languages or "").strip()]


def credentials(provider: str) -> list[dict]:
	"""What an astrologer lists as their credentials, each as {"text": "Jyotish Acharya · Banaras Hindu University · 2014", "reviewed": whether our team has checked it}
	(vocabulary hook "provider_credentials"). Plain text only: servicehq draws it and decides what to claim from `reviewed`."""
	row = profile_of(provider) if provider else None
	return [{"text": " · ".join(str(x) for x in (c.title, c.issued_by, c.year) if x), "reviewed": bool(c.reviewed)} for c in (row.credentials if row else [])]


def _spoken(text: str) -> list[str]:
	"""The languages written in an astrologer's profile ("Hindi, English"), one word each, in a tidy case."""
	return [w.strip().title() for w in re.split(r"[,;/]", text or "") if w.strip()]


def card_filters(names: list[str], choices: dict) -> dict:
	"""The ways a listing of astrologers can be narrowed beyond their persona (hook "provider_filters", see servicehq kinds.py): the language they consult in, and what is
	troubling the visitor. The language narrows the list. The trouble does not: every astrologer can answer every question, so it only goes along to the booking."""
	from raftor_astrohq.details import topics

	rows = frappe.get_all(DOCTYPE, filters={"provider": ["in", names or ["-"]]}, fields=["provider", "languages"])
	spoken = {r.provider: _spoken(r.languages) for r in rows}
	counts: dict[str, int] = {}
	for words in spoken.values():
		for word in set(words):
			counts[word] = counts.get(word, 0) + 1
	options = [{"value": w, "label": w, "count": n} for w, n in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
	facets = [
		{"name": "topic", "label": _("What is troubling you?"), "heading": _("What is troubling you?"), "display": "chips", "carry": True, "optional": True,
		 "options": [{"value": t, "label": t} for t in topics()]},
		{"name": "language", "label": _("Language"), "heading": _("Which language?"), "display": "chips", "options": options},
	]
	wanted = {w.strip().title() for w in str(choices.get("language") or "").split(",") if w.strip()}
	kept = [n for n in names if not wanted or wanted & set(spoken.get(n, []))]
	return {"facets": [f for f in facets if f["options"]], "names": kept}
