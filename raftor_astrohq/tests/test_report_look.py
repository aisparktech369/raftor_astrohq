"""What a report wears: the site's own brand (its still logo, its colours and type, from websitehq's `document_brand`), or the plain look the reports have always had when the site has none (report_pdf.py).

Run with: bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_report_look
"""
from unittest import mock

from raftor_astrohq import arrange, reports
from raftor_astrohq import report_pdf as rp
from raftor_astrohq.tests.helpers import AstroTestCase
from raftor_astrohq.tests.test_kundli_reports import ANSWERS, Stood

BRAND = {"name": "Brand & Co", "logo": "data:image/png;base64,AAAA", "ink": "#1f1626", "heading": "#3a1d49", "accent": "#a8832d", "muted": "#655a6e", "line": "#e6dece", "page": "#faf7f1", "soft": "#f1eff2",
		 "heading_font": '"Fraunces",Georgia,serif', "body_font": '"DM Sans",Helvetica,sans-serif', "styled": True}
CELLS = ["Mars♂\n"] + [""] * 11


class TestTheLook(AstroTestCase):
	def test_a_site_with_no_brand_wears_the_plain_look_the_reports_always_had(self):
		for nothing in ({}, None, {"styled": False}):
			self.assertEqual(rp.look_of(nothing), rp.DEFAULT_LOOK)
		self.assertEqual(rp.STYLE, rp.style())
		self.assertEqual(rp.style(rp.DEFAULT_LOOK), rp.style())
		self.assertIn(rp.ACCENT, rp.style())

	def test_a_brand_gives_its_colours_its_type_and_its_logo(self):
		look = rp.look_of(BRAND)
		self.assertEqual((look["ink"], look["heading"], look["accent"], look["line"], look["soft"], look["muted"]), ("#1f1626", "#3a1d49", "#a8832d", "#e6dece", "#f1eff2", "#655a6e"))
		self.assertEqual((look["logo"], look["name"], look["key"]), ("data:image/png;base64,AAAA", "Brand & Co", "#faf7f1"))
		self.assertEqual(look["heading_font"], '"Fraunces",Georgia,serif')
		self.assertNotEqual(look["now"], rp.DEFAULT_LOOK["now"])  # the running period is marked in the accent colour's tint

	def test_the_style_sheet_is_written_in_the_look_and_the_old_colours_are_gone(self):
		css = rp.style(rp.look_of(BRAND))
		for colour in ("#3a1d49", "#e6dece", "#f1eff2", "#a8832d"):
			self.assertIn(colour, css)
		for old in (rp.ACCENT, rp.LINE, rp.SOFT):
			self.assertNotIn(old, css)
		self.assertIn("h1, h2 { font-family: \"Fraunces\",Georgia,serif", css)
		self.assertNotIn("font-family: \"Fraunces\"", rp.style())  # no heading type of its own: the headings keep the body type, as before

	def test_the_top_of_the_page_is_the_logo_or_else_the_name_in_small_type_or_nothing(self):
		self.assertIn('<img src="data:image/png;base64,AAAA" alt="Brand &amp; Co">', rp.masthead(rp.look_of(BRAND), "Brand & Co"))
		self.assertNotIn("Brand &amp; Co</span>", rp.masthead(rp.look_of(BRAND), "Brand & Co"))  # the logo says the name
		self.assertEqual(rp.masthead(rp.DEFAULT_LOOK, "Brand & Co"), '<div class="brand">Brand &amp; Co</div>')
		self.assertEqual(rp.masthead(None, ""), "")

	def test_a_logo_cannot_break_out_of_its_tag(self):
		look = rp.look_of({**BRAND, "logo": 'x" onerror="alert(1)', "name": '"><script>'})
		html = rp.masthead(look, '"><script>')
		self.assertNotIn("<script>", html)
		self.assertNotIn('" onerror="', html)

	def test_the_chart_is_drawn_in_the_look(self):
		branded = rp.diamond_chart_svg(CELLS, 0, "T", look=rp.look_of(BRAND))
		self.assertIn("#3a1d49", branded)
		self.assertIn("#f1eff2", branded)  # the first house
		self.assertNotIn(rp.ACCENT, branded)
		self.assertIn(rp.ACCENT, rp.diamond_chart_svg(CELLS, 0, "T"))

	def test_the_site_look_is_the_brand_of_websitehq_or_the_plain_one(self):
		with mock.patch("raftor_websitehq.website_hq.brand.document_brand", lambda: BRAND):
			self.assertEqual(rp.site_look()["heading"], "#3a1d49")
		with mock.patch("raftor_websitehq.website_hq.brand.document_brand", lambda: {}):
			self.assertEqual(rp.site_look(), rp.DEFAULT_LOOK)


class TestTheReportsWearIt(Stood):
	def test_the_kundli_report_wears_the_brand(self):
		with mock.patch.object(rp, "site_look", lambda: rp.look_of(BRAND)):
			html = reports.kundli_html(self.kundli_context())
		self.assertIn('<img src="data:image/png;base64,AAAA"', html)
		self.assertIn("#3a1d49", html)
		self.assertNotIn(rp.ACCENT, html)
		self.assertIn("Lagna chart (Rasi, D1)", html)  # the chart's title is inside its picture, in the brand's colour

	def test_the_kundli_report_of_a_site_with_no_brand_is_as_it_was(self):
		with mock.patch.object(rp, "site_look", lambda: dict(rp.DEFAULT_LOOK)), mock.patch.object(reports, "_brand", lambda: "AstroHQ"):
			html = reports.kundli_html(self.kundli_context())
		self.assertIn('<div class="brand">AstroHQ</div>', html)
		self.assertNotIn("<img", html)
		self.assertIn(rp.ACCENT, html)

	def test_the_arranged_pages_wear_it_too(self):
		html = arrange.html(ANSWERS["boy_super_basic"], "basic", today=reports.getdate("2026-10-23"), look=rp.look_of(BRAND))
		self.assertIn('<img src="data:image/png;base64,AAAA"', html)
		self.assertIn("#3a1d49", html)
		self.assertIn("#f1eff2", html)  # the table heads and the first house
		self.assertNotIn(rp.ACCENT, html)  # none of the plain look is left: not in the page's style, nor in a chart
		plain = arrange.html(ANSWERS["boy_super_basic"], "basic", today=reports.getdate("2026-10-23"))
		self.assertNotIn("<img", plain)
		self.assertIn(rp.ACCENT, plain)
