"""A report as a page of panes (panes.py) on a board, for the web: what a customer sees of their chart, and what an astrologer sees of a customer's.

A *view* is a small JSON file in views/: a title, a board ("lite": three columns; "wide": four, for an expert on a big screen), the modes of the engine it is made from and its panes, each placed at
[column, row, columns wide, rows tall]. A pane the file calls reviewed has been checked by an astrologer; a customer's view has those only (reports.shown(): the same rule as a report's PDF), an astrologer's has all,
the others marked Draft. A pane with `"shut": true` folds to its title and one line on a phone (websitehq's Report View does the folding).

`customer_view` is what servicehq's page of a report calls (free_reports.report_view, after it has checked whose report it is): server-side code that checks nobody itself. The markup it makes is cleaned by websitehq before it reaches a page.

`chart_view` is the astrologer's page of a customer's chart (the wide board, every pane, the unchecked ones marked Draft): only for the astrologer of the customer's booking (and the team), only for a birth
profile the customer shares (their own, or a family member's they confirmed they may share), and what is kept for it is kept for the customer, never for the astrologer.
"""
import datetime
import functools
import json
from html import escape
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cint

from raftor_astrohq import answers, astrology, places, profiles, reports
from raftor_astrohq import panchang_panes
from raftor_astrohq import panes as pane_library

VIEWS = Path(__file__).parent / "views"
DRAFT = '<span class="rv-draft">Draft</span>'
BOARDS = ("lite", "wide")
LOOKS = ("roomy",)  # a board with more room: the panes of a row stand level and the writing is larger (the Panchang page)


@functools.cache
def _file(name: str) -> str:
	return (VIEWS / f"{name}.json").read_text(encoding="utf-8")


def view_named(name: str) -> dict:
	return json.loads(_file(name))


def place_of(pane: dict) -> str:
	"""The pane's place on the board as attributes: [column, row, columns wide, rows tall]."""
	col, row, wide, tall = (list(pane.get("at") or []) + [1, 1, 1, 1])[:4]
	return f' data-col="{int(col)}" data-row="{int(row)}"' + (f' data-w="{int(wide)}"' if int(wide) > 1 else "") + (f' data-h="{int(tall)}"' if int(tall) > 1 else "")


