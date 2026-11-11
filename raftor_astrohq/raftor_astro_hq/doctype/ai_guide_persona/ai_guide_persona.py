import frappe
from frappe import _
from frappe.model.document import Document


class AIGuidePersona(Document):
	def validate(self):
		from raftor_astrohq import agents

		if self.area not in agents.AGENTS:
			frappe.throw(_("The area must be one of the site's guides: {0}.").format(", ".join(agents.AGENTS)))
		if len(self.voice or "") > 1500:
			frappe.throw(_("Keep the voice short (1,500 characters): a few lines on how the guide speaks and what it leans toward."))

	def on_update(self):
		from raftor_astrohq import ai_guides

		ai_guides.sync_persona(self)
