"""The panes of the Panchang page (panchang.py): the day's panchang (with the sun and the moon beside it), the chaugharia, the times to know, the next seven days, and the way to ask a Pandit ji for a muhurat.

They are made like the panes of a chart (panes.py; report_view.py puts them on a board) but from the engine's answer for a day (`PANCHANGA_DAY`): `data` is {"day": that answer, "week": a list of them}
and `ctx` has "now" (the moment, in the town's time zone), "date" (the day shown), "place", "link" (a function: a date to the address of that day's page) and "muhurat" (the address of the muhurat
button, or None). A pane answers {"body": html, "summary": one line} or None. Nothing is worked out here: each time is written the way the engine gave it, and the part that is running is
the one whose times hold the moment `now`. Every word the engine wrote is escaped.
"""
import datetime
import math

from frappe import _

from raftor_astrohq import places
from raftor_astrohq.panes import esc, table

NEXT_DAY, DAY_BEFORE = " next day", " the day before"


def moment(text: str | None) -> datetime.datetime | None:
	return datetime.datetime.fromisoformat(text) if text else None


def clock(at: datetime.datetime) -> str:
	"""6:31 am, 1:38 pm"""
	return f"{at.hour % 12 or 12}:{at.minute:02d} {'am' if at.hour < 12 else 'pm'}"


def when(at: datetime.datetime | None, base: datetime.date) -> str:
	"""A time on the day shown as 1:38 pm; on the next day as 1:38 pm next day; on another as 1:38 pm on 25 Oct."""
	if at is None:
		return ""
	gap = (at.date() - base).days
	if gap == 0:
		return clock(at)
	if gap == 1:
		return clock(at) + _(NEXT_DAY)
	if gap == -1:
		return clock(at) + _(DAY_BEFORE)
	return f"{clock(at)} {_('on')} {at.day} {at.strftime('%b')}"


def span(first: dict, base: datetime.date) -> str:
	"""9:18–10:41 am: the am or pm said once when it is the same at both ends."""
	a, b = moment(first["from"]), moment(first["to"])
	left = clock(a)
	right = when(b, base)
	return f"{left[:-3]}–{right}" if left[-2:] == clock(b)[-2:] and a.date() == b.date() else f"{when(a, base)}–{right}"


def tithi_name(element: dict) -> str:
	"""Shukla Trayodashi; the full moon and the new moon are only Purnima and Amavasya."""
	return element["name"] if element["name"] in ("Purnima", "Amavasya") else f"{element['paksha']} {element['name']}"


def _label(kind: str) -> str:
	return {"tithi": _("Tithi"), "nakshatra": _("Nakshatra"), "yoga": _("Yoga"), "karana": _("Karana"), "weekday": _("Weekday")}[kind]


def _name(kind: str, element: dict) -> str:
	return tithi_name(element) if kind == "tithi" else element["name"]


def _facts(rows: list[tuple[str, str]]) -> str:
	body = "".join(f'<tr><th scope="row">{esc(label)}</th><td>{esc(value)}</td></tr>' for label, value in rows)
	return f'<table class="rv-facts"><tbody>{body}</tbody></table>'


def moon_picture(illumination: float, waxing: bool, label: str) -> str:
	"""The moon as it is lit, as a picture: a dark disc and the lit part (on the right while it waxes, as seen from India). The lit part is a polygon: the report's pictures have no curves, and a hundred points are as round as a hand can see."""
	lit = min(max(float(illumination), 0.0), 1.0)
	steps, radius = 36, 10.0
	points = []
	if lit > 0.004:
		points = [(radius * math.sin(math.radians(a)), -radius * math.cos(math.radians(a))) for a in (180 * i / steps for i in range(steps + 1))]  # down the right edge, from the top
		reach, side = radius * abs(1 - 2 * lit), (-1 if lit > 0.5 else 1)  # the line between light and dark: an ellipse, left of the middle for a gibbous moon, right of it for a crescent
		points += [(side * reach * math.sin(math.radians(a)), -radius * math.cos(math.radians(a))) for a in (180 - 180 * i / steps for i in range(steps + 1))]
	flip = 1 if waxing else -1
	shape = f'<polygon class="rv-moon-lit" points="{" ".join(f"{flip * x:.2f},{y:.2f}" for x, y in points)}"/>' if points else ""
	return (f'<svg class="rv-moon" viewBox="-11 -11 22 22" role="img" aria-label="{esc(label)}"><rect class="rv-moon-dark" x="-10" y="-10" width="20" height="20" rx="10" ry="10"/>{shape}</svg>')


