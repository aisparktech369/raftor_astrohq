"""The kundli report and the match making report, bought and received in a browser the PAID way (the cart, the order, the payment), as each person sees it. They are free as they ship, so the run
prices them for itself; the free way (no order at all) is free_reports_journey.py:

    stranger  (nobody signed in) cannot see the reports while they are drafts, and cannot open anyone's file
    customer  on a phone: finds both reports, gives the birth details (with the form saying plainly what is wrong), puts both in the cart, pays, and opens each PDF
    staff     in the team's pages: a paid report the astrology service could not make is listed with why; "Try again now" makes it once the service is back
    other     a second customer cannot open the first one's order or files

It uses the astrology service and the list of places on this computer (the real ones). The payment leg is stood in for: the order is placed in the browser and handed to the
gateway's page (Razorpay's checkout), and then the system step the gateway's confirmation runs (the Payment Request is told it was paid) is run, because the confirmation
reaches this computer by a webhook from outside. The two report items ship switched off and free; the run switches them on at test prices and puts them back exactly as they were.
Run: JOURNEY=reports_journey python3 reports_journey.py"""
import json
import os
import sys
import uuid

os.environ.setdefault("JOURNEY", "reports_journey")
os.environ.setdefault("JOURNEY_TITLE", "The kundli and the match making report")
sys.path.insert(0, "/home/ubuntu/dev-bench/apps/raftor_servicehq/e2e")
from playwright.sync_api import sync_playwright  # noqa: E402

import journey_lib as J  # noqa: E402
from shop_e2e import B, run, val  # noqa: E402

T = uuid.uuid4().hex[:5]
BUYER, OTHER, STAFF = f"book-{T}a@example.com", f"book-{T}b@example.com", f"staff-{T}@example.com"
KUNDLI, MATCH = "ASTROHQ-REPORT-KUNDLI", "ASTROHQ-REPORT-MATCH"
PRICES = {KUNDLI: 99, MATCH: 149}
state = {"shots": [], "steps": [], "segments": {}}
ORIGINAL = {}


def check(name, ok, extra=""):
	return J.check(state, name, ok, extra)


def snap(pg, role, caption, full=False):
	return J.snap(state, pg, role, caption, full=full)


def counts() -> dict:
	out = run('''
for doctype, filters in (("User", {}), ("Customer", {}), ("Sales Order", {}), ("Payment Entry", {}), ("Delivery Note", {}), ("Sales Invoice", {}), ("Service Proof", {}), ("Address", {}), ("Quotation", {}),
						 ("File", {"attached_to_doctype": "Sales Order"}), ("Item", {}), ("Website Item", {"published": 1}), ("Item Price", {}), ("Comment", {"reference_doctype": ["in", ["Sales Order", "Item"]]}), ("Error Log", {}),
						 ("Contact", {}), ("Payment Request", {}), ("Payment", {}), ("Email Queue", {}), ("Integration Request", {})):
    print("%s=%s" % (doctype.replace(" ", "_"), frappe.db.count(doctype, filters)))
''')
	return {line.split("=")[0]: int(line.split("=")[1]) for line in out.split() if "=" in line}


def setup():
	"""Off camera: the people, and the two reports switched on at test prices (what they were is kept to put back)."""
	global ORIGINAL
	out = run(f'''
import json
before = {{}}
for code in ("{KUNDLI}", "{MATCH}"):
    before[code] = {{"disabled": frappe.db.get_value("Item", code, "disabled"), "price": frappe.db.get_value("Item Price", {{"item_code": code, "price_list": "Standard Selling"}}, "price_list_rate"),
                    "published": frappe.db.get_value("Website Item", {{"item_code": code}}, "published")}}
print("ORIGINAL=" + json.dumps(before))
print("ASTRO=" + str(frappe.db.get_single_value("Astrology API Settings", "enabled")))
for email, first, kind in (("{BUYER}", "Asha", "Website User"), ("{OTHER}", "Ravi", "Website User"), ("{STAFF}", "Staff", "System User")):
    frappe.get_doc({{"doctype": "User", "email": email, "first_name": first, "send_welcome_email": 0, "user_type": kind,
                    "roles": [{{"role": "Customer"}}] if email.startswith("book-") else []}}).insert(ignore_permissions=True)
staff = frappe.get_doc("User", "{STAFF}")
for role in ("Business Team", "WebHQ Office Manager", "Purchase Manager", "Stock Manager", "Sales Manager", "Accounts Manager"):
    if frappe.db.exists("Role", role): staff.append("roles", {{"role": role}})
staff.save(ignore_permissions=True)
''')
	ORIGINAL = json.loads(val(out, "ORIGINAL"))
	state["astro_was"] = val(out, "ASTRO")
	assert all(v["disabled"] == 1 and v["published"] == 0 for v in ORIGINAL.values()), ("the reports are not in their shipped (draft) state", ORIGINAL)


