"""Places: from the town written to latitude, longitude and the time zone on the day, ambiguity asked and never guessed, and the list built from
GeoNames' files. The unit tests use a small list made here; the last class checks well-known places against the real list when it has been built.

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_places
"""
import datetime
import os
import tempfile
from unittest import mock

import frappe

from raftor_astrohq import places
from raftor_astrohq.tests.helpers import AstroTestCase


def city(geo_id, name, lat, lon, cc, admin1, admin2, population, tz, alternates=""):
	cells = [str(geo_id), name, name, alternates, str(lat), str(lon), "P", "PPL", cc, "", admin1, admin2, "", "", str(population), "", "", tz, "2020-01-01"]
	return "\t".join(cells)


CITIES = "\n".join([
	city(1, "Pune", 18.51957, 73.85535, "IN", "16", "521", 3124458, "Asia/Kolkata", "Poona,Puna,Pūne"),
	city(2, "Pune", 18.5400, 73.8000, "IN", "16", "521", 5000, "Asia/Kolkata"),  # the same town listed again, 5 km away: one place
	city(3, "Pune", 27.7, 85.3, "NP", "P3", "", 800, "Asia/Kathmandu"),  # a small place of that name elsewhere
	city(4, "Aurangabad", 19.8762, 75.3433, "IN", "16", "520", 1100000, "Asia/Kolkata"),
	city(5, "Aurangabad", 24.7520, 84.3742, "IN", "34", "901", 100000, "Asia/Kolkata"),
	city(6, "Sirsa", 29.5349, 75.0290, "IN", "10", "700", 160000, "Asia/Kolkata"),
	city(7, "Sirsa", 25.2634, 82.0919, "IN", "36", "810", 5000, "Asia/Kolkata"),
	city(8, "Hyderabad", 17.3850, 78.4867, "IN", "40", "600", 6800000, "Asia/Kolkata"),
	city(9, "Hyderabad", 25.3960, 68.3578, "PK", "05", "", 1700000, "Asia/Karachi"),
	city(10, "London", 51.50853, -0.12574, "GB", "ENG", "GLA", 8961989, "Europe/London"),
	city(11, "London", 42.9834, -81.2330, "CA", "08", "", 383822, "America/Toronto"),
	city(12, "New York City", 40.71427, -74.00597, "US", "NY", "061", 8175133, "America/New_York", "New York,NYC"),
	city(13, "Houston", 29.76328, -95.36327, "US", "TX", "201", 2296224, "America/Chicago"),
	city(14, "Sydney", -33.86785, 151.20732, "AU", "02", "", 4627345, "Australia/Sydney"),
	city(15, "Sydney", 46.1351, -60.1831, "CA", "07", "", 31597, "America/Glace_Bay"),
	city(16, "Rampur", 28.8100, 79.0300, "IN", "36", "820", 3000, "Asia/Kolkata"),
	city(17, "Rampur", 26.2000, 82.0000, "IN", "36", "821", 2500, "Asia/Kolkata"),
	city(18, "Rampur", 27.5000, 80.1000, "IN", "36", "822", 2000, "Asia/Kolkata"),
	city(19, "Delhi", 28.66667, 77.21667, "IN", "07", "DL1", 10927986, "Asia/Kolkata", "Dilli"),
	city(20, "Delhi", 42.2781, -74.9160, "US", "NY", "025", 2500, "America/New_York"),
	city(21, "Kathmandu", 27.70169, 85.3206, "NP", "P3", "", 1442271, "Asia/Kathmandu"),
	city(22, "Mumbai", 19.07283, 72.88261, "IN", "16", "519", 12691836, "Asia/Kolkata", "Bombay"),
])
ADMIN1 = "\n".join(["IN.16\tMaharashtra\tMaharashtra\t1", "IN.34\tBihar\tBihar\t2", "IN.10\tHaryana\tHaryana\t3", "IN.36\tUttar Pradesh\tUttar Pradesh\t4", "IN.40\tTelangana\tTelangana\t5",
					"IN.07\tDelhi\tDelhi\t6", "GB.ENG\tEngland\tEngland\t7", "CA.08\tOntario\tOntario\t8", "CA.07\tNova Scotia\tNova Scotia\t9", "US.NY\tNew York\tNew York\t10",
					"US.TX\tTexas\tTexas\t11", "AU.02\tNew South Wales\tNew South Wales\t12", "PK.05\tSindh\tSindh\t13", "NP.P3\tBagmati\tBagmati\t14"])
