from frappe.model.document import Document


class AstroBirthProfile(Document):
	"""One person's birth details, a row of the Birth Profiles table on a User.

	The rules live in raftor_astrohq/profiles.py and run when the User is saved, so the web pages and
	the Desk always agree."""
