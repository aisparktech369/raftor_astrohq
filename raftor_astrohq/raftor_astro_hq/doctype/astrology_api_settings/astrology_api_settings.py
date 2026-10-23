"""Astrology API Settings: where the hub is and AstroHQ's key there. Only a System Manager sees them: the key is AstroHQ's way into the hub."""
import frappe
from frappe import _
from frappe.model.document import Document


class AstrologyAPISettings(Document):
	def validate(self):
		from raftor_astrohq import astrology

		self.hub_address = astrology.clean_address(self.hub_address)
		self.api_name = (self.api_name or "").strip()
		if not 5 <= int(self.timeout_seconds or 0) <= 60:
			frappe.throw(_("Wait for an answer between 5 and 60 seconds."))
		if self.enabled:
			missing = [label for field, label in (("hub_address", _("the hub's address")), ("api_key", _("the API key")), ("api_name", _("the API's name"))) if not self.get(field)]
			if missing:
				frappe.throw(_("To make charts available, fill in {0}.").format(", ".join(missing)))

	@frappe.whitelist()
	def check_connection(self) -> dict:
		"""Asks the hub whether the saved key is accepted and the engine answers (one sample chart), and keeps what it said."""
		self.check_permission("write")  # (the key is AstroHQ's way into the hub: only those who may change it)
		from raftor_astrohq import astrology

		result = astrology.check_connection()
		astrology.note_connection(result)
		return result