def _sky(day: dict, base: datetime.date) -> str:
	"""The moon (its picture and how much of it is lit) and when the sun and the moon rise and set, to stand beside the day's panchang."""
	moon = day["moon"]
	lit = f"{round(float(moon['illumination']) * 100)}% {_('lit')}"
	phase = _("Waxing") if moon["waxing"] else _("Waning")
	rows = [(_("Sunrise"), clock(moment(day["sun"]["rise"]))), (_("Sunset"), clock(moment(day["sun"]["set"])))]
	for label, key in ((_("Moonrise"), "rise"), (_("Moonset"), "set")):
		if moon.get(key):
			rows.append((label, when(moment(moon[key]), base)))
	picture = moon_picture(moon["illumination"], moon["waxing"], f"{phase} {_('moon')}, {lit}")
	return f'<div class="rv-sky rv-fixed">{picture}<p class="rv-phase"><b>{esc(phase)}</b> · {esc(lit)}</p>{_facts(rows)}</div>'


# ---- the panes ----
def panchang(data: dict, ctx: dict) -> dict | None:
	day = data["day"]
	base = ctx["date"]
	rows = []
	for kind in ("tithi", "nakshatra", "yoga", "karana"):
		element = day[kind]
		value = _name(kind, element) + (f", {_('pada')} {element['pada']}" if kind == "nakshatra" else "")
		after = _name(kind, element["next"])
		ends = f"{_('till')} {when(moment(element['ends']), base)}, {_('then')} {after}"
		if kind == "tithi" and moment(element["next"]["ends"]) < moment(day["sun"]["next_rise"]):
			ends += f" {_('which ends before the next sunrise')}"
		rows.append([esc(_label(kind)), f"<b>{esc(value)}</b>", esc(ends)])
	rows.append([esc(_label("weekday")), f"<b>{esc(_(day['weekday']))}</b>", ""])
	head = esc(_("The day's tithi and nakshatra are the ones at sunrise ({0})").format(clock(moment(day["sun"]["rise"]))))
	credit = f'<p class="rv-cap">{esc(places.ATTRIBUTION)}</p>'  # the towns of the list are GeoNames' (CC BY 4.0), which asks for this line wherever its places are used
	body = f'<div class="rv-split"><div><div class="rv-wrap">{table([], rows, "rv-table rv-keys")}</div><p class="rv-cap">{head}</p>{credit}</div>{_sky(day, base)}</div>'
	return {"body": body, "summary": f"{tithi_name(day['tithi'])} {_('till')} {when(moment(day['tithi']['ends']), base)}"}


def times(data: dict, ctx: dict) -> dict | None:
	day, base, now = data["day"], ctx["date"], ctx.get("now")
	windows = []
	for label, key, quality in ((_("Rahu Kaal"), "rahu_kaal", "avoid"), (_("Gulika"), "gulika", "avoid"), (_("Yamaganda"), "yamaganda", "avoid"), (_("Abhijit muhurat"), "abhijit", "good")):
		window = day[key]
		running = bool(now) and moment(window["from"]) <= now < moment(window["to"])
		words = (_("good") if quality == "good" else _("avoid")) + (f" · {_('on now')}" if running else "")
		windows.append(f'<div class="rv-win rv-{quality}{" rv-now" if running else ""}"><span class="rv-k">{esc(label)}</span><b>{esc(span(window, base))}</b><span>{esc(words)}</span></div>')
	return {"body": f'<div class="rv-windows">{"".join(windows)}</div>', "summary": f"{_('Rahu Kaal')} {span(day['rahu_kaal'], base)}"}


