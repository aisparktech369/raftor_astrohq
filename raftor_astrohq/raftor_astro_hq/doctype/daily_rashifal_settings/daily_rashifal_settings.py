import frappe
from frappe.model.document import Document


class DailyRashifalSettings(Document):
	@frappe.whitelist()
	def write_today(self):
		from raftor_astrohq import rashifal

		return rashifal.write_day(manual=True)

	@frappe.whitelist()
	def publish_drafts(self):
		from raftor_astrohq import rashifal

		return rashifal.publish_day()
