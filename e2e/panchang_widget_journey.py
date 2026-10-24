"""The glass card over a banner, as a visitor meets it (nobody signed in): a pill in the corner that opens the day's panchang and chaugharia, from websitehq's Pop-over section and library cards.

It builds a throwaway page (a pop-over section just before the Home banner's own section, which it only reads), names a town for the Panchang for the run, and removes both afterwards; the Home page is never touched.
    desk    the pill in the corner of the banner with the glass, one card on view; a tap opens the card (bar of eight parts, the tiles, the link to the Panchang page); Escape and a tap elsewhere shut it
    kept    a town chosen on the Panchang page (kept in the browser) is the one the card is about
    phone   the pill in the middle; the open card is a sheet from the bottom over a dimmed page; nothing runs off the screen
Run: python3 panchang_widget_journey.py        (SHOTS=/some/folder to keep the pictures)"""
import json
import os
import sys

sys.path.insert(0, "/home/ubuntu/dev-bench/apps/raftor_servicehq/e2e")
from playwright.sync_api import sync_playwright  # noqa: E402

from shop_e2e import B, run, val  # noqa: E402

SHOTS = os.environ.get("SHOTS")
SETTINGS = "Astrology API Settings"
PAGE, SECTION, ROUTE = "Panchang widget check", "check:panchang-widget", "panchang-widget-check"
fails = []


def check(name, ok, extra=""):
	print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""), flush=True)
	if not ok:
		fails.append(name)


def shot(page, name, **options):
	if SHOTS:
		os.makedirs(SHOTS, exist_ok=True)
		page.screenshot(path=os.path.join(SHOTS, name), **options)


def build():
	links = json.dumps([{"label": "The full panchang, night chaugharia and the next 7 days →", "href": "/panchang", "kind": "secondary", "where": "bottom"}])
	run(f'''
import json
from raftor_websitehq.website_hq import page_sync as ps
for name in ({SECTION!r},):
    if frappe.db.exists("RFHQ Section", name):
        frappe.delete_doc("RFHQ Section", name, force=True)
doc = frappe.new_doc("RFHQ Section")
doc.title = {SECTION!r}
for k, v in dict(section_layout="Grid", columns="2", content_source="App Records", records_source="raftor_astrohq.panchang.widget_cards", records_card="Stat Card", records_args="{{}}",
                 records_kept="place", records_refresh=60, records_links={links!r}, popover="Top Right", surface="Glass", section_padding="None", gap="Small").items():
    doc.set(k, v)
doc.insert(ignore_permissions=True)
if frappe.db.exists("Web Page", {{"route": {ROUTE!r}}}):
    frappe.delete_doc("Web Page", frappe.db.get_value("Web Page", {{"route": {ROUTE!r}}}, "name"), force=True)
page = frappe.get_doc({{"doctype": "Web Page", "title": {PAGE!r}, "route": {ROUTE!r}, "published": 1, "content_type": "Page Builder", "rfhq_full_width": 1}})
for name in ({SECTION!r}, "site:home:hero", "site:home:boxes"):
    page.append("page_blocks", {{"web_template": ps.SECTION_BLOCK, "web_template_values": json.dumps({{"section_name": name}}), "add_top_padding": 0, "add_bottom_padding": 0}})
page.insert(ignore_permissions=True)
frappe.db.commit()
from frappe.website.utils import clear_cache
clear_cache()
''')


def remove():
	run(f'''
if frappe.db.exists("Web Page", {{"route": {ROUTE!r}}}):
    frappe.delete_doc("Web Page", frappe.db.get_value("Web Page", {{"route": {ROUTE!r}}}, "name"), force=True)
if frappe.db.exists("RFHQ Section", {SECTION!r}):
    frappe.delete_doc("RFHQ Section", {SECTION!r}, force=True)
frappe.db.commit()
from frappe.website.utils import clear_cache
clear_cache()
''')


