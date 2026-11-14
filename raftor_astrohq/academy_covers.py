"""A picture for each Dreams and Numerology article, chosen for what the article is about.
The files are in public/images/academy/ (credits in CREDITS.md there). All are public domain or CC0: NASA photographs and artworks from Wikimedia Commons.
`cover(item)` is used by content._cover; it returns None for an article it has no picture for, and the series picture is used then."""

import re

BASE = "/assets/raftor_astrohq/images/"
SERIES_PICTURE = {"dreams": BASE + "academy-dreams.jpg", "numerology": BASE + "academy-numerology.jpg"}  # The Starry Night; Pythagoras

PLANETS = {"1": "sun", "2": "moon", "3": "jupiter", "4": "eclipse", "5": "mercury", "6": "venus", "7": "comet", "8": "saturn", "9": "mars"}  # number: picture (Rahu is the eclipse, Ketu the comet)

BY_TITLE = {
	# numerology ("Cheiro on " is dropped before the lookup, so each pair of articles shares its picture)
	"numbers, an introduction": "pythagoras-tablet",
	"the single numbers and the birth number": "fortune-birth",
	"the planetary numbers of the months": "months",
	"name numbers and the mystic alphabet": "alphabet",
	"the compound numbers 10 to 52": "arithmetic",
	"using single and compound numbers": None,  # the series picture (Pythagoras)
	"why the birth number matters most": "fortune-matters",
	"names, titles and the two alphabets": "alphabet-two",
	"finding a lucky day": "fortune-lucky",
	"colours and numbers": "colours",
	"concentrating on one's number": "contemplation",
	"numbers 1 and 4, and advice for 4 and 8": "eclipse",
	"persons born under 4 and 8": "saturn-rings",
	"colours, numbers and music": "lute-music",
	# dreams
	"how a dream is read: the dream method": "sleeping-gypsy",
	"the lenses of dream reading and what each rests on": "eye-balloon",
	"common dream scenarios and what they may mean": "icarus",
	"dream archetypes: shadow, hero's journey and wise guide": "wanderer",
	"dream symbols: a starter dictionary": "vanitas-globe",
	"dream symbols: actions and events": "great-wave",
	"dream symbols: animals": "rousseau-dream",
	"dream symbols: objects": "vanitas-violin",
	"dream symbols: places and locations": "isle-of-the-dead",
	"dream symbols: feelings and emotional states": "scream",
	"following a dream over time (only if you choose)": "moon-phases",
	"dream symbols: spiritual and mythological images": "vishnu-shesha",
	"agni purana dream omens: compiled notes": "agni",
	"ayurvedic and garuda purana dream notes: compiled notes": "garuda",
	"swapna shastra symbol notes: compiled notes": "vishnu-drawing",
	"dream timing in the indian tradition: compiled notes": "sunrise",
}


def cover(item: dict) -> str | None:
	"""The picture for one article, by its title; None when it has no picture of its own."""
	title = re.sub(r"^cheiro on ", "", str(item.get("title") or "").strip().lower())
	number = re.fullmatch(r"(?:the )?number ([1-9])(?: and \w+: .*)?", title)
	key = PLANETS[number.group(1)] if number else BY_TITLE.get(title)
	return f"{BASE}academy/{key}.jpg" if key else None


def refresh():
	"""Give every published Dreams and Numerology article its picture (run after the pictures or the table above change): bench --site <site> execute raftor_astrohq.academy_covers.refresh"""
	import frappe

	changed = 0
	for post in frappe.get_all("Blog Post", filters={"blog_category": ["in", list(SERIES_PICTURE)]}, fields=["name", "title", "blog_category", "meta_image"]):
		want = cover({"title": post.title}) or SERIES_PICTURE[post.blog_category]
		if post.meta_image != want:
			frappe.db.set_value("Blog Post", post.name, "meta_image", want, update_modified=False)
			changed += 1
	frappe.db.commit()
	return changed