def switch_on():
	run(f'''
for code, price in {PRICES!r}.items():
    frappe.db.set_value("Item Price", {{"item_code": code, "price_list": "Standard Selling"}}, "price_list_rate", price)
    item = frappe.get_doc("Item", code); item.disabled = 0; item.save(ignore_permissions=True)
''')


def put_back():
	run(f'''
original = {ORIGINAL!r}
for code, was in original.items():
    frappe.db.set_value("Item Price", {{"item_code": code, "price_list": "Standard Selling"}}, "price_list_rate", was["price"])
    item = frappe.get_doc("Item", code); item.disabled = was["disabled"]; item.save(ignore_permissions=True)
''')


def fill_person(pg, prefix, name, date, time, place):
	pg.fill(f"#rfhq-f-{prefix}name" if prefix else "#rfhq-f-report_name", name)
	pg.fill(f"#rfhq-f-{prefix}birth_date", date)
	pg.fill(f"#rfhq-f-{prefix}birth_time", time)
	pg.fill(f"#rfhq-f-{prefix}birth_place", place)


def scroll_all(pg):
	"""The shop loads more of its list as it is scrolled: go down until nothing more comes."""
	last = -1
	for _ in range(30):
		pg.mouse.wheel(0, 4000)
		pg.wait_for_timeout(500)
		height = pg.evaluate("document.body.scrollHeight")
		if height == last:
			break
		last = height


def submit_and_read(pg):
	pg.click("button[type=submit]")
	pg.wait_for_timeout(2500)
	return pg.inner_text("main")


def stranger_sees_drafts_hidden(br):
	"""Nobody signed in, before the reports are switched on: neither is in the shop, and the reports are not found by name."""
	ctx = J.context(br, state, "stranger", J.PHONE, None, mobile=True)
	pg = ctx.new_page()
	pg.goto(B + "/services", wait_until="networkidle")
	pg.wait_for_timeout(1500)
	scroll_all(pg)
	body = pg.inner_text("body")
	check("a draft report is not in the shop", "Kundli report" not in body and "Match making report" not in body, f"{len(body)} characters read")
	snap(pg, "stranger", "Services before the reports are switched on: no report in the list")
	pg.goto(B + "/services?search=Kundli", wait_until="networkidle")
	pg.wait_for_timeout(1500)
	scroll_all(pg)
	check("a search does not find a draft report", "Kundli report" not in pg.inner_text("body"))
	pg.goto(B + "/services/kundli-report", wait_until="networkidle")
	check("a draft report has no page of its own", "Kundli report" not in pg.inner_text("body"))
	J.finish(state, "stranger", ctx, pg)


def route_of(code):
	return val(run(f'print("ROUTE=" + (frappe.db.get_value("Website Item", {{"item_code": "{code}"}}, "route") or ""))'), "ROUTE")


