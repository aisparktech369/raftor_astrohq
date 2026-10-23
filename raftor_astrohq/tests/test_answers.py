"""What the engine answered, kept for each person (answers.py, the Astro Answer record).

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_answers
"""
import hashlib
import json
from unittest import mock

import frappe

from raftor_astrohq import answers, astrology
from raftor_astrohq.tests.helpers import AstroTestCase, make_user

NUMBERS = {"year": 1980, "month": 6, "day": 8, "hour": 13, "minute": 49, "second": 0, "latitude": 28.65195, "longitude": 77.23149, "timezone_offset": 5.5}
OTHER = {**NUMBERS, "year": 1982, "month": 3, "day": 2}


class Engine(AstroTestCase):
	"""An engine that answers with what it was asked and counts the questions."""

	def setUp(self):
		super().setUp()
		self.asked = []

		def chart(birth, opcode="SUPER_BASIC", partner=None):
			self.asked.append((opcode, birth["year"], partner["year"] if partner else None))
			return {"mode": opcode, "year": birth["year"], "name": "Ásha ☉", "list": [1, 2, 3]}

		patcher = mock.patch.object(astrology, "chart", chart)
		patcher.start()
		self.addCleanup(patcher.stop)
		self.user = make_user().name
		self.other_user = make_user().name


class TestTheFingerprint(Engine):
	def test_it_is_the_same_for_the_same_person_mode_and_numbers_whatever_else_is_in_the_dict(self):
		first = answers.fingerprint(self.user, "CORE_ADVANCED", NUMBERS)
		self.assertEqual(first, answers.fingerprint(self.user, "CORE_ADVANCED", {**NUMBERS, "name": "Asha", "place": "Delhi", "note": "x"}))  # only what the engine is sent counts
		self.assertEqual(len(first), 64)

	def test_it_differs_by_person_mode_numbers_and_partner(self):
		base = answers.fingerprint(self.user, "CORE_ADVANCED", NUMBERS)
		for changed in (answers.fingerprint(self.other_user, "CORE_ADVANCED", NUMBERS), answers.fingerprint(self.user, "KP_SYSTEM", NUMBERS), answers.fingerprint(self.user, "CORE_ADVANCED", OTHER),
						answers.fingerprint(self.user, "MATCH_CALC", NUMBERS, OTHER), answers.fingerprint(self.user, "MATCH_CALC", OTHER, NUMBERS)):
			self.assertNotEqual(base, changed)
		self.assertNotEqual(answers.fingerprint(self.user, "MATCH_CALC", NUMBERS, OTHER), answers.fingerprint(self.user, "MATCH_CALC", NUMBERS))

	def test_an_answer_is_packed_and_read_back_exactly(self):
		data = {"name": "Ásha ☉", "list": [1, 2.5, None, True], "nested": {"a": "♍︎Virgo"}}
		packed = answers.pack(data)
		self.assertEqual(answers.unpack(packed), data)
		self.assertLess(len(answers.pack({"x": "abc" * 10000})), 600)  # long repeated answers pack small


class TestKeeping(Engine):
	def test_the_engine_is_asked_once_and_the_second_time_the_kept_answer_is_read(self):
		first = answers.get(self.user, NUMBERS, "CORE_ADVANCED")
		second = answers.get(self.user, NUMBERS, "CORE_ADVANCED")
		self.assertEqual(first, second)
		self.assertEqual(first["name"], "Ásha ☉")
		self.assertEqual(self.asked, [("CORE_ADVANCED", 1980, None)])
		self.assertEqual(frappe.db.count(answers.DOCTYPE, {"user": self.user}), 1)

	def test_another_mode_another_birth_or_another_person_is_asked_for_separately(self):
		answers.get(self.user, NUMBERS, "CORE_ADVANCED")
		answers.get(self.user, NUMBERS, "KP_SYSTEM")
		answers.get(self.user, OTHER, "CORE_ADVANCED")
		answers.get(self.other_user, NUMBERS, "CORE_ADVANCED")  # the same birth, another person: never shares what is kept
		self.assertEqual(len(self.asked), 4)
		self.assertEqual(frappe.db.count(answers.DOCTYPE, {"user": self.user}), 3)
		self.assertEqual(frappe.db.count(answers.DOCTYPE, {"user": self.other_user}), 1)

	def test_nothing_is_kept_for_a_guest_or_when_it_is_not_to_be(self):
		answers.get("Guest", NUMBERS, "CORE_ADVANCED")
		answers.get("", NUMBERS, "CORE_ADVANCED")
		answers.get(self.user, NUMBERS, "CORE_ADVANCED", kept=False)
		self.assertEqual(len(self.asked), 3)
		self.assertEqual(frappe.db.count(answers.DOCTYPE), frappe.db.count(answers.DOCTYPE, {"user": ["not in", ["Guest", ""]]}))
		self.assertEqual(frappe.db.count(answers.DOCTYPE, {"user": self.user}), 0)

	def test_a_bundle_has_each_mode_and_the_partner_goes_only_to_the_match(self):
		both = answers.bundle(self.user, NUMBERS, ["CORE_ADVANCED", "MATCH_CALC"], OTHER)
		self.assertEqual(set(both), {"CORE_ADVANCED", "MATCH_CALC"})
		self.assertEqual(self.asked, [("CORE_ADVANCED", 1980, None), ("MATCH_CALC", 1980, 1982)])
		answers.bundle(self.user, NUMBERS, ["CORE_ADVANCED", "MATCH_CALC"], OTHER)
		self.assertEqual(len(self.asked), 2)

	def test_the_record_belongs_to_the_person_and_nobody_but_a_system_manager_may_read_it(self):
		answers.get(self.user, NUMBERS, "CORE_ADVANCED")
		name = answers.fingerprint(self.user, "CORE_ADVANCED", NUMBERS)
		self.assertTrue(frappe.has_permission(answers.DOCTYPE, "read", user="Administrator"))
		for person in (self.user, self.other_user):
			self.assertFalse(frappe.has_permission(answers.DOCTYPE, "read", doc=name, user=person))
		self.assertEqual(frappe.db.get_value(answers.DOCTYPE, name, ["user", "mode"], as_dict=True), {"user": self.user, "mode": "CORE_ADVANCED"})

	def test_two_requests_for_the_same_birth_at_once_do_not_fail(self):
		key = answers.fingerprint(self.user, "CORE_ADVANCED", NUMBERS)
		real = frappe.get_doc
		def racing(*args, **kwargs):
			doc = real(*args, **kwargs)
			if args and isinstance(args[0], dict) and args[0].get("doctype") == answers.DOCTYPE:
				doc.insert = mock.Mock(side_effect=frappe.DuplicateEntryError(answers.DOCTYPE, key, Exception("x")))
			return doc
		with mock.patch.object(frappe, "get_doc", racing):
			self.assertEqual(answers.get(self.user, NUMBERS, "CORE_ADVANCED")["year"], 1980)


