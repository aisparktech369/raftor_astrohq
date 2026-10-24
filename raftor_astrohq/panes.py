"""The panes of a report view: each shows one part of what the astrology engine answered, as a small table or drawing, in markup websitehq's Report View draws (report_view.py puts them on a board).

A pane is a function of the answers (`data`, {mode: answer}), a context and its options: it answers `{"body": html, "summary": one line}`, or None when the answer has nothing for it (the pane is left out).
The summary is what a pane that is folded on a phone says of itself. Nothing here calculates anything the engine did not (a planet's house in today's sky is the sign it is in counted from the person's lagna).

Markup rules (website_hq/report_html.py decides what reaches the page): class names begin `rv-`; no style attributes; colours are `var(--rv-...)` (the site's theme gives them); every word the engine or a person wrote is escaped.
"""
import datetime
from html import escape

from raftor_astrohq import arrange
from raftor_astrohq import report_pdf as rp

CODES = {"Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me", "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra", "Ketu": "Ke", "Lagna": "As"}
TINT = {"Sun": "rv-su", "Moon": "rv-mo", "Mars": "rv-ma", "Mercury": "rv-me", "Jupiter": "rv-ju", "Venus": "rv-ve", "Saturn": "rv-sa", "Rahu": "rv-ra", "Ketu": "rv-ke"}
SHORT = {"Aries": "Ari", "Taurus": "Tau", "Gemini": "Gem", "Cancer": "Can", "Leo": "Leo", "Virgo": "Vir", "Libra": "Lib", "Scorpio": "Sco", "Sagittarius": "Sag", "Capricorn": "Cap", "Aquarius": "Aqu", "Pisces": "Pis"}
KARAKA = {"Atma": "AK", "Amatya": "AmK", "Bhratri": "BK", "Maitra": "MK", "Pitri": "PiK", "Putra": "PuK", "Jnaati": "GK", "Dhatha": "DK"}
KARAKA_ORDER = ["AK", "AmK", "BK", "MK", "PiK", "PuK", "GK", "DK"]
LAGNAS = [("BL", "Bhava Lagna (BL)"), ("HL", "Hora Lagna (HL)"), ("GL", "Ghati Lagna (GL)"), ("VL", "Vighati Lagna (VL)"), ("PL", "Pranapada Lagna (PL)"), ("IL", "Indu Lagna (IL)"),
		  ("BB", "Bhrigu Bindhu Lagna (BB)"), ("KL", "Kunda Lagna (KL)"), ("SL", "Sree Lagna (SL)")]
INFO = "Custom Kundali (Dn)-"
WEB_LOOK = {"paper": "none", "ink": "var(--rv-ink)", "heading": "var(--rv-heading)", "accent": "var(--rv-accent)", "line": "var(--rv-line)", "soft": "var(--rv-soft)", "faint": "var(--rv-faint)", "muted": "var(--rv-muted)"}


# ---- small things ----
def esc(value) -> str:
	return escape(str(value if value is not None else ""))


def name_of(value) -> str:
	"""A planet by its name ("Su☉" and "Venus♀℞" are both written as the engine writes them)."""
	return arrange.clean(value).replace(" (retrograde)", "")


def short_sign(value) -> str:
	return SHORT.get(arrange.sign_name(value).split(" ")[0], "")


def cls(*names: str) -> str:
	"""A class attribute with the names that are not empty, or nothing."""
	names = [n for n in names if n]
	return f' class="{" ".join(names)}"' if names else ""


def tinted(name: str, text: str | None = None, retro: bool = False) -> str:
	"""A planet's code (or other text) in its own tint."""
	return f'<span{cls(TINT.get(name, ""), "rv-n")}>{esc(text if text is not None else CODES.get(name, name))}</span>' + ('<sup>R</sup>' if retro else "")


def planet_rows(main: dict) -> list[dict]:
	"""The planets of the answer by name: {"name", "row", "retro"} in the usual order."""
	rows = {name_of(row["planet"]): row for row in main.get("planetary_positions") or []}
	return [{"name": name, "row": rows[name], "retro": bool(rows[name].get("is_retrograde"))} for name in arrange.ORDER if name in rows]


def degrees_only(value: float) -> str:
	return f"{int(value)}°"


def lagna_sign(main: dict) -> int | None:
	return rp.sign_index((main.get("lagna") or {}).get("sign"))


