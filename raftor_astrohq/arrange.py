"""Arranges what the astrology API answers into pages: tables, lists of facts and charts. Nothing here calculates anything.

Every mode of the API answers in JSON, and almost all of it is a table. A **layout** (a small JSON file in `layouts/`) says which part of the answer goes where, under which heading and in
which words; this file lays it out. With no layout (or for a part the layout does not name) the answer is shown as it comes: every record a row, every field a column, nothing hidden
and nothing left as raw JSON.

A layout is {"title", "intro", "hide": [top-level keys never shown], "sections": [section, ...], "rest": true|false (show what no section names, as it comes)}. A section is one of

    {"kind": "lines",  "title", "head": [labels], "rows": [[template, ...], ...]}      a few facts or fixed rows; a cell is a template such as "{birth.day:02d}-{birth.month:02d}"
    {"kind": "facts",  "title", "from": path, "rows": [[label, key, how?], ...]}          a few facts read by their keys from one place of the answer (keys with spaces or capitals too)
    {"kind": "times",  "title", "from": path, "rows": [[label, key], ...]}               stretches of time the library wrote in words (tithi, nakshatra, Rahu Kalam): what, from when, until when
    {"kind": "places", "title", "from": path, "prefix", "rows": [[label, key], ...]}        points the library wrote as a sign and a degree ("♉︎Taurus 24° 6’ 21" (Atma Karaka)"): the place, and what is said of it
    {"kind": "table",  "title", "from": path, "columns": [[label, key, how?], ...], "key": "label of the first column when the records are the values of a dict"}
    {"kind": "pivot",  "title", "from": path, "columns": [[label, key, how?], ...], "row_label"}   a dict of dicts turned round: one row for each inner key, one column for each outer key
    {"kind": "matrix", "title", "from": path, "row_labels": [...], "col_labels": "signs" or [...], "total": true, "footer": {"label", "from": path}}
    {"kind": "charts", "title", "from": path, "which": ["D1", ...], "titles": {"D1": "..."}, "columns": 3, "size": 200, "font": 12}
    {"kind": "dasha",  "title", "from": path, "now": true}                              a dasha with the running period marked, and its sub-periods
    {"kind": "auto",   "title", "from": path}                                           whatever is there, as it comes
    {"kind": "text",   "title", "text"}

`how` is how a value is written: planet, sign, sign_index, signdeg, longitude, dms_lon, nakshatra, degree, date, time, bool, num, names, text. With none the value is read for what it is (a true
or false, a date, a planet or sign the engine wrote with its symbols, a list). A path is dotted ("divisional_charts.D9.chart"); `@name` in a template asks one of the small readings below.
"""
import datetime
import functools
import json
import re
from html import escape
from pathlib import Path

from raftor_astrohq import report_pdf as rp

LAYOUTS = Path(__file__).parent / "layouts"
WORDS = Path(__file__).parent / "engine_words.json"
MAX_ROWS = 80
GLYPHS = {"☉": "Sun", "☾": "Moon", "♂": "Mars", "☿": "Mercury", "♃": "Jupiter", "♀": "Venus", "♄": "Saturn", "☊": "Rahu", "☋": "Ketu", "ℒ": "Lagna"}
ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
SHORT_SIGNS = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
BHAVA_PADAS = ["Arudha Lagna (AL)", "Dhanarudha (A2)", "Bhatrarudha (A3)", "Matri Pada (A4)", "Mantra Pada (A5)", "Roga Pada (A6)", "Dara Pada (A7)", "Mrityu Pada (A8)", "Bhagya Pada (A9)",
			   "Karma Pada (A10)", "Labha Pada (A11)", "Upapada Lagna (UL)"]