def customer_orders(br, desktop_session):
	"""The customer on a phone: both reports, the details with every mistake said in words, the cart. Returns the order name after paying on a desktop."""
	ctx = J.context(br, state, "customer", J.PHONE, desktop_session, mobile=True)
	pg = ctx.new_page()
	errors = []
	pg.on("pageerror", lambda e: errors.append(str(e)))
	pg.goto(B + "/services", wait_until="networkidle")
	pg.wait_for_timeout(2000)
	scroll_all(pg)
	body = pg.inner_text("body")
	check("both reports are in the shop", "Kundli report" in body and "Match making report" in body, f"{len(body)} characters read")
	pg.locator("a:has-text('Kundli report')").first.evaluate("e => e.scrollIntoView({block: 'center'})")
	pg.wait_for_timeout(600)
	snap(pg, "customer", "Services: the kundli report among the others")

	# the kundli report
	pg.goto(f"{B}/{route_of(KUNDLI)}", wait_until="networkidle")
	pg.wait_for_timeout(1800)
	body = pg.inner_text("body")
	check("the kundli page shows its price and asks for the details, not for a cart", "get your report" in body.lower() and "add to cart" not in body.lower() and "99.00" in body, body[:160].replace("\n", " | "))
	check("what the customer reads has no note meant for the team", "draft" not in body.lower() and "switch it on" not in body.lower(), body[:160].replace("\n", " | "))
	snap(pg, "customer", "The kundli report's page: Get your report")
	pg.locator("a:has-text('Get your report'), button:has-text('Get your report')").first.click()
	pg.wait_for_selector("#rfhq-f-report_name")
	pg.wait_for_timeout(900)
	snap(pg, "customer", "The details: name, day, time and place of birth", full=True)
	check("the form asks for the name, date, time and place", all(pg.locator(f"#rfhq-f-{n}").count() == 1 for n in ("report_name", "birth_date", "birth_time", "birth_place")))

	body = submit_and_read(pg)
	check("an empty form says what is missing", "required" in body.lower(), body[:300].replace("\n", " | "))
	snap(pg, "customer", "Nothing filled in: what is missing", full=True)

	fill_person(pg, "", "आशा राव", "2999-01-01", "13:49", "Delhi")
	body = submit_and_read(pg)
	check("a name in another script is refused in plain words", "English letters" in body, body[:400].replace("\n", " | "))
	check("a birth in the future is refused", "cannot be in the future" in body, body[:400].replace("\n", " | "))
	snap(pg, "customer", "Hindi name and a future date: both said in words", full=True)

	fill_person(pg, "", "Asha Rao", "1980-06-08", "13:49", "Sirsa")
	body = submit_and_read(pg)
	check("a town with several places of the name asks for the state", "More than one place is called Sirsa" in body and "Haryana" in body, body[:500].replace("\n", " | "))
	snap(pg, "customer", "Sirsa: the places of that name, ask for the state", full=True)

	fill_person(pg, "", "Asha Rao", "1980-06-08", "13:49", "Nowhereville")
	body = submit_and_read(pg)
	check("a place that is not found is said in words", "could not find Nowhereville" in body, body[:400].replace("\n", " | "))

	fill_person(pg, "", "Asha Rao", "1980-06-08", "13:49", "Delhi")
	pg.click("button[type=submit]")
	pg.wait_for_url("**/cart", timeout=30000)
	pg.wait_for_timeout(2500)
	body = pg.inner_text("body")
	check("the kundli report is in the cart at 99", "Kundli report" in body and "99.00" in body, body[:200].replace("\n", " | "))
	snap(pg, "customer", "The cart: the kundli report", full=True)

	# the match making report
	pg.goto(f"{B}/{route_of(MATCH)}", wait_until="networkidle")
	pg.wait_for_timeout(1500)
	pg.locator("a:has-text('Get your report'), button:has-text('Get your report')").first.click()
	pg.wait_for_selector("#rfhq-f-boy_name")
	pg.wait_for_timeout(900)
	snap(pg, "customer", "The match making details: the boy and the girl", full=True)
	check("the match form asks for both people", all(pg.locator(f"#rfhq-f-{p}{n}").count() == 1 for p in ("boy_", "girl_") for n in ("name", "birth_date", "birth_time", "birth_place")))
	fill_person(pg, "boy_", "Vikram Mehta", "1980-06-08", "13:49", "Delhi")
	fill_person(pg, "girl_", "Priya Shah", "1983-02-14", "09:30", "Mumbai")
	pg.click("button[type=submit]")
	pg.wait_for_url("**/cart", timeout=30000)
	pg.wait_for_timeout(2500)
	body = pg.inner_text("body")
	check("both reports are in the cart: 99 and 149", "Kundli report" in body and "Match making report" in body and "99.00" in body and "149.00" in body and "248.00" in body, body[:300].replace("\n", " | "))
	snap(pg, "customer", "The cart: both reports, 248 in all", full=True)
	check("no script errors on the way", errors == [], errors)
	J.finish(state, "customer", ctx, pg)


