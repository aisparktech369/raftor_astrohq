"""The AI guides listed with the guides on the Seek guidance page. Each is a Provider with an AI Guide Page (servicehq: card_feeds, presence): always online, free to chat with, labelled AI on its card, and its button opens the chat page of its agent.
They are data (ai_guides.json), made by `ensure()` on install and migrate and never changed once they exist beyond filling in what is missing, so a guide's words or photo that staff have edited in Desk stay. To add another: add a row to the file
(slug, name, persona, page, photo in public/images, languages, bio), make sure the persona is in the vocabulary, and migrate. Nothing in code names a guide."""
import json
from pathlib import Path

import frappe

HERE = Path(__file__).parent
DOMAIN = "guides.astrohq.in"  # the guides' own (never used) addresses: they are not people and nobody signs in as them


def rows() -> list[dict]:
	return json.loads((HERE / "ai_guides.json").read_text(encoding="utf-8"))


AREA_WORD = {"pandit_ji": "Pandit ji", "numerologist": "Numerologist", "dream_guide": "Dream interpreter"}  # the word each area's guides carry in the vocabulary
PERSONA = "AI Guide Persona"


def personas() -> list[dict]:
	"""The guides of the same area that speak differently (ai_personas.json): data, made into records on install and then kept in Desk."""
	return json.loads((HERE / "ai_personas.json").read_text(encoding="utf-8"))


def _available() -> bool:
	return "raftor_servicehq" in frappe.get_installed_apps() and frappe.db.exists("DocType", "Provider") and frappe.get_meta("Provider").has_field("ai_guide_page")


def ensure() -> None:
	"""Makes each AI guide that is missing. Safe to repeat. Does nothing when the provider app is not on the site."""
	if not _available():
		return
	for row in rows():
		_make(row)
	seed_personas()
	frappe.db.commit()


def seed_personas() -> None:
	"""The guides of each area, as records staff change in Desk (AI Guide Persona): made once, never put back once they exist, and each given its listing on the Seek guidance page."""
	if not frappe.db.exists("DocType", PERSONA):
		return
	if not frappe.db.count(PERSONA):
		for row in personas():
			frappe.get_doc({"doctype": PERSONA, "enabled": 1, "ai_image": 0, **row}).insert(ignore_permissions=True)
	for name in frappe.get_all(PERSONA, pluck="name"):
		sync_persona(frappe.get_doc(PERSONA, name))


def sync_persona(persona) -> None:
	"""A persona's listing: its Provider (the card on Seek guidance, always online, labelled AI), made when missing and kept in step with what staff write in Desk (name, words, languages, picture, on or off)."""
	if not _available() or persona.area not in AREA_WORD:
		return
	slug = persona.slug
	_make({"slug": slug, "name": persona.guide_name, "persona": AREA_WORD[persona.area], "page": f"ask/guide?persona={slug}", "photo": f"guide-{slug}.svg", "languages": persona.languages or "English",
		   "bio": " ".join(x for x in (persona.tagline and persona.tagline.rstrip(".") + ".", persona.bio) if x)})
	values = {"display_name": persona.guide_name, "bio": f"<p>{' '.join(x for x in (persona.tagline and persona.tagline.rstrip('.') + '.', persona.bio) if x)}</p>", "status": "Live" if persona.enabled else "Paused"}
	if persona.avatar and frappe.db.get_value("Provider", slug, "photo") != persona.avatar:
		values["photo"] = persona.avatar
	frappe.db.set_value("Provider", slug, values)
	if frappe.db.exists("Astrologer Profile", slug) and persona.languages:
		frappe.db.set_value("Astrologer Profile", slug, "languages", persona.languages)


PICTURE_TONES = {"Pandit ji": ("#8a3b12", "#f0a04b"), "Numerologist": ("#5b2a86", "#c86bd0"), "Dream interpreter": ("#1f3b73", "#6fa8f0")}


def _lettered(name: str, kind: str) -> bytes:
	"""A plain picture for a guide that has none yet: its first letter on a colour for its kind. A guide's real picture, attached in Desk, takes its place."""
	a, b = PICTURE_TONES.get(kind, ("#3a120e", "#d9a441"))
	letter = (name.strip()[:1] or "A").upper().replace("&", "").replace("<", "")
	return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 400"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs>'
			f'<rect width="300" height="400" fill="url(#g)"/><circle cx="150" cy="170" r="70" fill="#ffffff" fill-opacity="0.18"/><text x="150" y="196" font-family="Georgia,serif" font-size="84" fill="#fff" text-anchor="middle">{letter}</text></svg>').encode()


def _keep_photo(name: str, data: bytes, slug: str) -> str:
	"""The guide's picture, put in the site's public files with a File record made with no storage hooks: a site that keeps its files off-site would look for it in the bucket and fail. Returns its address."""
	folder = Path(frappe.get_site_path("public", "files"))
	folder.mkdir(parents=True, exist_ok=True)
	if not (folder / name).exists():
		(folder / name).write_bytes(data)
	url = f"/files/{name}"
	if not frappe.db.exists("File", {"file_url": url}):
		record = frappe.get_doc({"doctype": "File", "file_url": url, "file_name": name, "is_private": 0, "file_size": len(data), "attached_to_doctype": "Provider", "attached_to_name": slug})
		record.name = frappe.generate_hash(length=10)
		record.db_insert()
	return url


def _make(row: dict) -> None:
	slug, email = row["slug"], f"{row['slug']}@{DOMAIN}"
	if not frappe.db.exists("Provider", slug):
		if not frappe.db.exists("User", email):
			frappe.get_doc({"doctype": "User", "email": email, "first_name": row["name"], "send_welcome_email": 0, "user_type": "Website User"}).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "Provider", "user": email, "slug": slug, "display_name": row["name"], "provider_type": "Individual", "bio": f"<p>{row['bio']}</p>",
						"personas": [{"persona": row["persona"], "approved": 1}], "ai_guide_page": row["page"]}).insert(ignore_permissions=True)
		frappe.db.set_value("Provider", slug, {"status": "Live", "verification_status": "Verified"})  # a Provider's stage is a Workflow: made in Draft, brought Live as the tests' fixtures do
	if not frappe.db.get_value("Provider", slug, "photo"):
		shipped = HERE / "public" / "images" / row["photo"]
		frappe.db.set_value("Provider", slug, "photo", _keep_photo(row["photo"], shipped.read_bytes() if shipped.exists() else _lettered(row["name"], row.get("persona", "")), slug))
	if frappe.db.exists("DocType", "Astrologer Profile") and not frappe.db.exists("Astrologer Profile", slug):
		frappe.get_doc({"doctype": "Astrologer Profile", "provider": slug, "languages": row.get("languages") or "English"}).insert(ignore_permissions=True)
