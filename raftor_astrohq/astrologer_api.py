"""Website endpoints for an astrologer's own details and credentials. Signed-in people only, and only ever
for their own Provider. They answer in the shapes websitehq's page kit expects."""
import frappe
from frappe import _

from raftor_astrohq import astrologer

PROVIDER_JOURNEY = "ServiceHQ Provider"  # the journey servicehq owns; astrohq adds steps to it
DELETE = "raftor_astrohq.astrologer_api.delete_credential"


def _provider() -> str:
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in first."), frappe.PermissionError)
	provider = astrologer.provider_of(frappe.session.user)
	if not provider:
		frappe.throw(_("Please complete your profile first."), frappe.PermissionError)
	return provider


def _profile(provider: str, create: bool = False):
	row = astrologer.profile_of(provider)
	if row or not create:
		return row
	return frappe.get_doc({"doctype": astrologer.DOCTYPE, "provider": provider})


def _refresh_onboarding() -> None:
	from raftor_onboardinghq.applications import open_applications, run_completion_checks

	for name in open_applications(frappe.session.user, PROVIDER_JOURNEY):
		run_completion_checks(name)


@frappe.whitelist(methods=["POST"])
def personas_form_fields():
	return {"fields": [{k: v for k, v in f.items() if k != "persona"} for f in astrologer.persona_fields()],
			"values": {f["name"]: 1 for f in astrologer.persona_fields() if f["persona"] in _chosen(_provider())}}


def _chosen(provider: str) -> set[str]:
	return set(frappe.get_all("Provider Persona", filters={"parent": provider, "parenttype": "Provider"}, pluck="persona"))


@frappe.whitelist(methods=["POST"])
def save_personas(values=None):
	"""The personas the provider ticks. Ones already approved stay approved; new ones wait for the business team."""
	provider = _provider()
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	wanted = [f["persona"] for f in astrologer.persona_fields() if values.get(f["name"]) in (1, True, "1", "true", "on")]
	if not wanted:
		return {"ok": False, "errors": {astrologer.persona_fields()[0]["name"]: _("Choose at least one.")}}
	doc = frappe.get_doc("Provider", provider)
	approved = {row.persona for row in doc.personas if row.approved}
	doc.set("personas", [{"persona": p, "approved": int(p in approved)} for p in wanted])
	doc.save(ignore_permissions=True)
	_refresh_onboarding()
	waiting = [p for p in wanted if p not in approved]
	if waiting and approved:  # a live astrologer added a kind: it shows once the business team approves it
		return {"ok": True, "message": _("Saved. {0} will show once our team approves it.").format(", ".join(waiting))}
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def get_details():
	row = _profile(_provider())
	return {"values": {k: row.get(k) if row.get(k) is not None else "" for k in ("expertise", "languages", "years_of_practice")} if row else {}}


@frappe.whitelist(methods=["POST"])
def save_details(values=None):
	provider = _provider()
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	errors = astrologer.details_errors(values)
	if errors:
		return {"ok": False, "errors": errors}
	data = astrologer.clean(values)
	data["years_of_practice"] = int(data["years_of_practice"])
	row = _profile(provider, create=True)
	row.update(data)
	row.save(ignore_permissions=True)
	_refresh_onboarding()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def list_credentials():
	row = _profile(_provider())
	items = []
	for c in (row.credentials if row else []):
		lines = [" · ".join(str(x) for x in (c.issued_by, c.year) if x)]
		items.append({"id": c.name, "title": c.title, "lines": [line for line in lines if line],
					  "actions": [{"label": _("Remove"), "kind": "danger", "call": DELETE, "args": {"id": c.name},
								   "confirm": _("Remove {0}?").format(c.title), "confirm_label": _("Yes, remove")}]})
	return {"items": items}


@frappe.whitelist(methods=["POST"])
def add_credential(values=None):
	provider = _provider()
	if not astrologer.profile_of(provider):
		return {"ok": False, "errors": {"title": _("Fill in your astrologer details first.")}}
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	errors = astrologer.credential_errors(values)
	if errors:
		return {"ok": False, "errors": errors}
	row = _profile(provider)
	row.append("credentials", {
		"title": str(values.get("title")).strip(), "issued_by": str(values.get("issued_by") or "").strip(),
		"year": astrologer.credential_year(values.get("year")),
	})
	row.save(ignore_permissions=True)
	_refresh_onboarding()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def delete_credential(id):
	row = _profile(_provider())
	found = next((c for c in (row.credentials if row else []) if c.name == id), None)
	if not found:
		frappe.throw(_("That credential was not found."), frappe.DoesNotExistError)
	row.remove(found)
	row.save(ignore_permissions=True)
	return {"message": _("Removed.")}