def pay_on_desktop(br, session):
	"""The same customer, on a desktop: Place Order hands the order to the gateway's page; the gateway's confirmation is stood in for (see the top of this file)."""
	ctx = J.context(br, state, "customerpay", {"width": 1100, "height": 900}, session)
	pg = ctx.new_page()
	pg.goto(B + "/cart", wait_until="networkidle")
	pg.wait_for_timeout(2000)
	pg.click("button:has-text('Place Order')")
	pg.wait_for_url("**razorpay_checkout**", timeout=30000)
	pg.wait_for_timeout(2000)
	check("Place Order hands the order to the payment page", "razorpay_checkout" in pg.url, pg.url[:80])
	snap(pg, "customerpay", "Place Order: the gateway's payment page (Razorpay)")
	out = run(f'''
so = frappe.db.get_value("Sales Order", {{"owner": "{BUYER}"}}, ["name", "docstatus"], as_dict=True, order_by="creation desc")
pr = frappe.db.get_value("Payment Request", {{"reference_name": so.name}}, "name")
print("SO=" + so.name); print("DOCSTATUS=%s" % so.docstatus); print("PR=" + (pr or ""))
frappe.get_doc("Payment Request", pr).run_method("on_payment_authorized", "Completed")
print("AFTER=%s" % frappe.db.get_value("Sales Order", so.name, "per_delivered"))
''')
	so = val(out, "SO")
	check("the order waits as a draft until the payment is confirmed", val(out, "DOCSTATUS") == "0" and bool(val(out, "PR")), out[-200:])
	check("once the payment is confirmed both reports are made and the order is delivered", float(val(out, "AFTER") or 0) == 100, out[-200:])
	pg.goto(f"{B}/orders/{so}", wait_until="networkidle")
	pg.wait_for_timeout(3000)
	body = pg.inner_text("main")
	snap(pg, "customerpay", "The order page after paying", full=True)
	check("the order page says it is delivered in full", "100%" in body, body[:300].replace("\n", " | "))
	J.finish(state, "customerpay", ctx, pg)
	return so


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


def receive(br, session, so):
	"""The customer's own pages: Poojas and reports says Ready with one file for each report, and each file is the real PDF."""
	ctx = J.context(br, state, "customer", J.PHONE, session, mobile=True)
	pg = ctx.new_page()
	pg.goto(B + "/my/sessions", wait_until="networkidle")
	pg.wait_for_timeout(3000)
	body = pg.inner_text("main")
	snap(pg, "customer", "My sessions: both reports Ready, each with its own View report", full=True)
	check("both reports say Ready", body.lower().count("ready") >= 2, body[:300].replace("\n", " | "))
	links = pg.locator("a:has-text('View report')")
	check("each report has its own View report", links.count() == 2, links.count())
	files = []
	for i in range(links.count()):
		answer = ctx.request.get(B + links.nth(i).get_attribute("href"))
		files.append((answer.status, answer.body()[:5], answer.headers.get("content-disposition", ""), answer.body()))
	check("each file opens as a PDF for the customer", all(f[0] == 200 and f[1] == b"%PDF-" for f in files), [(f[0], f[1], f[2]) for f in files])
	pdf_texts = [pdf_read(body_bytes) for _status, _head, _disp, body_bytes in files]
	kundli = next((t for n, t in pdf_texts if "Kundli report" in t), "")
	match = next((t for n, t in pdf_texts if "Match making report" in t), "")
	pages = {("Kundli report" in t): n for n, t in pdf_texts}
	check("the kundli is two pages with the customer's own chart", "Asha Rao" in kundli and "Virgo (Kanya)" in kundli and "Revati, pada 3" in kundli and pages.get(True) == 2, (len(kundli), pages))
	check("the match making report is one page", pages.get(False) == 1, pages)
	check("the match making report names the two and scores out of 36", "Vikram Mehta and Priya Shah" in match and "out of 36" in match and "Ashtakoota" in match, match[:200])
	for n, (_status, _head, disposition, _bytes) in enumerate(files):
		check(f"file {n + 1} has a plain name", "report" in disposition and ".pdf" in disposition, disposition)
	J.finish(state, "customer", ctx, pg)
	return [f[3] for f in files]


