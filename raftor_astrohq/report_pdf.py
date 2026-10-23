"""The pages of the reports: the words of astrology as people read them, the birth chart as a North Indian diamond, and the HTML that becomes the PDF.

Nothing here calculates a chart. The engine's answers come in (see astrology.py); this turns them into names (the nakshatra by its usual Sanskrit name, the sign
with its Hindi name beside it), puts the planets in the houses of a drawing, and lays the pages out. The panchang's tithi, yoga and karana are read from the
Sun's and the Moon's longitudes the engine gave, by their usual rules, so that they have the same names everywhere.
"""
import datetime
from html import escape

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
RASHIS = ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya", "Tula", "Vrishchika", "Dhanu", "Makara", "Kumbha", "Meena"]
SIGN_LORDS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra",
			  "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
PLANETS = {"Su": "Sun", "Mo": "Moon", "Ma": "Mars", "Me": "Mercury", "Ju": "Jupiter", "Ve": "Venus", "Sa": "Saturn", "Ra": "Rahu", "Ke": "Ketu"}
TITHIS = ["Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi"]
YOGAS = ["Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarma", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
		 "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti"]
MOVABLE_KARANAS = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"]
# The engine writes a planet as "Mercury☿" (and "Venus♀℞" when it moves backwards); the first letters tell which.
ENGINE_NAMES = {"Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me", "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa", "Raagu": "Ra", "Rahu": "Ra", "Kethu": "Ke", "Ketu": "Ke",
				"Ascendant": "Asc"}

INK, ACCENT, LINE, SOFT = "#2b1a3d", "#6b3fa0", "#b9a6d3", "#f5f0fb"


# ---- reading the engine's words ----
def sign_index(text) -> int | None:
	"""The sign (0 = Aries) named in an engine string such as "♍︎Virgo 14° 11’ 53"", or None."""
	for index, name in enumerate(SIGNS):
		if name.lower() in str(text or "").lower():
			return index
	return None


def planet_code(text) -> str | None:
	"""The two-letter code of a planet in an engine name such as "Mercury☿" or "Me☿", or None."""
	head = "".join(ch for ch in str(text or "") if ch.isalpha())
	for name, code in ENGINE_NAMES.items():
		if head.startswith(name):
			return code
	return head[:2] if head[:2] in PLANETS else None


def sign_label(index: int) -> str:
	return f"{SIGNS[index]} ({RASHIS[index]})"


def nakshatra_label(index: int, pada: int | None = None) -> str:
	name = NAKSHATRAS[(int(index) - 1) % 27]
	return f"{name}, pada {pada}" if pada else name


def degrees(value) -> str:
	"""Degrees inside a sign as 14°11'."""
	whole = int(value)
	minutes = int((value - whole) * 60 + 1e-6)  # (the small sum keeps 14.2 from reading 14°11′: 0.2 * 60 is 11.999999999999996)
	return f"{whole}°{minutes:02d}′"