ADMIN2 = "\n".join(["IN.16.521\tPune\tPune\t1", "IN.16.520\tAurangabad\tAurangabad\t2", "IN.36.820\tMoradabad\tMoradabad\t3", "IN.36.821\tJaunpur\tJaunpur\t4", "IN.36.822\tHardoi\tHardoi\t5"])
COUNTRIES = "\n".join(["#ISO\tISO3\tNum\tfips\tCountry", "IN\tIND\t356\tIN\tIndia", "GB\tGBR\t826\tUK\tUnited Kingdom", "CA\tCAN\t124\tCA\tCanada", "US\tUSA\t840\tUS\tUnited States",
					   "AU\tAUS\t036\tAS\tAustralia", "PK\tPAK\t586\tPK\tPakistan", "NP\tNPL\t524\tNP\tNepal"])
BORN = datetime.datetime(1980, 6, 8, 13, 49)


class PlacesCase(AstroTestCase):
	"""A small list in a temporary file stands in for the real one."""

	def setUp(self):
		super().setUp()
		self.folder = tempfile.mkdtemp()
		self.file = os.path.join(self.folder, "places.sqlite")
		places.build_from_text(CITIES, ADMIN1, ADMIN2, COUNTRIES, self.file)
		patcher = mock.patch.object(places, "path", return_value=self.file)
		patcher.start()
		self.addCleanup(patcher.stop)


class TestBuilding(PlacesCase):
	def test_the_list_is_built_with_its_counts_and_its_attribution(self):
		meta = places._meta()
		self.assertEqual((meta["places"], meta["attribution"]), (str(len(CITIES.splitlines())), places.ATTRIBUTION))
		self.assertIn("GeoNames", meta["attribution"])

	def test_building_again_replaces_it_whole(self):
		counts = places.build_from_text(CITIES.splitlines()[0], ADMIN1, ADMIN2, COUNTRIES, self.file)
		self.assertEqual(counts["places"], 1)
		self.assertEqual(places._meta()["places"], "1")
		self.assertFalse(os.path.exists(self.file + ".part"))

	def test_a_failed_build_leaves_the_old_list_and_no_scrap(self):
		before = os.path.getsize(self.file)
		bad = city(99, "Broken", "not-a-number", 0, "IN", "16", "", 1, "Asia/Kolkata")
		with self.assertRaises(ValueError):
			places.build_from_text(bad, ADMIN1, ADMIN2, COUNTRIES, self.file)
		self.assertEqual(os.path.getsize(self.file), before)
		self.assertFalse(os.path.exists(self.file + ".part"))

	def test_building_does_nothing_when_it_is_built_unless_forced(self):
		with mock.patch.object(places, "_download", side_effect=AssertionError("must not download")):
			self.assertTrue(places.build()["already"])

	def test_a_site_without_the_list_says_how_to_build_it(self):
		with mock.patch.object(places, "path", return_value=os.path.join(self.folder, "nope.sqlite")):
			self.assertFalse(places.ready())
			with self.assertRaises(places.PlacesNotReady) as caught:
				places.lookup("Pune", BORN)
		self.assertIn("raftor_astrohq.places.build", str(caught.exception))


