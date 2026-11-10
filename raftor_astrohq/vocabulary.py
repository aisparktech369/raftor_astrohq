"""astrohq's words and extra questions for servicehq's service kinds (hook servicehq_vocabulary).
Only words, fields and one rule; the mechanics are servicehq's."""
import json
from pathlib import Path

from frappe import _

from raftor_astrohq.details import birth_details, kundli_fields, match_fields, numerology_fields, question, sankalp, visit_fields, whose, wish

PACK = Path(__file__).parent / "pack"


def pack_services() -> list[dict]:
	"""The dated services (and their dates) the installation pack ships: every .json file in the pack folder, a list of service entries. Add a file to add more."""
	return [entry for path in sorted(PACK.glob("*.json")) for entry in json.loads(path.read_text())]


def person_free() -> dict:
	"""What the free way does for a report about one person (servicehq free_reports.py): asks whose it is, keeps the details as a birth profile, says whose it is, names a new account and fills the form from the person's own profile."""
	return {"fields": [whose()], "keep": "raftor_astrohq.reports.keep_birth_profile", "summary": "raftor_astrohq.reports.kundli_summary", "prefill": "raftor_astrohq.reports.kundli_prefill", "picker": "raftor_astrohq.reports.kundli_picker", "account_name": "raftor_astrohq.reports.kundli_account_name",
			"keep_line": _("We keep these details in your birth profile so you do not have to write them again. If this is for someone else, you confirm that you may.")}


