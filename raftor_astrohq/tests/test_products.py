"""What astrohq knows about the things it sells that the store's pills are made of (products.py)."""
from unittest import TestCase

from raftor_astrohq import products


class TestPlanets(TestCase):
	def test_the_first_planet_named_is_the_one_kept_whatever_surrounds_it(self):
		cases = {"Jupiter / Venus": "Jupiter", "Saturn (Shani)": "Saturn", "<div class=\"ql-editor read-mode\"><p>Venus</p></div>": "Venus", "Sun / Venus": "Sun", "Rahu / All": "Rahu",
				 "Guru": "Jupiter", "": "", "All planets": "", "Moonstone is not the Moon": "Moon"}
		self.assertEqual({k: products.planet_of(k) for k in cases}, cases)

	def test_every_sign_has_a_lord_that_is_a_planet_of_the_store(self):
		self.assertEqual(len(products.SIGNS), 12)
		self.assertTrue({planet for _, planet in products.SIGNS} <= set(products.PLANETS))

	def test_the_gemstones_offer_one_pill_for_each_sign(self):
		(entry,) = products.product_pills()
		self.assertEqual((entry["group"], entry["field"], len(entry["options"])), ("Gemstones", products.FIELD, 12))
