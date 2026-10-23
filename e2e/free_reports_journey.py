"""The two free reports, asked for and received in a browser, as each person sees it:

    stranger   on a phone, finds the kundli report, gives the details and a mobile number on ONE page, gets the code on the same page, makes the account, chooses a password,
               and reads the report with what to do next; the details become their birth profile
    the same   signs back in later with the mobile number and the password (asked to switch device, as everyone is who is signed in elsewhere)
    signed in  asks for a kundli for a child and a match making report in one step each (no number, no code); the form is filled from their profile; the safety limit says so
    a second   whose password is a must (the setting) cannot read the report until it is chosen
    stranger / another customer   are refused the file
    staff      a free report the astrology service could not make is listed with why; "Try again now" makes it once the service is back

It uses the astrology service and the list of places on this computer (the real ones), the mobile code stub (nothing is sent; the code is `12345678`) and made-up mobile numbers
(+9100000...: no real number has them). The two report items are free (price 0), switched off as they ship or on as the owner has them; the run switches them on if they are off and puts
them back exactly as they were, and every site setting it changes is read and put back.
Run: python3 free_reports_journey.py"""
import json
import os
import sys
import time
import uuid

os.environ.setdefault("JOURNEY", "free_reports_journey")
os.environ.setdefault("JOURNEY_TITLE", "The free kundli and match making reports")
sys.path.insert(0, "/home/ubuntu/dev-bench/apps/raftor_servicehq/e2e")
from playwright.sync_api import sync_playwright  # noqa: E402

import journey_lib as J  # noqa: E402
from shop_e2e import B, run, val  # noqa: E402

T = uuid.uuid4().hex[:5]
OTHER, STAFF = f"book-{T}b@example.com", f"staff-{T}@example.com"
KUNDLI, MATCH = "ASTROHQ-REPORT-KUNDLI", "ASTROHQ-REPORT-MATCH"
CODE, PASSWORD, NEW_PASSWORD = "12345678", "maple-river-42", "river-maple-77"
ASHA = "+9100000" + str(int(T, 16) % 90000 + 10000)  # made-up numbers from the range no real number has (+9100000...), each typed with its plus
MEERA = "+9100000" + str((int(T, 16) + 4567) % 90000 + 10000)
state = {"shots": [], "steps": [], "segments": {}}
ORIGINAL = {}
SITE = {}
LAST_CODE = {"at": 0.0}  # when a code was last asked for the first person's number: a new one can be asked for a minute later


def check(name, ok, extra=""):
	return J.check(state, name, ok, extra)


def snap(pg, role, caption, full=False):
	return J.snap(state, pg, role, caption, full=full)


def counts() -> dict:
	out = run('''
for doctype, filters in (("User", {}), ("Customer", {}), ("Sales Order", {}), ("Quotation", {}), ("Delivery Note", {}), ("Sales Invoice", {}), ("Payment Entry", {}), ("Free Report", {}),
						 ("Service Proof", {}), ("File", {"attached_to_doctype": "Free Report"}), ("Item", {}), ("Item Price", {}), ("Contact", {}), ("Address", {}), ("Error Log", {})):
    print("%s=%s" % (doctype.replace(" ", "_"), frappe.db.count(doctype, filters)))
''')
	return {line.split("=")[0]: int(line.split("=")[1]) for line in out.split() if "=" in line}


def frappe_value(expression: str) -> str:
	return val(run(f'print("V=" + str({expression}))'), "V")


def setup():
	"""Off camera: the people, the site settings the run needs (what they were is kept), and the two reports switched on."""
	global ORIGINAL, SITE
	out = run(f'''
import json
before = {{}}
for code in ("{KUNDLI}", "{MATCH}"):
    before[code] = {{"disabled": frappe.db.get_value("Item", code, "disabled"), "price": frappe.db.get_value("Item Price", {{"item_code": code, "price_list": "Standard Selling"}}, "price_list_rate"),
                    "published": frappe.db.get_value("Website Item", {{"item_code": code}}, "published")}}
print("ORIGINAL=" + json.dumps(before))
site = {{"astro": frappe.db.get_single_value("Astrology API Settings", "enabled"),
        "free_per_day": frappe.db.get_singles_dict("ServiceHQ Settings").get("free_reports_per_day"), "free_password": frappe.db.get_singles_dict("ServiceHQ Settings").get("free_report_password_required")}}
website = frappe.db.get_singles_dict("Website HQ Settings")
for name in ("auth_allow_new_accounts", "auth_mobile_stub", "auth_default_country_code", "auth_mobile_stub_code", "auth_otp_resend_seconds"):
    site[name] = website.get(name)
print("SITE=" + json.dumps(site))
for email, first, kind in (("{OTHER}", "Ravi", "Website User"), ("{STAFF}", "Staff", "System User")):
    frappe.get_doc({{"doctype": "User", "email": email, "first_name": first, "send_welcome_email": 0, "user_type": kind,
                    "roles": [{{"role": "Customer"}}] if email.startswith("book-") else []}}).insert(ignore_permissions=True)
staff = frappe.get_doc("User", "{STAFF}")
for role in ("Business Team", "WebHQ Office Manager", "Purchase Manager", "Stock Manager", "Sales Manager", "Accounts Manager"):
    if frappe.db.exists("Role", role): staff.append("roles", {{"role": role}})
staff.save(ignore_permissions=True)
''')
	ORIGINAL = json.loads(val(out, "ORIGINAL"))
	SITE = json.loads(val(out, "SITE"))
	assert all(v["price"] == 0 for v in ORIGINAL.values()), ("the reports are not free", ORIGINAL)  # switched on or off, as the owner has them: they are put back as they were
	run('''
for name, value in (("auth_allow_new_accounts", 1), ("auth_mobile_stub", 1), ("auth_default_country_code", "+91"), ("auth_mobile_stub_code", "12345678"), ("auth_otp_resend_seconds", 60)):
    frappe.db.set_single_value("Website HQ Settings", name, value)
frappe.db.delete("Singles", {"doctype": "ServiceHQ Settings", "field": ["in", ["free_reports_per_day", "free_report_password_required"]]})
''')
	conf = json.load(open("/home/ubuntu/dev-bench/sites/astrohq.local/site_config.json"))
	SITE["conf_stub"] = conf.get("allow_mobile_code_stub")
	if not conf.get("allow_mobile_code_stub"):
		import subprocess

		subprocess.run(["bench", "--site", "astrohq.local", "set-config", "allow_mobile_code_stub", "1"], cwd="/home/ubuntu/dev-bench", capture_output=True)
	run(f'''
for code in ("{KUNDLI}", "{MATCH}"):
    item = frappe.get_doc("Item", code); item.disabled = 0; item.save(ignore_permissions=True)
''')


