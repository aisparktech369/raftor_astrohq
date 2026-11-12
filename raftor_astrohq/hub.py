"""The hub's text-to-text, asked for a short piece of plain text from facts the app gives it (the tarot reading and the numerology reading). The address, key and model come from Daily Rashifal Settings, the one
place the hub is set up. What comes back is cleaned (no markup, a safe length) and anything that goes wrong is one answer, Unavailable: the page then says the words could not be written just now."""
import json

import frappe
import requests
from frappe.utils import strip_html_tags

from raftor_astrohq import rashifal


class Unavailable(frappe.ValidationError):
	pass


def write(system: str, facts: dict, max_tokens: int = 500, limit: int = 1600) -> tuple[str, str]:
	"""(the text, the model's name) for `facts` (plain data, sent as JSON) under the instructions in `system`."""
	s = rashifal.settings()
	if not (s.address and s.key):
		raise Unavailable
	headers = {"X-Api-Key": s.key} | ({"X-Frappe-Site-Name": s.site} if s.site else {})
	body = {"api_name": s.api_name, "payload": {"system": system, "prompt": json.dumps(facts, ensure_ascii=False), "temperature": 0.7, "max_tokens": max_tokens}}
	try:
		response = requests.post(s.address + rashifal.GATEWAY, json=body, headers=headers, timeout=s.timeout)
		answer = response.json()
	except (requests.exceptions.RequestException, ValueError):
		raise Unavailable from None
	data = answer.get("data") if isinstance(answer, dict) else None
	text = strip_html_tags(str((data or {}).get("content") or "")).replace("*", "").replace("#", "").strip()[:limit]
	if response.status_code >= 400 or not text:
		raise Unavailable
	return text, str((data or {}).get("model") or "")
