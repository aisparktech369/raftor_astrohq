"""The reports made from a layout (reports.arranged_report, the vocabulary's "detailed", "dasha", "kp" and "panchang"): the engine's answers kept for the person, the layout's sections a customer may see, the site's brand, a PDF.

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_arranged_reports
"""
import io
import re
from unittest import mock

import frappe
from pypdf import PdfReader

from raftor_astrohq import answers, arrange, astrology, places, report_pdf as rp, reports, vocabulary
from raftor_astrohq.tests.helpers import AstroTestCase, make_user
from raftor_astrohq.tests.test_arrange import MODES
from raftor_astrohq.tests.test_kundli_reports import DELHI, KUNDLI_DETAILS

ENTRIES = vocabulary.arranged_reports()
KNOWN_MODES = set(MODES)


def pdf_text(content: bytes) -> str:
	return re.sub(r"\s+", " ", " ".join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages))


class Made(AstroTestCase):
	"""The engine, the place finder and the item's entry stood in for; the person is a real user (what is kept is theirs)."""

	def setUp(self):
		super().setUp()
		self.asked = []
		self.entry = ENTRIES["detailed"]

		def chart(birth, opcode="SUPER_BASIC", partner=None):
			self.asked.append((opcode, birth))
			return MODES[opcode]

		for patcher in (mock.patch.object(astrology, "chart", chart), mock.patch.object(places, "lookup", lambda text, on: dict(DELHI)),
						mock.patch.object(reports, "report_entry", lambda code: ENTRIES[code]), mock.patch.object(reports, "today", lambda: "2026-10-23")):
			patcher.start()
			self.addCleanup(patcher.stop)
		self.user = make_user().name

	def make(self, which="detailed", details=None):
		return reports.arranged_report(which, details or KUNDLI_DETAILS, self.user)


class TestWhatTheVocabularyShips(AstroTestCase):
	def test_each_report_names_a_layout_a_mode_and_a_maker_that_exist(self):
		self.assertEqual(sorted(ENTRIES), ["dasha", "detailed", "kp", "panchang"])
		for name, entry in ENTRIES.items():
			with self.subTest(name):
				layout = arrange.layout_named(entry["layout"])
				self.assertTrue(layout["sections"])
				self.assertTrue(entry["modes"] and set(entry["modes"]) <= KNOWN_MODES)
				self.assertTrue(callable(frappe.get_attr(entry["maker"])))
				self.assertTrue(callable(frappe.get_attr(entry["details"]["validate"])))
				self.assertEqual(entry["price"], 0)  # free, always
				self.assertTrue(entry["title"] and entry["blurb"] and entry["description"])
				self.assertEqual(entry["free"].keys(), vocabulary.person_free().keys())

	def test_the_reports_are_listed_after_the_two_that_were_there_first(self):
		self.assertEqual(list(vocabulary.vocabulary()["reports"]), ["kundli", "match", "detailed", "dasha", "kp", "panchang"])

	def test_the_kundli_and_the_detailed_kundli_ask_the_same_questions_in_the_same_way(self):
		reports_ = vocabulary.vocabulary()["reports"]
		self.assertEqual(reports_["kundli"]["free"], vocabulary.person_free())
		self.assertEqual(reports_["detailed"]["details"]["fields"], reports_["kundli"]["details"]["fields"])


