"""How a listing of astrohq's events (havans, poojas) can be narrowed: by what the visitor wishes for (hook "event_filters", see servicehq kinds.py).

Staff mark each event with the wishes it serves by adding a tag in Desk (the tags in the sidebar of the event). The words below are the wishes a tag may carry;
a wish nobody has tagged is not offered, so the buttons are only ever the ones that lead somewhere."""
import frappe
from frappe import _

from raftor_astrohq.details import wishes


def _tagged(row) -> set[str]:
	return {t.strip().lower() for t in (row._user_tags or "").split(",") if t.strip()}


def wish_filters(names: list[str], choices: dict) -> dict:
	"""{"facets": [what can be chosen], "names": [the events that match the choice]} for these Service Event names."""
	rows = frappe.get_all("Service Event", filters={"name": ["in", names or ["-"]]}, fields=["name", "_user_tags"])
	tags = {r.name: _tagged(r) for r in rows}
	options = [{"value": w, "label": w, "count": n} for w in wishes() if (n := sum(1 for t in tags.values() if w.lower() in t))]
	facets = [{"name": "wish", "label": _("What do you wish for?"), "heading": _("What do you wish for?"), "display": "chips", "options": options}] if options else []
	wanted = {w.strip().lower() for w in str(choices.get("wish") or "").split(",") if w.strip()}
	return {"facets": facets, "names": [n for n in names if not wanted or wanted & tags.get(n, set())]}


def wish_labels(names: list[str]) -> dict[str, str]:
	"""What each event is for, in words: "For Health" (up to two wishes, in the order staff keep them), from the same tags the buttons use."""
	rows = frappe.get_all("Service Event", filters={"name": ["in", names or ["-"]]}, fields=["name", "_user_tags"])
	out = {}
	for r in rows:
		tags = _tagged(r)
		mine = [w for w in wishes() if w.lower() in tags][:2]
		if mine:
			out[r.name] = _("For {0}").format(" · ".join(mine))
	return out
