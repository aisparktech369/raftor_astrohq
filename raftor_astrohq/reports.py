"""The reports astrohq makes from what a customer gave. servicehq digital.py asks the maker of the item's own report (vocabulary.py "reports": the kundli report
and the match making report below) or, for an item with no report of its own, the makers listed in the hook rfhq_report_makers (the birth summary).

A maker is called as maker(item_code, details, buyer) when the report is to be made (at once for a free report, servicehq free_reports.py; after the order is paid for one with
a price, digital.py) and answers {"file_name", "content"}. It reads the details the customer gave (checked when they gave them: details.py), finds the place (places.py), asks the
astrology API for the chart (astrology.py) and lays out a PDF (report_pdf.py). When it cannot (the astrology service is down, a place is not found) it raises an error whose message
is plain words: servicehq leaves the report undelivered, writes the reason on it, tries again every hour and shows it to the business team."""
import datetime
import re
import unicodedata

import frappe
from dateutil.relativedelta import relativedelta
from frappe import _
from frappe.utils import cint, escape_html, format_date, getdate, today
from frappe.utils.pdf import get_pdf

from raftor_astrohq import answers, arrange, astrology, details as detail_rules, places, profiles, report_pdf as rp

PDF_OPTIONS = {"margin-top": "14mm", "margin-bottom": "18mm", "margin-left": "14mm", "margin-right": "14mm", "footer-center": "[page] / [topage]", "footer-font-size": "8", "footer-spacing": "5"}
CREDIT = "Calculated with the Lahiri ayanamsa. Place data: GeoNames (geonames.org), licensed CC BY 4.0."
# The eight kootas in their usual order: (name, what it looks at, the key in the engine's answer, the most it can score)
KOOTAS = [
	("Varna", "Temperament and ego", "varna", 1), ("Vashya", "Mutual attraction and influence", "vasiya", 2), ("Tara", "Health and well-being, from the birth stars", "tara", 3),
	("Yoni", "Physical and instinctive match", "yoni", 4), ("Graha Maitri", "Friendship of the Moon sign lords: mental match", "adhipathi", 5), ("Gana", "Nature and temperament", "gana", 6),
	("Bhakoot", "Love, family welfare and prosperity, from the Moon signs", "rasi", 7), ("Nadi", "Health and heredity", "nadi", 8),
]


def birth_summary(item_code: str, details: dict, buyer: str) -> dict | None:
	"""A one-page PDF of the birth details the customer gave, for an item that is a report. None when the details are missing."""
	if not details.get("birth_date") or not details.get("report_name"):
		return None
	born = getdate(details["birth_date"])
	title = frappe.db.get_value("Item", item_code, "item_name") or _("Your report")
	rows = [(_("Name"), details["report_name"]), (_("Date of birth"), format_date(born)), (_("Weekday of birth"), born.strftime("%A")),
			(_("Time of birth"), details.get("birth_time") or "-"), (_("Place of birth"), details.get("birth_place") or "-")]
	body = "".join(f"<tr><th>{escape_html(label)}</th><td>{escape_html(str(value))}</td></tr>" for label, value in rows)
	html = (f"<html><head><meta charset='utf-8'><style>body{{font-family:sans-serif;margin:40px}}h1{{color:#3a1a4a}}th{{text-align:left;padding:6px 18px 6px 0;color:#555}}"
			f"td{{padding:6px 0}}</style></head><body><h1>{escape_html(title)}</h1><table>{body}</table>"
			f"<p style='margin-top:30px;color:#777'>{escape_html(_('Made for you from the details you gave.'))}</p></body></html>")
	return {"file_name": f"{frappe.scrub(title)}.pdf", "content": get_pdf(html)}


