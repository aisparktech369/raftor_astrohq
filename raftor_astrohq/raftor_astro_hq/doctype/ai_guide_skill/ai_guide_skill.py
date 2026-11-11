import frappe
from frappe import _
from frappe.model.document import Document


class AIGuideSkill(Document):
	def validate(self):
		from raftor_astrohq import agents

		if self.area and self.area not in agents.AGENTS:
			frappe.throw(_("The area must be one of the site's guides: {0}, or left blank while no guide can do this yet.").format(", ".join(agents.AGENTS)))
		if self.enabled and not self.area:
			frappe.throw(_("A skill no guide can do yet cannot be switched on: choose the area whose guide does it."))

	def on_update(self):
		"""The guides that use this skill follow it on and off."""
		from raftor_astrohq import ai_guides

		for name in frappe.get_all("AI Guide Persona Skill", filters={"skill": self.name, "parenttype": "AI Guide Persona"}, pluck="parent"):
			ai_guides.sync_persona(frappe.get_doc("AI Guide Persona", name))


def agents_shelves(skill) -> list:
	return [x.strip() for x in (skill.shelves or "").split(",") if x.strip()]