def desk(browser):
	context = browser.new_context(viewport={"width": 1440, "height": 900})
	page = context.new_page()
	errors = []
	page.on("pageerror", lambda e: errors.append(str(e)))
	page.goto(B + "/" + ROUTE, wait_until="networkidle")
	page.wait_for_selector(".rfhq-record-cell", timeout=15000)
	cells = page.locator("[data-rfhq-popover] .rfhq-record-cell")
	check("the card is drawn from the app's cards", cells.count() >= 8, cells.count())
	check("only the first card is on view", cells.nth(0).is_visible() and not cells.nth(1).is_visible())
	pill = page.inner_text("[data-rfhq-popover] .rfhq-record-cell:first-child").replace("\n", " | ")
	check("the pill says the tithi and the chaugharia", "Shukla" in pill or "Krishna" in pill or "Purnima" in pill or "Amavasya" in pill, pill)
	check("the pill says the chaugharia", "Chaugharia:" in pill and ("good" in pill or "avoid" in pill), pill)
	box = cells.nth(0).bounding_box()
	check("the pill is in the corner of the banner", box["x"] + box["width"] > 1440 - 400 and box["y"] < 140, str(box))
	glass = page.evaluate("getComputedStyle(document.querySelector('[data-rfhq-popover] .rfhq-feature-card--pill')).backdropFilter")
	check("the pill is the library's glass (blur)", "blur" in (glass or ""), glass)
	check("the pill is a button for a screen reader", page.get_attribute("[data-rfhq-popover] .rfhq-record-cell:first-child", "aria-expanded") == "false")
	shot(page, "widget-closed.png", clip={"x": 0, "y": 0, "width": 1440, "height": 420})

	page.click("[data-rfhq-popover] .rfhq-record-cell:first-child")
	check("a tap opens it", page.get_attribute("[data-rfhq-popover]", "data-open") is not None and page.get_attribute("[data-rfhq-popover] .rfhq-record-cell:first-child", "aria-expanded") == "true")
	check("the bar has its eight parts and one marked", page.locator("[data-rfhq-popover] .rfhq-sb-bar li").count() == 8 and page.locator("[data-rfhq-popover] .rfhq-sb-bar li.is-now").count() == 1)
	check("the tiles are there", page.locator("[data-rfhq-popover] .rfhq-stat-card").count() >= 5)
	check("the link to the Panchang page is there", page.locator("[data-rfhq-popover] .rfhq-records-links a[href='/panchang']").is_visible())
	panel = page.evaluate("(() => { const r = document.querySelector('[data-rfhq-popover] .rfhq-app-records').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom, innerWidth, innerHeight]; })()")
	check("it is in the window and no wider than 26rem", panel[0] >= 0 and panel[1] <= panel[4] and panel[1] - panel[0] <= 420 and panel[3] <= panel[5], str(panel))
	shot(page, "widget-open.png", clip={"x": 700, "y": 0, "width": 740, "height": 900})
	page.keyboard.press("Escape")
	check("Escape shuts it", page.get_attribute("[data-rfhq-popover]", "data-open") is None)
	page.click("[data-rfhq-popover] .rfhq-record-cell:first-child")
	page.mouse.click(300, 600)
	check("a tap elsewhere shuts it", page.get_attribute("[data-rfhq-popover]", "data-open") is None)
	check("no horizontal scroll", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
	home = page.request.get(B + "/").text()
	check("the Home page has no pop-over (it is not switched on there)", "data-rfhq-popover" not in home)

	page.evaluate("localStorage.setItem('rfhq:lookup:place', JSON.stringify({value: '1275339', label: 'Mumbai, India'}))")
	page.goto(B + "/" + ROUTE, wait_until="networkidle")
	page.wait_for_selector(".rfhq-record-cell", timeout=15000)
	page.click("[data-rfhq-popover] .rfhq-record-cell:first-child")
	check("the town kept in the browser is the one the card is about", "mumbai, india" in page.inner_text("[data-rfhq-popover] .rfhq-fc-tag").lower(), page.inner_text("[data-rfhq-popover] .rfhq-fc-tag"))
	check("desk: no errors", not errors, str(errors[:3]))
	context.close()


def phone(browser):
	context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
	page = context.new_page()
	page.goto(B + "/" + ROUTE, wait_until="networkidle")
	page.wait_for_selector(".rfhq-record-cell", timeout=15000)
	box = page.locator("[data-rfhq-popover] .rfhq-record-cell").nth(0).bounding_box()
	check("phone: the pill is in the middle", abs((box["x"] + box["width"] / 2) - 195) < 30, str(box))
	shot(page, "widget-phone-closed.png")
	page.tap("[data-rfhq-popover] .rfhq-record-cell:first-child")
	page.wait_for_timeout(300)
	sheet = page.evaluate("(() => { const r = document.querySelector('[data-rfhq-popover] .rfhq-app-records').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom, innerWidth, innerHeight, document.documentElement.scrollWidth]; })()")
	check("phone: the open card is a sheet from the bottom", sheet[0] <= 1 and sheet[1] >= sheet[4] - 1 and abs(sheet[3] - sheet[5]) <= 1, str(sheet))
	check("phone: it keeps to the screen", sheet[6] <= sheet[4] and sheet[2] >= 0, str(sheet))
	dim = page.evaluate("getComputedStyle(document.querySelector('[data-rfhq-popover]'), '::before').backgroundColor")
	check("phone: the page behind is dimmed", dim != "rgba(0, 0, 0, 0)", dim)
	shot(page, "widget-phone-open.png")
	page.tap("[data-rfhq-popover] .rfhq-record-cell:first-child")
	check("phone: a tap on the pill shuts it", page.get_attribute("[data-rfhq-popover]", "data-open") is None)
	context.close()


if __name__ == "__main__":
	was = val(run(f'print("was=" + str(frappe.db.get_single_value("{SETTINGS}", "panchang_place") or ""))'), "was")
	try:
		run(f'frappe.db.set_single_value("{SETTINGS}", "panchang_place", "Delhi")')
		build()
		with sync_playwright() as p:
			browser = p.chromium.launch()
			desk(browser)
			phone(browser)
			browser.close()
	finally:
		remove()
		run(f'frappe.db.set_single_value("{SETTINGS}", "panchang_place", {was!r})\nfor prefix in ("astro_panchang", "astro_panchang_new", "astro_panchang_muhurat"):\n\tfrappe.cache().delete_keys(prefix)')
		print("Place for the Panchang is back to:", repr(val(run(f'print("now=" + str(frappe.db.get_single_value("{SETTINGS}", "panchang_place") or ""))'), "now")))
	print("FAILED:" if fails else "ALL PASSED", fails)
	sys.exit(1 if fails else 0)