GLYPH = re.compile(r"[A-Za-z]*([☉☾♂☿♃♀♄☊☋ℒ])")
SIGN_GLYPH = re.compile("[♈-♓]︎?")
DMS = re.compile(r"(\d+)°\s*(\d+)[’']\s*(\d+)[\"”]?")
QUARTER = re.compile(r"\bQuarter-(\d)\b")
PLACE = re.compile(r"^(?P<sign>[♈-♓]\ufe0e?\s*[A-Za-z]+)\s*(?:(?P<d>\d+)°\s*(?P<m>\d+)[’'](?:\s*(?P<s>\d+)\")?)?\s*(?:\((?P<note>[^)]*)\))?$")
TIMED = re.compile(r"^(?P<name>.*?)\s*(?:(?P<a>\d{2}:\d{2}:\d{2})(?: \((?P<ad>[+-]\d)\))? from )?(?P<b>\d{2}:\d{2}:\d{2})(?: \((?P<bd>[+-]\d)\))? ends\b(?:\s*\([\d.]+% Balance\s*\))?\s*$")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
def extra_css(look: dict | None = None) -> str:
	"""What the arranger adds to the page's style sheet, in a look (the plain one when none is given)."""
	k = {**rp.DEFAULT_LOOK, **(look or {})}
	return f"""<style>
table.m td, table.m th {{ text-align: center; padding: 3px 4px; font-size: 10.5px; }}
table.m td.l, table.m th.l {{ text-align: left; }}
table.m tr.f td {{ background: {k['soft']}; font-weight: bold; }}
.grid {{ width: 100%; page-break-inside: auto; }}
.grid tr {{ page-break-inside: avoid; }}
.grid td {{ border: none; text-align: center; padding: 8px 0 2px 0; vertical-align: top; }}
td.wrap {{ white-space: normal; }}
table.sec, table.sec > tbody > tr > td {{ border: none; padding: 0; page-break-inside: avoid; }}
caption {{ caption-side: top; text-align: left; font-weight: bold; color: {k['heading']}; }}
caption.h2 {{ font-size: 15px; border-bottom: 2px solid {k['line']}; padding: 20px 0 3px 0; }}
caption.h3 {{ font-size: 13px; padding: 12px 0 4px 0; }}
table td.note, table.m td.note {{ border: none; padding: 6px 0 0 0; font-size: 10.5px; text-align: left; color: {k['muted']}; background: none; font-weight: normal; }}
h3 {{ font-size: 13px; color: {k['heading']}; margin: 12px 0 4px 0; }}
.draft {{ font-family: Arial, sans-serif; font-size: 8px; font-weight: bold; letter-spacing: 1px; text-transform: uppercase; color: {k['accent']}; border: 1px solid {k['accent']}; padding: 0 4px; margin-left: 8px; vertical-align: middle; }}
</style>"""


EXTRA_CSS = extra_css()


# ---- reading the engine's words ----
@functools.cache
def engine_words() -> tuple[re.Pattern, dict[str, str]]:
	"""The names as the library spells them (Revathi, Dhasami, Soubhagya) and as the app does (Revati, Dashami, Saubhagya): a pattern that finds them and what each becomes."""
	data = json.loads(WORDS.read_text(encoding="utf-8"))
	words = dict(data["words"])
	for n, name in enumerate(data["nakshatras"]):
		words[name] = rp.NAKSHATRAS[n] if n < len(rp.NAKSHATRAS) else "Abhijit"
	return re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")\b"), words


def clean(value) -> str:
	"""A text the engine wrote, as people read it: planets by name (not "Su☉"), signs by name with the Hindi one beside it, names as the app spells them, degrees as 14°12′, no symbols."""
	text = str(value if value is not None else "").replace("︎", "").replace("️", "")
	retro = "℞" in text
	text = text.replace("℞", "")
	text = GLYPH.sub(lambda m: GLYPHS[m.group(1)], text)
	pattern, words = engine_words()
	text = QUARTER.sub(lambda m: f"pada {m.group(1)}", pattern.sub(lambda m: words[m.group(1)], text))

	def sign(match):
		name = match.group(1)
		index = rp.sign_index(name)
		return rp.sign_label(index) if index is not None else name

	text = re.sub(r"[♈-♓]([A-Za-z]+)", sign, text)
	text = SIGN_GLYPH.sub("", text)
	text = DMS.sub(lambda m: f"{int(m.group(1))}°{int(m.group(2)):02d}′{int(m.group(3)):02d}″", text)
	return re.sub(r"\s+", " ", text).strip() + (" (retrograde)" if retro else "")


def sign_name(value) -> str:
	"""A sign by its name with the Hindi one beside it (Virgo (Kanya)), however the engine wrote it ("♍︎Virgo" or just "Virgo")."""
	text = clean(value)
	index = rp.sign_index(text)
	return rp.sign_label(index) if index is not None and text.lower() == rp.SIGNS[index].lower() else text


def pretty(key) -> str:
	text = re.sub(r"[_\s]+", " ", str(key)).strip().rstrip(":").strip()
	return text[:1].upper() + text[1:]


def longdate(value: str) -> str:
	day = datetime.date.fromisoformat(value)
	return f"{day.day:02d} {day.strftime('%b %Y')}"


def number(value, places: int = 2) -> str:
	text = f"{float(value):.{places}f}"
	return text.rstrip("0").rstrip(".") if "." in text else text


