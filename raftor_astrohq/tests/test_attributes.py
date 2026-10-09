"""AstroHQ's attribute sets: what it declares passes websitehq's checks, and every icon it names is a real file it ships."""
import os
from unittest import TestCase

import frappe

from raftor_astrohq import attributes
from raftor_websitehq.website_hq import attribute_sets as sets


class TestAttributeSets(TestCase):
	def test_the_hook_is_registered_and_what_it_declares_passes_the_checks(self):
		self.assertIn("raftor_astrohq.attributes.attribute_sets", frappe.get_hooks("rfhq_attribute_sets", app_name="raftor_astrohq"))
		declared = [{**e, "app": "raftor_astrohq"} for e in attributes.attribute_sets()]
		self.assertEqual(sets.check(declared), [])

	def test_type_is_shown_as_icons_with_a_value_for_a_stone_on_its_own_a_ring_and_a_pendant(self):
		type_set = next(e for e in attributes.attribute_sets() if e["attribute"] == "Type")
		self.assertEqual(type_set["display_as"], "Icons")
		self.assertTrue({"Gemstone only", "Ring", "Pendant"} <= {v["value"] for v in type_set["values"]})

	def test_every_icon_is_a_file_this_app_ships(self):
		public = os.path.join(os.path.dirname(attributes.__file__), "public")
		for entry in attributes.attribute_sets():
			for value in (v for v in entry["values"] if v.get("icon")):
				path = os.path.join(public, value["icon"].replace("/assets/raftor_astrohq/", "", 1))
				self.assertTrue(os.path.isfile(path), value["icon"])

	def test_the_site_has_the_attribute_after_a_migrate(self):
		doc = frappe.get_doc("Item Attribute", "Type")
		self.assertEqual(doc.rfhq_display_as, "Icons")
		self.assertTrue(all(r.rfhq_icon for r in doc.item_attribute_values))

	def test_size_gets_the_ratti_sizes_as_a_plain_dropdown_and_keeps_the_standard_ones(self):
		size = next(e for e in attributes.attribute_sets() if e["attribute"] == "Size")
		self.assertEqual(size["display_as"], "Default")
		self.assertTrue({"6 Ratti", "7 Ratti", "8 Ratti"} <= {v["value"] for v in size["values"]})
		doc = frappe.get_doc("Item Attribute", "Size")
		have = {r.attribute_value for r in doc.item_attribute_values}
		self.assertTrue({"6 Ratti", "7 Ratti", "8 Ratti", "Small", "Large"} <= have)
