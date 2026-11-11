import frappe
from frappe import _
from frappe.model.document import Document


class PoojaKind(Document):
	def validate(self):
		keys = [row.step_key for row in self.steps]
		if len(keys) != len(set(keys)):
			frappe.throw(_("Each step of a pooja needs its own key."))