def table(head: list[str], rows: list[list[str]], cls: str = "rv-table", row_classes: list[str] | None = None) -> str:
	"""A small table; cells are markup the caller has made safe."""
	header = "<thead><tr>" + "".join(f'<th scope="col">{esc(h)}</th>' for h in head) + "</tr></thead>" if head else ""
	body = "".join(f'<tr{" class=" + chr(34) + row_classes[n] + chr(34) if row_classes and row_classes[n] else ""}>' + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for n, row in enumerate(rows))
	return f'<table class="{cls}">{header}<tbody>{body}</tbody></table>'


# ---- the North Indian chart with a planet's degree beside it, in any rectangle ----
def rect_shapes(w: float, h: float) -> dict[int, list[tuple[float, float]]]:
	"""The twelve houses of a North Indian chart in a w by h rectangle (house 1 is the top diamond; the houses run anticlockwise from it)."""
	a, q, t = w / 2, w / 4, w * 3 / 4
	b, r, u = h / 2, h / 4, h * 3 / 4
	return {1: [(a, 0), (t, r), (a, b), (q, r)], 2: [(0, 0), (a, 0), (q, r)], 3: [(0, 0), (q, r), (0, b)], 4: [(0, b), (q, r), (a, b), (q, u)], 5: [(0, b), (q, u), (0, h)], 6: [(0, h), (q, u), (a, h)],
			7: [(a, h), (q, u), (a, b), (t, u)], 8: [(a, h), (t, u), (w, h)], 9: [(w, h), (t, u), (w, b)], 10: [(w, b), (t, u), (a, b), (t, r)], 11: [(w, b), (t, r), (w, 0)], 12: [(w, 0), (t, r), (a, 0)]}


def middle(points: list[tuple[float, float]]) -> tuple[float, float]:
	"""Where a house's writing goes: the centre of the biggest circle that fits in a triangle, the centre of a diamond."""
	if len(points) == 3:
		(x1, y1), (x2, y2), (x3, y3) = points
		a, b, c = ((x2 - x3) ** 2 + (y2 - y3) ** 2) ** .5, ((x1 - x3) ** 2 + (y1 - y3) ** 2) ** .5, ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** .5
		return (a * x1 + b * x2 + c * x3) / (a + b + c), (a * y1 + b * y2 + c * y3) / (a + b + c)
	return sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points)


def rich_chart(houses: dict[int, list[tuple[str, str]]], signs: dict[int, int], w: int = 330, h: int | None = None, font: float | None = None, label: str = "") -> str:
	"""A North Indian chart, square or wide. houses: house number -> [(text, planet name)]; signs: house number -> its sign's number (1 is Aries)."""
	h = h or w
	font = font or max(10.0, min(w, h) * 0.036)
	cx0, cy0 = w / 2, h / 2
	out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(label)}" class="rv-chart">',
		   f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" fill="var(--rv-page)" stroke="var(--rv-heading)" stroke-width="2"/>']
	for number, points in rect_shapes(w, h).items():
		coordinates = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
		out.append(f'<polygon points="{coordinates}" fill="{"var(--rv-soft)" if number == 1 else "none"}" stroke="var(--rv-heading)" stroke-width="1.2"/>')
		mx, my = middle(points)
		inner = min(points, key=lambda p: (p[0] - cx0) ** 2 + (p[1] - cy0) ** 2)
		sx, sy = inner[0] + 0.30 * (mx - inner[0]), inner[1] + 0.30 * (my - inner[1])
		out.append(f'<text x="{sx:.1f}" y="{sy + font * 0.35:.1f}" text-anchor="middle" font-size="{font * 0.85:.1f}" fill="var(--rv-faint)">{signs[number]}</text>')
		items = houses.get(number, [])
		line = font * 1.18
		top = my + (0.0 if len(points) == 4 else font * 0.35) - line / 2 * (len(items) - 1) + font * 0.3
		for n, (text, planet) in enumerate(items):
			out.append(f'<text{cls(TINT.get(planet, ""))} x="{mx:.1f}" y="{top + line * n:.1f}" text-anchor="middle" font-size="{font:.1f}" font-weight="600">{esc(text)}</text>')
	out.append("</svg>")
	return "".join(out)