def put_back():
	run(f'''
original = {ORIGINAL!r}
for code, was in original.items():
    frappe.db.set_value("Item Price", {{"item_code": code, "price_list": "Standard Selling"}}, "price_list_rate", was["price"])
    item = frappe.get_doc("Item", code); item.disabled = was["disabled"]; item.save(ignore_permissions=True)
site = {SITE!r}
for name in ("auth_allow_new_accounts", "auth_mobile_stub", "auth_default_country_code", "auth_mobile_stub_code", "auth_otp_resend_seconds"):
    if site.get(name) is None: frappe.db.delete("Singles", {{"doctype": "Website HQ Settings", "field": name}})
    else: frappe.db.set_single_value("Website HQ Settings", name, site[name])
for name, key in (("free_reports_per_day", "free_per_day"), ("free_report_password_required", "free_password")):
    frappe.db.delete("Singles", {{"doctype": "ServiceHQ Settings", "field": name}})
    if site.get(key) is not None: frappe.db.set_single_value("ServiceHQ Settings", name, site[key])
frappe.db.set_value("Astrology API Settings", None, "enabled", {1 if SITE.get("astro") in ("1", 1) else 0})
''')
	if not SITE.get("conf_stub"):
		import subprocess

		subprocess.run(["bench", "--site", "astrohq.local", "remove-config", "allow_mobile_code_stub"], cwd="/home/ubuntu/dev-bench", capture_output=True)


def setting(doctype, name, value):
	if value is None:
		run(f'frappe.db.delete("Singles", {{"doctype": "{doctype}", "field": "{name}"}})')
	else:
		run(f'frappe.db.set_single_value("{doctype}", "{name}", {value!r})')


def fill_person(pg, prefix, name, date, time, place):
	pg.fill(f"#rfhq-f-{prefix}name" if prefix else "#rfhq-f-report_name", name)
	pg.fill(f"#rfhq-f-{prefix}birth_date", date)
	pg.fill(f"#rfhq-f-{prefix}birth_time", time)
	pg.fill(f"#rfhq-f-{prefix}birth_place", place)


def scroll_all(pg):
	last = -1
	for _ in range(30):
		pg.mouse.wheel(0, 4000)
		pg.wait_for_timeout(500)
		height = pg.evaluate("document.body.scrollHeight")
		if height == last:
			break
		last = height


def sideways(pg) -> int:
	"""How far the page is wider than the phone (0 or less: nothing scrolls sideways)."""
	return pg.evaluate("document.documentElement.scrollWidth - innerWidth")


def press(pg, label=None):
	"""Presses the form's button and gives the page a moment."""
	pg.click("button[type=submit]")
	pg.wait_for_timeout(2200)
	return pg.inner_text("main")


def route_of(code):
	return val(run(f'print("ROUTE=" + (frappe.db.get_value("Website Item", {{"item_code": "{code}"}}, "route") or ""))'), "ROUTE")


def pdf_read(content: bytes) -> tuple[int, str]:
	"""(pages, the words) of a PDF, read with the bench's own Python (this script runs on the system's, which has no PDF reader)."""
	path = f"{J.OUT}/read-{uuid.uuid4().hex[:6]}.pdf"
	open(path, "wb").write(content)
	out = run(f'''
import json, re
from pypdf import PdfReader
reader = PdfReader("{path}")
print("PDF=" + json.dumps([len(reader.pages), re.sub(r"\\s+", " ", " ".join(page.extract_text() for page in reader.pages))]))
''')
	os.remove(path)
	pages, text = json.loads(val(out, "PDF"))
	return pages, text


def reports_of(mobile):
	"""[(name, state, tries, item)] of the Free Reports of the account with this number, oldest first."""
	out = run(f'''
import json
user = frappe.db.get_value("User", {{"mobile_no": "{mobile}"}}, "name")
rows = frappe.get_all("Free Report", filters={{"user": user or "-"}}, fields=["name", "workflow_state", "tries", "item"], order_by="creation asc")
print("ROWS=" + json.dumps([[r.name, r.workflow_state, r.tries, r.item] for r in rows]))
''')
	return json.loads(val(out, "ROWS"))


def open_file(ctx, pg, expect_pages=None, words=()):
	"""Opens the first View report link of the page and reads the PDF it gives."""
	href = pg.locator("a:has-text('View report')").first.get_attribute("href")
	answer = ctx.request.get(B + href)
	body = answer.body()
	pages, text = pdf_read(body) if body[:5] == b"%PDF-" else (0, "")
	return answer.status, body[:5], pages, text, href


def stranger_sees_drafts_hidden(br):
	"""While the reports are switched off nobody sees them; this runs first, so it is called before setup() switches them on (and only when they are off)."""
	ctx = J.context(br, state, "stranger", J.PHONE, None, mobile=True)
	pg = ctx.new_page()
	pg.goto(B + "/services", wait_until="networkidle")
	pg.wait_for_timeout(1500)
	scroll_all(pg)
	check("a switched-off free report is not in the shop", "Kundli report" not in pg.inner_text("body"))
	pg.goto(f"{B}/services/free-report?item={KUNDLI}", wait_until="networkidle")
	pg.wait_for_timeout(2000)
	body = pg.inner_text("main")
	check("its free page does not take anyone's details while it is off", "not available" in body.lower() and pg.locator("#rfhq-f-report_name").count() == 0, body[:200].replace("\n", " | "))
	snap(pg, "stranger", "The free page of a report that is switched off: not available")
	J.finish(state, "stranger", ctx, pg)


