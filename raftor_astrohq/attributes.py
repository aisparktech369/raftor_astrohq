"""The options AstroHQ sells as variants, as data for websitehq to draw (hook rfhq_attribute_sets; website_hq/attribute_sets.py).

A gemstone is worn as a ring or a pendant, or sold as the stone alone, so "Type" is a choice that changes what the shopper buys and pays; and a
stone is sold by weight in ratti, so "Size" gets the ratti sizes beside the standard ones the site already has. websitehq knows only how to draw
an attribute; what the values are, and their icons, are this vertical's. Edit the list (or the attribute in Desk) to change it: values are added
if missing and nothing already set on the site is overwritten.
"""

ICONS = "/assets/raftor_astrohq/icons/"
RATTI = range(3, 13)  # 3 to 12 ratti


def attribute_sets() -> list[dict]:
	return [
		{"attribute": "Type", "display_as": "Icons", "values": [
			{"value": "Gemstone only", "abbr": "GEM", "icon": ICONS + "gemstone.svg"},
			{"value": "Ring", "abbr": "RNG", "icon": ICONS + "ring.svg"},
			{"value": "Pendant", "abbr": "PND", "icon": ICONS + "pendant.svg"},
			{"value": "Bracelet", "abbr": "BRC", "icon": ICONS + "bracelet.svg"},
		]},
		{"attribute": "Size", "display_as": "Default", "values": [{"value": f"{n} Ratti", "abbr": f"R{n}"} for n in RATTI]},
	]
