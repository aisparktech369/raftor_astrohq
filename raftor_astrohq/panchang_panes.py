"""The panes of the Panchang page (panchang.py): the day's panchang, the sun and moon, the times to know, the chaugharia, the next seven days, and the way to ask a Pandit ji for a muhurat.

They are made like the panes of a chart (panes.py; report_view.py puts them on a board) but from the engine's answer for a day (`PANCHANGA_DAY`): `data` is {"day": that answer, "week": a list of them}
and `ctx` has "now" (the moment, in the town's time zone), "date" (the day shown), "place", "link" (a function: a date to the address of that day's page) and "muhurat" (the address of the muhurat
button, or None). A pane answers {"body": html, "summary": one line} or None. Nothing is worked out here: each time is written the way the engine gave it, and the part that is running is
the one whose times hold the moment `now`. Every word the engine wrote is escaped.
"""
import datetime

from frappe import _

from raftor_astrohq.panes import esc, table

NEXT_DAY, DAY_BEFORE = " next day", " the day before"
NOW_CLASS = ' class="rv-now"'


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


def _facts(rows: list[tuple[str, str, bool]]) -> str:
	body = "".join(f'<tr{NOW_CLASS if running else ""}><th scope="row">{esc(label)}</th><td>{esc(value)}</td></tr>' for label, value, running in rows)
	return f'<table class="rv-facts"><tbody>{body}</tbody></table>'


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
	body = f'<div class="rv-wrap">{table([], rows, "rv-table rv-keys")}</div><p class="rv-cap">{head}</p>'
	return {"body": body, "summary": f"{tithi_name(day['tithi'])} {_('till')} {when(moment(day['tithi']['ends']), base)}"}


def sun_moon(data: dict, ctx: dict) -> dict | None:
	day, base = data["day"], ctx["date"]
	rows = [(_("Sunrise"), clock(moment(day["sun"]["rise"])), False), (_("Sunset"), clock(moment(day["sun"]["set"])), False)]
	for label, key in ((_("Moonrise"), "rise"), (_("Moonset"), "set")):
		if day["moon"].get(key):
			rows.append((label, when(moment(day["moon"][key]), base), False))
	return {"body": _facts(rows), "summary": f"{_('Sunrise')} {clock(moment(day['sun']['rise']))} · {_('Sunset')} {clock(moment(day['sun']['set']))}"}


def times(data: dict, ctx: dict) -> dict | None:
	day, base, now = data["day"], ctx["date"], ctx.get("now")
	rows = []
	for label, key in ((_("Rahu Kaal"), "rahu_kaal"), (_("Gulika"), "gulika"), (_("Yamaganda"), "yamaganda"), (_("Abhijit muhurat"), "abhijit")):
		window = day[key]
		running = bool(now) and moment(window["from"]) <= now < moment(window["to"])
		rows.append((label, span(window, base) + (f" · {_('on now')}" if running else ""), running))
	return {"body": _facts(rows), "summary": f"{_('Rahu Kaal')} {span(day['rahu_kaal'], base)}"}


def muhurat(data: dict, ctx: dict) -> dict | None:
	link = ctx.get("muhurat")
	if not link:
		return None
	return {"body": f'<p class="rv-lede">{esc(_("A wedding, a new home, a vehicle, a new business: ask a Pandit ji for a muhurat made for you."))}</p>'
			f'<a class="rv-cta" href="{esc(link)}">{esc(_("Ask for a muhurat"))} →</a>', "summary": _("Ask a Pandit ji for a muhurat")}


def _parts(title: str, note: str, parts: list[dict], base: datetime.date, now: datetime.datetime | None) -> str:
	rows = []
	for part in parts:
		running = bool(now) and moment(part["from"]) <= now < moment(part["to"])
		tone = "rv-good" if part["quality"] == "good" else "rv-avoid"
		words = _("good") if part["quality"] == "good" else _("avoid")
		rows.append(f'<tr class="{tone}{" rv-now" if running else ""}"><th scope="row">{esc(_(part["name"]))}</th><td>{esc(words)}{esc(" · " + _("now")) if running else ""}</td>'
					f'<td>{esc(clock(moment(part["from"])))} – {esc(when(moment(part["to"]), base))}</td></tr>')
	return f'<div><div class="rv-sub"><b>{esc(title)}</b> <span>{esc(note)}</span></div><table class="rv-parts"><tbody>{"".join(rows)}</tbody></table></div>'


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


PANES = {"panchang": panchang, "sun_moon": sun_moon, "times": times, "muhurat": muhurat, "chaugharia": chaugharia, "week": week}