def visitor_gets_the_kundli(br):
	"""A stranger on a phone: from the product page to the report, in one sitting. Returns (the signed-in browser state, the report's name)."""
	ctx = J.context(br, state, "visitor", J.PHONE, None, mobile=True)
	pg = ctx.new_page()
	errors = []
	pg.on("pageerror", lambda e: errors.append(str(e)))
	pg.goto(B + "/services", wait_until="networkidle")
	pg.wait_for_timeout(2000)
	scroll_all(pg)
	body = pg.inner_text("body")
	check("both free reports are in the shop", "Kundli report" in body and "Match making report" in body, f"{len(body)} characters read")
	pg.locator("a:has-text('Kundli report')").first.evaluate("e => e.scrollIntoView({block: 'center'})")
	pg.wait_for_timeout(600)
	snap(pg, "visitor", "Services: the kundli report among the others")
	card = pg.evaluate("""() => { const a = [...document.querySelectorAll('a')].find(e => e.textContent.includes('Kundli report')); let n = a; for (let i = 0; i < 6 && n && n.parentElement; i++) { n = n.parentElement; if (n.querySelectorAll('a').length > 1 || n.className.includes('card')) break; } return n ? n.innerText : ''; }""")
	check("the shop's card says Free and leads to the free page, not to a cart", "free" in card.lower() and "get your free report" in card.lower() and "add to cart" not in card.lower(), card.replace("\n", " | "))
	button = pg.locator("a:has(div:text-is('Get your free report')), a:has-text('Get your free report')").first
	check("the card's button opens the report's free page", f"/services/free-report?item={KUNDLI}" in (button.get_attribute("href") or ""), button.get_attribute("href"))

	pg.goto(f"{B}/{route_of(KUNDLI)}", wait_until="networkidle")
	pg.wait_for_timeout(1800)
	body = pg.inner_text("body")
	check("the report's page says it is free and offers the free page, not a cart", "get your free report" in body.lower() and "add to cart" not in body.lower() and "free" in body.lower(), body[:200].replace("\n", " | "))
	check("what the person reads has no note meant for the team", "draft" not in body.lower() and "switch it on" not in body.lower() and "order is paid" not in body.lower(), body[:200].replace("\n", " | "))
	snap(pg, "visitor", "The kundli report's page: Get your free report")
	taps = 0
	pg.locator("a:has-text('Get your free report'), button:has-text('Get your free report')").first.click()
	pg.wait_for_selector("#rfhq-f-report_name")
	pg.wait_for_timeout(900)
	snap(pg, "visitor", "ONE page: whose it is, the details, the country and the mobile number", full=True)
	check("the app shell is on and nothing scrolls sideways on the free page", pg.evaluate("document.body.classList.contains('pwahq-active')") and sideways(pg) <= 0, sideways(pg))
	check("the page asks for whose it is, the four details, the country and the mobile number", all(pg.locator(f"#rfhq-f-{n}").count() == 1 for n in ("whose", "report_name", "birth_date", "birth_time", "birth_place", "country", "mobile")))
	check("whose it is starts at Me and the country at India (+91)", pg.eval_on_selector("#rfhq-f-whose", "e => e.options[e.selectedIndex].text") == "Me" and "India" in pg.eval_on_selector("#rfhq-f-country", "e => e.options[e.selectedIndex].text"),
		  (pg.eval_on_selector("#rfhq-f-whose", "e => e.value"), pg.eval_on_selector("#rfhq-f-country", "e => e.value")))
	body = pg.inner_text("main")
	check("the words beside the button say the details are kept, with the terms and privacy links", "birth profile" in body and pg.locator(".rfhq-form-consent a:has-text('Terms of Service')").count() == 1
		  and pg.locator(".rfhq-form-consent a:has-text('Privacy Policy')").count() == 1, pg.locator(".rfhq-form-consent").inner_text().replace("\n", " | "))
	check("the button says what it does: Send me the code", pg.locator("button[type=submit]:has-text('Send me the code')").count() == 1)

	body = press(pg)
	check("an empty page says what is missing, all at once", "required" in body.lower() and pg.locator(".rfhq-form-error:not([hidden])").count() >= 5, pg.locator(".rfhq-form-error:not([hidden])").count())
	snap(pg, "visitor", "Nothing filled in: what is missing", full=True)

	fill_person(pg, "", "आशा राव", "2999-01-01", "13:49", "Delhi")
	pg.fill("#rfhq-f-mobile", "12")
	body = press(pg)
	check("a name in another script, a future date and a short number are all said in plain words", "English letters" in body and "cannot be in the future" in body and "valid mobile number" in body, body[:500].replace("\n", " | "))
	snap(pg, "visitor", "Hindi name, a future date, a short number: all said in words", full=True)

	fill_person(pg, "", "Asha Rao", "1980-06-08", "13:49", "Sirsa")
	pg.fill("#rfhq-f-mobile", "98765 43210")
	body = press(pg)
	check("a town with several places of the name asks for the state", "More than one place is called Sirsa" in body and "Haryana" in body, body[:400].replace("\n", " | "))

	fill_person(pg, "", "Asha Rao", "1980-06-08", "13:49", "Delhi")
	pg.fill("#rfhq-f-mobile", "98765 43210")  # the country is India: this is +91 98765 43210 (a code is asked for it, no account is made until the right code is typed)
	body = press(pg)
	check("the page goes on to the code without leaving the page", pg.locator("#rfhq-f-code").count() == 1 and "/services/free-report" in pg.url, pg.url)
	check("the code step says where the code went (the last four digits of the number typed)", "3210" in body, body[:200].replace("\n", " | "))
	pg.reload(wait_until="networkidle")  # nothing was made: the person is back at the start; now the made-up number is used
	pg.wait_for_selector("#rfhq-f-report_name")
	pg.fill("#rfhq-f-report_name", "Asha Rao"); pg.fill("#rfhq-f-birth_date", "1980-06-08"); pg.fill("#rfhq-f-birth_time", "13:49"); pg.fill("#rfhq-f-birth_place", "Delhi")
	pg.fill("#rfhq-f-mobile", ASHA)
	body = press(pg)
	LAST_CODE["at"] = time.time()
	snap(pg, "visitor", "The code, on the same page", full=True)
	check("nothing scrolls sideways on the code step", sideways(pg) <= 0, sideways(pg))
	check("the code step has the code field, a Make my report button and a Send again that waits", pg.locator("#rfhq-f-code").count() == 1 and pg.locator("button[type=submit]:has-text('Make my report')").count() == 1
		  and pg.locator("button:has-text('Send again in')").count() == 1 and pg.locator("button:has-text('Send again in')").is_disabled(), body[:300].replace("\n", " | "))
	check("the code field takes the stub's 8 digits", pg.get_attribute("#rfhq-f-code", "maxlength") == "8")
	check("no account exists yet", frappe_value(f'frappe.db.exists("User", {{"mobile_no": "{ASHA}"}})') == "None")

	pg.fill("#rfhq-f-code", "00000000")
	body = press(pg)
	check("a wrong code is said with the tries left", "not right" in body and "4 tries" in body, body[:300].replace("\n", " | "))
	pg.fill("#rfhq-f-code", CODE)
	pg.click("button[type=submit]")
	pg.wait_for_selector("#rfhq-f-password", timeout=30000)
	pg.wait_for_timeout(600)
	body = pg.inner_text("main")
	snap(pg, "visitor", "The right code: the account exists and the report is made; a password, last", full=True)
	rows = reports_of(ASHA)
	check("the account exists and one Free Report is Ready", len(rows) == 1 and rows[0][1] == "Ready" and rows[0][2] == 1 and rows[0][3] == KUNDLI, rows)
	check("the password question has Show and Skip for now", "Choose a password" in body and pg.locator("button:has-text('Show')").count() == 1 and pg.locator("a:has-text('Skip for now')").count() == 1, body[:300].replace("\n", " | "))
	check("the account is called by the name given", frappe_value(f'frappe.db.get_value("User", {{"mobile_no": "{ASHA}"}}, "first_name")') == "Asha Rao")

	pg.fill("#rfhq-f-password", "short")
	pg.click("button[type=submit]")
	pg.wait_for_timeout(1800)
	body = pg.inner_text("main")
	check("a weak password is said in words on its field", pg.locator(".rfhq-form-error:not([hidden])").count() >= 1 and "password" in body.lower(), body[:300].replace("\n", " | "))
	pg.click("button:has-text('Show')")
	pg.fill("#rfhq-f-password", PASSWORD)
	check("Show makes the password readable", pg.get_attribute("#rfhq-f-password", "type") == "text")
	pg.click("button[type=submit]")
	pg.wait_for_url("**/my/report**", timeout=30000)
	pg.wait_for_timeout(2500)
	body = pg.inner_text("main")
	snap(pg, "visitor", "The report, and what to do next", full=True)
	check("nothing scrolls sideways on the report page", sideways(pg) <= 0, sideways(pg))
	check("the report page shows the report Ready for the person, with View report", "Kundli report" in body and "ready" in body.lower() and "For Asha Rao" in body and pg.locator("a:has-text('View report')").count() == 1, body[:300].replace("\n", " | "))
	lower = body.lower()
	check("what next offers the free first session, another report for family and the match making report", "ask about your report" in lower and "free first session" in lower and "talk free" in lower and "book free" in lower
		  and "another kundli report" in lower and "match making report" in lower, body[300:900].replace("\n", " | "))
	status, head, pages, text, href = open_file(ctx, pg)
	check("View report opens a PDF of two pages with the person's own chart", status == 200 and head == b"%PDF-" and pages == 2 and "Asha Rao" in text and "Virgo (Kanya)" in text and "Revati, pada 3" in text, (status, head, pages, text[:80]))
	check("no script errors on the way", errors == [], errors)
	report = reports_of(ASHA)[0][0]
	out = run(f'''
user = frappe.db.get_value("User", {{"mobile_no": "{ASHA}"}}, "name")
doc = frappe.get_doc("User", user)
print("PROFILES=%s" % [(r.relationship, r.full_name, str(r.date_of_birth), r.time_of_birth, r.place_of_birth, r.permission_given) for r in doc.astro_birth_profiles])
print("ORDERS=%s" % [frappe.db.count(d, {{"owner": user}}) for d in ("Sales Order", "Quotation", "Delivery Note", "Sales Invoice", "Payment Request")])
print("PROOF=%s" % frappe.db.count("Service Proof", {{"ref_doctype": "Free Report", "ref_name": "{report}"}}))
print("FILE=%s" % frappe.db.get_value("File", {{"attached_to_doctype": "Free Report", "attached_to_name": "{report}"}}, "is_private"))
''')
	check("the details became the person's own birth profile", val(out, "PROFILES") == "[('You', 'Asha Rao', '1980-06-08', '13:49', 'Delhi', 0)]", val(out, "PROFILES"))
	check("no cart, order, delivery note, invoice or payment request was made", val(out, "ORDERS") == "[0, 0, 0, 0, 0]", val(out, "ORDERS"))
	check("the file is private and has its proof", val(out, "FILE") == "1" and val(out, "PROOF") == "1", out.strip().replace("\n", " | "))
	pg.goto(B + "/my/sessions", wait_until="networkidle")
	pg.wait_for_timeout(3000)
	body = pg.inner_text("main")
	snap(pg, "visitor", "My sessions: the report among Poojas and reports", full=True)
	check("the report is among Poojas and reports, Ready", "Poojas and reports" in body and "Kundli report" in body and "ready" in body.lower(), body[:300].replace("\n", " | "))
	session = ctx.storage_state()
	J.finish(state, "visitor", ctx, pg)
	return session, report


