"""The numerology report as a page: the numbers as medallions, a chip for each topic (self, love, career, money, health, family) and, under the one chosen, what the tradition says of the person's numbers for it.

Drawn by websitehq's Medallion Report Card from what this answers (servicehq's report_board asks the vertical: vocabulary "reports" "numerology" "board"). Every sum is the engine's; the words of the Self topic are the engine's own reading,
the words of the others are numerology_topics.py (a few plain sentences per number). Classical numerology, a traditional system: it says what a number is said to mean, never what will happen. The report's PDF is kept as it was."""
from frappe import _
from frappe.utils import getdate, today

from raftor_astrohq import astrology
from raftor_astrohq.numerology_topics import TOPICS

ORDER = (("self", "user"), ("love", "heart"), ("career", "briefcase"), ("money", "wallet"), ("health", "flame"), ("family", "users"))


def _labels() -> dict:
	return {"self": _("Self"), "love": _("Love"), "career": _("Career"), "money": _("Money"), "health": _("Health"), "family": _("Family")}


def _topic_text(number, key: str) -> str:
	return (TOPICS.get(int(number)) or {}).get(key, "") if str(number).isdigit() else ""


def board(item_code: str, details: dict, user: str) -> dict:
	name = str(details.get("report_name") or "").strip()
	born = getdate(details.get("birth_date"))
	on = getdate(today())
	answer = astrology.numerology(day=born.day, month=born.month, year=born.year, name=name, start=on.isoformat())
	reading = answer["reading"]
	rb, rn, rp, ry = reading["birth"], reading["name"], reading.get("period"), reading.get("year")
	labels = _labels()

	medallions = [{"label": _("Birth number"), "value": str(rb["number"]), "caption": rb["headline"]}, {"label": _("Name number"), "value": str(rn["number"]), "caption": rn["headline"]}]
	if ry:
		medallions.append({"label": _("Year number"), "value": str(ry["number"]), "caption": str(ry["year"])})
	if rp:
		medallions.append({"label": _("Period"), "value": str(rp["number"]), "caption": f'{rp["sign"]} · {rp["element"]}'})

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
	lead = _("{0}, you were born on a day of the {1}: {2}. Your name carries the number {3} ({4}).").format(first, rb["number"], rb["headline"].lower(), rn["number"], rn["headline"].lower())
	return {
		"title": _("Your numerology report"), "subtitle": f'{name} · {born.strftime("%A")}, {born.day} {born.strftime("%B %Y")}', "lead": lead,
		"topic_label": _("What would you like to look at?"),
		"medallions": medallions,
		"topics": [{"key": key, "label": labels[key], "icon": icon} for key, icon in ORDER],
		"sections": {key: [b for b in blocks if b.get("text")] for key, blocks in sections.items()},
		"note": _("This is classical numerology, a traditional system: it describes what each number is said to mean. It is not a fact and not a prediction. Read it as a mirror to think with."),
	}
