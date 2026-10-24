"""What the glass card over a banner says about this moment, as the field values of cards from websitehq's library (panchang.widget_cards).

AstroHQ writes no markup and no look here: it answers a list of items, each naming a library card (`card`) and giving that card's own fields, and websitehq's pop-over section draws them, in the glass
the site chose. The first item is the card that stays on view (a Pill Card: the moon, the tithi and the chaugharia running now); the others open from it: the tithi with when it ends, the chaugharia as a
bar of its eight parts, the nakshatra, the sun, Rahu Kaal and Abhijit as they stand now, the yoga and the karana, and the way to ask a Pandit ji for a muhurat.

Nothing is worked out here: the astrology engine says when each tithi, nakshatra, yoga and karana begins and ends and where the chaugharia fall (panchang.py keeps its answers for a day); this picks the one
that holds the moment, from the answer of the day (sunrise to sunrise) that holds it and the day after, and says it in words.
"""
import datetime

from frappe import _

from raftor_astrohq.panchang_panes import clock, moment, span, tithi_name, when

TONE = {"good": "success", "avoid": "danger"}  # the library's tones for what the engine calls good and avoid


def lasting(gap: datetime.timedelta) -> str:
	"""1 h 12 min, 48 min, 2 h"""
	minutes = max(1, round(gap.total_seconds() / 60))
	hours, rest = divmod(minutes, 60)
	if hours and rest:
		return f"{hours} {_('h')} {rest} {_('min')}"
	return f"{hours} {_('h')}" if hours else f"{rest} {_('min')}"


def running(kind: str, answers: tuple, now: datetime.datetime) -> tuple[dict | None, dict | None]:
	"""The tithi, nakshatra, yoga or karana running at `now`, and the one after it, from the answers of days that follow each other. Each answer holds the one running at its sunrise and the one after it,
	so together they cover the moment; (None, None) when a day holds more of them than an answer lists and the moment falls in the gap (a karana is only half a tithi)."""
	seen, items = set(), []
	for answer in answers:
		for element in (answer[kind], answer[kind]["next"]):
			if element["begins"] not in seen:
				seen.add(element["begins"])
				items.append(element)
	items.sort(key=lambda e: moment(e["begins"]))
	for index, element in enumerate(items):
		if moment(element["begins"]) <= now < moment(element["ends"]):
			return element, items[index + 1] if index + 1 < len(items) else None
	return None, None


def moon_mark(illumination: float, waxing: bool) -> str:
	"""The moon as one of the eight phases the emoji font has, as it is lit now and seen from India (a waxing moon is lit on its right)."""
	lit = min(max(float(illumination), 0.0), 1.0)
	if lit < 0.03:
		return "🌑"
	if lit >= 0.97:
		return "🌕"
	if lit < 0.35:
		return "🌒" if waxing else "🌘"
	if lit < 0.65:
		return "🌓" if waxing else "🌗"
	return "🌔" if waxing else "🌖"


def _words(part: dict) -> str:
	return _("good") if part["quality"] == "good" else _("avoid")


def _parts(answer: dict, which: str) -> list[dict]:
	return answer["chaugharia"][which]


def _bar(state: dict) -> dict:
	"""The chaugharia as a Parts Bar: the eight parts of the half of the day it is in, the one running now, and what comes next."""
	now, base = state["now"], state["now"].date()
	cur, held, after = state["running"], state["held"], state["after"]
	part = cur["part"]
	which = part["of"]
	parts = _parts(held, which)
	following = cur["next"] or _parts(after, "day")[0]  # (the last part of the night is followed by the first of the day after)
	good_after = cur["next_good"] or next((p for p in _parts(after, "day") + _parts(after, "night") if p["quality"] == "good"), None)
	if which == "day":
		start, end = f"{_('Sunrise')} {clock(moment(held['sun']['rise']))}", f"{_('Sunset')} {clock(moment(held['sun']['set']))}"
	else:
		start, end = f"{_('Sunset')} {when(moment(held['sun']['set']), base)}", f"{_('Sunrise')} {when(moment(held['sun']['next_rise']), base)}"
	if part["quality"] == "good":
		note = f"{_('Good for {0} more').format(lasting(moment(part['to']) - now))} · {_('then')} {_(following['name'])} {_words(following)}"
	elif good_after:
		note = f"{_('Next good')}: {_(good_after['name'])} {span(good_after, base)} · {_('in {0}').format(lasting(moment(good_after['from']) - now))}"
	else:
		note = ""
	return {"card": "Parts Bar", "heading": _("Chaugharia"), "heading_note": f"{_(part['name'])} · {_words(part)} · {_('till')} {when(moment(part['to']), base)}", "heading_tone": TONE[part["quality"]],
			"steps": "\n".join(_(p["name"]) for p in parts), "tones": "\n".join(TONE[p["quality"]] for p in parts),
			"current": next((i for i, p in enumerate(parts, 1) if p["from"] == part["from"]), 1), "start_label": start, "end_label": end, "note": note}


