"""AstroHQ's way of asking for a town (places.py): it keeps no list; the astrology service holds the one list and answers for it. What the list does (a name written out, two towns of one name, the order of a search,
the offset of the day of birth) is tested in the service (raftor_apimanager.tests.test_astrology_places); here it is that the right question is asked, once, and that what comes back is the same as it always was.

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_places
"""
import datetime
from unittest import mock

from raftor_astrohq import astrology, places
from raftor_astrohq.tests.places_fake import PlacesCase

BORN = datetime.datetime(1980, 6, 8, 13, 49)


class TestAskingForATown(PlacesCase):
	def test_a_town_written_out_is_asked_with_the_date_of_birth_and_kept_for_an_hour(self):
		found = places.lookup("Delhi", BORN)
		self.assertEqual(self.places_asked, [{"opcode": "PLACE_FIND", "place": {"text": "Delhi", "at": "1980-06-08T13:49"}}])
		self.assertEqual((found["id"], found["name"], found["timezone"], found["timezone_offset"]), (19, "Delhi, Delhi, India", "Asia/Kolkata", 5.5))
		places.lookup("  delhi", BORN)
		self.assertEqual(len(self.places_asked), 1)  # the same town and moment: not asked again
		places.lookup("Delhi", datetime.datetime(1943, 6, 8, 13, 49))
		self.assertEqual(len(self.places_asked), 2)  # another date of birth is another question (the offset is of that day)

	def test_the_date_may_be_a_date_a_datetime_or_text(self):
		for town, on, at in (("Pune", datetime.date(1980, 6, 8), "1980-06-08"), ("Delhi", datetime.datetime(1980, 6, 8, 13, 49, 59), "1980-06-08T13:49"), ("Mumbai", "1980-06-08 13:49:00", "1980-06-08T13:49")):
			self.places_asked.clear()
			places.lookup(town, on)
			self.assertEqual(self.places_asked[0]["place"]["at"], at, on)

	def test_a_town_by_its_id_is_kept_for_a_day_and_an_id_that_is_not_a_number_is_not_asked(self):
		self.assertEqual(places.by_id("22", datetime.date(2026, 11, 8))["name"], "Mumbai, Maharashtra, India")
		self.assertEqual(self.places_asked, [{"opcode": "PLACE_GET", "place": {"id": 22, "at": "2026-11-08"}}])
		places.by_id(22, datetime.date(2026, 11, 8))
		self.assertEqual(len(self.places_asked), 1)
		self.places_asked.clear()
		for bad in ("abc", None, "", "1.5"):
			with self.assertRaises(places.PlaceNotFound):
				places.by_id(bad, BORN)
		self.assertEqual(self.places_asked, [])
		with self.assertRaises(places.PlaceNotFound) as caught:
			places.by_id(9999, BORN)
		self.assertEqual(str(caught.exception), "That place is not in the list.")

	def test_what_the_service_refuses_is_a_town_not_found_and_two_towns_of_a_name_are_ambiguous_in_its_words(self):
		words = "More than one place is called Sirsa: Sirsa, Haryana; Sirsa, Uttar Pradesh. Please write the town and its state, for example Sirsa, Haryana."
		with mock.patch.object(astrology, "_ask", side_effect=astrology.AstrologyRefused(words)):
			with self.assertRaises(places.PlaceAmbiguous) as caught:
				places.lookup("Sirsa", BORN)
			self.assertEqual(str(caught.exception), words)
			self.assertIsInstance(caught.exception, places.PlaceNotFound)  # whoever asks for a town to be found catches both
		with self.assertRaises(places.PlaceNotFound) as caught:
			places.lookup("Nowhereville", BORN)
		self.assertNotIsInstance(caught.exception, places.PlaceAmbiguous)
		self.assertIn("Nowhereville", str(caught.exception))
		self.assertIn("Nowhereville", places.problem("Nowhereville", BORN))

	def test_a_service_that_cannot_be_asked_gives_no_towns_and_never_refuses_a_sale(self):
		with mock.patch.object(astrology, "_ask", side_effect=astrology.AstrologyUnavailable("down")):
			with self.assertRaises(places.PlacesNotReady):
				places.lookup("Delhi", BORN)
			with self.assertRaises(places.PlacesNotReady):
				places.by_id(19, BORN)
			self.assertEqual(places.suggest("Mum"), [])
			self.assertIsNone(places.near(19.1, 72.9, BORN))
			self.assertEqual(places.problem("Anything at all", BORN), "")
			self.assertFalse(places.ready())
		self.assertTrue(places.ready())

	def test_the_first_letters_are_asked_as_typed_and_kept_and_one_letter_is_not_asked(self):
		self.assertEqual(places.suggest("m"), [])
		self.assertEqual(self.places_asked, [])
		self.assertEqual(places.suggest("  Mum")[0], {"id": 22, "name": "Mumbai", "region": "Maharashtra, India"})
		self.assertEqual(self.places_asked, [{"opcode": "PLACE_SEARCH", "place": {"text": "mum", "limit": 6}}])
		places.suggest("MUM")
		self.assertEqual(len(self.places_asked), 1)
		places.suggest("mum", limit=3)
		self.assertEqual(self.places_asked[-1]["place"]["limit"], 3)

	def test_a_point_is_asked_as_numbers_and_only_when_it_is_on_the_earth(self):
		for bad in (("x", 1), (91, 0), (0, 181), (None, None)):
			self.assertIsNone(places.near(*bad, BORN))
		self.assertEqual(self.places_asked, [])
		found = places.near("19.1", "72.9", datetime.date(2026, 10, 24))
		self.assertEqual(found["id"], 22)
		self.assertEqual(self.places_asked, [{"opcode": "PLACE_NEAR", "place": {"latitude": 19.1, "longitude": 72.9, "at": "2026-10-24"}}])
		self.assertIsNone(places.near(0, -150, BORN))

	def test_the_offset_of_a_zone_on_a_day_and_the_credit_line(self):
		self.assertEqual(places.offset_hours("Europe/London", datetime.datetime(2026, 8, 15, 12)), 1.0)
		self.assertEqual(places.offset_hours("Asia/Kathmandu", datetime.datetime(2026, 8, 15, 12)), 5.75)
		with self.assertRaises(places.PlaceNotFound):
			places.offset_hours("Nowhere/Land", datetime.datetime(2026, 8, 15, 12))
		self.assertEqual(places.ATTRIBUTION, "Place data: GeoNames (geonames.org), licensed CC BY 4.0.")
