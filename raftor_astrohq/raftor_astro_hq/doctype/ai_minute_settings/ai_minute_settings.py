"""AI Minute Settings: the price of one AI minute, in rupees (always at least 1: no AI guide is free)."""
import frappe
from frappe import _
from frappe.model.document import Document


class AIMinuteSettings(Document):
	def validate(self):
		if (self.minute_price or 0) < 1:
			frappe.throw(_("An AI minute costs at least 1 rupee: no AI guide is free."))