# ---- what a free report does besides making the file (servicehq free_reports.py, vocabulary "free") ----
def keep_birth_profile(user: str, details: dict) -> None:
	"""A free kundli's details become a birth profile of the person, so they are not typed again (a consultation needs one too): their own ("You") when the report is for
	them, a family member's when it is for someone else (the person's asking is their confirmation that they may keep it). The profile the person already has is never
	overwritten by a report, and the same person is not kept twice."""
	relation = details.get("whose") or profiles.SELF
	account = frappe.get_doc("User", user)
	if relation == profiles.SELF and profiles.you_row(account):
		return
	name, born = str(details.get("report_name") or "").strip(), str(details.get("birth_date") or "")
	if any(str(row.full_name).strip().lower() == name.lower() and str(row.date_of_birth) == born for row in account.get(profiles.TABLE) or []):
		return
	account.append(profiles.TABLE, {"relationship": relation, "full_name": name, "date_of_birth": born, "time_of_birth": details.get("birth_time") or "", "time_unknown": 0,
									"place_of_birth": details.get("birth_place") or "", "permission_given": 0 if relation == profiles.SELF else 1})
	account.flags.ignore_permissions = True
	account.save()


def kundli_account_name(details: dict) -> str:
	"""The name for a new account: the person's own, when the kundli is theirs."""
	return str(details.get("report_name") or "").strip() if (details.get("whose") or profiles.SELF) == profiles.SELF else ""


def kundli_summary(details: dict) -> str:
	return str(details.get("report_name") or "").strip()


def match_summary(details: dict) -> str:
	names = [str(details.get(key) or "").strip() for key in ("boy_name", "girl_name")]
	return _("{0} and {1}").format(*names) if all(names) else ""


def _usable_profiles(user: str) -> list:
	"""The person's saved birth profiles a report can be made from: complete, and with the time of birth known (the report needs it)."""
	rows = frappe.get_doc("User", user).get(profiles.TABLE) or []
	return [row for row in rows if not row.time_unknown and row.time_of_birth and not profiles.row_errors(profiles.row_values(row))]


def _picker_option(row, keys: dict[str, str], extra: dict | None = None) -> dict:
	"""One saved person as a choice: their name and how they are related to the person, and what choosing them fills in (a report's own names for the details)."""
	words = {o["value"]: o["label"] for o in detail_rules.whose()["options"]}
	relation = words.get(row.relationship, row.relationship)
	return {"value": row.name, "label": f"{row.full_name} · {relation}" if row.relationship != profiles.SELF else f"{row.full_name} · {_('You')}",
			"fills": {keys["name"]: row.full_name, keys["date"]: str(row.date_of_birth), keys["time"]: row.time_of_birth, keys["place"]: row.place_of_birth, **(extra or {})}}


def kundli_picker(user: str) -> list[dict]:
	"""For a report about one person: a choice among the people the customer has saved, filled in when chosen (their own first), or "someone new" to write the details. Nothing when none is saved."""
	rows = _usable_profiles(user)
	if not rows:
		return []
	keys = detail_rules.person_keys()
	you = next((row for row in rows if row.relationship == profiles.SELF), None)
	return [{"name": "profile", "label": _("Who is it for?"), "type": "select", "placeholder": _("Someone new"), "default": you.name if you else "",
			 "options": [_picker_option(row, keys, {"whose": row.relationship}) for row in rows], "controls": ["whose", *keys.values()],
			 "hint": _("Choose someone you have saved, or someone new. Only people whose time of birth is known are listed.")}]


def match_picker(user: str) -> list[dict]:
	"""For a match between two people: each is chosen from the people the customer has saved (any two of them), or written as someone new."""
	rows = _usable_profiles(user)
	if not rows:
		return []
	out = []
	for prefix, label in (("boy_", _("The boy")), ("girl_", _("The girl"))):
		keys = detail_rules.person_keys(prefix)
		out.append({"name": prefix + "profile", "label": label, "type": "select", "placeholder": _("Someone new"), "default": "", "options": [_picker_option(row, keys) for row in rows],
					"controls": list(keys.values())})
	return out