def dms_lon(value) -> str:
	"""A longitude written 054-12-11 (degrees, minutes, seconds from Aries) as its sign and the place in it: Taurus (Vrishabha) 24°12′."""
	parts = [int(p) for p in re.findall(r"\d+", str(value))[:3]] + [0, 0]
	total = parts[0] + parts[1] / 60 + parts[2] / 3600
	return f"{rp.sign_label(int(total // 30) % 12)} {rp.degrees(total % 30)}"


def clock(time: str, day: str | None = None) -> str:
	"""A time of day the library wrote ("17:30:06", with "(+1)" after it when it is the next day's) as hours and minutes. The library writes a time before midnight as how far it is from midnight with
	"(-1)" after it (a tithi that began at 17:08 the day before comes as "06:51:18 (-1)"): that is turned back into the time it is."""
	hours, minutes, seconds = (int(x) for x in time.split(":"))
	total = hours * 3600 + minutes * 60 + seconds
	if day == "-1":
		total, note = 86400 - total, " (the day before)"
	elif day == "+1":
		note = " (the next day)"
	else:
		note = f" ({day[1:]} days later)" if day and day.startswith("+") else f" ({day})" if day else ""
	return f"{total // 3600:02d}:{total % 3600 // 60:02d}{note}"


def timed(text) -> dict | None:
	"""A stretch of time the library wrote in words — "Revathi  (Me☿) Quarter-3 02:05:50 from 00:19:48 (+1) ends (47.29% Balance )" — as {"name", "begins", "ends"}; None for any other text.
	(The "% Balance" is left out: for a tithi that began the day before, the library works it out from the wrong start.)"""
	match = TIMED.match(str(text or "").strip())
	if not match:
		return None
	return {"name": clean(match.group("name")), "begins": clock(match.group("a"), match.group("ad")) if match.group("a") else "", "ends": clock(match.group("b"), match.group("bd"))}


def fmt(value, how: str | None = None) -> str:
	"""A value written for a page. `how` names the way (see the top of this file); with none it is read for what it is."""
	if value is None or value == "":
		return ""
	if how == "planet":
		return "Lagna" if str(value).strip() == "L" else clean(value)  # (the yearly dashas name the lagna "L")
	if how == "planet_index":
		return ORDER[int(value)] if 0 <= int(value) < len(ORDER) else str(value)
	if how == "tajaka_planet":  # the Tajaka charts name their rows "L" (the lagna) or a planet's number
		return "Lagna" if str(value).upper() == "L" else ORDER[int(value)] if str(value).isdigit() and int(value) < len(ORDER) else str(value)
	if how == "sign":
		return sign_name(value)
	if how == "sign_index":
		return rp.sign_label(int(value) % 12)
	if how == "signdeg" and isinstance(value, list | tuple) and len(value) == 2:
		return f"{rp.sign_label(int(value[0]) % 12)} {rp.degrees(float(value[1]))}"
	if how == "longitude":
		total = float(value)
		return f"{rp.sign_label(int(total // 30) % 12)} {rp.degrees(total % 30)}"
	if how == "dms_lon":
		return dms_lon(value)
	if how == "nakshatra":
		return rp.NAKSHATRAS[(int(value) - 1) % 27]
	if how == "degree":
		return rp.degrees(float(value))
	if how == "date":
		return longdate(str(value)) if ISO.match(str(value)) else str(value)
	if how == "time":  # 05:26:45 as 05:26
		return str(value)[:5] if re.match(r"^\d{2}:\d{2}:\d{2}$", str(value)) else str(value)
	if how == "bool":
		return "Yes" if value else "No"
	if how == "num":
		return number(value)
	if how == "names":
		return ", ".join(fmt(v.get("name") if isinstance(v, dict) else v, "planet") for v in value) if isinstance(value, list) else clean(value)
	if how == "text":
		return clean(value)
	if isinstance(value, bool):
		return "Yes" if value else "No"
	if isinstance(value, int):
		return str(value)
	if isinstance(value, float):
		return number(value)
	if isinstance(value, str):
		return longdate(value) if ISO.match(value) else clean(value)
	if isinstance(value, list | tuple):
		shown = [fmt(v) for v in value[:12]]
		return ", ".join(shown) + (f" … ({len(value)} in all)" if len(value) > 12 else "")
	if isinstance(value, dict):
		return "; ".join(f"{pretty(k)}: {fmt(v)}" for k, v in list(value.items())[:10])
	return str(value)