def signs_back_in(br, first_session):
	"""Another day, another phone: the mobile number and the password. The first phone is still signed in, so the person is asked to switch. Returns the new browser state."""
	ctx = J.context(br, state, "returning", J.PHONE, None, mobile=True)
	pg = ctx.new_page()
	pg.goto(B + "/login", wait_until="networkidle")
	pg.wait_for_selector("#rfhq-auth-root:not([hidden])")
	pg.click("[data-key='password']")
	pg.wait_for_selector("#rfhq_auth_secret")
	snap(pg, "returning", "Sign in with a password: the mobile number and the password")
	check("the password tab asks for a mobile number or email and a password", pg.locator("#rfhq_auth_identifier").count() == 1 and pg.locator("#rfhq_auth_secret").count() == 1 and pg.locator("button:has-text('Forgot password?')").count() == 1)
	pg.fill("#rfhq_auth_identifier", ASHA)
	pg.fill("#rfhq_auth_secret", "not-the-password-1")
	pg.click("button:has-text('Sign in')")
	pg.wait_for_timeout(1800)
	body = pg.inner_text("main")
	check("a wrong password is refused with the tries left, not saying which part was wrong", "not right" in body and "4 tries" in body, body[:300].replace("\n", " | "))
	pg.click("button:has-text('Forgot password?')")
	pg.wait_for_selector("#rfhq_auth_identifier")
	check("forgot password starts with the mobile number, which is kept", pg.input_value("#rfhq_auth_identifier") == ASHA and "Reset your password" in pg.inner_text("main"), pg.inner_text("main")[:120])
	left = 62 - (time.time() - LAST_CODE["at"])  # a new code for a number can be asked for a minute after the last one
	if left > 0:
		pg.wait_for_timeout(int(left * 1000))
	pg.click("button.rfhq-auth__primary")
	pg.wait_for_selector(".rfhq-code__input")
	snap(pg, "returning", "Forgot the password: a code to the same number")
	pg.keyboard.type(CODE)
	pg.wait_for_selector("#rfhq_auth_secret", timeout=20000)
	body = pg.inner_text("main")
	check("with the code typed, the new password is asked for", "Choose a new password" in body and "At least 8" in body, body[:200].replace("\n", " | "))
	pg.fill("#rfhq_auth_secret", "short")
	pg.click("button[type=submit]")
	pg.wait_for_timeout(1500)
	check("a weak new password is refused in words and the code is not used up", pg.locator("#rfhq_auth_secret").count() == 1 and "at least" in pg.inner_text("main").lower(), pg.inner_text("main")[:200].replace("\n", " | "))
	pg.fill("#rfhq_auth_secret", NEW_PASSWORD)
	pg.click("button[type=submit]")
	pg.wait_for_selector("#rfhq_auth_identifier", timeout=20000)
	pg.wait_for_timeout(800)
	body = pg.inner_text("main")
	snap(pg, "returning", "The new password is saved: back at the password screen")
	check("the password is updated and the screen is the password sign-in again", "updated" in body.lower() and "Sign in with your password" in body, body[:200].replace("\n", " | "))
	pg.fill("#rfhq_auth_identifier", ASHA)
	pg.fill("#rfhq_auth_secret", PASSWORD)
	pg.click("button:has-text('Sign in')")
	pg.wait_for_timeout(1800)
	check("the old password no longer works", "not right" in pg.inner_text("main"), pg.inner_text("main")[:200].replace("\n", " | "))
	pg.fill("#rfhq_auth_secret", NEW_PASSWORD)
	pg.click("button:has-text('Sign in')")
	pg.wait_for_timeout(2200)
	body = pg.inner_text("main")
	snap(pg, "returning", "The new password, but the first phone is still signed in: asked to switch")
	check("the person is asked to switch device, as anyone signed in elsewhere is", "signed in on another device" in body and pg.locator("button:has-text('Switch to this device')").count() == 1, body[:300].replace("\n", " | "))
	pg.click("button:has-text('Switch to this device')")
	pg.wait_for_timeout(2500)
	if pg.locator("a:has-text('Skip for now'), button:has-text('Skip for now')").count():  # the quick PIN is offered to everyone without one
		pg.click("a:has-text('Skip for now'), button:has-text('Skip for now')")
	pg.wait_for_url(lambda u: "/login" not in u, timeout=20000)
	pg.wait_for_timeout(1500)
	pg.goto(B + "/my/sessions", wait_until="networkidle")
	pg.wait_for_timeout(2500)
	body = pg.inner_text("main")
	snap(pg, "returning", "Signed in again: the report is there", full=True)
	check("signed in again by the mobile number and the password, the report is in the list", "Kundli report" in body and "ready" in body.lower(), body[:200].replace("\n", " | "))
	old = br.new_context(storage_state=first_session)
	answer = old.request.get(B + "/api/method/frappe.auth.get_logged_user")
	check("the first phone was signed out by the switch", answer.status in (401, 403) or "Guest" in answer.text(), answer.status)
	old.close()
	session = ctx.storage_state()
	J.finish(state, "returning", ctx, pg)
	return session