def panchang_of(sun: float, moon: float) -> dict:
	"""Tithi (with its paksha), yoga and karana from the Sun's and the Moon's longitudes (0 to 360, sidereal)."""
	elongation = (moon - sun) % 360.0
	number = int(elongation // 12.0) + 1  # 1 to 30
	paksha = "Shukla" if number <= 15 else "Krishna"
	name = "Purnima" if number == 15 else "Amavasya" if number == 30 else TITHIS[(number - 1) % 15]
	half = int(elongation // 6.0)  # 0 to 59
	karana = "Kimstughna" if half == 0 else "Shakuni" if half == 57 else "Chatushpada" if half == 58 else "Naga" if half == 59 else MOVABLE_KARANAS[(half - 1) % 7]
	yoga = YOGAS[int(((sun + moon) % 360.0) // (360.0 / 27.0))]
	return {"tithi": f"{paksha} paksha {name}", "tithi_number": number, "yoga": yoga, "karana": karana}


# ---- the birth chart, North Indian style ----
def _house_shapes(size: float) -> dict[int, list[tuple[float, float]]]:
	a, q, t, w = size / 2, size / 4, size * 3 / 4, size
	return {
		1: [(a, 0), (t, q), (a, a), (q, q)], 2: [(0, 0), (a, 0), (q, q)], 3: [(0, 0), (q, q), (0, a)], 4: [(0, a), (q, q), (a, a), (q, t)],
		5: [(0, a), (q, t), (0, w)], 6: [(0, w), (q, t), (a, w)], 7: [(a, w), (q, t), (a, a), (t, t)], 8: [(a, w), (t, t), (w, w)],
		9: [(w, w), (t, t), (w, a)], 10: [(w, a), (t, t), (a, a), (t, q)], 11: [(w, a), (t, q), (w, 0)], 12: [(w, 0), (t, q), (a, 0)],
	}


def diamond_chart_svg(cells: list[str], lagna: int, title: str = "", size: int = 300, font: int = 12) -> str:
	"""A North Indian chart. `cells` is the engine's list of twelve texts, one for each sign from Aries, naming the planets in it; `lagna` is the sign (0 = Aries)
	of house 1, which is the top diamond, and the houses run anticlockwise from it. Each house shows its sign's number and its planets (written `font` high: smaller for a small chart).
	The title, when there is one, is written under the drawing, in room made for it."""
	shapes = _house_shapes(size)
	room = 22 if title else 0
	out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size + room}" viewBox="0 0 {size} {size + room}">',
		   f'<rect x="0" y="0" width="{size}" height="{size}" fill="#ffffff" stroke="{ACCENT}" stroke-width="2"/>']
	for number, points in shapes.items():
		coordinates = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
		out.append(f'<polygon points="{coordinates}" fill="{SOFT if number == 1 else "#ffffff"}" stroke="{ACCENT}" stroke-width="1.4"/>')
		sign = (lagna + number - 1) % 12
		cx, cy = sum(x for x, _y in points) / len(points), sum(y for _x, y in points) / len(points)
		names = []
		for line in str(cells[sign] if sign < len(cells) else "").splitlines():
			code = planet_code(line)
			if code:
				names.append(code + ("(R)" if "℞" in line else ""))
		out.append(f'<text x="{cx:.1f}" y="{cy + 15:.1f}" text-anchor="middle" font-size="11" fill="#8a7aa3" font-family="Arial, sans-serif">{sign + 1}</text>')
		rows = [" ".join(names[i:i + 3]) for i in range(0, len(names), 3)] or [""]
		line = font + 2
		top = cy - 4 - line / 2 * (len(rows) - 1)
		for n, row in enumerate(rows):
			out.append(f'<text x="{cx:.1f}" y="{top + line * n:.1f}" text-anchor="middle" font-size="{font}" font-weight="bold" fill="{INK}" font-family="Arial, sans-serif">{escape(row)}</text>')
	if title:
		out.append(f'<text x="{size / 2}" y="{size + 16}" text-anchor="middle" font-size="12" fill="{INK}" font-family="Arial, sans-serif">{escape(title)}</text>')
	out.append("</svg>")
	return "".join(out)


# ---- pages ----
STYLE = f"""
<style>
body {{ font-family: Arial, Helvetica, sans-serif; color: {INK}; font-size: 12px; line-height: 1.45; }}
h1 {{ font-size: 25px; color: {ACCENT}; margin: 0 0 2px 0; }}
h2 {{ font-size: 15px; color: {ACCENT}; border-bottom: 2px solid {LINE}; padding-bottom: 3px; margin: 20px 0 8px 0; page-break-after: avoid; }}
p.sub {{ color: #6f6285; margin: 0 0 10px 0; font-size: 13px; }}
table {{ border-collapse: collapse; width: 100%; page-break-inside: avoid; }}
th {{ background: {SOFT}; color: {ACCENT}; text-align: left; padding: 5px 8px; border: 1px solid {LINE}; font-size: 11px; }}
td {{ padding: 5px 8px; border: 1px solid {LINE}; vertical-align: top; }}
td.k {{ width: 32%; color: #6f6285; background: #fbf9fe; }}
.num {{ text-align: right; white-space: nowrap; }}
.now td {{ background: #fff4d6; font-weight: bold; }}
.charts td {{ border: none; text-align: center; padding: 6px 0 0 0; }}
.note {{ color: #6f6285; font-size: 10.5px; margin-top: 6px; }}
.total {{ font-size: 15px; font-weight: bold; color: {ACCENT}; }}
.bar {{ background: #e9e1f5; height: 11px; width: 100%; }}
.bar div {{ background: {ACCENT}; height: 11px; }}
.footer {{ color: #8a7aa3; font-size: 10px; margin-top: 22px; border-top: 1px solid {LINE}; padding-top: 6px; }}
.brand {{ color: #8a7aa3; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; }}
.card td {{ width: 50%; }}
</style>
"""


def _table(rows: list[list], head: list[str] | None = None, classes: dict | None = None) -> str:
	body = ""
	for row in rows:
		cls = (classes or {}).get(id(row), "")
		body += f'<tr class="{cls}">' + "".join(f"<td>{cell}</td>" if not str(cell).startswith("<td") else str(cell) for cell in row) + "</tr>"
	header = "<tr>" + "".join(f"<th>{escape(h)}</th>" for h in head) + "</tr>" if head else ""
	return f"<table>{header}{body}</table>"


def _facts(rows: list[tuple[str, str]]) -> str:
	return "<table>" + "".join(f'<tr><td class="k">{escape(label)}</td><td>{escape(value)}</td></tr>' for label, value in rows) + "</table>"


def page(title: str, body: str, brand: str, credit: str) -> str:
	return (f"<html><head><meta charset='utf-8'>{STYLE}</head><body>{body}"
			f'<div class="footer">{escape(credit)}<br>{escape(brand)}</div></body></html>')


def offset_text(hours: float) -> str:
	sign = "+" if hours >= 0 else "-"
	total = int(round(abs(hours) * 60))
	return f"UTC{sign}{total // 60:02d}:{total % 60:02d}"


def long_date(day: datetime.date) -> str:
	return f"{day.day:02d} {day.strftime('%B %Y')}"
