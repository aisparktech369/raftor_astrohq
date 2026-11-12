"""What the numerology page shows for a name and a birth date: the numbers as medallions (each with how it was found and what it is said to mean), a chip for each topic (self, love, career, money, health, family) and,
under the one chosen, what the tradition says of the person's numbers for it.

Every sum is the engine's; the words of the Self topic and of each number are the engine's own reading, the words of the other topics are numerology_topics.py (a few plain sentences per number). Classical numerology, a traditional
system: it says what a number is said to mean, never what will happen. numerology_page.py is the page's methods; websitehq's Number Reveal Card draws what they answer."""
import datetime

from frappe import _
from frappe.utils import getdate, today

from raftor_astrohq import astrology
from raftor_astrohq.numerology_topics import TOPICS

ORDER = (("self", "user"), ("love", "heart"), ("career", "briefcase"), ("money", "wallet"), ("health", "flame"), ("family", "users"))


def _labels() -> dict:
	return {"self": _("Self"), "love": _("Love"), "career": _("Career"), "money": _("Money"), "health": _("Health"), "family": _("Family")}


def _topic_text(number, key: str) -> str:
	return (TOPICS.get(int(number)) or {}).get(key, "") if str(number).isdigit() else ""


def _sum(step: str) -> str:
	"""'1+4=5' as '1 + 4 = 5'."""
	return str(step).replace("+", " + ").replace("=", " = ")


def _chain(steps: list) -> str:
	return " → ".join(_sum(step) for step in steps)


def _day_month(text: str) -> str:
	"""'04-20' as '20 Apr'."""
	try:
		month, day = (int(part) for part in str(text).split("-"))
		return f"{day} {datetime.date(2001, month, 1).strftime('%b')}"
	except ValueError:
		return str(text)


def build(name: str, born: datetime.date, on: datetime.date | None = None) -> dict:
	on = on or getdate(today())
	answer = astrology.numerology(day=born.day, month=born.month, year=born.year, name=name, start=on.isoformat())
	reading = answer["reading"]
	rb, rn, rp, ry = reading["birth"], reading["name"], reading.get("period"), reading.get("year")
	labels = _labels()

	spelled = []
	for word in answer["name"]["words"]:
		letters = " + ".join(f'{x["letter"]}{x["value"]}' for x in word["letters"])
		spelled.append(f'{word["word"].upper()}: {letters} = {word["total"]} → ' + " → ".join(str(s).split("=")[-1] for s in word["steps"][1:] or [str(word["root"])]))
	if len(answer["name"]["words"]) > 1:
		spelled.append(_chain(answer["name"]["combined"]["steps"]))
	numbers = [
		{"key": "birth", "label": _("Birth number"), "value": str(rb["number"]), "caption": rb["headline"], "found": f'{born.day}: ' + _chain(answer["birth"]["steps"]), "text": rb["summary"]},
		{"key": "name", "label": _("Name number"), "value": str(rn["number"]), "caption": rn["headline"], "found": "\n".join(spelled), "text": rn["summary"]},
	]
	if ry:
		numbers.append({"key": "year", "label": _("Year number"), "value": str(ry["number"]), "caption": str(ry["year"]), "found": f'{ry["year"]}: ' + _chain(answer["year"]["steps"]), "text": ry["text"][:1].upper() + ry["text"][1:]})
	if rp:
		period = (answer.get("zodiac") or {}).get("periods", [{}])[0]
		span = f'{_day_month(period.get("from"))} – {_day_month(period.get("to"))}' if period.get("from") else ""
		numbers.append({"key": "period", "label": _("Period"), "value": str(rp["number"]), "caption": f'{rp["sign"]} · {rp["element"]}', "found": f'{rp["sign"]}, {span}, ' + _("ruled by {0}").format(rp["ruler"]) if span else rp["sign"],
						"text": rp["text"][:1].upper() + rp["text"][1:]})

	def about(key: str) -> list[dict]:
		blocks = [{"heading": _("Birth number {0}").format(rb["number"]), "text": _topic_text(rb["number"], key)}]
		if rn["number"] != rb["number"]:
			blocks.append({"heading": _("Name number {0}").format(rn["number"]), "text": _topic_text(rn["number"], key)})
		return [b for b in blocks if b["text"]]

	sections = {
		"self": [{"heading": _("Who you are: birth number {0}").format(rb["number"]), "text": rb["summary"]},
				 {"heading": _("What you bring"), "text": ", ".join(rb["strengths"]) + "."},
				 {"heading": _("What to watch"), "text": ", ".join(rb["watch"]) + "."},
				 {"heading": _("How your name fits your birth number"), "text": rn["harmony"]["text"]}],
		"love": about("love") + [{"heading": _("Numbers that go with yours"), "text": rb["pairs"]}],
		"career": about("career") + [{"heading": _("Using your number"), "text": rb["use_it"]}],
		"money": about("money"), "health": about("health"), "family": about("family"),
	}
	first = name.split()[0] if name.split() else name
	return {
		"name": name, "born_label": f'{born.day} {born.strftime("%B %Y")}',
		"lead": _("{0}, you were born on a day of the {1}: {2}. Your name carries the number {3} ({4}).").format(first, rb["number"], rb["headline"].lower(), rn["number"], rn["headline"].lower()),
		"numbers": numbers,
		"topics": [{"key": key, "label": labels[key], "icon": icon} for key, icon in ORDER],
		"sections": {key: [b for b in blocks if b.get("text")] for key, blocks in sections.items()},
		"note": _("This is classical numerology, a traditional system: it describes what each number is said to mean. It is not a fact and not a prediction. Read it as a mirror to think with."),
	}
