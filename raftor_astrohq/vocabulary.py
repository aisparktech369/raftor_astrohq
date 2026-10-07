"""astrohq's words and extra questions for servicehq's service kinds (hook servicehq_vocabulary).
Only words, fields and one rule; the mechanics are servicehq's."""
from raftor_astrohq.details import question, sankalp, wish


def vocabulary() -> dict:
	return {
		"words": {"provider": "astrologer", "providers": "astrologers", "unit": "unit", "units": "units", "recommendation": "remedy", "recommendations": "remedies"},
		"personas": {
			"Astrologer": {"word": "astrologer", "plural": "astrologers"},
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
			{"name": "Muhurat", "persona": "Pandit ji"},
			{"name": "Shadi date", "persona": "Pandit ji"},
			{"name": "Tarot reading", "persona": "Tarot reader", "minutes_by_provider": True},
			{"name": "Palm reading", "persona": "Palmist", "minutes_by_provider": True},
			{"name": "Numerology reading", "persona": "Numerologist", "minutes_by_provider": True},
			{"name": "Vastu consultation", "persona": "Vastu expert", "minutes_by_provider": True},
		],
		"kinds": {
			"Consultation": {"details": {"fields": [question()], "validate": "raftor_astrohq.details.consultation_rules"}},
			"Subscription": {"service": "daily pooja", "services": "daily poojas", "unit": "day", "units": "days", "book": "Subscribe", "details": {"fields": [*sankalp(), wish()]}},
			"Event": {"service": "havan", "services": "havans", "unit": "seat", "units": "seats", "book": "Register", "details": {"fields": sankalp(), "per_person": True}},
			"Timed service": {"service": "pooja", "services": "poojas", "unit": "pooja", "units": "poojas", "book": "Book a pooja", "details": {"fields": [*sankalp(), wish()]}},
		},
	}