def _window(label: str, window: dict, now: datetime.datetime, good: bool) -> dict:
	"""Rahu Kaal or Abhijit as it stands now: still to come, on now, or over, as a Stat Card."""
	start, end = moment(window["from"]), moment(window["to"])
	tone = "success" if good else "danger"
	if now < start:
		words = _("the day's best time") if good else _("starts in {0}").format(lasting(start - now))
	elif now < end:
		words = f"{_('on now')} · {_('till')} {clock(end)}"
	else:
		words, tone = _("over for today"), ""
	return {"card": "Stat Card", "label": label, "value": span(window, now.date()), "description": words, "tone": tone}


def cards(state: dict, links: dict) -> list[dict]:
	"""The items of the widget for this moment. `state` is panchang.state(place); `links` has "muhurat" (the address of the muhurat button, or None) and "place" (the town's name, for the line above the tithi)."""
	now, base = state["now"], state["now"].date()
	held, after, today, cur = state["held"], state["after"], state["calendar"], state["running"]
	tithi, then = running("tithi", (held, after), now)
	tithi = tithi or held["tithi"]  # (never in practice: a tithi is longer than half a day)
	nakshatra, _next_nakshatra = running("nakshatra", (held, after), now)
	yoga, _next_yoga = running("yoga", (held, after), now)
	karana, _next_karana = running("karana", (held, after), now)
	moon = moon_mark(today["moon"]["illumination"], today["moon"]["waxing"])
	out = [
		{"card": "Pill Card", "icon": moon, "title": tithi_name(tithi), "body": f"{_('Chaugharia')}: {_(cur['part']['name'])} · {_words(cur['part'])}", "tone": TONE[cur["part"]["quality"]]},
		{"card": "Feature Card", "layout": "Icon Left", "icon": moon, "tag": f"{_('Today')} · {_(now.strftime('%A'))} {now.day} {_(now.strftime('%b'))} · {links['place']}", "title": tithi_name(tithi),
		 "body": f"{_('till')} {when(moment(tithi['ends']), base)}" + (f" · {_('then')} {tithi_name(then)}" if then else "")},
		_bar(state),
	]
	if nakshatra:
		out.append({"card": "Stat Card", "label": _("Nakshatra"), "value": nakshatra["name"], "description": f"{_('till')} {when(moment(nakshatra['ends']), base)}"})
	sun = {"card": "Stat Card", "label": _("Sun"), "value": f"↑ {clock(moment(today['sun']['rise']))} · ↓ {clock(moment(today['sun']['set']))}"}
	if today["moon"].get("rise"):
		sun["description"] = f"{_('Moonrise')} {when(moment(today['moon']['rise']), base)}"
	out += [sun, _window(_("Rahu Kaal"), today["rahu_kaal"], now, False), _window(_("Abhijit"), today["abhijit"], now, True)]
	if yoga:
		out.append({"card": "Fact Card", "label": _("Yoga"), "value": yoga["name"], "description": f"{_('till')} {when(moment(yoga['ends']), base)}"})
	if karana:
		out.append({"card": "Fact Card", "label": _("Karana"), "value": karana["name"]})
	if links.get("muhurat"):
		out.append({"card": "Focus Card", "tag": _("Important work?"), "title": _("Ask a Pandit ji for a muhurat"), "body": _("A wedding, a new home, a vehicle, a new business"),
					"link_url": links["muhurat"], "link_label": _("Ask for a muhurat")})
	return out
