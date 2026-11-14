"""Adds the five stock mandir pictures to a gallery that already exists (a new site gets them from mandirs.json)."""
import json
from pathlib import Path

import frappe


def execute():
	rows = json.loads((Path(frappe.get_app_path("raftor_astrohq")) / "mandirs.json").read_text(encoding="utf-8"))["images"]
	for row in rows:
		if row["image"] and not frappe.db.exists("Mandir Image", {"image_key": row["key"]}):
			frappe.get_doc({"doctype": "Mandir Image", "enabled": row["enabled"], "image_key": row["key"], **{k: row.get(k) or "" for k in ("title", "deity", "mandir", "image", "credit", "licence", "licence_url", "source_url", "live_channel", "channel_name", "official")}, "sequence": row["sequence"]}).insert(ignore_permissions=True)