# ---- finding things in the answer ----
def dig(data, path: str | None):
	"""The part of the answer a dotted path names ("houses.houses", "divisional_charts.D9.chart"), or None."""
	here = data
	for part in [p for p in str(path or "").split(".") if p]:
		if isinstance(here, dict):
			here = here.get(part)
		elif isinstance(here, list) and part.lstrip("-").isdigit() and -len(here) <= int(part) < len(here):
			here = here[int(part)]
		else:
			return None
	return here


def planet(data, name: str) -> dict:
	"""A planet's row of planetary_positions by its name (the standard answer has none: see where())."""
	for row in data.get("planetary_positions") or []:
		if clean(row.get("planet")) == name:
			return row
	return {}


def where(data, name: str) -> dict:
	"""The sign and the house a planet is in: from planetary_positions when the answer has them, else from the houses (each lists the planets in it)."""
	row = planet(data, name)
	if row.get("sign") and row.get("house"):
		return {"sign": sign_name(row["sign"]), "house": row["house"]}
	for house in dig(data, "houses.houses") or []:
		if any(clean(p.get("name") if isinstance(p, dict) else p) == name for p in house.get("planets") or []):
			return {"sign": sign_name(house.get("sign")), "house": house.get("house_number")}
	return {}


LABELS = {"bhava_padas": BHAVA_PADAS, "houses": [f"House {n}" for n in range(1, 13)]}

READINGS = {
	"mars_house": lambda data: str(where(data, "Mars").get("house", "")),
	"moon_sign": lambda data: where(data, "Moon").get("sign", ""),
	"sun_sign": lambda data: where(data, "Sun").get("sign", ""),
	"lagna": lambda data: f"{clean((data.get('lagna') or {}).get('sign'))} {rp.degrees((data.get('lagna') or {}).get('degree') or 0)}" if data.get("lagna") else "",
}


def tpl(template, data) -> str:
	"""A cell of a layout: text with {path} or {path:format} in it ("{birth.day:02d}-{birth.month:02d}-{birth.year}"), or "@name" for one of the small readings."""
	text = str(template)
	if text.startswith("@"):
		return READINGS.get(text[1:], lambda _data: "")(data)

	def one(match):
		value = dig(data, match.group(1))
		if value is None:
			return ""
		try:
			return format(value, match.group(3)) if match.group(3) else fmt(value, match.group(2))
		except (TypeError, ValueError):
			return fmt(value, match.group(2))

	return re.sub(r"\{([\w.\-]+)(?:\|(\w+))?(?::([^}]*))?\}", one, text)


# ---- the pieces of a page ----
DRAFT = "<span class='draft'>Draft</span>"


def caption(text: str, level: int = 2, draft: bool = False) -> str:
	"""A heading written as the caption of the table under it, so a page can never end between the two. A part nobody has checked yet says Draft beside its heading."""
	return f"<caption class='h{level}'>{escape(text)}{DRAFT if draft else ''}</caption>" if text else ""


def add_note(table: str, text: str) -> str:
	"""A note as the last row of the table it belongs to, so it can never be left alone at the top of the next page."""
	first = re.search(r"<tr[^>]*>(.*?)</tr>", table, re.S)
	columns = max(len(re.findall(r"<t[hd][ >]", first.group(1))) if first else 1, 1)
	return table[:-len("</table>")] + f"<tr><td colspan='{columns}' class='note'>{escape(text)}</td></tr></table>"


def keep(html: str) -> str:
	"""Parts of a page that must not be split between two pages (a heading and its table). The PDF maker never ends a page inside a table row, so they are put in a table of one."""
	return f"<table class='sec'><tr><td>{html}</td></tr></table>"


def cell(text, cls: str = "") -> str:
	return f"<td{' class=' + chr(34) + cls + chr(34) if cls else ''}>{escape(str(text))}</td>"


def table_html(head: list[str], rows: list[list], matrix: bool = False, row_classes: list[str] | None = None, title: str = "", level: int = 2, draft: bool = False) -> str:
	more = max(len(rows) - MAX_ROWS, 0)
	rows = rows[:MAX_ROWS]
	header = "<tr>" + "".join(f"<th{' class=l' if matrix and n == 0 else ''}>{escape(str(h))}</th>" for n, h in enumerate(head)) + "</tr>" if head else ""
	body = "".join(f'<tr{" class=" + chr(34) + row_classes[n] + chr(34) if row_classes and row_classes[n] else ""}>' + "".join(cell(c, "l" if matrix and i == 0 else "") for i, c in enumerate(row)) + "</tr>"
				   for n, row in enumerate(rows))
	tail = f"<tr><td colspan='{max(len(head), 1)}' class='note'>… and {more} more</td></tr>" if more else ""
	return f"<table{' class=m' if matrix else ''}>{caption(title, level, draft)}{header}{body}{tail}</table>"