def keep_match_profiles(user: str, details: dict) -> None:
	"""The two people of a free match are kept as birth profiles, so that they are not typed again and can be matched with anyone else saved (a family member's, with the person's
	confirmation that they may: their asking is it). Someone already saved (the same name and day) is not kept twice."""
	account = frappe.get_doc("User", user)
	saved = {(str(row.full_name).strip().lower(), str(row.date_of_birth)) for row in account.get(profiles.TABLE) or []}
	changed = False
	for prefix in ("boy_", "girl_"):
		k = detail_rules.person_keys(prefix)
		name, born = str(details.get(k["name"]) or "").strip(), str(details.get(k["date"]) or "")
		if not name or not born or (name.lower(), born) in saved:
			continue
		account.append(profiles.TABLE, {"relationship": "Other", "full_name": name, "date_of_birth": born, "time_of_birth": details.get(k["time"]) or "", "time_unknown": 0,
										"place_of_birth": details.get(k["place"]) or "", "permission_given": 1})
		saved.add((name.lower(), born))
		changed = True
	if changed:
		account.flags.ignore_permissions = True
		account.save()


def kundli_prefill(user: str) -> dict:
	"""A signed-in person's own profile as the answers of the kundli form (their time of birth must be known: the report needs it)."""
	row = profiles.you_row(frappe.get_doc("User", user))
	if not row or row.time_unknown or not row.time_of_birth:
		return {}
	return {"whose": profiles.SELF, "report_name": row.full_name, "birth_date": str(row.date_of_birth), "birth_time": row.time_of_birth, "birth_place": row.place_of_birth}


# ---- the kundli report ----
def _brand() -> str:
	return frappe.db.get_single_value("Website Settings", "app_name") or "AstroHQ"


def _person(details: dict, prefix: str = "") -> dict:
	"""One person from a report's answers: {"name", "born" (the local date and time), "place" (as written)}."""
	k = detail_rules.person_keys(prefix)
	return {"name": details.get(k["name"]) or "-", "born": detail_rules.born_at(details, prefix), "place_text": details.get(k["place"]) or ""}


def _find(person: dict) -> dict:
	"""The place of the person's birth with its coordinates and the time zone of the day (places.py), or an error saying what is wrong with it."""
	return places.lookup(person["place_text"], person["born"])


def _numbers(person: dict, place: dict, gender: str | None = None) -> dict:
	born = person["born"]
	return astrology.birth_data({"date_of_birth": born.date(), "time_of_birth": born.strftime("%H:%M"), "time_unknown": 0}, place["latitude"], place["longitude"], place["timezone_offset"], gender)


def _span(start: datetime.date, end: datetime.date) -> str:
	gap = relativedelta(end, start)
	return f"{gap.years} years {gap.months} months {gap.days} days"


def _short_date(value) -> str:
	"""A date as 28 Jun 1971, or a dash when the engine gave none (getdate("") would answer today)."""
	return getdate(value).strftime("%d %b %Y") if value else "-"


def _running(period: dict, on: datetime.date) -> bool:
	"""Whether a dasha period (its start_date and end_date as the engine writes them) is running on that day; one with no end date runs on."""
	start, end = period.get("start_date"), period.get("end_date")
	return bool(start) and getdate(start) <= on and (not end or on <= getdate(end))


def _lord(text: str) -> str:
	return rp.PLANETS.get(rp.planet_code(text) or "", str(text))


def kundli_context(person: dict, place: dict, chart: dict, panchanga: dict, on: datetime.date) -> dict:
	"""Everything the kundli page shows, ready to print, from the engine's SUPER_BASIC and PANCHANGA answers."""
	positions = {rp.planet_code(p["planet"]): p for p in chart["planetary_positions"]}
	lagna = chart["lagna"]
	lagna_sign = rp.sign_index(lagna["sign"])
	sun, moon = positions["Su"]["absolute_longitude"], positions["Mo"]["absolute_longitude"]
	return {
		"name": person["name"], "born": person["born"], "place": place, "lagna_sign": lagna_sign, "lagna": lagna, "positions": positions, "panchang": {**rp.panchang_of(sun, moon), **{
			key: panchanga.get(key) for key in ("vaara", "day_lord", "sunrise", "sunset")}},
		"d1": chart["divisional_charts"]["D1"], "d9": chart["divisional_charts"]["D9"], "dasha": chart["dasha_sequences"]["vimshottari"]["mahadasha"], "on": on,
	}


