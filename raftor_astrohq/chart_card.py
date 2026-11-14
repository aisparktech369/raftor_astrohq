"""A person's birth chart drawn for the chat: the North Indian diamond, from the engine's answer for one of the signed-in person's own saved profiles.

The guides' `get_report` tool hands the chat a card with the address of the drawing (`card`); the chat shows it in the guide's reply and a tap opens it larger. The drawing itself is made here, only for a
person who is signed in and only for a profile saved under that person's own account, so a chart (which is made from birth details) is never a public file whose link can be passed on.
"""
import frappe
from frappe import _

from raftor_astrohq import answers, person, report_pdf as rp, report_view

KINDS = {"d1": ("D1", _("Lagna chart (Rasi, D1)")), "d9": ("D9", _("Navamsa chart (D9)"))}  # the two the kundli report draws
DRAWING = "/api/method/raftor_astrohq.chart_card.drawing"


def card(row_name: str, who: str, chart: str = "d1") -> dict:
	"""What the chat needs to show one chart: a title, the person's name and the address of the drawing (this site's own path)."""
	words = KINDS.get(chart, KINDS["d1"])[1]
	return {"kind": "chart", "title": f"{who}: {words}", "image": f"{DRAWING}?profile={row_name}&chart={chart}", "url": f"{DRAWING}?profile={row_name}&chart={chart}"}


def svg_for(user: str, row, chart: str = "d1") -> str | None:
	"""The drawing for one saved profile, or None when its chart cannot be made yet (no time or place of birth)."""
	numbers = report_view.profile_numbers(row)
	if not numbers:
		return None
	data = answers.get(user, numbers, "SUPER_BASIC")
	code, words = KINDS.get(chart, KINDS["d1"])
	divisional = data["divisional_charts"][code]["chart"]
	lagna = rp.sign_index(data["lagna"]["sign"]) if code == "D1" else data["divisional_charts"]["D9"]["ascendant_house"]  # the sign of house 1, as the kundli report draws it
	return rp.diamond_chart_svg(divisional, lagna, f"{row.full_name}: {words}", look=rp.site_look())


@frappe.whitelist()
def drawing(profile: str, chart: str = "d1") -> None:
	"""The chart as a picture, for the signed-in person's own saved profile only (anyone else's, or a name that is not a profile of theirs, is not found)."""
	user = frappe.session.user
	if user == "Guest":
		raise frappe.PermissionError
	row = next((r for r in person._rows(user) if r.name == profile), None)
	if row is None:
		raise frappe.DoesNotExistError
	svg = svg_for(user, row, chart if chart in KINDS else "d1")
	if not svg:
		raise frappe.DoesNotExistError
	frappe.response["type"] = "download"
	frappe.response["filename"] = "chart.svg"
	frappe.response["filecontent"] = svg.encode("utf-8")
	frappe.response["content_type"] = "image/svg+xml"
	frappe.response["display_content_as"] = "inline"
