from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from raftor_astrohq import hub


class TestHubMode(FrappeTestCase):
	def test_with_no_limit_set_every_call_is_quick(self):
		with patch("frappe.conf", {}):
			self.assertEqual(hub._mode_for("s" * 5000, "p" * 5000), "quick")

	def test_a_long_context_is_deep_when_the_site_sets_a_limit(self):
		with patch("frappe.conf", {"reading_deep_context_chars": 1000}):
			self.assertEqual(hub._mode_for("s" * 400, "p" * 500), "quick")
			self.assertEqual(hub._mode_for("s" * 400, "p" * 600), "deep")