def kundli_html(c: dict) -> str:
	place, positions, lagna, panchang, born = c["place"], c["positions"], c["lagna"], c["panchang"], c["born"]
	moon, sun = positions["Mo"], positions["Su"]
	moon_sign = moon["sign_index"]
	sunrise, sunset = (str(panchang.get(key) or "")[:5] for key in ("sunrise", "sunset"))
	civil = born.strftime("%A")  # the weekday the customer knows; the panchang's day runs from sunrise to sunrise and may be the one before
	vaara = panchang.get("vaara") or civil
	weekday = f"{vaara} (lord {panchang.get('day_lord')})" + ("" if vaara == civil else " " + _("(the day runs from sunrise to sunrise: you were born before sunrise on {0})").format(civil))
	facts = rp._facts([
		(_("Name"), c["name"]),
		(_("Born"), f"{civil}, {rp.long_date(born.date())}, {born.strftime('%H:%M')}"),
		(_("Place"), f"{place['name']} ({place['latitude']:.2f}\u00b0{'N' if place['latitude'] >= 0 else 'S'}, {abs(place['longitude']):.2f}\u00b0{'E' if place['longitude'] >= 0 else 'W'})"),
		(_("Time zone"), f"{rp.offset_text(place['timezone_offset'])} ({place['timezone']}), as it was on that day"),
		(_("Lagna (ascendant)"), f"{rp.sign_label(c['lagna_sign'])}, {rp.degrees(lagna['degree'])}; lord {lagna.get('lord') or rp.SIGN_LORDS[c['lagna_sign']]}"),
		(_("Moon sign (Rashi)"), rp.sign_label(moon_sign)),
		(_("Birth star (Nakshatra)"), rp.nakshatra_label(moon["nakshatra_index"], moon["pada"]) + f"; lord {_lord(moon['nakshatra_lord'])}"),
		(_("Sun sign"), rp.sign_label(sun["sign_index"])),
	])
	pan = rp._facts([
		(_("Weekday"), weekday), (_("Tithi"), panchang["tithi"]), (_("Nakshatra"), rp.nakshatra_label(moon["nakshatra_index"])),
		(_("Yoga"), panchang["yoga"]), (_("Karana"), panchang["karana"]), (_("Sunrise and sunset"), f"{sunrise} and {sunset} (local time)"),
	])
	look = rp.site_look()
	charts = (f'<table class="charts"><tr><td>{rp.diamond_chart_svg(c["d1"]["chart"], c["lagna_sign"], _("Lagna chart (Rasi, D1)"), look=look)}</td>'
			  f'<td>{rp.diamond_chart_svg(c["d9"]["chart"], c["d9"]["ascendant_house"], _("Navamsa chart (D9)"), look=look)}</td></tr></table>'
			  f'<p class="note">{escape_html(_("The number in each house is its sign (1 is Aries). House 1 is the top diamond and the houses run anticlockwise. R means the planet is moving backwards."))}</p>')
	rows = [[_("Lagna"), rp.sign_label(c["lagna_sign"]), rp.degrees(lagna["degree"]), "-", "1", ""]]
	for code in ("Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"):
		p = positions[code]
		rows.append([rp.PLANETS[code], rp.sign_label(p["sign_index"]), rp.degrees(p["longitude"]), rp.nakshatra_label(p["nakshatra_index"], p["pada"]), str(p["house"]), _("Yes") if p["is_retrograde"] else ""])
	planets = rp._table([[escape_html(str(cell)) for cell in row] for row in rows], [_("Planet"), _("Sign"), _("Degree"), _("Nakshatra"), _("House"), _("Retrograde")])
	return rp.page(_("Kundli report"),
		f'{rp.masthead(look, _brand())}<h1>{escape_html(_("Kundli report"))}</h1><p class="sub">{escape_html(c["name"])}</p>'
		f'<h2>{escape_html(_("Birth details"))}</h2>{facts}<h2>{escape_html(_("Panchang of the day"))}</h2>{pan}'
		f'<h2>{escape_html(_("Birth chart"))}</h2>{charts}'
		f'<h2 style="page-break-before: always">{escape_html(_("Planets"))}</h2>{planets}'
		f'<h2>{escape_html(_("Vimshottari dasha"))}</h2>{_dasha_html(c)}',
		_brand(), CREDIT + " " + _("Made for you on {0}.").format(rp.long_date(c["on"])), look)


