"""The birth chart drawn for the chat: a picture only for the signed-in person's own saved profile, never a public file."""
import frappe

from raftor_astrohq import chart_card
from raftor_astrohq.tests.helpers import GOOD, TABLE, AstroTestCase, make_user


def _person_with_profile():
	user = make_user()
	user.append(TABLE, GOOD)
	user.save(ignore_permissions=True)
	return user.name, frappe.get_all("Astro Birth Profile", filters={"parent": user.name, "parentfield": TABLE}, pluck="name")[0]


class TestChartCard(AstroTestCase):
	def test_the_card_names_a_picture_on_this_site_with_the_profile_and_chart(self):
		card = chart_card.card("abc123", "Ravi Rao", "d9")
		self.assertEqual(card["kind"], "chart")
		self.assertTrue(card["image"].startswith("/api/method/raftor_astrohq.chart_card.drawing?"))
		self.assertIn("profile=abc123", card["image"])
		self.assertIn("chart=d9", card["image"])
		self.assertIn("Navamsa", card["title"])

	def test_nobody_but_the_owner_gets_the_drawing(self):
		owner, profile = _person_with_profile()
		stranger, _other = _person_with_profile()
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, chart_card.drawing, profile)
		frappe.set_user(stranger)
		self.assertRaises(frappe.DoesNotExistError, chart_card.drawing, profile)
		frappe.set_user("Administrator")