def natal_houses(main: dict, minutes: bool = True) -> tuple[dict, dict]:
	"""The planets of the answer in the houses of their chart, each with its degree; and the number of each house's sign."""
	lagna = main["lagna"]
	houses = {n: [] for n in range(1, 13)}
	houses[1].append((f"As {rp.degrees(lagna['degree']) if minutes else degrees_only(lagna['degree'])}", "Lagna"))
	for item in planet_rows(main):
		row = item["row"]
		degree = rp.degrees(row["longitude"]) if minutes else degrees_only(row["longitude"])
		houses[row["house"]].append((f"{CODES[item['name']]} {degree}" + (" R" if item["retro"] else ""), item["name"]))
	first = lagna_sign(main)
	return houses, {n: (first + n - 1) % 12 + 1 for n in range(1, 13)}


# ---- the panes ----
def chart(data: dict, ctx: dict, width: int = 330, height: int | None = None, minutes: bool = True, facts_beside: bool = False) -> dict | None:
	main = data["CORE_ADVANCED"]
	houses, signs = natal_houses(main, minutes)
	svg = rich_chart(houses, signs, width, height, label=arrange.pretty("Birth chart"))
	lagna = main["lagna"]
	moon = next((p for p in planet_rows(main) if p["name"] == "Moon"), None)
	summary = f"Lagna {arrange.sign_name(lagna['sign'])} {rp.degrees(lagna['degree'])}" + (f" · Moon {short_sign(moon['row']['sign'])}" if moon else "")
	if facts_beside:
		return {"body": f'<div class="rv-split"><div class="rv-fixed">{svg}</div><div>{facts(data, ctx, True)["body"]}</div></div>', "summary": summary}
	return {"body": svg, "summary": summary}


def varga(data: dict, ctx: dict, chart_key: str = "D9", size: int = 250, label: str = "") -> dict | None:
	main = data["CORE_ADVANCED"]
	picked = (main.get("divisional_charts") or {}).get(chart_key)
	if not picked or not picked.get("chart"):
		return None
	svg = rp.diamond_chart_svg(picked["chart"], int(picked.get("ascendant_house") or 0) % 12, "", size, 11, WEB_LOOK)
	svg = svg.replace("<svg ", f'<svg role="img" aria-label="{esc(label or chart_key)}" class="rv-chart" ', 1)
	return {"body": svg, "summary": f"Lagna {rp.SIGNS[int(picked.get('ascendant_house') or 0) % 12]}"}


def planets(data: dict, ctx: dict, compact: bool = False) -> dict | None:
	main = data["CORE_ADVANCED"]
	items = planet_rows(main)
	if not items:
		return None
	kp = {row["Object"]: row for row in (data.get("KP_SYSTEM") or {}).get("planets") or []}  # (a view that is not made from KP_SYSTEM has no sub lords: its table has no columns for them)
	lagna = main["lagna"]
	d9 = (main.get("divisional_charts") or {}).get("D9", {}).get("planet_signs") or {}
	rows = []
	if compact:
		head = ["", "Degree", "Sign", "H", "Nakshatra", "Star·Sub" if kp else "Star"]
		rows.append([f"<b>As</b>", rp.degrees(lagna["degree"]), short_sign(lagna["sign"]), "1", "", ""])
	else:
		head = ["", "Degree", "Sign", "Lord", "H", "Nakshatra", "Pada", "Star", *(["Sub", "SS"] if kp else []), "D9"]
		rows.append(["<b>As</b>", rp.degrees(lagna["degree"]), esc(arrange.sign_name(lagna["sign"])), CODES[rp.SIGN_LORDS[rp.sign_index(lagna["sign"])]], "1", "", "", "", *(["", ""] if kp else []), ""])
	for item in items:
		row, name = item["row"], item["name"]
		k = kp.get(name, {})
		star = CODES.get(name_of(row["nakshatra_lord"]), "")
		sub = CODES.get(k.get("SubLord", ""), "")
		nak = rp.NAKSHATRAS[(row["nakshatra_index"] - 1) % 27]
		if compact:
			rows.append([tinted(name, retro=item["retro"]), rp.degrees(row["longitude"]), short_sign(row["sign"]), str(row["house"]), f"{esc(nak)} {row['pada']}", f"{star}·{sub}" if sub else star])
		else:
			d9_value = next((v for key, v in d9.items() if key.startswith(name) and not key.startswith(name + " ")), "")
			rows.append([tinted(name, retro=item["retro"]), rp.degrees(row["longitude"]), esc(arrange.sign_name(row["sign"])), CODES[rp.SIGN_LORDS[rp.sign_index(row["sign"])]], str(row["house"]), esc(nak), str(row["pada"]),
						 star, *([sub, CODES.get(k.get("SubSubLord", ""), "")] if kp else []), esc(SHORT.get(arrange.place(d9_value)[0].split(" ")[0], ""))])
	moon = next((i for i in items if i["name"] == "Moon"), None)
	return {"body": f'<div class="rv-wrap">{table(head, rows, "rv-table rv-tight" if compact else "rv-table")}</div>',
			"summary": f"{len(items)} planets" + (f" · Moon in {short_sign(moon['row']['sign'])}" if moon else "")}


