import uuid
from unittest import TestCase

import frappe

TABLE = "astro_birth_profiles"
GOOD = {"relationship": "You", "full_name": "Asha Rao", "date_of_birth": "1990-08-14", "time_of_birth": "06:42",
		"time_unknown": 0, "place_of_birth": "Pune, India", "permission_given": 0}
FAMILY = {"relationship": "Spouse", "full_name": "Ravi Rao", "date_of_birth": "1988-03-02", "time_of_birth": "",
		  "time_unknown": 1, "place_of_birth": "Jaipur, India", "permission_given": 1}


def make_user(**values):
	email = f"astro-{uuid.uuid4().hex[:8]}@example.com"
	return frappe.get_doc({"doctype": "User", "email": email, "first_name": "Astro", "send_welcome_email": 0,
						   "user_type": "Website User", **values}).insert(ignore_permissions=True)


class AstroTestCase(TestCase):
	"""Runs as Administrator and leaves nothing behind."""

	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