def strangers_cannot_open(br, other_session, so, guest_files=True):
	"""Another customer, and somebody not signed in, are not given the first customer's order or files."""
	proofs = run(f'print("PROOFS=" + ",".join(frappe.get_all("Service Proof", filters={{"ref_doctype": "Sales Order", "ref_name": "{so}"}}, pluck="name")))')
	names = [n for n in val(proofs, "PROOFS").split(",") if n]
	ctx = J.context(br, state, "other", J.PHONE, other_session, mobile=True)
	pg = ctx.new_page()
	answers = [ctx.request.get(f"{B}/api/method/raftor_servicehq.proof.view?proof={n}", max_redirects=0) for n in names]
	check("another customer is refused each file", names and all(a.status in (401, 403, 404) or "login" in a.headers.get("location", "") for a in answers), [a.status for a in answers])
	pg.goto(f"{B}/orders/{so}", wait_until="networkidle")
	pg.wait_for_timeout(2000)
	body = pg.inner_text("body")
	snap(pg, "other", "Another customer asks for the first customer's order")
	check("another customer does not see the first one's order", "Asha Rao" not in body and "kundli-report" not in body.lower() and "100%" not in body, body[:200].replace("\n", " | "))
	J.finish(state, "other", ctx, pg)
	ctx = br.new_context()
	answers = [ctx.request.get(f"{B}/api/method/raftor_servicehq.proof.view?proof={n}", max_redirects=0) for n in names]
	check("somebody not signed in is refused each file", all(a.status in (401, 403, 404) or "login" in a.headers.get("location", "") for a in answers), [a.status for a in answers])
	ctx.close()