def signed_in_asks_more(br, session):
	"""Signed in: the details only, no number and no code. A kundli for a child, a match, the form filled from the profile, and the limit."""
	ctx = J.context(br, state, "member", J.PHONE, session, mobile=True)
	pg = ctx.new_page()
	pg.goto(f"{B}/services/free-report?item={KUNDLI}", wait_until="networkidle")
	pg.wait_for_selector("#rfhq-f-report_name")
	pg.wait_for_timeout(1200)
	snap(pg, "member", "Signed in: no number and no code, the form is filled from their profile", full=True)
	check("signed in, there is no number and no code to give", pg.locator("#rfhq-f-mobile").count() == 0 and pg.locator("#rfhq-f-country").count() == 0 and pg.locator("button[type=submit]:has-text('Get my free report')").count() == 1)
	filled = [pg.input_value(f"#rfhq-f-{n}") for n in ("report_name", "birth_date", "birth_time", "birth_place", "whose")]
	check("the form is filled from the person's own profile", filled == ["Asha Rao", "1980-06-08", "13:49", "Delhi", "You"], filled)

	pg.select_option("#rfhq-f-whose", "Child")
	fill_person(pg, "", "Little Ravi", "2015-03-02", "06:15", "Pune, Maharashtra")
	pg.click("button[type=submit]")
	pg.wait_for_url("**/my/report**", timeout=40000)
	pg.wait_for_timeout(2500)
	body = pg.inner_text("main")
	snap(pg, "member", "A kundli for a child: made at once", full=True)
	check("a kundli for the child is made at once and says whose it is", "For Little Ravi" in body and "ready" in body.lower(), body[:300].replace("\n", " | "))
	status, head, pages, text, href = open_file(ctx, pg)
	check("it is the child's own chart", status == 200 and pages == 2 and "Little Ravi" in text, (status, pages, text[:60]))
	out = run(f'''
user = frappe.db.get_value("User", {{"mobile_no": "{ASHA}"}}, "name")
doc = frappe.get_doc("User", user)
print("PROFILES=%s" % sorted((r.relationship, r.full_name, r.permission_given) for r in doc.astro_birth_profiles))
print("NAME=" + doc.first_name)
''')
	check("the child is kept as a family profile with the person's confirmation, the account name is unchanged", val(out, "PROFILES") == "[('Child', 'Little Ravi', 1), ('You', 'Asha Rao', 0)]" and val(out, "NAME") == "Asha Rao", out.strip().replace("\n", " | "))

	pg.goto(f"{B}/{route_of(MATCH)}", wait_until="networkidle")
	pg.wait_for_timeout(1500)
	pg.locator("a:has-text('Get your free report'), button:has-text('Get your free report')").first.click()
	pg.wait_for_selector("#rfhq-f-boy_name")
	pg.wait_for_timeout(800)
	check("the match form asks for both people and nothing about whose it is", all(pg.locator(f"#rfhq-f-{p}{n}").count() == 1 for p in ("boy_", "girl_") for n in ("name", "birth_date", "birth_time", "birth_place")) and pg.locator("#rfhq-f-whose").count() == 0)
	fill_person(pg, "boy_", "Vikram Mehta", "1980-06-08", "13:49", "Delhi")
	fill_person(pg, "girl_", "Priya Shah", "1983-02-14", "09:30", "Mumbai")
	pg.click("button[type=submit]")
	pg.wait_for_url("**/my/report**", timeout=40000)
	pg.wait_for_timeout(2500)
	body = pg.inner_text("main")
	snap(pg, "member", "The match making report", full=True)
	check("the match report says who it is for and is Ready", "For Vikram Mehta and Priya Shah" in body and "ready" in body.lower(), body[:300].replace("\n", " | "))
	status, head, pages, text, href = open_file(ctx, pg)
	check("it is one page and scores out of 36", status == 200 and pages == 1 and "Vikram Mehta and Priya Shah" in text and "out of 36" in text, (status, pages, text[:80]))
	check("a match leaves no birth profile of its own", frappe_value(f'frappe.db.count("Astro Birth Profile", {{"parent": frappe.db.get_value("User", {{"mobile_no": "{ASHA}"}}, "name")}})') == "2")
	check("what next offers another match making report and the kundli", "Another match making report" in body and "Kundli report" in body, body[300:700].replace("\n", " | "))

	pg.goto(B + "/my/sessions", wait_until="networkidle")
	pg.wait_for_timeout(2500)
	body = pg.inner_text("main")
	snap(pg, "member", "Poojas and reports: three free reports", full=True)
	check("the three reports are in Poojas and reports, newest first", body.lower().count("ready") >= 3 and body.index("Match making report") < body.index("Kundli report"), body[:400].replace("\n", " | "))

	setting("ServiceHQ Settings", "free_reports_per_day", 3)
	try:
		pg.goto(f"{B}/services/free-report?item={KUNDLI}", wait_until="networkidle")
		pg.wait_for_selector("#rfhq-f-report_name")
		pg.wait_for_timeout(1000)
		pg.select_option("#rfhq-f-whose", "Other")
		fill_person(pg, "", "One Too Many", "2000-01-01", "10:00", "Delhi")
		body = press(pg)
		snap(pg, "member", "The safety limit: said in words", full=True)
		check("the safety limit is said in words and nothing is made", "3 reports" in body and "tomorrow" in body and len(reports_of(ASHA)) == 3, body[:300].replace("\n", " | "))
	finally:
		setting("ServiceHQ Settings", "free_reports_per_day", None)
	session = ctx.storage_state()
	J.finish(state, "member", ctx, pg)
	return session


