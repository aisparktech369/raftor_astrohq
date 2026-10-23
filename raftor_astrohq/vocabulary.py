"""astrohq's words and extra questions for servicehq's service kinds (hook servicehq_vocabulary).
Only words, fields and one rule; the mechanics are servicehq's."""
import json
from pathlib import Path

from frappe import _

from raftor_astrohq.details import birth_details, kundli_fields, match_fields, question, sankalp, wish

PACK = Path(__file__).parent / "pack"


def pack_services() -> list[dict]:
	"""The dated services (and their dates) the installation pack ships: every .json file in the pack folder, a list of service entries. Add a file to add more."""
	return [entry for path in sorted(PACK.glob("*.json")) for entry in json.loads(path.read_text())]


def vocabulary() -> dict:
	return {
		"words": {"provider": "astrologer", "providers": "astrologers", "unit": "unit", "units": "units", "recommendation": "remedy", "recommendations": "remedies", "clock": "h:mm a",
				  "join_title": "Become an astrologer", "join_subtitle": "Share your guidance with people who are looking for it. Here is how it works.", "join_already": "You are already an astrologer", "join_hint": "Share your guidance with people who are looking for it.",
				  "privacy_note": "Your details are private and used only for your chart."},
		"provider_lines": "raftor_astrohq.astrologer.card_lines",
		"provider_credentials": "raftor_astrohq.astrologer.credentials",
		"provider_filters": "raftor_astrohq.astrologer.card_filters",
		"event_filters": "raftor_astrohq.event_filters.wish_filters",
		"event_labels": "raftor_astrohq.event_filters.wish_labels",
		"personas": {
			"Astrologer": {"word": "astrologer", "plural": "astrologers"},
			"KP astrologer": {"word": "KP astrologer", "plural": "KP astrologers"},
			"Tarot reader": {"word": "tarot reader", "plural": "tarot readers"},
			"Pandit ji": {"word": "pandit ji", "plural": "pandit ji"},
			"Palmist": {"word": "palmist", "plural": "palmists"},
			"Numerologist": {"word": "numerologist", "plural": "numerologists"},
			"Vastu expert": {"word": "vastu expert", "plural": "vastu experts"},
		},
		# The standard services providers enrol in. Fixed work has set minutes; readings let the provider choose theirs.
		"services": [
			{"name": "Match making", "persona": "Astrologer"},
			{"name": "Astrology reading", "persona": "Astrologer", "minutes_by_provider": True},
			{"name": "KP astrology reading", "persona": "KP astrologer", "minutes_by_provider": True},
			{"name": "Muhurat", "persona": "Pandit ji"},
			{"name": "Shadi date", "persona": "Pandit ji"},
			{"name": "Tarot reading", "persona": "Tarot reader", "minutes_by_provider": True},
			{"name": "Palm reading", "persona": "Palmist", "minutes_by_provider": True},
			{"name": "Numerology reading", "persona": "Numerologist", "minutes_by_provider": True},
			{"name": "Vastu consultation", "persona": "Vastu expert", "minutes_by_provider": True},
			*pack_services(),
		],
		# The reports sold from the shop, made from the buyer's own birth details (servicehq digital.py). Each ships as an item switched off, for the business team
		# to price and switch on; servicehq asks the details, takes the order and delivers the PDF the maker returns.
		"reports": {
			"kundli": {"title": _("Kundli report"), "blurb": _("Your birth chart made from your date, time and place of birth."),
					   "description": _("Your kundli: the lagna, where each planet stood, the houses, the navamsa chart, your dasha periods and the panchang of the day you were born.\n\n"
										"Made for you from the details you give, by the same calculation astrologers use (Lahiri ayanamsa). It is sent to you as a PDF once the order is paid."),
					   "details": {"fields": kundli_fields(), "validate": "raftor_astrohq.details.kundli_rules"}, "maker": "raftor_astrohq.reports.kundli_report"},
			"match": {"title": _("Match making report"), "blurb": _("How well two birth charts match, by the eight kootas out of 36."),
					  "description": _("The Ashtakoota (Guna Milan) score for a boy and a girl, koota by koota, out of 36, with the Moon sign and nakshatra of each and their manglik check.\n\n"
									   "Made from the details you give for both. It is sent to you as a PDF once the order is paid."),
					  "details": {"fields": match_fields(), "validate": "raftor_astrohq.details.match_rules"}, "maker": "raftor_astrohq.reports.match_report"},
		},
		"kinds": {
			"Consultation": {"line_title": "Seek guidance", "line_subtitle": "Every guide can help with every kind of question. Choose who to talk to, online now or at a time you choose.", "details": {"fields": [question()], "topic_field": "question", "validate": "raftor_astrohq.details.consultation_rules"}},
			"Subscription": {"service": "daily pooja", "services": "daily poojas", "unit": "day", "units": "days", "book": "Subscribe", "details": {"fields": [*sankalp(), wish()]}},
			"Event": {"event_card": "Event Row", "line_title": "Book blessings", "line_subtitle": "Havans and poojas for what you wish for. Choose one and book your place.", "service": "havan", "services": "havans", "unit": "seat", "units": "seats", "book": "Register", "dated_name": "{0} Samuhik Pooja Blessings", "details": {"fields": sankalp(), "per_person": True}},
			"Report": {"details": {"fields": birth_details()}},  # not a service kind: what a report made from someone's birth asks (servicehq digital.py)
			"Timed service": {"service": "pooja", "services": "poojas", "unit": "pooja", "units": "poojas", "book": "Book a pooja", "dated_name": "{0} Personalised Pooja Blessings", "details": {"fields": [*sankalp(), wish()]}},
		},
	}