def _dasha_html(c: dict) -> str:
	on = c["on"]
	mahadashas = c["dasha"]
	born_day = c["born"].date()
	first = mahadashas[0]
	left = _span(born_day, getdate(first["end_date"])) if first.get("end_date") and _running(first, born_day) else ""
	intro = (f'<p>{escape_html(_("At birth the {0} dasha was running, with {1} still to run.").format(_lord(first["lord"]), left))}</p>' if left else "")
	rows, classes = [], {}
	for m in mahadashas:
		running = _running(m, on)
		row = [escape_html(_lord(m["lord"])), escape_html(_short_date(m.get("start_date"))), escape_html(_short_date(m.get("end_date"))), escape_html(_("Running now") if running else "")]
		rows.append(row)
		if running:
			classes[id(row)] = "now"
	table = rp._table(rows, [_("Mahadasha"), _("From"), _("To"), ""], classes)
	current = next((m for m in mahadashas if _running(m, on)), None)
	sub = ""
	if current:
		subrows, subclasses = [], {}
		for a in current.get("antardasha") or []:
			running = _running(a, on)
			row = [escape_html(f"{_lord(current['lord'])} / {_lord(a['lord'])}"), escape_html(_short_date(a.get("start_date"))), escape_html(_short_date(a.get("end_date"))), escape_html(_("Running now") if running else "")]
			subrows.append(row)
			if running:
				subclasses[id(row)] = "now"
		sub = f'<h2>{escape_html(_("The {0} dasha: its antardashas").format(_lord(current["lord"])))}</h2>' + rp._table(subrows, [_("Antardasha"), _("From"), _("To"), ""], subclasses)
	note = f'<p class="note">{escape_html(_("The dasha periods follow the Moon\'s position at birth (Vimshottari, 120 years). Dates are as on {0}.").format(rp.long_date(on)))}</p>'
	return intro + table + sub + note


def _pdf(html: str) -> bytes:
	return get_pdf(html, dict(PDF_OPTIONS))


def _file_name(prefix: str, *names: str) -> str:
	"""prefix-names.pdf with the people's names as plain lower-case letters and digits only (what a customer types can never become a path or a header)."""
	plain = lambda name: re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()).strip("-")
	slug = "-".join(part for part in (plain(name) for name in names) if part)[:100].strip("-") or "report"
	return f"{prefix}-{slug}.pdf"


def kundli_report(item_code: str, details: dict, buyer: str) -> dict:
	"""The kundli report: a PDF of the birth chart, the planets, the navamsa, the dasha and the panchang of the day, made from the details the customer gave."""
	person = _person(details)
	place = _find(person)
	numbers = _numbers(person, place)
	chart = astrology.chart(numbers, "SUPER_BASIC")
	panchanga = astrology.chart(numbers, "PANCHANGA")["panchanga"]
	html = kundli_html(kundli_context(person, place, chart, panchanga, getdate(today())))
	return {"file_name": _file_name("kundli-report", person["name"]), "content": _pdf(html)}


# ---- the reports made from a layout ----
def report_entry(item_code: str) -> dict:
	"""What the vocabulary says about the report an item is (its title, its layout, the modes it is made from)."""
	from raftor_servicehq import kinds

	name, vertical = frappe.db.get_value("Item", item_code, ["custom_report_kind", "custom_vertical"]) or ("", "")
	return kinds.report(vertical, name) if name else {}


def shown() -> str:
	"""What a customer's report shows: "reviewed" (the sections an astrologer has checked) or, when the setting says so (a demonstration), "all"."""
	return "all" if cint(frappe.db.get_single_value("Astrology API Settings", "show_unreviewed")) else "reviewed"


def born_line(person: dict, place: dict) -> str:
	"""Who, when and where, as the line under a report's title."""
	born = person["born"]
	return f"{person['name']} · {born.strftime('%A')}, {rp.long_date(born.date())}, {born.strftime('%H:%M')} · {place['name']}"