def lines(spec, data) -> str:
	rows = [[tpl(c, data) for c in row] for row in spec.get("rows") or []]
	rows = [r for r in rows if any(c for c in r[1:] or r)]
	if not rows:
		return ""
	if spec.get("head"):
		rows = [[r[0], *[c or "—" for c in r[1:]]] for r in rows]  # a cell the answer leaves empty says so
	if not spec.get("head") and len(rows[0]) == 2:
		return "<table>" + "".join(f'<tr><td class="k">{escape(r[0])}</td><td>{escape(r[1])}</td></tr>' for r in rows) + "</table>"
	return table_html(spec.get("head") or [], rows)


def place(text) -> tuple[str, str]:
	"""A place the library wrote as ♉︎Taurus 24° 6’ 21" (Amatya Karaka): where it is (Taurus (Vrishabha) 24°06′) and what is said of it (Amatya Karaka)."""
	match = PLACE.match(str(text or "").strip())
	if not match:
		return clean(text), ""
	spot = clean(match.group("sign"))
	if match.group("d"):
		spot += f" {int(match.group('d'))}°{int(match.group('m')):02d}′"
	return spot, clean(match.group("note"))


def places(spec, data) -> str:
	"""Points the library wrote as a sign and a degree (the planets with their karakas, the special lagnas, the shadow points), a row each: {"from": path of the dict, "prefix": how every key
	starts, "rows": [[label, key], ...]}. A key is found by how it starts, so "Venus" finds the library's "Venus♀℞" (a retrograde planet is said to be)."""
	source = dig(data, spec.get("from")) or {}
	prefix = spec.get("prefix", "")
	rows = []
	for label, key in [r[:2] for r in spec.get("rows") or []]:
		found = next((k for k in source if k == prefix + key), None) or next((k for k in source if k.startswith(prefix + key)), None)
		if not found:
			continue
		spot, remark = place(source[found])
		if "℞" in found:
			remark = "retrograde" + (f"; {remark}" if remark else "")
		rows.append([label, spot, remark])
	if not rows:
		return ""
	if not any(r[2] for r in rows):
		return table_html([spec.get("first", ""), "Place"], [r[:2] for r in rows])
	return table_html([spec.get("first", ""), "Place", spec.get("remark", "Note")], rows)


def facts(spec, data) -> str:
	"""A few facts out of one place of the answer, a row each: {"from": path, "rows": [[label, key, how?], ...]}. A row whose key the answer does not hold is left out."""
	source = dig(data, spec.get("from")) if spec.get("from") else data
	source = source if isinstance(source, dict) else {}
	rows = [[row[0], fmt(source.get(row[1]), row[2] if len(row) > 2 else None)] for row in spec.get("rows") or []]
	rows = [r for r in rows if r[1]]
	return "<table>" + "".join(f'<tr><td class="k">{escape(r[0])}</td><td>{escape(r[1])}</td></tr>' for r in rows) + "</table>" if rows else ""


def times(spec, data) -> str:
	"""Stretches of time the library wrote in words (a tithi, a nakshatra, Rahu Kalam), a row each, with what it is, when it begins and when it ends: {"from": path, "rows": [[label, key], ...]}."""
	source = dig(data, spec.get("from")) if spec.get("from") else data
	source = source if isinstance(source, dict) else {}
	rows = []
	for label, key in [r[:2] for r in spec.get("rows") or []]:
		span = timed(source.get(key))
		if span:
			rows.append([label, span["name"], span["begins"], span["ends"]])
		elif source.get(key):
			rows.append([label, fmt(source.get(key)), "", ""])
	if not rows:
		return ""
	if not any(r[1] for r in rows):  # a list of times alone (the day's Rahu Kalam and the like) has no names to show
		return table_html([spec.get("first", ""), "From", "Until"], [[r[0], r[2], r[3]] for r in rows])
	return table_html([spec.get("first", ""), "At the birth", "From", "Until"], rows)


def records(source, key_label: str | None = None) -> list[dict]:
	"""A list of records, whatever the answer holds: a list of dicts as it is, a dict of dicts with its keys as a first column."""
	if isinstance(source, list):
		if source and all(isinstance(r, dict) for r in source):
			return source
		if source and all(isinstance(r, list | tuple) and len(r) == 2 for r in source):  # [name, value] pairs (the Tajaka charts)
			return [{"__key__": r[0], "value": r[1]} for r in source]
		return [{"value": r} for r in source if not isinstance(r, dict)]  # plain values, one to a row (their names come from the layout's "labels")
	if isinstance(source, dict):
		return [{"__key__": pretty(k), **(v if isinstance(v, dict) else {"value": v})} for k, v in source.items()]
	return []