def running(periods: list[dict], today: datetime.date) -> dict | None:
	return next((p for p in periods if arrange.running(p, today)), None)


def dasha(data: dict, ctx: dict, later: int = 2) -> dict | None:
	main = data["CORE_ADVANCED"]
	periods = ((main.get("dasha_sequences") or {}).get("vimshottari") or {}).get("mahadasha") or []
	now = running(periods, ctx["today"])
	if not now:
		return None
	lord = name_of(now["lord"])
	sub = running(now.get("antardasha") or [], ctx["today"])
	head = f'<div class="rv-run"><b>{CODES[lord]}–{CODES[name_of(sub["lord"])] if sub else ""}</b> running' + (f" · until {esc(arrange.longdate(sub['end_date']))}" if sub and sub.get("end_date") else "") + "</div>"
	rows, classes = [], []
	for item in now.get("antardasha") or []:
		rows.append([f"{CODES[lord]}–{CODES[name_of(item['lord'])]}", esc(arrange.longdate(item["end_date"])) if item.get("end_date") else "—"])
		classes.append("rv-now" if arrange.running(item, ctx["today"]) else "")
	after = [p for p in periods if now.get("end_date") and p.get("start_date") and p["start_date"] >= now["end_date"]][:later]
	for p in after:
		rows.append([f"{CODES[name_of(p['lord'])]} main", esc(arrange.longdate(p["end_date"])) if p.get("end_date") else "—"])
		classes.append("rv-dim")
	summary = f"{CODES[lord]}–{CODES[name_of(sub['lord'])]}" if sub else CODES[lord]
	if sub and sub.get("end_date"):
		summary += f" until {arrange.longdate(sub['end_date'])}"
	return {"body": head + table([], rows, "rv-table rv-tight", classes), "summary": summary}


def drishti(data: dict, ctx: dict) -> dict | None:
	d = data["CORE_ADVANCED"].get("drishti")
	if not d or not d.get("matrix"):
		return None
	names = d["planets"]
	head = "<thead><tr><th></th>" + "".join(f'<th scope="col">{CODES.get(n, n)}</th>' for n in names) + "</tr></thead>"
	rows = []
	for i, name in enumerate(names):
		cells = []
		for j, value in enumerate(d["matrix"][i]):
			if i == j:
				cells.append('<td class="rv-x">·</td>')
			elif value < 1:
				cells.append("<td></td>")
			else:
				cells.append(f'<td class="rv-h{min(int(value / 60 * 9) + 1, 9)}{" rv-strong" if value >= 45 else ""}">{round(value)}</td>')
		rows.append(f'<tr><th scope="row"{cls(TINT.get(name, ""))}>{CODES.get(name, name)}</th>{"".join(cells)}</tr>')
	pairs = sorted(((v, i, j) for i, row in enumerate(d["matrix"]) for j, v in enumerate(row) if i != j and {i, j} != {7, 8}), reverse=True)[:3]
	return {"body": f'<table class="rv-matrix">{head}<tbody>{"".join(rows)}</tbody></table><p class="rv-cap">Row looks at column, in virupas (60 is a full aspect). Darker is stronger.</p>',
			"summary": "strongest " + ", ".join(f"{CODES[names[i]]}→{CODES[names[j]]} {round(v)}" for v, i, j in pairs)}