def arranged_report(item_code: str, details: dict, buyer: str) -> dict:
	"""A report made from a layout (arrange.py, layouts/): the engine's answer for the person in the layout's mode (kept, so a second report of the same birth costs no call), laid out by the layout the
	vocabulary names, in the site's brand, as a PDF. A customer's report has the sections an astrologer has checked (`shown`)."""
	entry = report_entry(item_code)
	if not entry.get("layout") or not entry.get("modes"):
		frappe.throw(_("This report has no layout to be made from."))
	layout = arrange.layout_named(entry["layout"])
	show = shown()
	if show == "reviewed" and not any(section.get("reviewed") for section in layout["sections"]):
		frappe.throw(_("Nothing in this report has been checked by an astrologer yet, so it cannot be given."))
	person = _person(details)
	place = _find(person)
	numbers = {**_numbers(person, place), **(layout.get("ask") or {})}
	data = {}
	for mode in entry["modes"]:  # a report can need more than one engine mode (a KP chart with its dasha): each answer is kept on its own, and read together here
		data.update(answers.get(buyer, numbers, mode))
	on = getdate(today())
	html = arrange.html(data, {**layout, "title": entry.get("title") or layout.get("title")}, brand=_brand(), credit=CREDIT + " " + _("Made for you on {0}.").format(rp.long_date(on)), today=on,
						subject=born_line(person, place), look=rp.site_look(), show=show)
	return {"file_name": _file_name(f"{entry['layout']}-report", person["name"]), "content": _pdf(html)}


# ---- the match making report ----
def match_context(boy: dict, girl: dict, boy_place: dict, girl_place: dict, match: dict, boy_chart: dict, girl_chart: dict, on: datetime.date) -> dict:
	return {"boy": boy, "girl": girl, "places": (boy_place, girl_place), "match": match, "charts": (boy_chart, girl_chart), "on": on}


def _person_card(person: dict, place: dict, chart: dict) -> list[str]:
	positions = {rp.planet_code(p["planet"]): p for p in chart["planetary_positions"]}
	moon = positions["Mo"]
	return [person["name"], f"{rp.long_date(person['born'].date())}, {person['born'].strftime('%H:%M')}", place["name"], rp.sign_label(moon["sign_index"]),
			rp.nakshatra_label(moon["nakshatra_index"], moon["pada"]), rp.sign_label(rp.sign_index(chart["lagna"]["sign"]))]


MANGLIK_HOUSES = "2nd, 4th, 7th, 8th or 12th"  # the houses from the lagna in which Mars makes the dosha (the engine's rule, checked in the hub's tests)


def _ordinal(number: int) -> str:
	return {1: "1st", 2: "2nd", 3: "3rd"}.get(number, f"{number}th")


def _mars_house(chart: dict) -> str:
	mars = next(p for p in chart["planetary_positions"] if rp.planet_code(p["planet"]) == "Ma")
	return _("{0} from the lagna").format(_ordinal(int(mars["house"])))


def _verdict(total: float) -> str:
	if total >= 33:
		return _("33 and above is usually read as excellent.")
	if total >= 25:
		return _("25 to 32 is usually read as good.")
	if total >= 18:
		return _("18 to 24 is usually read as acceptable.")
	return _("Below 18 is usually read as not suitable without remedies.")


