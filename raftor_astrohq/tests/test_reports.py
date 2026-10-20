"""The birth summary report astrohq makes from a customer's details (reports.py)."""
from frappe.tests.utils import FrappeTestCase

from raftor_astrohq import reports
from raftor_astrohq.details import birth_details


class TestBirthSummary(FrappeTestCase):
	DETAILS = {"report_name": "Asha <b>Rao</b>", "birth_date": "1990-05-17", "birth_time": "06:30", "birth_place": "Pune"}

	def test_it_makes_a_pdf_named_for_the_item_from_the_details(self):
		made = reports.birth_summary("Any Item", self.DETAILS, "x@example.com")
		self.assertTrue(made["content"].startswith(b"%PDF"))
		self.assertTrue(made["file_name"].endswith(".pdf"))

	def test_it_has_nothing_without_a_name_and_a_birth_date(self):
		self.assertIsNone(reports.birth_summary("Any Item", {"report_name": "A"}, "x@example.com"))
		self.assertIsNone(reports.birth_summary("Any Item", {"birth_date": "1990-05-17"}, "x@example.com"))

	def test_what_it_asks_is_what_it_uses(self):
		self.assertEqual([f["name"] for f in birth_details()], ["report_name", "birth_date", "birth_time", "birth_place"])