def muhurat(data: dict, ctx: dict) -> dict | None:
	link = ctx.get("muhurat")
	if not link:
		return None
	return {"body": f'<div class="rv-banner"><p class="rv-lede"><b>{esc(_("Choosing a time for something important?"))}</b> '
			f'{esc(_("A wedding, a new home, a vehicle, a new business: ask a Pandit ji for a muhurat made for you."))}</p>'
			f'<a class="rv-cta" href="{esc(link)}">{esc(_("Ask for a muhurat"))} →</a></div>', "summary": _("Ask a Pandit ji for a muhurat")}


def _parts(title: str, note: str, parts: list[dict], base: datetime.date, now: datetime.datetime | None) -> str:
	rows, here = [], False
	for part in parts:
		running = bool(now) and moment(part["from"]) <= now < moment(part["to"])
		here = here or running
		tone = "rv-good" if part["quality"] == "good" else "rv-avoid"
		words = _("good") if part["quality"] == "good" else _("avoid")
		rows.append(f'<tr class="{tone}{" rv-now" if running else ""}"><th scope="row">{esc(_(part["name"]))}</th><td>{esc(words)}{esc(" · " + _("now")) if running else ""}</td>'
					f'<td>{esc(clock(moment(part["from"])))} – {esc(when(moment(part["to"]), base))}</td></tr>')
	first = ' class="rv-first"' if here else ""  # (on a phone the table with the part running now comes first)
	return f'<div{first}><div class="rv-sub"><b>{esc(title)}</b> <span>{esc(note)}</span></div><table class="rv-parts"><tbody>{"".join(rows)}</tbody></table></div>'


def chaugharia(data: dict, ctx: dict) -> dict | None:
	day, base, now = data["day"], ctx["date"], ctx.get("now")
	parts = day["chaugharia"]
	rise, sset = clock(moment(day["sun"]["rise"])), clock(moment(day["sun"]["set"]))
	good = sorted({p["name"] for p in parts["day"] + parts["night"] if p["quality"] == "good"})
	avoid = sorted({p["name"] for p in parts["day"] + parts["night"] if p["quality"] != "good"})
	legend = f'{_("Good")}: {", ".join(_(n) for n in good)}. {_("Avoid")}: {", ".join(_(n) for n in avoid)}.'
	body = (f'<div class="rv-split">{_parts(_("Day"), _("sunrise {0} to sunset {1}").format(rise, sset), parts["day"], base, now)}'
			f'{_parts(_("Night"), _("sunset to the next sunrise"), parts["night"], base, now)}</div><p class="rv-cap">{esc(legend)}</p>')
	running = next((p for p in parts["day"] + parts["night"] if now and moment(p["from"]) <= now < moment(p["to"])), None)
	summary = (f"{_(running['name'])} · {_('good') if running['quality'] == 'good' else _('avoid')} {_('till')} {when(moment(running['to']), base)}" if running
			   else _("Eight parts by day and eight by night"))
	return {"body": body, "summary": summary}


def week(data: dict, ctx: dict) -> dict | None:
	days = data.get("week") or []
	if not days:
		return None
	link, shown = ctx["link"], ctx["date"]
	tiles = []
	for one in days:
		on_date = datetime.date.fromisoformat(one["date"])
		pada = f", {_('pada')} {one['nakshatra']['pada']}"
		tiles.append(f'<a class="rv-tile{" rv-on" if on_date == shown else ""}" href="{esc(link(on_date))}"><span class="rv-k">{esc(_(on_date.strftime("%a")))} {on_date.day} {esc(_(on_date.strftime("%b")))}</span>'
					 f'<b>{esc(tithi_name(one["tithi"]))}</b><span>{esc(one["nakshatra"]["name"])}{esc(pada)}</span></a>')
	return {"body": f'<div class="rv-tiles">{"".join(tiles)}</div>', "summary": f"{tithi_name(days[0]['tithi'])} · {len(days)} {_('days')}"}


PANES = {"panchang": panchang, "times": times, "muhurat": muhurat, "chaugharia": chaugharia, "week": week}