def a_report_that_cannot_be_made(br, buyer_session, staff_session):
	"""The astrology service is switched off for a moment (the setting, as the owner would), a customer buys a kundli, and the team is told and makes it later."""
	run('frappe.db.set_value("Astrology API Settings", None, "enabled", 0)')
	try:
		out = run(f'''
frappe.set_user("{BUYER}")
from raftor_servicehq import personalised
from webshop.webshop.shopping_cart.cart import _get_cart_quotation, place_order
personalised.add_to_cart("{KUNDLI}", {{"report_name": "Meera Iyer", "birth_date": "1992-03-21", "birth_time": "06:42", "birth_place": "Pune, Maharashtra"}})
q = _get_cart_quotation()
address = frappe.db.get_value("Address", {{"owner": "{BUYER}"}}, "name") or frappe.get_doc({{"doctype": "Address", "address_title": "{BUYER}", "address_line1": "1 Test Road", "city": "Pune", "country": "India",
                                                                                           "links": [{{"link_doctype": "Customer", "link_name": q.party_name}}]}}).insert(ignore_permissions=True).name
frappe.db.set_value("Quotation", q.name, {{"customer_address": address, "shipping_address_name": address}})
so = place_order()
frappe.set_user("Administrator")
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
pe = get_payment_entry("Sales Order", so); pe.reference_no, pe.reference_date = "E2E", frappe.utils.today(); pe.insert(); pe.submit()
from frappe.utils import add_to_date, now_datetime
frappe.db.set_value("Sales Order", so, "creation", add_to_date(now_datetime(), minutes=-30))
print("SO=" + so)
print("DELIVERED=%s" % frappe.db.get_value("Sales Order", so, "per_delivered"))
''')
		so = val(out, "SO")
		check("the order was paid and the report could not be made yet", bool(so) and float(val(out, "DELIVERED") or 1) == 0, out[-300:])

		ctx = J.context(br, state, "customer", J.PHONE, buyer_session, mobile=True)
		pg = ctx.new_page()
		pg.goto(B + "/my/sessions", wait_until="networkidle")
		pg.wait_for_timeout(3000)
		body = pg.inner_text("main")
		check("the customer is told it is being made", "being made" in body.lower(), body[:200].replace("\n", " | "))
		snap(pg, "customer", "My sessions: the new report is Being made", full=True)
		J.finish(state, "customer", ctx, pg)

		ctx = J.context(br, state, "staff", J.DESK, staff_session)
		pg = ctx.new_page()
		pg.goto(B + "/team/attention", wait_until="networkidle")
		pg.wait_for_timeout(3500)
		body = pg.inner_text("main")
		snap(pg, "staff", "Needs attention: a paid report that could not be made, with the reason", full=True)
		check("the team's list shows the paid report with why", "paid, not made" in body.lower() and "Kundli report" in body and so in body and "could not be made yet" in body, body[:500].replace("\n", " | "))
		check("it offers Try again now", pg.locator("button:has-text('Try again now'), a:has-text('Try again now')").count() == 1)
		with pg.expect_response(lambda r: "make_report" in r.url, timeout=60000):
			pg.locator("button:has-text('Try again now'), a:has-text('Try again now')").first.click()
		pg.wait_for_timeout(1500)
		body = pg.inner_text("body")
		snap(pg, "staff", "Try again now while the service is still off: it says why", full=True)
		check("trying while it is still off says why and delivers nothing", "could not be made yet" in body and delivered(so) == 0, body[:300].replace("\n", " | "))

		run('frappe.db.set_value("Astrology API Settings", None, "enabled", 1)')  # the service is back
		pg.reload(wait_until="networkidle")
		pg.wait_for_timeout(3500)
		with pg.expect_response(lambda r: "make_report" in r.url, timeout=90000):
			pg.locator("button:has-text('Try again now'), a:has-text('Try again now')").first.click()
		pg.wait_for_timeout(1500)
		pg.reload(wait_until="networkidle")
		pg.wait_for_timeout(3000)
		body = pg.inner_text("main")
		snap(pg, "staff", "After trying again with the service back: the list is clear", full=True)
		check("the report is made and delivered", delivered(so) == 100, body[:200].replace("\n", " | "))
		check("the report is gone from the list", so not in body, body[:200].replace("\n", " | "))
		J.finish(state, "staff", ctx, pg)

		ctx = J.context(br, state, "customer", J.PHONE, buyer_session, mobile=True)
		pg = ctx.new_page()
		pg.goto(B + "/my/sessions", wait_until="networkidle")
		pg.wait_for_timeout(3000)
		body = pg.inner_text("main")
		snap(pg, "customer", "My sessions: the new report is Ready", full=True)
		check("the customer's new report is Ready", body.lower().count("ready") >= 3, body[:200].replace("\n", " | "))
		J.finish(state, "customer", ctx, pg)
	finally:
		run(f'frappe.db.set_value("Astrology API Settings", None, "enabled", {1 if state.get("astro_was") in ("1", 1) else 0})')


def frappe_value(expression: str) -> str:
	return val(run(f'print("V=" + str({expression}))'), "V")


def delivered(so: str) -> float:
	return float(frappe_value(f'frappe.db.get_value("Sales Order", "{so}", "per_delivered")') or 0)


PURGE = '''
from raftor_servicehq.tests.purge import purge
print(purge())
for so in frappe.get_all("File", filters={"attached_to_doctype": "Sales Order"}, fields=["name", "attached_to_name"]):
    if not frappe.db.exists("Sales Order", so.attached_to_name): frappe.delete_doc("File", so.name, force=True, ignore_permissions=True)
for name in frappe.get_all("Comment", filters={"reference_doctype": "Sales Order"}, fields=["name", "reference_name"]):
    if not frappe.db.exists("Sales Order", name.reference_name): frappe.delete_doc("Comment", name.name, force=True, ignore_permissions=True)
frappe.db.delete("Error Log", {"method": ["like", "%A report could not be made%"]})
# the gateway page asks for an Integration Request each time (the purge removes the Payment Request they point at, not them)
for name in frappe.get_all("Integration Request", filters={"reference_doctype": "Payment Request", "creation": [">=", frappe.utils.add_days(frappe.utils.now(), -1)]}, fields=["name", "reference_docname"]):
    if not frappe.db.exists("Payment Request", name.reference_docname): frappe.delete_doc("Integration Request", name.name, force=True, ignore_permissions=True)
'''


