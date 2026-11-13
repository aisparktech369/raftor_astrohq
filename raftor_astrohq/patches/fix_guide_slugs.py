"""A guide made from a person whose key carries an apostrophe (Rhea D'Souza: `rhea-d'souza`) has a slug the Seek guidance listing refuses, so it could never be listed. The slug is the guide's record name, so the record is renamed
to the clean slug (apostrophes dropped, other characters hyphens: `rhea-dsouza`) and its slug field follows; everything that links to it follows the rename. A guide with a clean slug is not touched."""
import re

import frappe


def execute():
	from raftor_astrohq.ai_profiles import slug_of

	for old in frappe.get_all("AI Guide Persona", pluck="name"):
		if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", old):
			continue
		new = slug_of(old)
		if new and new != old and not frappe.db.exists("AI Guide Persona", new):
			frappe.rename_doc("AI Guide Persona", old, new, force=True)
			frappe.db.set_value("AI Guide Persona", new, "slug", new)