def match_html(c: dict) -> str:
	boy, girl = c["boy"], c["girl"]
	scores, doshas = c["match"]["compatibility"], c["match"]["doshas"]
	total, best = float(scores["total_score"]), 36
	labels = [_("Name"), _("Born"), _("Place"), _("Moon sign (Rashi)"), _("Birth star (Nakshatra)"), _("Lagna")]
	cards = [_person_card(boy, c["places"][0], c["charts"][0]), _person_card(girl, c["places"][1], c["charts"][1])]
	people = rp._table([[escape_html(label), escape_html(a), escape_html(b)] for label, a, b in zip(labels, cards[0], cards[1])], ["", _("Boy"), _("Girl")])
	rows = [[escape_html(name), escape_html(_(what)), f'<td class="num">{scores[key]:g}</td>', f'<td class="num">{best_score}</td>'] for name, what, key, best_score in KOOTAS]
	table = rp._table(rows + [[f'<b>{escape_html(_("Total"))}</b>', "", f'<td class="num total">{total:g}</td>', '<td class="num">36</td>']], [_("Koota"), _("What it looks at"), _("Scored"), _("Out of")])
	bar = f'<div class="bar"><div style="width: {max(0, min(100, total / best * 100)):.0f}%"></div></div>'
	present = lambda flags: _("Present") if flags.get("manglik") else _("Not present")
	manglik = rp._table([[escape_html(_("Mars is in the house")), escape_html(_mars_house(c["charts"][0])), escape_html(_mars_house(c["charts"][1]))],
						 [escape_html(_("Manglik dosha")), escape_html(present(doshas["person1"])), escape_html(present(doshas["person2"]))]], ["", _("Boy"), _("Girl")])
	look = rp.site_look()
	return rp.page(_("Match making report"),
		f'{rp.masthead(look, _brand())}<h1>{escape_html(_("Match making report"))}</h1><p class="sub">{escape_html(boy["name"])} {escape_html(_("and"))} {escape_html(girl["name"])}</p>'
		f'<h2>{escape_html(_("The two people"))}</h2>{people}'
		f'<h2>{escape_html(_("Ashtakoota (Guna Milan)"))}</h2><p class="total">{escape_html(_("{0} out of 36").format(f"{total:g}"))} ({total / best * 100:.0f}%)</p>{bar}<br>{table}'
		f'<p class="note">{escape_html(_verdict(total))} {escape_html(_("A guideline, not a decision: a full match is read with the two charts and by an astrologer."))}</p>'
		f'<h2>{escape_html(_("Manglik"))}</h2>{manglik}'
		f'<p class="note">{escape_html(_("Manglik is counted when Mars stands in the {0} house from the lagna. Astrologers also read it from the Moon and from Venus, and look at exceptions, so ask an astrologer before you decide anything on it.").format(MANGLIK_HOUSES))}</p>',
		_brand(), CREDIT + " " + _("Made for you on {0}.").format(rp.long_date(c["on"])), look)


def match_report(item_code: str, details: dict, buyer: str) -> dict:
	"""The match making report: the Ashtakoota score of a boy and a girl koota by koota, the Moon sign and nakshatra of each and their manglik check."""
	boy, girl = _person(details, "boy_"), _person(details, "girl_")
	boy_place, girl_place = _find(boy), _find(girl)
	boy_numbers, girl_numbers = _numbers(boy, boy_place, "Male"), _numbers(girl, girl_place, "Female")
	match = astrology.chart(boy_numbers, "MATCH_CALC", partner=girl_numbers)
	boy_chart, girl_chart = astrology.chart(boy_numbers, "SUPER_BASIC"), astrology.chart(girl_numbers, "SUPER_BASIC")
	html = match_html(match_context(boy, girl, boy_place, girl_place, match, boy_chart, girl_chart, getdate(today())))
	return {"file_name": _file_name("match-making-report", boy["name"], girl["name"]), "content": _pdf(html)}


# ---- the numerology report (Cheiro's numerology, calculated by the engine) ----
NUMEROLOGY_CREDIT = "Cheiro's numerology, from Cheiro's Book of Numbers. A historical doctrine, not a fact or a prediction."


def numerology_summary(details: dict) -> str:
	return _("For {0}").format(details.get("report_name") or "")


def numerology_context(name: str, born: datetime.date, answer: dict, on: datetime.date) -> dict:
	return {"name": name, "born": born, "answer": answer, "on": on}


def _steps(steps: list[str]) -> str:
	return escape_html("; ".join(steps))