class TestFindingAPlace(PlacesCase):
	def test_a_town_with_its_coordinates_and_the_time_zone_of_the_day(self):
		found = places.lookup("Pune", BORN)
		self.assertEqual((found["name"], found["timezone"], found["timezone_offset"]), ("Pune, Maharashtra, India", "Asia/Kolkata", 5.5))
		self.assertAlmostEqual(found["latitude"], 18.51957, places=4)
		self.assertAlmostEqual(found["longitude"], 73.85535, places=4)

	def test_the_time_zone_is_the_one_in_force_that_day(self):
		self.assertEqual(places.lookup("Pune", datetime.datetime(1943, 6, 1, 12, 0))["timezone_offset"], 6.5)  # India's wartime clock
		self.assertEqual(places.lookup("London, England", datetime.datetime(1972, 8, 15, 6, 0))["timezone_offset"], 1.0)  # summer time
		self.assertEqual(places.lookup("London, England", datetime.datetime(1972, 12, 15, 6, 0))["timezone_offset"], 0.0)
		self.assertEqual(places.lookup("New York", datetime.datetime(1988, 7, 4, 14, 20))["timezone_offset"], -4.0)
		self.assertEqual(places.lookup("Sydney, Australia", datetime.datetime(2015, 12, 25, 12, 0))["timezone_offset"], 11.0)
		self.assertEqual(places.lookup("Kathmandu", BORN)["timezone_offset"], 5.5)  # Nepal's clock was +5:30 until 1986
		self.assertEqual(places.lookup("Kathmandu", datetime.datetime(1995, 1, 1, 12, 0))["timezone_offset"], 5.75)

	def test_the_date_may_be_a_date_a_datetime_or_text(self):
		for on in (datetime.date(1980, 6, 8), BORN, "1980-06-08 13:49:00", "1980-06-08"):
			with self.subTest(str(on)):
				self.assertEqual(places.lookup("Pune", on)["timezone_offset"], 5.5)

	def test_other_names_accents_case_and_spaces_do_not_matter(self):
		for text in ("Poona", "puna", "  PUNE  ", "Pūne", "pune,   maharashtra", "Pune (Maharashtra)", "Pune - Maharashtra", "Pune, Maharashtra, India", "Pune, MH", "Pune, Pune, Maharashtra"):
			with self.subTest(text):
				self.assertEqual(places.lookup(text, BORN)["name"], "Pune, Maharashtra, India")

	def test_without_commas_the_town_and_the_state_are_told_apart(self):
		self.assertEqual(places.lookup("Pune Maharashtra", BORN)["name"], "Pune, Maharashtra, India")
		self.assertEqual(places.lookup("New York New York", BORN)["name"], "New York City, New York, United States")
		self.assertEqual(places.lookup("Sirsa Haryana", BORN)["name"], "Sirsa, Haryana, India")

	def test_one_town_listed_twice_close_together_is_one_place(self):
		self.assertEqual(places.lookup("Pune", BORN)["population"], 3124458)

	def test_a_small_place_of_the_same_name_does_not_make_a_big_town_ask(self):
		self.assertEqual(places.lookup("Pune", BORN)["name"], "Pune, Maharashtra, India")  # a Pune in Nepal of 800 people
		self.assertEqual(places.lookup("Delhi", BORN)["name"], "Delhi, Delhi, India")  # a Delhi in New York State has 2,500 people
		self.assertEqual(places.lookup("London", BORN)["name"], "London, England, United Kingdom")  # one of 8.9 million, against one of 380,000
		self.assertEqual(places.lookup("Sydney", BORN)["name"], "Sydney, New South Wales, Australia")  # and a Sydney in Nova Scotia of 32,000

	def test_the_other_place_of_the_same_name_is_reached_by_its_qualifier(self):
		self.assertEqual(places.lookup("London, Canada", BORN)["name"], "London, Ontario, Canada")
		self.assertEqual(places.lookup("London, Ontario", BORN)["name"], "London, Ontario, Canada")
		self.assertEqual(places.lookup("Sydney, Canada", BORN)["name"], "Sydney, Nova Scotia, Canada")
		self.assertEqual(places.lookup("Delhi, NY", BORN)["name"], "Delhi, New York, United States")

	def test_states_and_countries_in_their_usual_short_forms(self):
		for text in ("Houston, TX", "Houston, Texas", "Houston, USA", "Houston, US", "Houston, United States of America", "Houston, Texas, USA"):
			with self.subTest(text):
				self.assertEqual(places.lookup(text, BORN)["name"], "Houston, Texas, United States")
		self.assertEqual(places.lookup("London, UK", BORN)["name"], "London, England, United Kingdom")
		self.assertEqual(places.lookup("Mumbai, MH", BORN)["name"], "Mumbai, Maharashtra, India")
		self.assertEqual(places.lookup("Bombay", BORN)["name"], "Mumbai, Maharashtra, India")

	def test_a_name_two_places_share_is_asked_about_never_guessed(self):
		for text, options in (("Aurangabad", ("Maharashtra", "Bihar")), ("Sirsa", ("Haryana", "Uttar Pradesh")), ("Hyderabad", ("Telangana", "Sindh"))):
			with self.subTest(text):
				with self.assertRaises(places.PlaceAmbiguous) as caught:
					places.lookup(text, BORN)
				message = str(caught.exception)
				self.assertTrue(all(o in message for o in options), message)
				self.assertIn("state", message)

	def test_a_state_settles_it_and_a_district_settles_the_same_name_in_one_state(self):
		self.assertEqual(places.lookup("Sirsa, Haryana", BORN)["latitude"], 29.5349)
		self.assertEqual(places.lookup("Sirsa, Uttar Pradesh", BORN)["latitude"], 25.2634)
		with self.assertRaises(places.PlaceAmbiguous) as caught:
			places.lookup("Rampur, Uttar Pradesh", BORN)
		self.assertTrue(all(d in str(caught.exception) for d in ("Moradabad", "Jaunpur", "Hardoi")))
		self.assertEqual(places.lookup("Rampur, Jaunpur, Uttar Pradesh", BORN)["latitude"], 26.2)
		self.assertEqual(places.lookup("Rampur, Hardoi", BORN)["latitude"], 27.5)

	def test_a_qualifier_that_does_not_fit_is_an_error_not_a_guess(self):
		with self.assertRaises(places.PlaceNotFound) as caught:
			places.lookup("Pune, Bihar", BORN)
		self.assertIn("not found in Bihar", str(caught.exception))
		with self.assertRaises(places.PlaceNotFound):
			places.lookup("Pune, Maharashtra, Pakistan", BORN)
		with self.assertRaises(places.PlaceNotFound):
			places.lookup("Pune, Nowhereland", BORN)

	def test_a_place_that_is_not_in_the_list_says_what_to_try(self):
		with self.assertRaises(places.PlaceNotFound) as caught:
			places.lookup("Nowhereville", BORN)
		self.assertIn("Nowhereville", str(caught.exception))
		self.assertIn("nearest bigger town", str(caught.exception))

	def test_nothing_or_another_alphabet_is_told_in_words(self):
		with self.assertRaises(places.PlaceNotFound) as caught:
			places.lookup("   ", BORN)
		self.assertIn("write the place", str(caught.exception))
		with self.assertRaises(places.PlaceNotFound) as caught:
			places.lookup("पुणे", BORN)  # Pune in Devanagari
		self.assertIn("English letters", str(caught.exception))

	def test_the_options_are_not_a_wall_of_text(self):
		many = "\n".join(city(100 + i, "Rampur", 20 + i, 70 + i, "IN", "36", str(900 + i), 1000 + i, "Asia/Kolkata") for i in range(20))
		places.build_from_text(many, ADMIN1, "", COUNTRIES, self.file)
		with self.assertRaises(places.PlaceAmbiguous) as caught:
			places.lookup("Rampur", BORN)
		self.assertLessEqual(str(caught.exception).count(";"), places.MAX_OPTIONS - 1)


