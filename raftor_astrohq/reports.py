"""The reports astrohq makes from what a customer gave (servicehq digital.py calls the makers listed in the hook rfhq_report_makers).

A birth summary: who, when and where, and the weekday of the birth. It is the simple report; a fuller one (a chart, written advice) replaces or
sits beside it as another maker, with no change to how it is sold, paid, delivered or billed."""
import frappe
from frappe import _
from frappe.utils import escape_html, format_date, getdate
from frappe.utils.pdf import get_pdf


def birth_summary(item_code: str, details: dict, buyer: str) -> dict | None:
	"""A one-page PDF of the birth details the customer gave, for an item that is a report. None when the details are missing."""
	if not details.get("birth_date") or not details.get("report_name"):
		return None
	born = getdate(details["birth_date"])
	title = frappe.db.get_value("Item", item_code, "item_name") or _("Your report")
	rows = [(_("Name"), details["report_name"]), (_("Date of birth"), format_date(born)), (_("Weekday of birth"), born.strftime("%A")),
			(_("Time of birth"), details.get("birth_time") or "-"), (_("Place of birth"), details.get("birth_place") or "-")]
	body = "".join(f"<tr><th>{escape_html(label)}</th><td>{escape_html(str(value))}</td></tr>" for label, value in rows)
	html = (f"<html><head><meta charset='utf-8'><style>body{{font-family:sans-serif;margin:40px}}h1{{color:#3a1a4a}}th{{text-align:left;padding:6px 18px 6px 0;color:#555}}"
			f"td{{padding:6px 0}}</style></head><body><h1>{escape_html(title)}</h1><table>{body}</table>"
			f"<p style='margin-top:30px;color:#777'>{escape_html(_('Made for you from the details you gave.'))}</p></body></html>")
	return {"file_name": f"{frappe.scrub(title)}.pdf", "content": get_pdf(html)}
