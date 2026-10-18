"""How AstroHQ names the two forms of a dated service (the pattern is words; the rules are servicehq's, dated.py)."""
from unittest import TestCase

from raftor_servicehq import dated


class TestDatedNames(TestCase):
	def test_the_shared_and_personalised_forms_read_as_pooja_blessings(self):
		self.assertEqual(dated.service_name("Mahalakshmi–Ganesh", "Event", "astrohq"), "Mahalakshmi–Ganesh Samuhik Pooja Blessings")
		self.assertEqual(dated.service_name("Mahalakshmi–Ganesh", "Timed service", "astrohq"), "Mahalakshmi–Ganesh Personalised Pooja Blessings")