class TestMakingOne(Made):
	def test_it_is_a_pdf_in_the_reports_own_name_for_the_person(self):
		made = self.make()
		self.assertTrue(made["content"].startswith(b"%PDF"))
		self.assertEqual(made["file_name"], "advanced-report-asha-rao.pdf")
		text = pdf_text(made["content"])
		self.assertIn("Detailed kundli report", text)
		self.assertIn("Asha Rao", text)
		self.assertIn("Sunday, 08 June 1980, 13:49", text)
		self.assertIn("Delhi, Delhi, India", text)
		self.assertIn("Made for you on 23 October 2026", text)
		self.assertIn("Virgo (Kanya)", text)

	def test_a_customer_has_the_sections_an_astrologer_checked_and_no_draft_mark(self):
		text = pdf_text(self.make()["content"])
		for there in ("Birth", "Planets", "Vimshottari dasha", "Moon / Saturn"):
			self.assertIn(there, text)
		for not_there in ("Yogas", "Ashtakavarga", "Planet strength", "Panchang of the birth day"):
			self.assertNotIn(not_there, text)
		self.assertNotIn("DRAFT", text.upper())  # (the mark is set in capitals)

	def test_the_setting_that_shows_everything_marks_what_nobody_has_checked_as_draft(self):
		with mock.patch.object(reports, "shown", lambda: "all"):
			text = pdf_text(self.make()["content"])
		for there in ("Yogas", "Ashtakavarga", "Planet strength"):
			self.assertIn(there, text)
		self.assertGreater(text.upper().count("DRAFT"), 10)  # every part nobody has checked

	def test_the_setting_is_read_from_astrology_api_settings(self):
		frappe.db.set_single_value("Astrology API Settings", "show_unreviewed", 0)
		self.assertEqual(reports.shown(), "reviewed")
		frappe.db.set_single_value("Astrology API Settings", "show_unreviewed", 1)
		self.assertEqual(reports.shown(), "all")
		frappe.db.set_single_value("Astrology API Settings", "show_unreviewed", 0)

	def test_a_report_nobody_has_checked_any_of_cannot_be_given(self):
		for which in ("kp", "panchang"):
			self.asked.clear()
			with self.assertRaises(frappe.ValidationError) as caught:
				self.make(which)
			self.assertIn("checked by an astrologer", str(caught.exception))
			self.assertEqual(self.asked, [], which)  # and the engine was not asked for it

	def test_a_report_with_no_layout_says_so(self):
		with mock.patch.dict(ENTRIES, {"broken": {"title": "x", "modes": ["CORE_ADVANCED"]}}):
			with self.assertRaises(frappe.ValidationError):
				reports.arranged_report("broken", KUNDLI_DETAILS, self.user)


class TestTheEngineIsAskedOnce(Made):
	def test_a_second_report_of_the_same_birth_in_the_same_mode_costs_no_new_call(self):
		self.make()
		self.make()
		with mock.patch.object(reports, "shown", lambda: "all"):
			self.make()
		self.assertEqual([opcode for opcode, _birth in self.asked], ["CORE_ADVANCED"])
		self.assertEqual(frappe.db.count(answers.DOCTYPE, {"user": self.user}), 1)

	def test_another_person_with_the_same_birth_is_asked_for_again(self):
		self.make()
		reports.arranged_report("detailed", KUNDLI_DETAILS, make_user().name)
		self.assertEqual(len(self.asked), 2)

	def test_the_dasha_report_asks_for_the_systems_its_layout_names_and_nothing_else_goes_with_the_birth(self):
		with mock.patch.object(reports, "shown", lambda: "all"):
			text = pdf_text(self.make("dasha")["content"])
		(opcode, birth), = self.asked
		self.assertEqual(opcode, "DASHA_CALC")
		self.assertEqual(len(birth["requested_dasha_systems"]), 47)
		self.assertEqual(set(birth) - set(astrology.SENT), set())
		self.assertIn("Dasha periods report", text)
		self.assertIn("Vimshottari", text)

	def test_only_numbers_are_sent_never_the_name_or_the_place(self):
		self.make()
		(_opcode, birth), = self.asked
		self.assertEqual(set(birth), {"year", "month", "day", "hour", "minute", "second", "latitude", "longitude", "timezone_offset"})
		self.assertEqual((birth["year"], birth["month"], birth["day"], birth["hour"], birth["minute"]), (1980, 6, 8, 13, 49))


class TestTheBrandIsWorn(Made):
	def test_the_pdf_is_drawn_in_the_look_the_site_has(self):
		look = rp.look_of({"name": "Brand & Co", "logo": "", "ink": "#1f1626", "heading": "#3a1d49", "accent": "#a8832d", "muted": "#655a6e", "line": "#e6dece", "page": "#faf7f1", "soft": "#f1eff2", "heading_font": "", "body_font": "", "styled": True})
		with mock.patch.object(rp, "site_look", lambda: look), mock.patch.object(arrange, "html", wraps=arrange.html) as lay:
			self.make()
		self.assertIs(lay.call_args.kwargs["look"], look)
		self.assertEqual(lay.call_args.kwargs["show"], "reviewed")