def arranged_reports() -> dict:
	"""The reports made by laying the engine's answer out with a layout (arrange.py, layouts/): each says its layout and the mode it is made from. They ship as items switched off like the others; a customer
	sees the sections an astrologer has ticked as reviewed in the layout (reports.arranged_report). The names are plain words to be changed in Desk."""
	person = {"fields": kundli_fields(), "validate": "raftor_astrohq.details.kundli_rules"}
	maker = "raftor_astrohq.reports.arranged_report"
	return {
		"detailed": {"kind": "Astrologer", "title": _("Detailed kundli report"), "blurb": _("Your kundli in full: the houses, the strength of each planet, the divisional charts, ashtakavarga, doshas and more."), "price": 0,
					 "description": _("Everything the kundli report has, and more: the houses, the strength of each planet, the divisional charts, ashtakavarga, arudhas, doshas and the panchang of the day you were born.\n\n"
									  "Made for you from the details you give. It is free: you can read it as a PDF as soon as it is made."),
					 "details": person, "maker": maker, "layout": "advanced", "modes": ["CORE_ADVANCED"], "view": "raftor_astrohq.report_view.customer_view", "free": person_free()},
		"dasha": {"kind": "Astrologer", "title": _("Dasha periods report"), "blurb": _("Every dasha system and the period you are in now."), "price": 0,
				  "description": _("The dasha periods of your life, system by system, with the one running today marked.\n\nMade for you from the details you give. It is free: you can read it as a PDF as soon as it is made."),
				  "details": person, "maker": maker, "layout": "dasha", "modes": ["DASHA_CALC"], "free": person_free()},
		"kp": {"kind": "KP astrologer", "title": _("KP chart report"), "blurb": _("Your chart the Krishnamurti way: cusps, star and sub lords, significators, and your Vimshottari dasha periods."), "price": 0,
			   "description": _("Your chart as a KP astrologer reads it: the ruling planets, each planet and house cusp with its sign, star, sub and sub-sub lord, the significators and the aspects. With it, your Vimshottari dasha periods, with the running one marked.\n\n"
								"Made for you from the details you give. It is free: you can read it as a PDF as soon as it is made."),
			   "details": person, "maker": maker, "layout": "kp", "modes": ["KP_SYSTEM", "DASHA_CALC"], "free": person_free()},  # the Vimshottari dasha only: the layout asks for that one,
		"panchang": {"kind": "Astrologer", "title": _("Panchang of your birth day"), "blurb": _("The tithi, nakshatra, yoga and karana you were born in, with when each begins and ends."), "price": 0,
					 "description": _("The panchang of the day and moment you were born, with the times each part begins and ends.\n\nMade for you from the details you give. It is free: you can read it as a PDF as soon as it is made."),
					 "details": person, "maker": maker, "layout": "panchang", "modes": ["PANCHANGA"], "free": person_free()},
	}


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
			# the order the page shows them in: leaders open with the astrologer, then the specialities by how much they are asked for (KP, numerology, tarot), then the pandit, vastu and palmistry
			"Astrologer": {"icon": "star", "word": "astrologer", "plural": "astrologers"},
			"KP astrologer": {"icon": "hash", "word": "KP astrologer", "plural": "KP astrologers"},
			"Numerologist": {"icon": "chart", "word": "numerologist", "plural": "numerologists"},
			"Tarot reader": {"icon": "cards", "word": "tarot reader", "plural": "tarot readers"},
			"Pandit ji": {"icon": "flame", "word": "pandit ji", "plural": "pandit ji"},
			"Vastu expert": {"icon": "home", "word": "vastu expert", "plural": "vastu experts"},
			"Palmist": {"icon": "hand", "word": "palmist", "plural": "palmists"},
			"Dream interpreter": {"icon": "moon", "word": "dream interpreter", "plural": "dream interpreters"},
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
		# What an astrologer can open from their booking (servicehq provider_bookings asks the vertical): the customer's chart.
		"booking_actions": "raftor_astrohq.report_view.booking_actions",
		# The reports a customer asks for from the shop, made from their own birth details (servicehq digital.py, free_reports.py). Each ships as an item switched off, at price 0
		# (both are free, always: they are given, not sold; the kundli and the match making report ship switched on, the rest wait for the business team to switch them on); servicehq asks the details and delivers the PDF the maker returns.
		"reports_soon": [{"title": _("Career report"), "icon": "briefcase"}, {"title": _("Love report"), "icon": "heart"}, {"title": _("Daily horoscope"), "icon": "sun"}, {"title": _("Tarot reading"), "icon": "cards"}],  # (what people ask for next: shown with "Coming soon", no way in yet)
		"reports": {
			"kundli": {"kind": "Astrologer", "icon": "chart", "title": _("Kundli report"), "blurb": _("Your birth chart made from your date, time and place of birth."), "price": 0, "on": True,
					   "description": _("Your kundli: the lagna, where each planet stood, the houses, the navamsa chart, your dasha periods and the panchang of the day you were born.\n\n"
										"Made for you from the details you give, by the same calculation astrologers use (Lahiri ayanamsa). It is free: you can read it as a PDF as soon as it is made."),
					   "details": {"fields": kundli_fields(), "validate": "raftor_astrohq.details.kundli_rules"}, "maker": "raftor_astrohq.reports.kundli_report", "view": "raftor_astrohq.report_view.customer_view",
					   # What only the free way does (servicehq free_reports.py): asks whose it is, keeps the details as a birth profile, says whose it is, and fills the form from the person's own profile.
					   "free": person_free()},
			"match": {"kind": "Astrologer", "icon": "rings", "title": _("Match making report"), "blurb": _("How well two birth charts match, by the eight kootas out of 36."), "price": 0, "on": True,
					  "description": _("The Ashtakoota (Guna Milan) score for a boy and a girl, koota by koota, out of 36, with the Moon sign and nakshatra of each and their manglik check.\n\n"
									   "Made from the details you give for both. It is free: you can read it as a PDF as soon as it is made."),
					  "details": {"fields": match_fields(), "validate": "raftor_astrohq.details.match_rules"}, "maker": "raftor_astrohq.reports.match_report",
					  "free": {"summary": "raftor_astrohq.reports.match_summary", "picker": "raftor_astrohq.reports.match_picker", "keep": "raftor_astrohq.reports.keep_match_profiles"}},  # each of the two is chosen from the saved people or written new, and kept for next time
			"numerology": {"kind": "Astrologer", "icon": "hash", "title": _("Numerology report"), "blurb": _("Your birth number and name number, by the rules of classical numerology."), "price": 0,
						   "description": _("Your birth number from the day you were born, the zodiac period, and the number of your name, each with what it is said to mean: your character, your dates, days and colours, the planet of your number and what the tradition links with it.\n\n"
											"Made from your name and date of birth. It is classical numerology, a traditional system, not a prediction. It is free: you can read it as a PDF as soon as it is made."),
						   "details": {"fields": numerology_fields(), "validate": "raftor_astrohq.details.numerology_rules"}, "maker": "raftor_astrohq.reports.numerology_report",
						   "free": {"summary": "raftor_astrohq.reports.numerology_summary"}},
			**arranged_reports(),
		},
		"kinds": {
			"Consultation": {"recommendation_mode": "Required", "line_title": "Seek guidance", "meta_title": "Seek guidance from verified astrologers | AstroHQ", "meta_description": "Choose an astrologer, KP astrologer, numerologist, tarot reader or pandit. See the fee before you book. Your first session is free.", "line_subtitle": "Every guide can help with every kind of question. Choose who to talk to, online now or at a time you choose.", "details": {"fields": [question()], "fields_for": "raftor_astrohq.details.consultation_fields", "topic_field": "question", "validate": "raftor_astrohq.details.consultation_rules"}},
			"Subscription": {"service": "daily pooja", "services": "daily poojas", "unit": "day", "units": "days", "book": "Subscribe", "details": {"fields": [*sankalp(), wish()]}},
			"Event": {"event_card": "Event Row", "meta_title": "Book blessings: pooja and havan | AstroHQ", "meta_description": "Book a pooja or havan at your home or online: Graha shanti, Kamna purti, Samasya samadhan and home services.", "listing_group": "Blessings", "kind_icons": {"Home services": "home", "Kamna purti": "heart", "Samasya samadhan": "shield", "Graha shanti": "sun"}, "at_customer": "At your home", "kind_label": "Kind of blessing", "topic_label": "What for", "line_title": "Book blessings", "line_subtitle": "Havans and poojas for what you wish for. Choose one and book your place.", "service": "havan", "services": "havans", "unit": "seat", "units": "seats", "book": "Register", "dated_name": "{0} Samuhik Pooja Blessings", "details": {"fields": sankalp(), "per_person": True}},
			"Report": {"details": {"fields": birth_details()}},  # not a service kind: what a report made from someone's birth asks (servicehq digital.py)
			"At the customer's place": {"details": {"fields": [*visit_fields(), *sankalp(), wish()]}},  # a pooja done at the home (servicehq personalised.AT_CUSTOMER)
			"Timed service": {"service": "pooja", "services": "poojas", "unit": "pooja", "units": "poojas", "book": "Book a pooja", "dated_name": "{0} Personal Pooja Blessings", "details": {"fields": [*sankalp(), wish()]}},
		},
	}
