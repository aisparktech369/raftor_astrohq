"""astrohq's words and extra questions for servicehq's service kinds (hook servicehq_vocabulary).
Only words, fields and one rule; the mechanics are servicehq's."""
from raftor_astrohq.details import question, sankalp, wish


def vocabulary() -> dict:
	return {
		"words": {"provider": "astrologer", "providers": "astrologers", "unit": "unit", "units": "units", "recommendation": "remedy", "recommendations": "remedies"},
		"dashboard_sections": ["raftor_astrohq.details.dashboard_section"],
		"kinds": {
			"Consultation": {"service": "session", "services": "sessions", "unit": "session", "units": "sessions", "book": "Book a session",
				"details": {"fields": [question()], "validate": "raftor_astrohq.details.consultation_rules"}},
			"Subscription": {"service": "daily pooja", "services": "daily poojas", "unit": "day", "units": "days", "book": "Subscribe", "details": {"fields": [*sankalp(), wish()]}},
			"Event": {"service": "havan", "services": "havans", "unit": "seat", "units": "seats", "book": "Register", "details": {"fields": sankalp(), "per_person": True}},
			"Timed service": {"service": "pooja", "services": "poojas", "unit": "pooja", "units": "poojas", "book": "Book a pooja", "details": {"fields": [*sankalp(), wish()]}},
		},
	}
