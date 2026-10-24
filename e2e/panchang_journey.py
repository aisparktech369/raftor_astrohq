"""The Panchang page, used in a browser the way a visitor uses it (nobody signed in):

    desk     the day, the town and the panes; the day before and after, Today, the far ends (1800 and 2399), a day typed into the calendar's box, a town found by its first letters and
             chosen with the keyboard, the town kept and used when the page is opened without one, a town that is not in the list, "use my location", the keys (Tab, Escape)
    phone    the town list fits the screen, a town chosen by a tap, the day after keeps the town, every control is at least 40 high
    off      with no town in the settings the page is quiet: no bar, no panes

It uses the astrology service and the list of places on this computer (the real ones). The one setting it changes (Astrology API Settings, "Place for the Panchang") is read first and put back
exactly as it was, and what the page kept of the days it asked for is removed.
Run: python3 panchang_journey.py        (SHOTS=/some/folder to keep the pictures)"""
import os
import re
import sys

sys.path.insert(0, "/home/ubuntu/dev-bench/apps/raftor_servicehq/e2e")
from playwright.sync_api import sync_playwright  # noqa: E402

from shop_e2e import B, run, val  # noqa: E402

SHOTS = os.environ.get("SHOTS")
SETTINGS = "Astrology API Settings"
fails = []


def check(name, ok, extra=""):
	print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""), flush=True)
	if not ok:
		fails.append(name)


def shot(page, name, **options):
	if SHOTS:
		os.makedirs(SHOTS, exist_ok=True)
		page.screenshot(path=os.path.join(SHOTS, name), **options)


def pill(page):
	return page.inner_text(".rv-ctl-pick").strip()


def town(page):
	return page.inner_text(".rv-ctl-town").replace("▾", "").strip()


def tithi(page):
	return page.evaluate("document.querySelector('.rv-keys tr td:nth-child(2)')?.textContent || ''")


