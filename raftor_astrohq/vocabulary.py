"""astrohq's words and extra questions for servicehq's service kinds (hook servicehq_vocabulary).
Only words, fields and one rule; the mechanics are servicehq's."""
import json
from pathlib import Path

from raftor_astrohq.details import question, sankalp, wish

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
		"kinds": {
			"Consultation": {"line_title": "Seek guidance", "line_subtitle": "Every guide can help with every kind of question. Choose who to talk to, online now or at a time you choose.", "details": {"fields": [question()], "topic_field": "question", "validate": "raftor_astrohq.details.consultation_rules"}},
			"Subscription": {"service": "daily pooja", "services": "daily poojas", "unit": "day", "units": "days", "book": "Subscribe", "details": {"fields": [*sankalp(), wish()]}},
			"Event": {"event_card": "Event Row", "line_title": "Book blessings", "line_subtitle": "Havans and poojas for what you wish for. Choose one and book your place.", "service": "havan", "services": "havans", "unit": "seat", "units": "seats", "book": "Register", "dated_name": "{0} Samuhik Pooja Blessings", "details": {"fields": sankalp(), "per_person": True}},
			"Timed service": {"service": "pooja", "services": "poojas", "unit": "pooja", "units": "poojas", "book": "Book a pooja", "dated_name": "{0} Personalised Pooja Blessings", "details": {"fields": [*sankalp(), wish()]}},
		},
	}