class TestWhenToAskAgain(Engine):
	def made(self, days_ago: int):
		answers.get(self.user, NUMBERS, "CORE_ADVANCED")
		key = answers.fingerprint(self.user, "CORE_ADVANCED", NUMBERS)
		frappe.db.set_value(answers.DOCTYPE, key, "made_on", frappe.utils.add_days(frappe.utils.now_datetime(), -days_ago))
		return key

	def good_from(self, days_ago):
		return mock.patch.object(answers, "_good_from", lambda: frappe.utils.add_days(frappe.utils.today(), -days_ago))

	def test_an_answer_made_before_the_date_in_the_settings_is_asked_for_again_and_replaced(self):
		key = self.made(days_ago=3)
		with self.good_from(1):
			answers.get(self.user, NUMBERS, "CORE_ADVANCED")
		self.assertEqual(len(self.asked), 2)
		self.assertEqual(frappe.db.count(answers.DOCTYPE, {"key": key}), 1)  # replaced, not added
		self.assertEqual(frappe.utils.getdate(frappe.db.get_value(answers.DOCTYPE, key, "made_on")), frappe.utils.getdate())
		with self.good_from(1):
			answers.get(self.user, NUMBERS, "CORE_ADVANCED")
		self.assertEqual(len(self.asked), 2)  # and now it is good again

	def test_an_answer_made_after_that_date_or_with_no_date_set_is_kept_as_it_is(self):
		self.made(days_ago=3)
		with self.good_from(10):
			answers.get(self.user, NUMBERS, "CORE_ADVANCED")
		with mock.patch.object(answers, "_good_from", lambda: None):
			answers.get(self.user, NUMBERS, "CORE_ADVANCED")
		self.assertEqual(len(self.asked), 1)


class TestTheSkyAndForgetting(Engine):
	def test_the_sky_of_a_moment_is_kept_for_a_day_for_anyone_and_not_as_a_person_record(self):
		moment = {**NUMBERS, "year": 2026, "month": 10, "day": 23, "hour": 15, "minute": 0, "second": 17}  # (a second nobody else uses: the cache is shared)
		key = "astro_sky:" + hashlib.sha256(json.dumps(astrology._sendable(moment), sort_keys=True).encode()).hexdigest()[:32] + ":SUPER_BASIC"
		frappe.cache().delete_value(key)
		before = frappe.db.count(answers.DOCTYPE)
		try:
			first = answers.sky(moment)
			answers.sky(moment)
			self.assertEqual(len(self.asked), 1)
			self.assertEqual(first["year"], 2026)
			self.assertEqual(frappe.db.count(answers.DOCTYPE), before)  # nothing is kept as a person's record
		finally:
			frappe.cache().delete_value(key)

	def test_what_was_kept_for_a_person_goes_with_them_and_only_them(self):
		answers.get(self.user, NUMBERS, "CORE_ADVANCED")
		answers.get(self.user, NUMBERS, "KP_SYSTEM")
		answers.get(self.other_user, NUMBERS, "CORE_ADVANCED")
		self.assertEqual(answers.forget(self.user), 2)
		self.assertEqual(frappe.db.count(answers.DOCTYPE, {"user": self.user}), 0)
		self.assertEqual(frappe.db.count(answers.DOCTYPE, {"user": self.other_user}), 1)
		self.assertEqual(answers.forget(self.user), 0)

	def test_deleting_a_user_removes_what_was_kept_for_them(self):
		answers.get(self.user, NUMBERS, "CORE_ADVANCED")
		self.assertIn("raftor_astrohq.answers.forget_user", frappe.get_hooks("doc_events")["User"]["on_trash"])
		answers.forget_user(frappe.get_doc("User", self.user))
		self.assertEqual(frappe.db.count(answers.DOCTYPE, {"user": self.user}), 0)
