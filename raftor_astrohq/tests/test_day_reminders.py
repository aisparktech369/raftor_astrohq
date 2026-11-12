"""The days a person of astrohq follows (day_reminders.py): which days a rule holds on, the special days, the words and what a person may choose. The reminding itself is servicehq's (its tests)."""
import datetime
import frappe

from raftor_astrohq import day_reminders as reminders
from raftor_astrohq.tests.helpers import AstroTestCase

DAY = datetime.date(2031, 3, 9)


def day(**kw):
	base = {"date": DAY, "weekday": "Tuesday", "tithi": "Ashtami", "paksha": "Krishna", "tithi_begins": datetime.datetime(2031, 3, 8, 22, 5), "tithi_ends": datetime.datetime(2031, 3, 9, 20, 40),
			"nakshatras": {"Ashwini"}, "nakshatra": "Ashwini"}
	return {**base, **kw}


class TestWhichDays(AstroTestCase):
	def test_a_tithi_in_either_fortnight_or_one(self):
		self.assertTrue(reminders.follows({"tithi": "Ashtami", "paksha": "Both"}, day()))
		self.assertTrue(reminders.follows({"tithi": "Ashtami", "paksha": "Krishna"}, day()))
		self.assertFalse(reminders.follows({"tithi": "Ashtami", "paksha": "Shukla"}, day()))
		self.assertFalse(reminders.follows({"tithi": "Ekadashi", "paksha": "Both"}, day()))

	def test_amavasya_and_purnima_need_no_fortnight(self):
		self.assertTrue(reminders.follows({"tithi": "Amavasya"}, day(tithi="Amavasya", paksha="Krishna")))
		self.assertTrue(reminders.follows({"tithi": "Purnima", "paksha": "Both"}, day(tithi="Purnima", paksha="Shukla")))

	def test_any_of_the_things_a_reminder_names_is_enough(self):
		self.assertTrue(reminders.follows({"tithi": "Ashtami", "weekday": "Friday"}, day()))  # an Ashtami that is not a Friday
		self.assertTrue(reminders.follows({"tithi": "Ekadashi", "weekday": "Tuesday"}, day()))  # a Tuesday that is not an Ekadashi
		self.assertFalse(reminders.follows({"tithi": "Ekadashi", "weekday": "Friday"}, day()))  # neither
		self.assertTrue(reminders.follows({"tithi": "Ekadashi", "special": "Ravi Pushya"}, day(weekday="Sunday", nakshatras={"Pushya"})))

	def test_a_fortnight_only_narrows_its_tithi(self):
		self.assertFalse(reminders.follows({"tithi": "Ashtami", "paksha": "Shukla"}, day()))  # a Krishna Ashtami
		self.assertTrue(reminders.follows({"tithi": "Ashtami", "paksha": "Shukla", "weekday": "Tuesday"}, day()))  # but the Tuesday still counts

	def test_the_message_says_which_one_the_day_is(self):
		reminder = {"tithi": "Ekadashi", "weekday": "Tuesday", "paksha": "Both"}
		self.assertIn("is a Tuesday", reminders.text_for(reminder, day(), "evening"))
		self.assertEqual(reminders.why({"tithi": "Ashtami", "paksha": "Krishna", "weekday": "Tuesday"}, day()), "Ashtami (Krishna) and a Tuesday")

	def test_a_reminder_that_names_nothing_never_holds(self):
		self.assertFalse(reminders.follows({"tithi": "", "weekday": "", "special": ""}, day()))

	def test_the_special_days(self):
		self.assertIn("Ravi Pushya", reminders.specials(day(weekday="Sunday", nakshatras={"Pushya"})))
		self.assertIn("Guru Pushya", reminders.specials(day(weekday="Thursday", nakshatras={"Pushya"})))
		self.assertNotIn("Ravi Pushya", reminders.specials(day(weekday="Monday", nakshatras={"Pushya"})))
		self.assertIn("Sarvartha Siddhi", reminders.specials(day(weekday="Tuesday", nakshatras={"Krittika"})))
		self.assertIn("Amrit Siddhi", reminders.specials(day(weekday="Wednesday", nakshatras={"Anuradha"})))
		self.assertEqual(reminders.specials(day(weekday="Friday", nakshatras={"Bharani"})), [])
		self.assertTrue(reminders.follows({"special": "Ravi Pushya"}, day(weekday="Sunday", nakshatras={"Pushya"})))

	def test_several_choices_in_one_reminder(self):
		reminder = {"tithi": "Ashtami,Amavasya", "paksha": "Both", "weekday": "Tuesday,Friday", "special": ""}
		self.assertTrue(reminders.follows(reminder, day(tithi="Amavasya", weekday="Monday")))
		self.assertTrue(reminders.follows(reminder, day(tithi="Dashami", weekday="Friday")))
		self.assertFalse(reminders.follows(reminder, day(tithi="Dashami", weekday="Monday")))
		self.assertEqual(reminders.title_of(reminder), "Ashtami, Amavasya, Every Tuesday, Every Friday")

	def test_the_words(self):
		self.assertEqual(reminders.title_of({"tithi": "Ashtami", "paksha": "Krishna"}), "Ashtami (Krishna)")
		self.assertEqual(reminders.title_of({"tithi": "Amavasya", "paksha": "Both"}), "Amavasya")
		self.assertEqual(reminders.title_of({"weekday": "Tuesday"}), "Every Tuesday")
		self.assertEqual(reminders.title_of({"tithi": "Ashtami", "paksha": "Both", "weekday": "Tuesday"}), "Ashtami, Every Tuesday")
		text = reminders.text_for({"tithi": "Ashtami", "paksha": "Krishna"}, day(), "evening")
		self.assertIn("Tomorrow", text)
		self.assertIn("begins", text)
		self.assertIn("ends", text)


class TestWhatAPersonChooses(AstroTestCase):
	def test_the_choice_becomes_the_rule_in_the_lists_order(self):
		rule, errors = reminders.clean({"tithi": "Amavasya,Ashtami", "paksha": "Krishna", "weekday": "Friday,Tuesday", "special": ""})
		self.assertEqual(errors, {})
		self.assertEqual(rule, {"tithi": ["Ashtami", "Amavasya"], "paksha": "Krishna", "weekday": ["Tuesday", "Friday"], "special": []})

	def test_what_is_wrong_comes_back_per_field(self):
		self.assertIn("tithi", reminders.clean({})[1])  # nothing named
		self.assertIn("tithi", reminders.clean({"tithi": "Ashtami,Nonsense"})[1])
		self.assertIn("weekday", reminders.clean({"weekday": "Funday"})[1])
		self.assertIn("special", reminders.clean({"special": "Made up"})[1])
		self.assertIn("paksha", reminders.clean({"weekday": "Monday", "paksha": "Both or neither"})[1])

	def test_purnima_and_amavasya_need_no_fortnight(self):
		self.assertEqual(reminders.clean({"tithi": "Amavasya", "paksha": "Krishna"})[0]["paksha"], "Both")

	def test_astrohq_tells_servicehq_what_its_days_are(self):
		self.assertEqual(frappe.get_hooks("servicehq_day_reminders"), {"astrohq": ["raftor_astrohq.day_reminders.definition"]})
		d = reminders.definition()
		self.assertEqual([f["name"] for f in d["fields"]], ["tithi", "paksha", "weekday", "special"])
		for name in ("clean", "facts", "follows", "title", "text", "link"):
			self.assertTrue(frappe.get_attr(d[name]))
