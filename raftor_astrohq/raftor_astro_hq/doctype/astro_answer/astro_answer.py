"""Astro Answer: what the astrology engine answered for one person's birth in one mode, kept so that every report, page and second report made from it costs no new call (raftor_astrohq/answers.py).
Birth details are personal: only a System Manager sees these records, nothing is shown to a customer from here but through a report they may open, and they go with the person (a User's deletion removes them)."""
from frappe.model.document import Document


class AstroAnswer(Document):
	pass