def table(spec, data) -> str:
	source = dig(data, spec.get("from"))
	rows = records(source, spec.get("key"))
	if not rows:
		return ""
	columns = spec.get("columns")
	if not columns:
		keys = [k for k in dict.fromkeys(k for r in rows for k in r) if k != "__key__"]
		columns = [[pretty(k), k] for k in keys]
	head, body = [c[0] for c in columns], []
	labels = LABELS.get(spec["labels"]) if isinstance(spec.get("labels"), str) else spec.get("labels")
	keyed = bool(spec.get("key")) and any("__key__" in r for r in rows)
	if keyed:
		head = [spec["key"], *head]
	elif labels:
		head = [spec.get("label", ""), *head]
	for n, record in enumerate(rows):
		row = [fmt(dig(record, c[1]) if "." in c[1] else record.get(c[1]), c[2] if len(c) > 2 else None) for c in columns]
		if keyed:
			row = [fmt(record["__key__"], spec.get("key_how")) if spec.get("key_how") else record["__key__"], *row]
		elif labels:
			row = [labels[n] if n < len(labels) else n + 1, *row]
		body.append(row)
	return table_html(head, body)


def pivot(spec, data) -> str:
	source = dig(data, spec.get("from")) or {}
	columns = spec.get("columns") or [[pretty(k), k] for k, v in source.items() if isinstance(v, dict)]
	first = next((source[c[1]] for c in columns if isinstance(source.get(c[1]), dict)), {})
	names = list(first)
	if not names:
		return ""
	head = [spec.get("row_label", ""), *[c[0] for c in columns]]
	rows = [[clean(name), *[fmt((source.get(c[1]) or {}).get(name), c[2] if len(c) > 2 else "num") for c in columns]] for name in names]
	return table_html(head, rows, matrix=True)


def matrix(spec, data) -> str:
	grid = dig(data, spec.get("from")) or []
	if not grid:
		return ""
	cols = SHORT_SIGNS if spec.get("col_labels") == "signs" else spec.get("col_labels") or [str(n + 1) for n in range(len(grid[0]) if grid else 0)]
	labels = spec.get("row_labels") or [str(n + 1) for n in range(len(grid))]
	head = ["", *cols, *(["Total"] if spec.get("total") else [])]
	rows = [[labels[n] if n < len(labels) else n + 1, *[fmt(v) for v in row], *([str(sum(row))] if spec.get("total") else [])] for n, row in enumerate(grid)]
	classes = [""] * len(rows)
	footer = spec.get("footer")
	if footer:
		line = dig(data, footer.get("from")) or []
		rows.append([footer.get("label", ""), *[fmt(v) for v in line], *([str(sum(line))] if spec.get("total") else [])])
		classes.append("f")
	return table_html(head, rows, matrix=True, row_classes=classes)


def charts(spec, data, look: dict | None = None) -> str:
	source = dig(data, spec.get("from")) or {}
	size, per_row = int(spec.get("size") or 220), int(spec.get("columns") or 2)
	cells = []
	for key in spec.get("which") or list(source):
		chart = source.get(key)
		if not isinstance(chart, dict) or not chart.get("chart"):
			continue
		title = (spec.get("titles") or {}).get(key) or key
		cells.append(rp.diamond_chart_svg(chart["chart"], int(chart.get("ascendant_house") or 0) % 12, title, size, int(spec.get("font") or 12), look))
	if not cells:
		return ""
	return "<table class='grid'>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in cells[n:n + per_row]) + "</tr>" for n in range(0, len(cells), per_row)) + "</table>"


def running(period: dict, on: datetime.date) -> bool:
	start, end = period.get("start_date"), period.get("end_date")
	return bool(start) and datetime.date.fromisoformat(start) <= on and (not end or on <= datetime.date.fromisoformat(end))