def strangers_cannot_open(br, other_session, report):
	"""Another customer, and somebody not signed in, are not given the first person's report or its file."""
	proof = frappe_value(f'frappe.db.get_value("Service Proof", {{"ref_doctype": "Free Report", "ref_name": "{report}"}}, "name")')
	ctx = J.context(br, state, "other", J.PHONE, other_session, mobile=True)
	pg = ctx.new_page()
	answer = ctx.request.get(f"{B}/api/method/raftor_servicehq.proof.view?proof={proof}", max_redirects=0)
	check("another customer is refused the file", answer.status in (401, 403, 404) or "login" in answer.headers.get("location", ""), answer.status)
	pg.goto(f"{B}/my/report?report={report}", wait_until="networkidle")
	pg.wait_for_timeout(2500)
	body = pg.inner_text("body")
	snap(pg, "other", "Another customer asks for the first person's report page")
	check("another customer does not see the report, its owner's name or its file", "Asha Rao" not in body and "View report" not in body, body[:200].replace("\n", " | "))
	J.finish(state, "other", ctx, pg)
	ctx = br.new_context()
	answer = ctx.request.get(f"{B}/api/method/raftor_servicehq.proof.view?proof={proof}", max_redirects=0)
	check("somebody not signed in is refused the file", answer.status in (401, 403, 404) or "login" in answer.headers.get("location", ""), answer.status)
	ctx.close()


