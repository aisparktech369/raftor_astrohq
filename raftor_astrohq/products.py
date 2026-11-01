"""What astrohq knows about the things it sells that the store's pills are made of: which planet rules a gemstone, and which signs that planet is lord of.

A gemstone's website entry says its ruling planet in words ("Jupiter / Venus", "Saturn (Shani)"). The store's listing can only narrow by a field, so the first planet named is kept as the field
`rfhq_ruling_planet` on the website entry (the words stay as they are). The zodiac pills of the Gemstones group then speak in signs and filter by the planet that is the lord of the sign
(hook `rfhq_product_pills`, asked by websitehq): Leo shows the Sun's stones."""
import re

import frappe
from frappe import _

FIELD = "rfhq_ruling_planet"
CUSTOM_FIELDS = {"Website Item": [{"fieldname": FIELD, "label": "Ruling Planet", "fieldtype": "Link", "options": "Ruling Planet", "insert_after": "short_description", "read_only": 1, "no_copy": 1,
								   "description": "The first planet named in the ruling planet of the item, so the store can narrow its listing by it."}]}

PLANETS = {"Sun": ("sun", "surya"), "Moon": ("moon", "chandra"), "Mars": ("mars", "mangal"), "Mercury": ("mercury", "budh"), "Jupiter": ("jupiter", "guru", "brihaspati"),
		   "Venus": ("venus", "shukra"), "Saturn": ("saturn", "shani"), "Rahu": ("rahu",), "Ketu": ("ketu",)}
SIGNS = (("Aries", "Mars"), ("Taurus", "Venus"), ("Gemini", "Mercury"), ("Cancer", "Moon"), ("Leo", "Sun"), ("Virgo", "Mercury"), ("Libra", "Venus"), ("Scorpio", "Mars"),
		 ("Sagittarius", "Jupiter"), ("Capricorn", "Saturn"), ("Aquarius", "Saturn"), ("Pisces", "Jupiter"))  # the lord of each sign


def ensure_fields() -> None:
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	for planet in PLANETS:  # the planets are records, so the store can narrow its listing by one (the shop only filters by a link)
		if not frappe.db.exists("Ruling Planet", planet):
			frappe.get_doc({"doctype": "Ruling Planet", "planet_name": planet}).insert(ignore_permissions=True)
	create_custom_fields(CUSTOM_FIELDS, update=True)
	settings = frappe.get_doc("Webshop Settings")  # and the field is one the listing may be narrowed by
	if not any(row.fieldname == FIELD for row in settings.filter_fields):
		settings.append("filter_fields", {"fieldname": FIELD})
		settings.enable_field_filters = 1
		settings.save(ignore_permissions=True)


def planet_of(text) -> str:
	"""The first planet named in these words (any markup around them dropped), or nothing."""
	plain = re.sub(r"<[^>]+>", " ", str(text or "")).lower()
	best = None
	for planet, names in PLANETS.items():
		for name in names:
			found = re.search(rf"\b{name}\b", plain)
			if found and (best is None or found.start() < best[0]):
				best = (found.start(), planet)
	return best[1] if best else ""


def sync_planets() -> int:
	"""Fills the planet of each website entry that has none yet from its own "Ruling Planet" line. Returns how many it filled."""
	if not frappe.get_meta("Website Item").has_field(FIELD):
		return 0
	rows = frappe.get_all("Item Website Specification", filters={"parenttype": "Website Item", "label": ["like", "Ruling Planet%"]}, fields=["parent", "description", "label"])
	done = 0
	for row in rows:
		if frappe.db.get_value("Website Item", row.parent, FIELD):
			continue
		planet = planet_of(row.description) or planet_of(row.label.split(":", 1)[-1] if ":" in row.label else "")
		if planet:
			frappe.db.set_value("Website Item", row.parent, FIELD, planet, update_modified=False)
			done += 1
	return done


def product_pills() -> list[dict]:
	"""The pills a group of products offers (hook `rfhq_product_pills`): [{"group", "field", "label", "options": [{"label": what is shown, "value": what the field must be}]}]."""
	return [{"group": "Gemstones", "field": FIELD, "label": _("Zodiac sign"), "options": [{"label": _(sign), "value": planet} for sign, planet in SIGNS]}]