def dasha(spec, data, today: datetime.date, title: str = "", level: int = 2, draft: bool = False) -> str:
	source = dig(data, spec.get("from")) or {}
	periods = source.get("mahadasha") or []
	if not periods:
		return ""
	rows, classes = [], []
	for period in periods:
		on = spec.get("now", True) and running(period, today)
		rows.append([fmt(period.get("lord"), "planet"), fmt(period.get("start_date"), "date"), fmt(period.get("end_date"), "date") or "—", number(period.get("duration_years") or 0) if period.get("end_date") else "—"])
		classes.append("now" if on else "")
	out = table_html(["Main period", "From", "To", "Years"], rows, row_classes=classes, title=title, level=level, draft=draft)
	current = next((p for p in periods if spec.get("now", True) and running(p, today)), None)
	if current and current.get("antardasha"):
		inner = [[f"{fmt(current['lord'], 'planet')} / {fmt(a.get('lord'), 'planet')}", fmt(a.get("start_date"), "date"), fmt(a.get("end_date"), "date") or "—"] for a in current["antardasha"]]
		out += keep(f"<h3>Sub-periods of the running {escape(fmt(current['lord'], 'planet'))} period</h3>" + table_html(["Period", "From", "To"], inner, row_classes=["now" if running(a, today) else "" for a in current["antardasha"]]))
	return out


def short(text: str, limit: int = 240) -> str:
	"""A long text cut at the end of a word, with … after it."""
	if len(text) <= limit:
		return text
	return text[:limit].rsplit(" ", 1)[0].rstrip(",;:-") + " …"


def yogas(spec, data) -> str:
	"""The yogas the chart has, one row each: its kind, its name, where it was found and the rule that makes it. (The classical text of what it gives is left out unless the layout asks for it.)"""
	source = dig(data, spec.get("from")) or {}
	rows = []
	for group, items in source.items():
		if not isinstance(items, dict):
			continue
		if "present" in items:
			if items.get("present"):
				rows.append([pretty(group), pretty(group), "", clean(items.get("note"))])
			continue
		for key, item in items.items():
			if isinstance(item, list) and len(item) >= 3:
				name = clean(item[1]) or pretty(key)
				name = name.replace("_", " ").title() if "_" in name else name
				rule = re.sub(r"^\d+\s*[-–.]\s*", "", clean(item[2]))  # (the library's rules keep the number of the sentence in the book they come from)
				row = [pretty(group), name, re.sub(r"-?Raja Yoga Pairs:\s*\[(.*?)\]", r" (\1)", clean(item[0])), short(rule)]
				if spec.get("effects") and len(item) > 3:
					row.append(short(clean(item[3]), 400))
				rows.append(row)
	head = ["Kind", "Yoga", "Found in", "Rule"] + (["What it gives (classical text)"] if spec.get("effects") else [])
	return table_html(head, rows) if rows else ""


def dashas(spec, data, today: datetime.date, show: str = "all") -> str:
	"""Every dasha system the answer holds, each under its own name (a system with no periods is left out). When the layout names the systems an astrologer has checked ("reviewed": ["vimshottari"]),
	a customer's page has those only and the others, on a page that shows all, say Draft."""
	checked = spec.get("reviewed")
	out = []
	for section in spec.get("from_all") or ["dasha_sequences", "extra_dashas"]:
		for key, system in (dig(data, section) or {}).items():
			if isinstance(system, dict) and system.get("mahadasha"):
				ok = checked is True or (isinstance(checked, list) and key in checked)
				if show == "reviewed" and not ok:
					continue
				name = system.get("dasha_system") or pretty(key)
				out.append(dasha({"from": f"{section}.{key}", "now": spec.get("now", True)}, data, today, title=name, level=3, draft=not ok))
	return "".join(out)


def auto(value, title: str = "", depth: int = 0, hide: tuple = ()) -> str:
	"""A part of the answer as it comes: a dict of facts as a table (what holds more is laid out under its own heading), a list of records as a table with a column for each field."""
	if isinstance(value, dict):
		scalars = [(pretty(k), fmt(v)) for k, v in value.items() if not isinstance(v, dict | list) and k not in hide and fmt(v)]
		out = ("<table>" + "".join(f'<tr><td class="k">{escape(k)}</td><td>{escape(v)}</td></tr>' for k, v in scalars) + "</table>") if scalars else ""
		for key, inner in value.items():
			if isinstance(inner, dict | list) and key not in hide and inner and depth < 3:
				body = auto(inner, key, depth + 1, hide)
				if body:
					out += keep(f"<h3>{escape(pretty(key))}</h3>{body}")
		return out
	if isinstance(value, list):
		if value and all(isinstance(v, dict) for v in value):
			keys = list(dict.fromkeys(k for r in value for k in r))
			return table_html([pretty(k) for k in keys], [[fmt(r.get(k)) for k in keys] for r in value])
		if value and all(isinstance(v, list) for v in value):
			return table_html([""] + [str(n + 1) for n in range(len(value[0]))], [[n + 1, *[fmt(v) for v in row]] for n, row in enumerate(value)], matrix=True)
		return escape(fmt(value))
	return escape(fmt(value))