def a_password_that_is_a_must(br):
	"""With the setting on, the password has no Skip, and the report stays closed until it is chosen."""
	setting("ServiceHQ Settings", "free_report_password_required", 1)
	try:
		ctx = J.context(br, state, "visitor2", J.PHONE, None, mobile=True)
		pg = ctx.new_page()
		pg.goto(f"{B}/services/free-report?item={KUNDLI}", wait_until="networkidle")
		pg.wait_for_selector("#rfhq-f-report_name")
		pg.wait_for_timeout(900)
		fill_person(pg, "", "Meera Iyer", "1992-03-21", "06:42", "Pune, Maharashtra")
		pg.fill("#rfhq-f-mobile", MEERA)
		press(pg)
		pg.fill("#rfhq-f-code", CODE)
		pg.click("button[type=submit]")
		pg.wait_for_selector("#rfhq-f-password", timeout=30000)
		pg.wait_for_timeout(500)
		snap(pg, "visitor2", "The password is a must: no Skip for now", full=True)
		check("the password step has no Skip for now when it is a must", pg.locator("a:has-text('Skip for now')").count() == 0)
		report = reports_of(MEERA)[0][0]
		pg.goto(f"{B}/my/report?report={report}", wait_until="networkidle")
		pg.wait_for_timeout(2500)
		body = pg.inner_text("main")
		snap(pg, "visitor2", "Going to the report without the password: the question, and no View report", full=True)
		check("the report page asks for the password and gives no way to the file until it is chosen", pg.locator("#rfhq-f-password").count() == 1 and pg.locator("a:has-text('View report')").count() == 0, body[:300].replace("\n", " | "))
		proof = frappe_value(f'frappe.db.get_value("Service Proof", {{"ref_doctype": "Free Report", "ref_name": "{report}"}}, "name")')
		answer = ctx.request.get(f"{B}/api/method/raftor_servicehq.proof.view?proof={proof}", max_redirects=0)
		check("the file itself is refused to the owner until the password is chosen", answer.status in (401, 403, 404), answer.status)
		pg.fill("#rfhq-f-password", PASSWORD)
		pg.click("button[type=submit]")
		pg.wait_for_timeout(3000)
		pg.goto(f"{B}/my/report?report={report}", wait_until="networkidle")
		pg.wait_for_timeout(2500)
		body = pg.inner_text("main")
		snap(pg, "visitor2", "After choosing the password: View report", full=True)
		check("once the password is chosen the report opens", pg.locator("a:has-text('View report')").count() == 1 and pg.locator("#rfhq-f-password").count() == 0, body[:300].replace("\n", " | "))
		status, head, pages, text, href = open_file(ctx, pg)
		check("and its file is the person's own", status == 200 and head == b"%PDF-" and "Meera Iyer" in text, (status, head, text[:60]))
		J.finish(state, "visitor2", ctx, pg)
	finally:
		setting("ServiceHQ Settings", "free_report_password_required", None)


def a_report_that_cannot_be_made(br, member_session, staff_session):
	"""The astrology service is off for a moment, the person asks, the team is told and makes it later."""
	run('frappe.db.set_value("Astrology API Settings", None, "enabled", 0)')
	try:
		ctx = J.context(br, state, "member", J.PHONE, member_session, mobile=True)
		pg = ctx.new_page()
		pg.goto(f"{B}/services/free-report?item={KUNDLI}", wait_until="networkidle")
		pg.wait_for_selector("#rfhq-f-report_name")
		pg.wait_for_timeout(1000)
		pg.select_option("#rfhq-f-whose", "Sibling")
		fill_person(pg, "", "Kabir Rao", "1984-09-12", "21:10", "Delhi")
		pg.click("button[type=submit]")
		pg.wait_for_url("**/my/report**", timeout=40000)
		pg.wait_for_timeout(2500)
		body = pg.inner_text("main")
		snap(pg, "member", "The service is off: the report is Being made, in plain words", full=True)
		report = pg.url.split("report=")[1].split("&")[0]
		check("the person is told it is being made and shown no technical reason", "being made" in body.lower() and "a little longer" in body and "switched off" not in body and pg.locator("a:has-text('View report')").count() == 0, body[:300].replace("\n", " | "))
		J.finish(state, "member", ctx, pg)
		run(f'''
from frappe.utils import add_to_date, now_datetime
frappe.db.set_value("Free Report", "{report}", "creation", add_to_date(now_datetime(), minutes=-30))
''')
		ctx = J.context(br, state, "staff", J.DESK, staff_session)
		pg = ctx.new_page()
		pg.goto(B + "/team/attention", wait_until="networkidle")
		pg.wait_for_timeout(3500)
		body = pg.inner_text("main")
		snap(pg, "staff", "Needs attention: a free report that could not be made, with the reason", full=True)
		check("the team's list shows the free report with why", "free, not made" in body.lower() and "Kundli report" in body and report in body and "Charts are switched off" in body, body[:500].replace("\n", " | "))
		check("it offers Try again now", pg.locator("button:has-text('Try again now'), a:has-text('Try again now')").count() == 1)
		with pg.expect_response(lambda r: "make_free_report" in r.url, timeout=60000):
			pg.locator("button:has-text('Try again now'), a:has-text('Try again now')").first.click()
		pg.wait_for_timeout(1500)
		body = pg.inner_text("body")
		snap(pg, "staff", "Try again now while the service is still off: it says why", full=True)
		check("trying while it is still off says why and makes nothing", "Charts are switched off" in body and frappe_value(f'frappe.db.get_value("Free Report", "{report}", "workflow_state")') == "Being made", body[:300].replace("\n", " | "))
		run('frappe.db.set_value("Astrology API Settings", None, "enabled", 1)')
		pg.reload(wait_until="networkidle")
		pg.wait_for_timeout(3500)
		with pg.expect_response(lambda r: "make_free_report" in r.url, timeout=90000):
			pg.locator("button:has-text('Try again now'), a:has-text('Try again now')").first.click()
		pg.wait_for_timeout(1500)
		pg.reload(wait_until="networkidle")
		pg.wait_for_timeout(3000)
		body = pg.inner_text("main")
		snap(pg, "staff", "After trying again with the service back: the list is clear", full=True)
		check("the report is made", frappe_value(f'frappe.db.get_value("Free Report", "{report}", "workflow_state")') == "Ready")
		check("and gone from the list", report not in body, body[:200].replace("\n", " | "))
		J.finish(state, "staff", ctx, pg)
		ctx = J.context(br, state, "member", J.PHONE, member_session, mobile=True)
		pg = ctx.new_page()
		pg.goto(f"{B}/my/report?report={report}", wait_until="networkidle")
		pg.wait_for_timeout(2500)
		body = pg.inner_text("main")
		snap(pg, "member", "The person's page after the team made it: Ready", full=True)
		check("the person's report is now Ready with View report", "ready" in body.lower() and pg.locator("a:has-text('View report')").count() == 1, body[:200].replace("\n", " | "))
		J.finish(state, "member", ctx, pg)
	finally:
		run(f'frappe.db.set_value("Astrology API Settings", None, "enabled", {1 if SITE.get("astro") in ("1", 1) else 0})')


