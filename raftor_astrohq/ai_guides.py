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


def ensure() -> None:
	"""Makes each AI guide that is missing. Safe to repeat. Does nothing when the provider app is not on the site."""
	if "raftor_servicehq" not in frappe.get_installed_apps() or not frappe.db.exists("DocType", "Provider") or not frappe.get_meta("Provider").has_field("ai_guide_page"):
		return
	for row in rows():
		_make(row)
	frappe.db.commit()


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
		frappe.db.set_value("Provider", slug, "photo", _keep_photo(row["photo"], (HERE / "public" / "images" / row["photo"]).read_bytes(), slug))
	if frappe.db.exists("DocType", "Astrologer Profile") and not frappe.db.exists("Astrologer Profile", slug):
		frappe.get_doc({"doctype": "Astrologer Profile", "provider": slug, "languages": row.get("languages") or "English"}).insert(ignore_permissions=True)