def shadbala(data: dict, ctx: dict) -> dict | None:
	comp = (data["CORE_ADVANCED"].get("shadbala") or {}).get("components") or {}
	if not comp.get("total_rupas"):
		return None
	names = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
	keys = {n: next((k for k in comp["total_rupas"] if name_of(k) == n), None) for n in names}
	if not all(keys.values()):
		return None
	w, h, base, unit = 300, 130, 106, 46
	out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="Strength of each planet in rupas" class="rv-bars">',
		   f'<line x1="8" x2="{w - 8}" y1="{base - unit}" y2="{base - unit}" stroke="var(--rv-low)" stroke-dasharray="3 3" stroke-width="1"/>',
		   f'<text x="{w - 10}" y="{base - unit - 4}" text-anchor="end" font-size="9" fill="var(--rv-low)">needed</text>']
	good, low = [], []
	for n, name in enumerate(names):
		relative, rupa = comp["relative_strength"][keys[name]], comp["total_rupas"][keys[name]]
		height = min(relative, 2.0) * unit
		x = 14 + n * 40
		out.append(f'<rect class="{"rv-bar-good" if relative >= 1 else "rv-bar-low"}" x="{x}" y="{base - height:.1f}" width="30" height="{height:.1f}" rx="2"/>')
		out.append(f'<text x="{x + 15}" y="{base - height - 4:.1f}" text-anchor="middle" font-size="10" font-weight="700" fill="var(--rv-ink)">{rupa:.1f}</text>')
		out.append(f'<text class="{TINT[name]}" x="{x + 15}" y="{base + 14}" text-anchor="middle" font-size="11" font-weight="700">{CODES[name]}</text>')
		(good if relative >= 1 else low).append((rupa, f"{CODES[name]} {rupa:.1f}"))
	out.append("</svg>")
	strong, weak = [text for _, text in sorted(good, reverse=True)[:2]], [text for _, text in sorted(low)[:2]]
	return {"body": "".join(out) + '<p class="rv-cap">Total rupas; a bar is green when the planet has the strength it needs.</p>', "summary": f"strong {', '.join(strong) or '—'} · weak {', '.join(weak) or '—'}"}


def karakas(data: dict, ctx: dict, lagnas: bool = True, arudhas: bool = True) -> dict | None:
	info = data["CORE_ADVANCED"].get("planets", {}).get("info") or {}
	found = {}
	for key, value in info.items():
		for word, code in KARAKA.items():
			if f"({word} Karaka)" in value:
				found[code] = name_of(key.replace(INFO, "").replace("℞", ""))
	if not found:
		return None
	top = "".join(f'<th scope="col">{c}</th>' for c in KARAKA_ORDER)
	low = "".join(f'<td{cls(TINT.get(found.get(c), ""))}>{CODES.get(found.get(c), "")}</td>' for c in KARAKA_ORDER)
	out = [f'<table class="rv-karakas"><thead><tr>{top}</tr></thead><tbody><tr>{low}</tr></tbody></table>']
	if lagnas:
		cells = []
		for code, key in LAGNAS:
			spot = arrange.place(info.get(INFO + key, ""))[0]
			cells.append(f"<td><b>{code}</b> {esc(SHORT.get(spot.split(' ')[0], ''))} {esc(spot.split(') ')[-1] if ') ' in spot else '')}</td>")
		out.append('<table class="rv-cells"><tbody>' + "".join("<tr>" + "".join(cells[i:i + 3]) + "</tr>" for i in range(0, len(cells), 3)) + "</tbody></table>")
	if arudhas:
		cells = []
		for key, value in info.items():
			if key.startswith("D-1-") and "(" in key:
				cells.append(f"<td><b>{esc(key[key.rindex('(') + 1:-1])}</b> {esc(short_sign(value))}</td>")
		if cells:
			out.append('<table class="rv-cells"><tbody>' + "".join("<tr>" + "".join(cells[i:i + 4]) + "</tr>" for i in range(0, len(cells), 4)) + "</tbody></table>")
	return {"body": "".join(out), "summary": " · ".join(f"{c} {CODES.get(found.get(c), '')}" for c in KARAKA_ORDER[:3])}


def houses(data: dict, ctx: dict, two: bool = False) -> dict | None:
	listed = (data["CORE_ADVANCED"].get("houses") or {}).get("houses") or []
	if not listed:
		return None
	cells = [(str(h["house_number"]), esc(short_sign(h["sign"])), CODES[name_of(h["lord"])], esc(", ".join(CODES[name_of(p["name"])] for p in h.get("planets") or []))) for h in listed]
	head = ["H", "Sign", "Lord", "Planets"]
	if two:
		rows = [list(cells[i]) + [""] + list(cells[i + 6]) for i in range(6)]
		body = table(head + [""] + head, rows, "rv-table rv-tight")
	else:
		body = table(head, [list(c) for c in cells], "rv-table rv-tight")
	occupied = [f"{h['house_number']} {', '.join(CODES[name_of(p['name'])] for p in h['planets'])}" for h in listed if h.get("planets")]
	return {"body": f'<div class="rv-wrap">{body}</div>', "summary": " · ".join(occupied)}


