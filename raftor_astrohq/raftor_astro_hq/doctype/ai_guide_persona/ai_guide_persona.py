import frappe
from frappe import _
from frappe.model.document import Document

MOST_SKILLS = 3


class AIGuidePersona(Document):
	def before_validate(self):
		"""A guide with skills belongs to the area of its skills."""
		skills = self.skill_rows()
		if skills and not self.area:
			self.area = skills[0].area or ""

	def skill_rows(self) -> list:
		return [frappe.get_cached_doc("AI Guide Skill", row.skill) for row in self.skills or []]

	def validate(self):
		from raftor_astrohq import agents

		skills = self.skill_rows()
		if self.area and self.area not in agents.AGENTS:
			frappe.throw(_("The area must be one of the site's guides: {0}.").format(", ".join(agents.AGENTS)))
		if self.enabled and not self.area:
			frappe.throw(_("A guide needs an area, or skills of one, before it can be switched on."))
		if len(skills) > MOST_SKILLS:
			frappe.throw(_("A guide has at most {0} skills: a guide that does everything does nothing well.").format(MOST_SKILLS))
		if len({s.name for s in skills}) != len(skills):
			frappe.throw(_("A skill is listed twice."))
		for skill in skills:
			if skill.area != self.area:
				frappe.throw(_("The skill {0} belongs to another guide's area ({1}); this guide is of {2}.").format(skill.title, skill.area or _("none yet"), self.area))
		if self.enabled and any(not s.enabled for s in skills):
			frappe.throw(_("Switch on the skill {0} first, or switch this guide off.").format(next(s.title for s in skills if not s.enabled)))
		if self.profile_id and frappe.db.exists("AI Guide Persona", {"profile_id": self.profile_id, "name": ("!=", self.name)}):
			frappe.throw(_("Another guide is already made from the profile {0}.").format(self.profile_id))
		if not (self.voice or self.mindset or self.communication_style):
			frappe.throw(_("Say how the guide speaks: fill in the voice, or the mindset and how it communicates."))
		if len(self.voice or "") > 1500:
			frappe.throw(_("Keep the voice short (1,500 characters): a few lines on how the guide speaks and what it leans toward."))

	def on_update(self):
		from raftor_astrohq import ai_guides

		ai_guides.sync_persona(self)
