from frappe.model.document import Document


class AstroReminderSent(Document):
	"""One reminder already sent for one day and one time of day, so that a run that is repeated never sends it twice."""
