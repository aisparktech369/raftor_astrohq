"""Home (with the panchang card switched on) and the Panchang page on phones and a tablet (320, 360, 390, 430, 768 wide), in the app shell: nothing runs off the screen, the pill is a full-size tap target, the open card fits
and, on a phone, is a sheet that locks the page behind it, the Panchang bar fits with its controls at least 40 high. Run: python3 panchang_mobile_check.py   (SHOTS=/some/folder to keep the pictures)"""
import os
from playwright.sync_api import sync_playwright
B = "http://localhost:8701"
OUT = os.environ.get("SHOTS", "/tmp/panchang-mobile") + "/"
os.makedirs(OUT, exist_ok=True)
bad = []
def check(name, ok, extra=""):
    print(("ok   " if ok else "FAIL ") + name + (f" [{extra}]" if extra else ""))
    if not ok: bad.append(name)
with sync_playwright() as p:
    br = p.chromium.launch()
    for w, h in ((320, 640), (360, 740), (390, 844), (430, 932), (768, 1024)):
        ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True); pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(B + "/", wait_until="networkidle"); pg.wait_for_selector("[data-rfhq-popover] .rfhq-record-cell", timeout=15000); pg.wait_for_timeout(1200)
        m = pg.evaluate("""() => { const c = document.querySelector('[data-rfhq-popover] .rfhq-record-cell'); const r = c.getBoundingClientRect(); const pill = c.querySelector('.rfhq-card').getBoundingClientRect();
          return {cell: [Math.round(r.left), Math.round(r.right), Math.round(r.height)], pill: [Math.round(pill.left), Math.round(pill.right), Math.round(pill.height)], shell: document.body.classList.contains('pwahq-active'), fit: document.documentElement.scrollWidth <= innerWidth}; }""")
        check(f"{w}: Home fits the screen", m["fit"])
        check(f"{w}: the pill is inside the screen", m["pill"][0] >= 0 and m["pill"][1] <= w, str(m["pill"]))
        check(f"{w}: the tap target is at least 44 high" if w < 768 else f"{w}: tablet", m["cell"][2] >= 44 or w >= 768, str(m["cell"]))
        if w == 360: pg.screenshot(path=OUT + "home-360-closed.png")
        pg.tap("[data-rfhq-popover] .rfhq-record-cell:first-child"); pg.wait_for_timeout(450)
        s = pg.evaluate("""() => { const r = document.querySelector('[data-rfhq-popover] .rfhq-app-records').getBoundingClientRect(); return {l: Math.round(r.left), r: Math.round(r.right), t: Math.round(r.top), b: Math.round(r.bottom), w: innerWidth, h: innerHeight, sw: document.documentElement.scrollWidth, htmlOverflow: getComputedStyle(document.documentElement).overflow}; }""")
        check(f"{w}: the open card is inside the screen", s["l"] >= 0 and s["r"] <= s["w"] and s["t"] >= 0 and s["b"] <= s["h"] + 1 and s["sw"] <= s["w"], str(s))
        if w < 768:
            check(f"{w}: the sheet comes from the bottom and the page behind is locked", abs(s["b"] - s["h"]) <= 1 and s["htmlOverflow"] == "hidden", str(s))
        if w == 360: pg.screenshot(path=OUT + "home-360-open.png")
        pg.tap("[data-rfhq-popover] .rfhq-record-cell:first-child"); pg.wait_for_timeout(200)
        check(f"{w}: shut again and the page scrolls again", pg.get_attribute("[data-rfhq-popover]", "data-open") is None and pg.evaluate("getComputedStyle(document.documentElement).overflow") != "hidden")
        pg.goto(B + "/panchang", wait_until="networkidle"); pg.wait_for_selector(".rv-ctl", timeout=15000); pg.wait_for_timeout(600)
        q = pg.evaluate("""() => ({fit: document.documentElement.scrollWidth <= innerWidth, out: [...document.querySelectorAll('.rv-ctl-btn')].filter(e => { const r = e.getBoundingClientRect(); return r.left < -1 || r.right > innerWidth + 1; }).length, small: [...document.querySelectorAll('.rv-ctl-btn')].filter(e => e.getBoundingClientRect().height < 40).length})""")
        check(f"{w}: /panchang fits and its controls are inside and big enough", q["fit"] and q["out"] == 0 and q["small"] == 0, str(q))
        if w == 320: pg.screenshot(path=OUT + "panchang-320.png")
        check(f"{w}: no errors", not errs, str(errs[:2]))
        ctx.close()
    br.close()
print("FAILED:" if bad else "ALL OK", bad)