def sky_numbers(numbers: dict, place: dict, now: datetime.datetime | None = None) -> dict:
	"""The numbers for a "birth" at this hour, at the birth place, in the time of that place now (the minutes are dropped: one hour's sky is asked for once)."""
	offset = float(place["timezone_offset"])
	local = (now or datetime.datetime.now(datetime.timezone.utc)).astimezone(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(hours=offset)
	return {**{k: numbers[k] for k in ("latitude", "longitude", "timezone_offset")}, "year": local.year, "month": local.month, "day": local.day, "hour": local.hour, "minute": 0, "second": 0}


def data_from(user: str, numbers: dict, place_text: str, view: dict, today: datetime.date | None = None, show: str = "reviewed") -> tuple[dict, dict]:
	"""What a view is made from: the kept answers (kept for `user`, the person the birth belongs to) for each mode it names, and its context (the day, and today's sky when a pane that will be shown wants it)."""
	on = today or frappe.utils.getdate(frappe.utils.today())
	data = answers.bundle(user, numbers, view["modes"])
	ctx = {"today": on, "sky": None}
	if any(p["pane"] == "today" and (show == "all" or p.get("reviewed")) for p in view["panes"]):
		ctx["sky"] = answers.sky(sky_numbers(numbers, places.lookup(place_text, datetime.datetime.combine(on, datetime.time(12)))))
	return data, ctx


def data_for(user: str, details: dict, view: dict, today: datetime.date | None = None, show: str = "reviewed") -> tuple[dict, dict]:
	"""`data_from` for the details a customer gave (name, birth date and time, place) when they asked for a report."""
	person = reports._person(details)
	return data_from(user, reports._numbers(person, reports._find(person)), person["place_text"], view, today, show)


def render(view: dict, data: dict, ctx: dict, show: str = "reviewed") -> str:
	"""The board: each pane the view names that the answers have something for (and, for a customer, that has been checked)."""
	out = []
	for spec in view["panes"]:
		checked = bool(spec.get("reviewed"))
		if show == "reviewed" and not checked:
			continue
		try:
			made = (pane_library.PANES.get(spec["pane"]) or panchang_panes.PANES[spec["pane"]])(data, ctx, **(spec.get("options") or {}))
		except Exception:  # one pane that cannot be drawn is not a page that cannot be shown
			frappe.log_error(title=f"Report view: pane {spec.get('pane')}")
			continue
		if not made:
			continue
		title = f'<h3 class="rv-title">{escape(spec.get("title") or "")}{"" if checked else DRAFT}</h3>'
		out.append(f'<details class="rv-pane" open{place_of(spec)}{" data-shut" if spec.get("shut") else ""}><summary>{title}<span class="rv-sum">{escape(made.get("summary") or "")}</span></summary>'
				   f'<div class="rv-body">{made["body"]}</div></details>')
	board = view.get("board") if view.get("board") in BOARDS else "lite"
	look = f' rv-look-{view["look"]}' if view.get("look") in LOOKS else ""
	return f'<div class="rv-board rv-board-{board}{look}" role="group" aria-label="{escape(view.get("title") or "")}">{"".join(out)}</div>' if out else ""


def customer_view(item_code: str, details: dict, user: str) -> str:
	"""The page of a report for the person who asked for it."""
	view = view_named("customer")
	show = reports.shown()
	data, ctx = data_for(user, details, view, show=show)
	return render(view, data, ctx, show)


# ---- the astrologer's page: a customer's chart, for the astrologer of their booking ----
ALLOWED_STATES = ("Requested", "Confirmed", "Delivered")  # an astrologer prepares for a request, runs a confirmed session and may look again once it is done; not a declined, cancelled, missed or expired one
WORDS = {profiles.SELF: _("Themselves")}


def booking_of(booking: str | None) -> frappe._dict:
	"""The booking, if the signed-in person is its astrologer (or the team) and it is one a chart is opened for; the same answer whether it exists or not."""
	from raftor_servicehq.roles import is_staff

	row = frappe.db.get_value("Booking", booking, ["name", "provider_user", "customer_user", "workflow_state", "slot_start"], as_dict=True) if booking else None
	if not row or row.workflow_state not in ALLOWED_STATES or not row.customer_user or (row.provider_user != frappe.session.user and not is_staff()):
		frappe.throw(_("That was not found."), frappe.DoesNotExistError)
	return row


def shared_profiles(customer_user: str) -> list:
	"""The birth profiles of the customer an astrologer of their booking may open: their own (booking the reading is the use) and a family member's when the customer confirmed they may share it."""
	rows = frappe.get_doc("User", customer_user).get(profiles.TABLE) or []
	return sorted((row for row in rows if row.relationship == profiles.SELF or cint(row.permission_given)), key=lambda row: row.relationship != profiles.SELF)


def chosen_profile(rows: list, profile: str | None):
	return next((row for row in rows if row.name == profile), rows[0] if rows else None)


def profile_numbers(row) -> dict | None:
	"""The numbers the engine is asked with for a birth profile; none when its time of birth is not known (a chart needs the minute)."""
	try:
		born = datetime.datetime.combine(frappe.utils.getdate(row.date_of_birth), datetime.time.fromisoformat(str(row.time_of_birth or "")[:5]))
	except ValueError:
		return None
	place = places.lookup(row.place_of_birth or "", born)
	return astrology.birth_data(row, place["latitude"], place["longitude"], place["timezone_offset"])


def booking_actions(booking: str) -> list[dict]:
	"""What an astrologer can open from their booking (servicehq's provider page asks the vertical for these): the customer's chart, when the customer has a birth profile they share."""
	row = frappe.db.get_value("Booking", booking, ["provider_user", "customer_user", "workflow_state"], as_dict=True)
	if not row or row.workflow_state not in ALLOWED_STATES or row.provider_user != frappe.session.user or not row.customer_user or not shared_profiles(row.customer_user):
		return []
	from raftor_servicehq.links import page_url

	return [{"label": _("View chart"), "href": page_url("provider", "chart", booking=booking)}]


def who_strip(chosen, rows: list, booking: str) -> str:
	"""The top of the astrologer's page: whose chart it is, the way back to the bookings and a way to each other person the customer shares (links to pages of this site: websitehq's sanitiser keeps no other)."""
	from raftor_servicehq.links import page_url

	when = ", ".join(part for part in (frappe.utils.formatdate(chosen.date_of_birth, "d MMMM yyyy"), str(chosen.time_of_birth or "")[:5]) if part)
	born = " · ".join(part for part in (when, chosen.place_of_birth) if part)
	links = [(_("Back to your bookings"), page_url("provider", "bookings")),
			 *((_("See {0}'s chart").format(other.full_name), page_url("provider", "chart", booking=booking, profile=other.name)) for other in rows if other.name != chosen.name)]
	return ('<div class="rv-who">'
			f'<h1 class="rv-name">{escape(chosen.full_name or "")}</h1><span class="rv-badge">{escape(WORDS.get(chosen.relationship, chosen.relationship or ""))}</span><span class="rv-born">{escape(born)}</span>'
			f'<span class="rv-links">{"".join(link(label, href) for label, href in links)}</span></div>')


def link(label: str, href: str) -> str:
	return f'<a class="rv-link" href="{escape(href)}">{escape(label)}</a>'


@frappe.whitelist(methods=["POST"])
def chart_view(booking=None, profile=None) -> dict:
	"""The astrologer's page of a customer's chart: whose it is and the other people the customer shares, then the wide board (every pane: those nobody has checked are marked Draft). Only the booking's astrologer
	and the team; only a profile the customer shares. Listed in the hook rfhq_trusted_html_sources: websitehq cleans what it answers before it reaches the page."""
	row = booking_of(booking)
	rows = shared_profiles(row.customer_user)
	chosen = chosen_profile(rows, profile)
	if not chosen:
		return {"items": []}
	head = who_strip(chosen, rows, row.name)
	numbers = profile_numbers(chosen)
	if numbers is None:  # no minute of birth, no chart; the people the customer shares are still there
		return {"items": [{"body_html": head + f'<p class="rv-note">{escape(_("The time of birth is not known, so a chart cannot be drawn."))}</p>'}]}
	view = view_named("astrologer")
	board = render(view, *data_from(row.customer_user, numbers, chosen.place_of_birth or "", view, show="all"), "all")
	return {"items": [{"body_html": head + board}] if board else []}