# ---- a page ----
def layout_named(name: str) -> dict:
	layout = json.loads((LAYOUTS / f"{name}.json").read_text(encoding="utf-8"))
	if layout.get("extends"):
		base = layout_named(layout["extends"])
		layout = {**base, **{k: v for k, v in layout.items() if k not in ("sections", "extends", "append")}, "sections": [*base["sections"], *(layout.get("append") or [])]}
	return layout


def section_html(spec: dict, data: dict, today: datetime.date, look: dict | None = None, show: str = "all") -> str:
	"""One section of a layout. `show` is "all" (every section, those nobody has checked marked Draft: for astrologers and the team) or "reviewed" (only what the layout calls reviewed: for customers)."""
	kind = spec.get("kind")
	checked = bool(spec.get("reviewed"))
	if show == "reviewed" and not checked:
		return ""
	draft = not checked
	if kind == "lines":
		body = lines(spec, data)
	elif kind == "facts":
		body = facts(spec, data)
	elif kind == "times":
		body = times(spec, data)
	elif kind == "places":
		body = places(spec, data)
	elif kind == "table":
		body = table(spec, data)
	elif kind == "pivot":
		body = pivot(spec, data)
	elif kind == "matrix":
		body = matrix(spec, data)
	elif kind == "charts":
		body = charts(spec, data, look)
	elif kind == "dasha":
		return dasha(spec, data, today, title=spec.get("title", ""), draft=draft) + (f"<p class='note'>{escape(spec['note'])}</p>" if spec.get("note") else "")
	elif kind == "yogas":
		body = yogas(spec, data)
	elif kind == "dashas":
		return dashas(spec, data, today, show)
	elif kind == "auto":
		body = auto(dig(data, spec.get("from")) if spec.get("from") else data, spec.get("title", ""), hide=tuple(spec.get("hide") or ()))
	elif kind == "text":
		body = f"<p>{escape(spec.get('text', ''))}</p>"
	else:
		body = ""
	if not body:
		return ""
	if body.startswith("<table") and body.count("<table") == 1:  # one table: its heading is its caption and its note its last row, so a page can never end between them
		opening, rest = body.split(">", 1)
		one = f"{opening}>{caption(spec.get('title', ''), 2, draft)}{rest}"
		return add_note(one, spec["note"]) if spec.get("note") else one
	note = f"<p class='note'>{escape(spec['note'])}</p>" if spec.get("note") else ""
	title = f"<h2>{escape(spec['title'])}{DRAFT if draft else ''}</h2>" if spec.get("title") else ""
	return keep(f"{title}{body}{note}")


def body(data: dict, layout: dict | str, today: datetime.date | None = None, subject: str = "", look: dict | None = None, show: str = "all") -> str:
	"""The page: its title, then each section of the layout that has something to show; with "rest" on, then whatever the layout did not name, as it comes."""
	layout = layout_named(layout) if isinstance(layout, str) else layout
	today = today or datetime.date.today()
	parts = [f"<h1>{escape(layout.get('title', ''))}</h1>"]
	if subject or layout.get("intro"):
		parts.append(f"<p class='sub'>{escape(' · '.join(x for x in (subject, layout.get('intro')) if x))}</p>")
	if layout.get("note"):
		parts.append(f"<p class='note'>{escape(layout['note'])}</p>")
	named = set()
	for spec in layout.get("sections") or []:
		if spec.get("from"):
			named.add(spec["from"].split(".")[0])
		parts.append(section_html(spec, data, today, look, show))
	if layout.get("rest"):
		hide = set(layout.get("hide") or []) | named
		for key, value in data.items():
			if key not in hide and value:
				text = auto(value, key, hide=tuple(layout.get("hide") or ()))
				if text:
					parts.append(f"<h2>{escape(pretty(key))}</h2>{text}")
	return "".join(p for p in parts if p)


def html(data: dict, layout: dict | str, brand: str = "", credit: str = "", today: datetime.date | None = None, subject: str = "", look: dict | None = None, show: str = "all") -> str:
	"""The whole page for a PDF or a screen: the masthead (the site's logo and name when it has them), then the layout's page, in the look (the plain one when none is given)."""
	name = brand or (look or {}).get("name") or ""
	title = layout.get("title", "") if isinstance(layout, dict) else layout
	return rp.page(title, extra_css(look) + rp.masthead(look, name) + body(data, layout, today, subject, look, show), name, credit or "Calculated with the Lahiri ayanamsa.", look)