class TestTheCheckForTheForm(PlacesCase):
	def test_a_good_place_has_no_problem(self):
		self.assertEqual(places.problem("Pune, Maharashtra", BORN), "")

	def test_a_bad_place_has_a_sentence(self):
		self.assertIn("Nowhereville", places.problem("Nowhereville", BORN))
		self.assertIn("More than one place", places.problem("Sirsa", BORN))

	def test_a_site_without_the_list_never_refuses_a_sale_for_a_place(self):
		with mock.patch.object(places, "path", return_value=os.path.join(self.folder, "nope.sqlite")):
			self.assertEqual(places.problem("Anything at all", BORN), "")


class TestTheRealList(AstroTestCase):
	"""Well-known places against the real list, when it has been built on this site."""

	def setUp(self):
		super().setUp()
		if not places.ready():
			self.skipTest("the list of places has not been built here (bench --site astrohq.local execute raftor_astrohq.places.build)")

	def test_well_known_places_are_where_they_are(self):
		for text, lat, lon, tz in (
			("Pune, Maharashtra", 18.52, 73.86, "Asia/Kolkata"), ("Delhi", 28.65, 77.2, "Asia/Kolkata"), ("Mumbai", 19.07, 72.88, "Asia/Kolkata"), ("Kolkata", 22.57, 88.36, "Asia/Kolkata"),
			("Chennai", 13.08, 80.27, "Asia/Kolkata"), ("Bangalore", 12.97, 77.59, "Asia/Kolkata"), ("Sirsa, Haryana", 29.53, 75.03, "Asia/Kolkata"), ("Barnala, Punjab", 30.37, 75.55, "Asia/Kolkata"),
			("Bhilai, Chhattisgarh", 21.21, 81.43, "Asia/Kolkata"), ("Haridwar, Uttarakhand", 29.95, 78.16, "Asia/Kolkata"), ("Dwarka, Gujarat", 22.24, 68.97, "Asia/Kolkata"),
			("London, United Kingdom", 51.51, -0.13, "Europe/London"), ("New York, NY", 40.71, -74.0, "America/New_York"), ("Sydney, Australia", -33.87, 151.21, "Australia/Sydney"),
			("Kathmandu, Nepal", 27.7, 85.32, "Asia/Kathmandu"), ("Dubai, United Arab Emirates", 25.07, 55.3, "Asia/Dubai"), ("Toronto, Canada", 43.7, -79.4, "America/Toronto"),
			("Singapore", 1.29, 103.85, "Asia/Singapore"), ("Colombo, Sri Lanka", 6.93, 79.85, "Asia/Colombo"), ("Houston, TX", 29.76, -95.37, "America/Chicago"),
		):
			with self.subTest(text):
				found = places.lookup(text, BORN)
				self.assertAlmostEqual(found["latitude"], lat, delta=0.2, msg=found["name"])
				self.assertAlmostEqual(found["longitude"], lon, delta=0.2, msg=found["name"])
				self.assertEqual(found["timezone"], tz, found["name"])

	def test_names_shared_by_many_places_are_asked_about(self):
		for text in ("Aurangabad", "Hyderabad", "Sirsa", "Rampur", "Hamirpur"):
			with self.subTest(text):
				with self.assertRaises(places.PlaceAmbiguous):
					places.lookup(text, BORN)

	def test_the_big_names_need_no_state(self):
		for text, name in (("Delhi", "Delhi"), ("Mumbai", "Maharashtra"), ("Pune", "Maharashtra"), ("London", "England"), ("Paris", "France")):
			with self.subTest(text):
				self.assertIn(name, places.lookup(text, BORN)["name"])
