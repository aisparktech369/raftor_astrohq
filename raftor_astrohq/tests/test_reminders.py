"""My reminders (reminders.py): which days a reminder holds on, the special days, what a person may keep, and that a reminder is sent once."""
import datetime
from unittest.mock import patch

import frappe

from raftor_astrohq import reminders
from raftor_astrohq.tests.helpers import AstroTestCase, make_user

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


class TestMyList(AstroTestCase):
	def setUp(self):
		super().setUp()
		self.me, self.other = make_user(), make_user()

	def _as(self, user):
		frappe.set_user(user.name)

	def test_a_person_adds_lists_pauses_and_deletes_their_own(self):
		self._as(self.me)
		self.assertTrue(reminders.save_reminder({"tithi": "Ashtami", "paksha": "Krishna", "lead": "Both"})["ok"])
		(item,) = reminders.list_reminders()["items"]
		self.assertEqual(item["title"], "Ashtami (Krishna)")
		reminders.toggle_reminder(item["id"])
		self.assertFalse(reminders.list_reminders()["items"][0]["switch"]["on"])
		reminders.delete_reminder(item["id"])
		self.assertEqual(reminders.list_reminders()["items"], [])

	def test_a_person_cannot_touch_another_persons_reminder(self):
		self._as(self.me)
		reminders.save_reminder({"weekday": "Tuesday"})
		name = reminders.list_reminders()["items"][0]["id"]
		self._as(self.other)
		self.assertEqual(reminders.list_reminders()["items"], [])
		with self.assertRaises(frappe.DoesNotExistError):
			reminders.delete_reminder(name)
		with self.assertRaises(frappe.DoesNotExistError):
			reminders.toggle_reminder(name)

	def test_a_guest_is_refused(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			reminders.list_reminders()

	def test_what_is_wrong_comes_back_per_field(self):
		self._as(self.me)
		self.assertIn("tithi", reminders.save_reminder({})["errors"])  # nothing named
		self.assertIn("tithi", reminders.save_reminder({"tithi": "Nonsense"})["errors"])
		self.assertIn("weekday", reminders.save_reminder({"weekday": "Funday"})["errors"])
		self.assertIn("special", reminders.save_reminder({"special": "Made up"})["errors"])
		self.assertIn("lead", reminders.save_reminder({"weekday": "Monday", "lead": "Whenever"})["errors"])

	def test_several_choices_are_kept_in_the_lists_order_and_unknown_ones_refused(self):
		self._as(self.me)
		self.assertTrue(reminders.save_reminder({"tithi": "Amavasya,Ashtami", "weekday": "Friday,Tuesday"})["ok"])
		row = frappe.db.get_value("Astro Reminder", {"user": self.me.name}, ["tithi", "weekday"], as_dict=True)
		self.assertEqual((row.tithi, row.weekday), ("Ashtami,Amavasya", "Tuesday,Friday"))
		self.assertIn("tithi", reminders.save_reminder({"tithi": "Ashtami,Nonsense"})["errors"])

	def test_the_same_reminder_twice_and_too_many_are_refused(self):
		self._as(self.me)
		self.assertTrue(reminders.save_reminder({"tithi": "Ekadashi"})["ok"])
		self.assertFalse(reminders.save_reminder({"tithi": "Ekadashi"})["ok"])
		with patch.object(reminders, "MAX_PER_PERSON", 1):
			self.assertFalse(reminders.save_reminder({"weekday": "Friday"})["ok"])


class TestSending(AstroTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.delete(reminders.DOCTYPE)  # (only for this test: what real people saved is back when it ends)
		frappe.db.delete(reminders.SENT)
		self.me = make_user()
		frappe.set_user(self.me.name)
		reminders.save_reminder({"tithi": "Ashtami", "paksha": "Krishna", "lead": "Both"})
		reminders.save_reminder({"weekday": "Friday", "lead": "Morning of"})
		frappe.set_user("Administrator")

	def _run(self, slot, **kw):
		with patch("raftor_astrohq.panchang.default_place", return_value={"timezone": "Asia/Kolkata"}), patch("raftor_astrohq.panchang.today", return_value=DAY - datetime.timedelta(days=1 if slot == "evening" else 0)), \
				patch.object(reminders, "facts", return_value=day(**kw)), patch("raftor_servicehq.messages.send") as send, patch.object(frappe.db, "commit"):
			return reminders.remind(slot), send

	def test_the_evening_before_tells_those_whose_day_it_is_once(self):
		sent, send = self._run("evening")
		self.assertEqual(sent, 1)
		event, user, context = send.call_args.args
		self.assertEqual((event, user), ("astro.reminder", self.me.name))
		self.assertEqual(context["title"], "Ashtami (Krishna)")
		self.assertIn("Tomorrow", context["text"])
		again, send = self._run("evening")  # a run that is repeated sends nothing new
		self.assertEqual(again, 0)
		send.assert_not_called()

	def test_the_morning_is_a_different_time_and_respects_the_lead(self):
		sent, _ = self._run("morning")  # the Ashtami reminder is Both, the Friday one is Morning of but today is a Tuesday
		self.assertEqual(sent, 1)
		sent, _ = self._run("morning", weekday="Friday", tithi="Dashami")
		self.assertEqual(sent, 1)  # the Friday reminder holds, the Ashtami one does not (and the first was already sent for the Tuesday)

	def test_a_paused_reminder_or_a_disabled_person_is_not_told(self):
		for name in frappe.get_all("Astro Reminder", filters={"user": self.me.name}, pluck="name"):
			frappe.db.set_value("Astro Reminder", name, "enabled", 0)
		sent, _ = self._run("evening")
		self.assertEqual(sent, 0)