def facts(data: dict, ctx: dict, panchang: bool = True) -> dict | None:
	main = data["CORE_ADVANCED"]
	moon = next((p for p in planet_rows(main) if p["name"] == "Moon"), None)
	now = running(((main.get("dasha_sequences") or {}).get("vimshottari") or {}).get("mahadasha") or [], ctx["today"])
	sub = running((now or {}).get("antardasha") or [], ctx["today"])
	items = [("Lagna", f"{arrange.sign_name(main['lagna']['sign'])} {rp.degrees(main['lagna']['degree'])}")]
	if moon:
		items += [("Moon sign", arrange.sign_name(moon["row"]["sign"])), ("Birth star", f"{rp.NAKSHATRAS[(moon['row']['nakshatra_index'] - 1) % 27]}, pada {moon['row']['pada']}")]
	if panchang and main.get("panchanga"):
		p = main["panchanga"]
		spans = {key: arrange.timed(p.get(label)) for key, label in (("tithi", "Tithi"), ("yoga", "Yoga"), ("karana", "Karana"))}
		if all(spans.values()):
			items += [("Tithi", spans["tithi"]["name"]), ("Yoga · karana", f"{spans['yoga']['name']} · {spans['karana']['name']}")]
		if p.get("Day"):
			items.append(("Weekday", f"{p['Day']} · rise {str(p.get('Sun Rise', ''))[:5]}, set {str(p.get('Sun Set', ''))[:5]}"))
	if now and sub:
		items.append(("Running", f"{name_of(now['lord'])} / {name_of(sub['lord'])}" + (f" · to {arrange.longdate(sub['end_date'])}" if sub.get("end_date") else "")))
	if panchang:
		dosha = main.get("dosha") or {}
		manglik = dosha.get("manglik") or {}
		if manglik:
			items.append(("Manglik", "Yes by the usual rule" if manglik.get("present") else "No"))  # (the library's "exceptions" are 17 loose conditions nearly everyone meets: they are not read as a cancellation)
		if "kala_sarpa" in dosha:
			items.append(("Kala sarpa", "Yes" if dosha["kala_sarpa"] else "No"))
	return {"body": '<table class="rv-facts"><tbody>' + "".join(f'<tr><th scope="row">{esc(k)}</th><td>{esc(v)}</td></tr>' for k, v in items) + "</tbody></table>", "summary": " · ".join(v for _, v in items[:3])}


def today(data: dict, ctx: dict, size: int = 190) -> dict | None:
	"""Today's planets in the person's houses: today's sky gives each planet's sign; the person's lagna turns the sign into a house."""
	sky, main = ctx.get("sky"), data["CORE_ADVANCED"]
	first = lagna_sign(main)
	if not sky or first is None:
		return None
	houses = {n: [] for n in range(1, 13)}
	houses[1].append(("As", "Lagna"))
	lines = []
	for row in sky.get("planetary_positions") or []:
		name = name_of(row["planet"])
		sign = rp.sign_index(row["sign"])
		house = (sign - first) % 12 + 1
		retro = bool(row.get("is_retrograde"))
		houses[house].append((CODES[name] + (" R" if retro else ""), name))
		lines.append([tinted(name, retro=retro), f"{SHORT[rp.SIGNS[sign]]} {rp.degrees(row['longitude'])}", f"house {house}"])
	svg = rich_chart(houses, {n: (first + n - 1) % 12 + 1 for n in range(1, 13)}, size, size, 9, label="Today's planets in your houses")
	moved = [f"{CODES[name_of(r['planet'])]} {(rp.sign_index(r['sign']) - first) % 12 + 1}" for r in sky.get("planetary_positions") or []]
	return {"body": f'<div class="rv-split"><div class="rv-fixed">{svg}</div><div>{table([], lines, "rv-table rv-tight")}</div></div>', "summary": "today: " + " · ".join(moved[:4])}


PANES = {"chart": chart, "varga": varga, "planets": planets, "dasha": dasha, "drishti": drishti, "shadbala": shadbala, "karakas": karakas, "houses": houses, "facts": facts, "today": today}