def main():
	run(PURGE)  # what earlier test runs left is cleared first, so the count before is the site's own
	before = counts()
	setup()
	try:
		with sync_playwright() as p:
			br = p.chromium.launch(slow_mo=120)
			stranger_sees_drafts_hidden(br)
			switch_on()
			buyer_session, other_session = J.session(br, BUYER), J.session(br, OTHER)
			staff_session = J.staff_login(br, STAFF)
			customer_orders(br, buyer_session)
			so = pay_on_desktop(br, buyer_session)
			receive(br, buyer_session, so)
			strangers_cannot_open(br, other_session, so)
			a_report_that_cannot_be_made(br, buyer_session, staff_session)
			br.close()
	except BaseException:
		import traceback

		traceback.print_exc()  # shown before the clean-up below, which must not hide it
		check("the journey ran to its end", False, traceback.format_exc().strip().splitlines()[-1])
	finally:
		put_back()
		run(PURGE)
		mine = run(f'''
import json
people = ["{BUYER}", "{OTHER}", "{STAFF}"]
left = {{}}
left["users"] = frappe.db.count("User", {{"name": ["in", people]}})
for doctype in ("Customer", "Sales Order", "Quotation", "Address", "Payment Request", "Payment Entry", "Delivery Note", "Sales Invoice", "Contact"):
    left[doctype] = frappe.db.count(doctype, {{"owner": ["in", people]}})
left["customers by email"] = frappe.db.count("Customer", {{"email_id": ["in", people]}})
left["proofs without an order"] = sum(1 for p in frappe.get_all("Service Proof", fields=["ref_doctype", "ref_name"]) if p.ref_doctype == "Sales Order" and not frappe.db.exists("Sales Order", p.ref_name))
left["files without an order"] = sum(1 for f in frappe.get_all("File", filters={{"attached_to_doctype": "Sales Order"}}, fields=["attached_to_name"]) if not frappe.db.exists("Sales Order", f.attached_to_name))
left["gateway requests without a payment request"] = sum(1 for r in frappe.get_all("Integration Request", filters={{"reference_doctype": "Payment Request"}}, fields=["reference_docname", "creation"]) if frappe.utils.get_datetime(r.creation) >= frappe.utils.get_datetime(frappe.utils.add_days(frappe.utils.now(), -1)) and not frappe.db.exists("Payment Request", r.reference_docname))
print("LEFT=" + json.dumps({{k: v for k, v in left.items() if v}}))
''')
		check("nothing of this run is left behind: no user, customer, order, payment, file or gateway request", json.loads(val(mine, "LEFT")) == {}, val(mine, "LEFT"))
		after = counts()
		moved = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
		print("COUNTS THAT MOVED (other people use this site too):", moved)
		now = json.loads(val(run(f'''
import json
print("NOW=" + json.dumps({{code: {{"disabled": frappe.db.get_value("Item", code, "disabled"), "price": frappe.db.get_value("Item Price", {{"item_code": code, "price_list": "Standard Selling"}}, "price_list_rate"),
                                    "published": frappe.db.get_value("Website Item", {{"item_code": code}}, "published")}} for code in ("{KUNDLI}", "{MATCH}")}}))
'''), "NOW"))
		check("the two reports are back as they shipped: switched off, free, page down", now == ORIGINAL, (now, ORIGINAL))
		check("the astrology setting is as it was", frappe_value('frappe.db.get_single_value("Astrology API Settings", "enabled")') == str(state.get("astro_was")), state.get("astro_was"))
	videos = J.join_segments(state)
	J.save(state)
	print("REVIEW", J.review_page(state, videos))
	failed = [s for s in state["steps"] if not s["ok"]]
	print(f"{len(state['steps']) - len(failed)} of {len(state['steps'])} checks passed")
	sys.exit(1 if failed else 0)


if __name__ == "__main__":
	main()