def numerology_html(c: dict) -> str:
	answer, born = c["answer"], c["born"]
	birth, name, zodiac = answer["birth"], answer["name"], answer.get("zodiac")
	profile = birth["profile"]
	look = rp.site_look()
	joined = lambda words: ", ".join(words)
	number_rows = [[escape_html(_("Day of birth")), escape_html(str(birth["day"]))], [escape_html(_("Birth number")), f'<td class="num total">{birth["number"]}</td>'],
				   [escape_html(_("How it is found")), escape_html(_steps(birth["steps"]))], [escape_html(_("Planet (Cheiro)")), escape_html(profile["cheiro_planet"])],
				   [escape_html(_("Days of the month of this number")), escape_html(joined(str(d) for d in profile["days"]))],
				   [escape_html(_("Colours")), escape_html(joined(profile["colours"]))], [escape_html(_("Jewels")), escape_html(joined(profile["jewels"]))]]
	if birth.get("compound"):
		number_rows.insert(2, [escape_html(_("Compound")), escape_html(str(birth["compound"]))])
	body = (f'{rp.masthead(look, _brand())}<h1>{escape_html(_("Numerology report"))}</h1>'
			f'<p class="sub">{escape_html(c["name"])} · {escape_html(born.strftime("%A"))}, {escape_html(rp.long_date(born))}</p>'
			f'<h2>{escape_html(_("Your birth number"))}</h2>{rp._table(number_rows)}'
			f'<p class="note">{escape_html(_("Cheiro describes this number as: {0}.").format(profile["character"]))} ({escape_html(_("Cheiro, Chapter {0}").format(profile["source"]["chapter"]))})</p>')
	meaning = birth.get("compound_meaning")
	if meaning:
		body += f'<p class="note">{escape_html(_numerology_meaning(meaning))}</p>'
	if zodiac:
		periods = "; ".join(f'{p["sign"]} ({p["from"]} to {p["to"]})' for p in zodiac["periods"])
		body += f'<h2>{escape_html(_("The zodiac period"))}</h2><p>{escape_html(periods)}</p>' + (f'<p class="note">{escape_html(zodiac["note"])}</p>' if zodiac.get("note") else "")
	word_rows = [[escape_html(w["word"]), escape_html(" + ".join(f'{p["letter"]}{p["value"]}' for p in w["letters"])), f'<td class="num">{w["total"]}</td>', f'<td class="num">{w["root"]}</td>'] for w in name["words"]]
	combined = name["combined"]
	word_rows.append([f'<b>{escape_html(_("The name"))}</b>', escape_html(" + ".join(str(r) for r in combined["roots"])), f'<td class="num total">{combined["total"]}</td>', f'<td class="num total">{combined["root"]}</td>'])
	body += (f'<h2>{escape_html(_("Your name number"))}</h2><p>{escape_html(_("Counted with Cheiro\'s Mystic Alphabet, for the name {0}.").format(name["spelling_counted"]))}</p>'
			 f'{rp._table(word_rows, [_("Word"), _("Letters"), _("Total"), _("Root")])}')
	if combined.get("compound_meaning"):
		body += f'<p class="note">{escape_html(_numerology_meaning(combined["compound_meaning"]))}</p>'
	body += (f'<h2>{escape_html(_("How to read this"))}</h2><p class="note">{escape_html(answer["safeguard"])} '
			 f'{escape_html(_("The same name can give another number in other numerology methods. Ask the numerology guide or a live numerologist (on the site, under Seek guidance) about what it means for you."))}</p>')
	return rp.page(_("Numerology report"), body, _brand(), NUMEROLOGY_CREDIT + " " + _("Made for you on {0}.").format(rp.long_date(c["on"])), look)


def _numerology_meaning(meaning: dict) -> str:
	"""What Cheiro says of a compound. A warning compound is given as a symbol only, never as a prediction (the engine marks it sensitive)."""
	label = _("Compound {0} (Cheiro, Chapter XIII)").format(meaning["compound"])
	if meaning.get("sensitive"):
		return f"{label}: " + _("Cheiro treats this as a cautionary symbol. It is a historical reading, not a prediction about you.")
	return f"{label}: {meaning['meaning']}"


def numerology_report(item_code: str, details: dict, buyer: str) -> dict:
	"""The numerology report: a PDF of the birth number, the zodiac period and the name number by Cheiro's rules, every sum by the engine, from the name and the date of birth the customer gave."""
	name = str(details.get("report_name") or "").strip()
	born = getdate(details.get("birth_date"))
	answer = astrology.numerology(day=born.day, month=born.month, name=name)
	html = numerology_html(numerology_context(name, born, answer, getdate(today())))
	return {"file_name": _file_name("numerology-report", name), "content": _pdf(html)}