PURGE = '''
from raftor_servicehq.tests.purge import purge
print(purge())
'''


def main():
	run(PURGE)  # what earlier test runs left is cleared first, so the count before is the site's own
	before = counts()
	started = False
	try:
		with sync_playwright() as p:
			br = p.chromium.launch(slow_mo=120)
			if frappe_value(f'frappe.db.count("Item", {{"name": ["in", ["{KUNDLI}", "{MATCH}"]], "disabled": 1}})') == "2":  # while they are switched off nobody sees them
				stranger_sees_drafts_hidden(br)
			setup()
			started = True
			other_session = J.session(br, OTHER)
			staff_session = J.staff_login(br, STAFF)
			first_session, report = visitor_gets_the_kundli(br)
			session = signs_back_in(br, first_session)
			session = signed_in_asks_more(br, session)
			strangers_cannot_open(br, other_session, report)
			a_password_that_is_a_must(br)
			a_report_that_cannot_be_made(br, session, staff_session)
			br.close()
	except BaseException:
		import traceback

		traceback.print_exc()  # shown before the clean-up below, which must not hide it
		check("the journey ran to its end", False, traceback.format_exc().strip().splitlines()[-1])
	finally:
		if started:
			put_back()
		run(PURGE)
		mine = run(f'''
import json
left = {{}}
left["users"] = frappe.db.count("User", {{"name": ["like", "9100000%@mobile.invalid"]}}) + frappe.db.count("User", {{"name": ["in", ["{OTHER}", "{STAFF}"]]}})
left["free reports"] = frappe.db.count("Free Report")
left["proofs of free reports"] = frappe.db.count("Service Proof", {{"ref_doctype": "Free Report"}})
left["files of free reports"] = frappe.db.count("File", {{"attached_to_doctype": "Free Report"}})
left["customers by number"] = frappe.db.count("Customer", {{"email_id": ["like", "9100000%@mobile.invalid"]}})
left["contacts by number"] = len(frappe.db.sql("select name from `tabContact Email` where email_id like %s", ("9100000%@mobile.invalid",)))
print("LEFT=" + json.dumps({{k: v for k, v in left.items() if v}}))
''')
		check("nothing of this run is left behind: no person, customer, contact, report, proof or file", json.loads(val(mine, "LEFT")) == {}, val(mine, "LEFT"))
		after = counts()
		moved = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
		print("COUNTS THAT MOVED (other people use this site too):", moved)
		if started:
			now = json.loads(val(run(f'''
import json
print("NOW=" + json.dumps({{code: {{"disabled": frappe.db.get_value("Item", code, "disabled"), "price": frappe.db.get_value("Item Price", {{"item_code": code, "price_list": "Standard Selling"}}, "price_list_rate"),
                                    "published": frappe.db.get_value("Website Item", {{"item_code": code}}, "published")}} for code in ("{KUNDLI}", "{MATCH}")}}))
'''), "NOW"))
			check("the two reports are back as they were (switched on or off), still free", now == ORIGINAL, (now, ORIGINAL))
			settings_now = json.loads(val(run('''
import json
website = frappe.db.get_singles_dict("Website HQ Settings")
print("S=" + json.dumps({k: website.get(k) for k in ("auth_allow_new_accounts", "auth_mobile_stub", "auth_default_country_code", "auth_mobile_stub_code", "auth_otp_resend_seconds")}))
'''), "S"))
			check("the site's sign-in settings are as they were", all(settings_now[k] == SITE[k] for k in settings_now), (settings_now, {k: SITE[k] for k in settings_now}))
			check("the free report settings are as they were", frappe_value('frappe.db.get_singles_dict("ServiceHQ Settings").get("free_reports_per_day")') == str(SITE["free_per_day"])
				  and frappe_value('frappe.db.get_singles_dict("ServiceHQ Settings").get("free_report_password_required")') == str(SITE["free_password"]), SITE)
			check("the astrology setting is as it was", frappe_value('frappe.db.get_single_value("Astrology API Settings", "enabled")') == str(SITE.get("astro")), SITE.get("astro"))
	videos = J.join_segments(state)
	J.save(state)
	print("REVIEW", J.review_page(state, videos))
	failed = [s for s in state["steps"] if not s["ok"]]
	print(f"{len(state['steps']) - len(failed)} of {len(state['steps'])} checks passed")
	sys.exit(1 if failed else 0)


if __name__ == "__main__":
	main()