def desk(browser):
	context = browser.new_context(viewport={"width": 1440, "height": 900}, geolocation={"latitude": 19.076, "longitude": 72.8777}, permissions=["geolocation"])
	page = context.new_page()
	errors = []
	page.on("pageerror", lambda e: errors.append(str(e)))
	page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)

	page.goto(B + "/panchang?date=2026-10-24", wait_until="networkidle")
	check("the bar is drawn", page.locator(".rv-ctl").count() == 1)
	check("the panes, chaugharia second", page.evaluate("[...document.querySelectorAll('.rv-pane .rv-title')].map(x => x.textContent)")[:3] == ["Panchang", "Chaugharia", "Times to know"])
	check("the date says the day", pill(page) == "Saturday, 24 October 2026", pill(page))
	check("the town is the default one", town(page).startswith("Delhi"), town(page))
	check("the tithi of that day at Delhi", tithi(page) == "Shukla Trayodashi", tithi(page))
	check("the moon is drawn", page.locator("svg.rv-moon polygon.rv-moon-lit").count() == 1)
	check("no horizontal scroll", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
	names = page.evaluate("[...document.querySelectorAll('.rv-ctl a, .rv-ctl button, .rv-ctl input')].map(e => [e.tagName, e.getAttribute('aria-label') || e.textContent.trim(), e.getAttribute('tabindex'), e.getAttribute('aria-hidden')])")
	check("the date box is out of the keyboard's way", ["INPUT", "Choose a date", "-1", "true"] in [list(n) for n in names], str(names))
	check("the date and town buttons are named with what they show", any(n[1] == "Choose a date: Saturday, 24 October 2026" for n in names) and any(n[1] == "Choose a town: Delhi, India" for n in names), str(names))
	tabs = []
	page.focus("body")
	for _ in range(14):
		page.keyboard.press("Tab")
		tabs.append(page.evaluate("document.activeElement.getAttribute('aria-label') || document.activeElement.textContent.trim().slice(0, 30)"))
	order = [t for t in tabs if t.startswith(("The day", "Choose", "Use my"))]
	check("Tab goes through the bar in order", order[:5] == ["The day before", "Choose a date: Saturday, 24 October 2026", "The day after", "Choose a town: Delhi, India", "Use my location"], str(tabs))
	shot(page, "panchang-desk.png", full_page=True)

	page.click(".rv-ctl-step[aria-label='The day after']")
	page.wait_for_url(lambda url: "date=2026-10-25" in url, timeout=10000)
	page.wait_for_load_state("networkidle")
	check("the day after", pill(page) == "Sunday, 25 October 2026" and tithi(page) == "Shukla Chaturdashi", f"{pill(page)} {tithi(page)}")
	check("nothing is marked as running on another day", page.locator(".rv-pane tr.rv-now, .rv-win.rv-now").count() == 0)
	check("Today is offered on another day", page.locator(".rv-ctl-today").count() == 1)
	page.click(".rv-ctl-today")
	page.wait_for_url(lambda url: "date=" not in url, timeout=10000)
	check("Today goes to the page without a date", re.search(r"/panchang(\?place=\d+)?$", page.url) is not None, page.url)

	page.goto(B + "/panchang?date=2026-10-24", wait_until="networkidle")
	page.evaluate("""() => { const i = document.querySelector('input.rv-ctl-date'); i.value = '1900-01-01'; i.dispatchEvent(new Event('change', {bubbles: true})); }""")
	page.wait_for_url("**/panchang?date=1900-01-01", timeout=10000)
	page.wait_for_load_state("networkidle")
	check("a day in 1900 is worked out", pill(page) == "Monday, 1 January 1900" and page.locator(".rv-keys").count() == 1, pill(page))
	page.goto(B + "/panchang?date=2399-12-31", wait_until="networkidle")
	check("the last day has no day after", page.locator("a.rv-ctl-step[aria-label='The day after']").count() == 0 and page.locator(".rv-ctl-step.is-off").count() == 1)
	page.goto(B + "/panchang?date=1700-05-05", wait_until="networkidle")
	check("before 1800 is the first day", pill(page).endswith("1 January 1800"), pill(page))
	check("the first day has no day before", page.locator("a.rv-ctl-step[aria-label='The day before']").count() == 0)

	page.goto(B + "/panchang?date=2026-11-08", wait_until="networkidle")
	page.evaluate("localStorage.clear(); sessionStorage.clear()")
	page.click(".rv-ctl-town")
	check("the list opens with the search box ready", page.evaluate("document.activeElement.classList.contains('rv-ctl-search')"))
	page.keyboard.type("Mum", delay=60)
	page.wait_for_selector(".rv-ctl-options li", timeout=8000)
	found = page.evaluate("[...document.querySelectorAll('.rv-ctl-options li')].map(li => li.innerText.replace(/\\n/g, ' | '))")
	check("Mum finds Mumbai first", found and found[0].startswith("Mumbai"), str(found[:3]))
	shot(page, "panchang-search.png", clip={"x": 100, "y": 150, "width": 1240, "height": 420})
	page.keyboard.press("ArrowDown")
	check("arrow down goes to the first town", page.evaluate("document.activeElement.tagName") == "LI")
	page.keyboard.press("Enter")
	page.wait_for_url(re.compile(r".*place=\d+.*"), timeout=10000)
	page.wait_for_load_state("networkidle")
	check("the address has the town and keeps the day", "date=2026-11-08" in page.url and "place=" in page.url, page.url)
	check("the bar names Mumbai", town(page).startswith("Mumbai"), town(page))
	check("the next days keep the town", all("place=" in h for h in page.evaluate("[...document.querySelectorAll('.rv-tile')].map(a => a.getAttribute('href'))")))
	kept = page.evaluate("JSON.parse(localStorage.getItem('rfhq:lookup:place') || 'null')")
	check("the town is kept in the browser", bool(kept) and kept["value"].isdigit(), str(kept))
	page.goto(B + "/panchang?date=2026-11-08", wait_until="networkidle")
	page.wait_for_timeout(500)
	check("a page opened without a town uses the kept one", "place=" in page.url and town(page).startswith("Mumbai"), page.url)

	page.click(".rv-ctl-town")
	page.keyboard.press("Escape")
	check("Escape closes the list", page.locator(".rv-ctl-list").is_hidden())
	page.click(".rv-ctl-town")
	page.keyboard.type("Zzzqx", delay=40)
	page.wait_for_selector(".rv-ctl-none:not([hidden])", timeout=8000)
	check("a town that is not there says so", "No town" in page.inner_text(".rv-ctl-none"))
	page.keyboard.press("Escape")
	page.click(".rv-ctl-town")
	page.mouse.click(700, 120)
	check("a click outside closes the list", page.locator(".rv-ctl-list").is_hidden())

	page.evaluate("localStorage.clear(); sessionStorage.clear()")
	page.goto(B + "/panchang?date=2026-10-24&place=19999999", wait_until="networkidle")
	check("a town that is not in the list gives the default", town(page).startswith("Delhi"), town(page))
	check("a town the page did not accept is not kept", page.evaluate("localStorage.getItem('rfhq:lookup:place')") is None)
	page.click(".rv-ctl-near")
	page.wait_for_url(lambda url: "place=" in url and "19999999" not in url, timeout=15000)
	page.wait_for_load_state("networkidle")
	check("use my location finds Mumbai", town(page).startswith("Mumbai"), town(page))
	check("desk: no errors in the console", not errors, str(errors[:3]))
	context.close()


def phone(browser):
	context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
	page = context.new_page()
	errors = []
	page.on("pageerror", lambda e: errors.append(str(e)))
	page.goto(B + "/panchang?date=2026-10-24", wait_until="networkidle")
	check("phone: no horizontal scroll", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
	shot(page, "panchang-phone.png", full_page=True)
	page.tap(".rv-ctl-town")
	page.fill(".rv-ctl-search", "Pun")
	page.wait_for_selector(".rv-ctl-options li", timeout=8000)
	box = page.evaluate("(() => { const r = document.querySelector('.rv-ctl-list').getBoundingClientRect(); return [r.left, r.right, innerWidth, document.documentElement.scrollWidth]; })()")
	check("phone: the town list fits the screen", box[0] >= 0 and box[1] <= box[2] and box[3] <= box[2], str(box))
	shot(page, "panchang-phone-search.png")
	page.tap(".rv-ctl-options li")
	page.wait_for_url(lambda url: "place=" in url, timeout=10000)
	page.wait_for_load_state("networkidle")
	check("phone: the town is chosen by a tap", "Pun" in town(page), town(page))
	page.tap(".rv-ctl-step[aria-label='The day after']")
	page.wait_for_url(lambda url: "date=2026-10-25" in url, timeout=10000)
	page.wait_for_load_state("networkidle")
	check("phone: the day after keeps the town", "place=" in page.url, page.url)
	sizes = page.evaluate("[...document.querySelectorAll('.rv-ctl-btn')].map(e => Math.round(e.getBoundingClientRect().height))")
	check("phone: every control is at least 40 high", sizes and all(h >= 40 for h in sizes), str(sizes))
	check("phone: no errors", not errors, str(errors[:3]))
	context.close()


def off(browser):
	run(f'frappe.db.set_single_value("{SETTINGS}", "panchang_place", "")')
	page = browser.new_page()
	page.goto(B + "/panchang?date=2026-10-24", wait_until="networkidle")
	page.wait_for_timeout(800)
	check("off: no bar and no panes", page.locator(".rv-ctl").count() == 0 and page.locator(".rv-pane").count() == 0)
	page.close()


if __name__ == "__main__":
	was = val(run(f'print("was=" + str(frappe.db.get_single_value("{SETTINGS}", "panchang_place") or ""))'), "was")
	try:
		run(f'frappe.db.set_single_value("{SETTINGS}", "panchang_place", "Delhi")')
		with sync_playwright() as p:
			browser = p.chromium.launch()
			desk(browser)
			phone(browser)
			off(browser)
			browser.close()
	finally:
		run(f'frappe.db.set_single_value("{SETTINGS}", "panchang_place", {was!r})\nfor prefix in ("astro_panchang", "astro_panchang_new", "astro_panchang_muhurat"):\n\tfrappe.cache().delete_keys(prefix)')
		print("Place for the Panchang is back to:", repr(val(run(f'print("now=" + str(frappe.db.get_single_value("{SETTINGS}", "panchang_place") or ""))'), "now")))
	print("FAILED:" if fails else "ALL PASSED", fails)
	sys.exit(1 if fails else 0)
