"""Astrology API Settings in a browser, as each person sees it: the owner (a System Manager) fills in the hub's address and AstroHQ's key, is told
what is missing, switches charts on and checks the connection; an accounts user and a Business Team user are not given the page that holds the key.
The hub here is a small stand-in on this computer that answers the way the real hub does (the real one is checked in docs/astrology-api.md's steps),
so nothing outside is called and nothing real is stored. Run: JOURNEY=astrology_check python3 astrology_settings_check.py [clean]"""
import json
import os
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ.setdefault("JOURNEY", "astrology_check")
sys.path.insert(0, "/home/ubuntu/dev-bench/apps/raftor_servicehq/e2e")
from playwright.sync_api import sync_playwright  # noqa: E402

import journey_lib as J  # noqa: E402
from shop_e2e import B, report, run, step  # noqa: E402

T = uuid.uuid4().hex[:5]
OWNER, ACCOUNTS, BUSINESS = f"astro-{T}@example.com", f"astro-{T}b@example.com", f"astro-{T}c@example.com"
PORT, GOOD_KEY, WRONG_KEY = 8792, "e2e-good-key-0001", "e2e-wrong-key-0002"
state = J.load()


class StandInHub(BaseHTTPRequestHandler):
	"""Answers /usage and /call as the hub's gateway does: 401 for a key it does not know, a panchang for the sample birth."""

	def _reply(self, code, body):
		data = json.dumps(body).encode()
		self.send_response(code)
		self.send_header("content-type", "application/json")
		self.send_header("content-length", str(len(data)))
		self.end_headers()
		self.wfile.write(data)

	def _handle(self):
		engine = self.path in ("/", "")  # the astrology API's own contract; the hub's paths are .../gateway.usage and .../gateway.call
		if engine and self.command == "GET":  # who are you: asks for no key
			return self._reply(200, {"service": "astrology", "version": "e2e-stand-in", "ready": True, "operations": ["PANCHANGA"], "libraries": {}, "source": None})
		if self.headers.get("X-Api-Key") != GOOD_KEY:
			if engine:
				return self._reply(401, {"status": "error", "error": {"code": "unauthorized", "message": "Missing or wrong API key.", "request_id": "stand-in"}})
			return self._reply(401, {"exc_type": "AuthenticationError", "_server_messages": json.dumps([json.dumps({"message": "Invalid or inactive API key"})])})
		if self.path.endswith("gateway.usage"):
			return self._reply(200, {"subscription": "ACC-SUB-STAND-IN", "plan": "Internal", "status": "Active", "calls_used": 0, "calls_limit": 0, "calls_remaining": 0})
		length = int(self.headers.get("content-length") or 0)
		asked = json.loads(self.rfile.read(length) or b"{}")
		envelope = {"status": "success", "opcode": (asked.get("payload") or asked)["opcode"], "processing_time": 0.01, "data": {"panchanga": {"tithi": "Krishna Paksha Dhasami", "vaara": "Sunday"}}}
		if engine:
			return self._reply(200, envelope)
		return self._reply(200, {"success": True, "request_id": "stand-in", "data": envelope})

	do_GET = do_POST = _handle

	def log_message(self, *args):
		pass


def start_hub():
	server = HTTPServer(("127.0.0.1", PORT), StandInHub)
	threading.Thread(target=server.serve_forever, daemon=True).start()
	return server


def snap(pg, role, caption):
	J.snap(state, pg, role, caption)


def setup():
	if run('print("R=" + str(frappe.db.get_single_value("Astrology API Settings", "enabled", cache=False) or 0))').strip() == "R=1":
		sys.exit("Astrology API Settings is switched on (in real use): this check starts from an empty page and would wipe it. Not running.")
	run(f'''
for email, first, roles in (("{OWNER}", "Asha", ["System Manager"]), ("{ACCOUNTS}", "Bina", ["Accounts Manager"]), ("{BUSINESS}", "Chitra", ["Business Team"])):
    frappe.get_doc({{"doctype": "User", "email": email, "first_name": first, "send_welcome_email": 0, "user_type": "System User", "roles": [{{"role": r}} for r in roles if frappe.db.exists("Role", r)]}}).insert(ignore_permissions=True)
frappe.db.delete("Singles", {{"doctype": "Astrology API Settings"}})
frappe.db.delete("__Auth", {{"doctype": "Astrology API Settings"}})
''')
	print("SETUP")


def clean():
	run(f'''
for u in ["{OWNER}", "{ACCOUNTS}", "{BUSINESS}"]:
    if frappe.db.exists("User", u): frappe.delete_doc("User", u, force=True, ignore_permissions=True)
frappe.db.delete("Singles", {{"doctype": "Astrology API Settings"}})  # what was typed, and what the check said
frappe.db.delete("__Auth", {{"doctype": "Astrology API Settings"}})
''')
	print("CLEAN")


def desk(who, email, steps):
	with sync_playwright() as p:
		br = p.chromium.launch(slow_mo=100)
		ctx = J.context(br, state, who, J.DESK, J.staff_login(br, email))
		pg = ctx.new_page()
		steps(pg)
		J.finish(state, who, ctx, pg)
		br.close()


def saved():
	out = run('''doc = frappe.get_single("Astrology API Settings")
print("R=" + "|".join([str(doc.enabled), doc.hub_address or "", doc.get_password("api_key", raise_exception=False) or "", doc.api_name or "", str(doc.timeout_seconds)]))''')
	return next((line.split("=", 1)[1] for line in out.splitlines() if line.startswith("R=")), "")


def way():
	out = run('print("R=" + (frappe.get_single("Astrology API Settings").how or ""))')
	return next((line.split("=", 1)[1] for line in out.splitlines() if line.startswith("R=")), "")


def alert_text(pg):
	return pg.inner_text(".desk-alert") if pg.locator(".desk-alert").count() else ""


def stage_owner():
	def look(pg):
		pg.goto(B + "/app/astrology-api-settings", wait_until="networkidle")
		pg.wait_for_timeout(3000)
		text = pg.inner_text("body")
		step("the owner sees the page: the way, the address, the key, the name, the wait and the check", all(w in text for w in ("How AstroHQ Reaches It", "Where It Is", "Address", "API Key", "Name of the API in the Hub", "Wait for an Answer", "Is It Connected", "Check the Connection")), text[:120].replace("\n", " | "))
		step("it explains what is sent (numbers, never a name) and says charts are not available yet", "never a name" in text and "Charts are not available" in text, "")
		step("the name of the API and the wait start filled in", saved().endswith("|astrology|20") or saved() == "", saved())
		snap(pg, "owner", "Desk: Astrology API Settings, off and empty")

		pg.locator('[data-fieldname="enabled"] input[type=checkbox]').first.check()
		pg.wait_for_timeout(400)
		pg.keyboard.press("Control+s")
		pg.wait_for_timeout(2500)
		text = pg.inner_text(".modal.show") if pg.locator(".modal.show").count() else pg.inner_text("body")
		step("switching charts on with nothing filled in is refused and says what to fill in", "fill in" in text and "address" in text and "key" in text, text[:140].replace("\n", " | "))
		snap(pg, "owner", "Desk: charts cannot be switched on without the address and the key")
		pg.keyboard.press("Escape")
		pg.wait_for_timeout(800)

		pg.locator('[data-fieldname="hub_address"] input').first.fill("http://hub.example.com")
		pg.locator('[data-fieldname="api_key"] input').first.fill(GOOD_KEY)
		pg.keyboard.press("Control+s")
		pg.wait_for_timeout(2500)
		text = pg.inner_text(".modal.show") if pg.locator(".modal.show").count() else pg.inner_text("body")
		step("an address that does not start with https:// is refused, and says why", "https://" in text and "travel safely" in text, text[:140].replace("\n", " | "))
		pg.keyboard.press("Escape")
		pg.wait_for_timeout(800)

		pg.locator('[data-fieldname="hub_address"] input').first.fill(f"http://127.0.0.1:{PORT}/")
		pg.keyboard.press("Control+s")
		pg.wait_for_timeout(3000)
		step("with an address and the key it is saved: the address tidied, the key kept", saved() == f"1|http://127.0.0.1:{PORT}|{GOOD_KEY}|astrology|20", saved())
		pg.reload()
		pg.wait_for_timeout(3000)
		text = pg.inner_text("body")
		step("the page says charts are available and does not show the key", "Charts are available" in text and GOOD_KEY not in text, "")
		snap(pg, "owner", "Desk: Astrology API Settings, on")

		pg.locator('[data-fieldname="check_connection"] button').first.click()
		pg.wait_for_timeout(5000)
		step("the check says it is connected, names the plan and that the engine answered", "Connected" in alert_text(pg) and "Internal" in alert_text(pg), alert_text(pg)[:160])
		snap(pg, "owner", "Desk: the check of the connection, connected")
		pg.reload()
		pg.wait_for_timeout(3000)
		text = pg.inner_text("body")
		step("and the page keeps what the hub said and when", "Connected to the hub, which knows AstroHQ" in text and "Last Checked" in text, "")

		pg.locator('[data-fieldname="api_key"] input').first.fill(WRONG_KEY)
		pg.keyboard.press("Control+s")
		pg.wait_for_timeout(3000)
		pg.locator('[data-fieldname="check_connection"] button').first.click()
		pg.wait_for_timeout(5000)
		step("a key the hub does not accept is reported in plain words", "did not accept AstroHQ's API key" in alert_text(pg), alert_text(pg)[:160])
		snap(pg, "owner", "Desk: the check of the connection, the hub turns the key away")
		pg.reload()
		pg.wait_for_timeout(3000)
		step("and that is what the page now says the hub said", "did not accept" in pg.inner_text("body"), "")

		pg.locator('[data-fieldname="api_key"] input').first.fill(GOOD_KEY)
		pg.locator('[data-fieldname="enabled"] input[type=checkbox]').first.uncheck()
		pg.keyboard.press("Control+s")
		pg.wait_for_timeout(3000)
		step("switched off again, the page says charts are not available", "Charts are not available" in pg.inner_text("body"), saved())
		pg.locator('[data-fieldname="check_connection"] button').first.click()
		pg.wait_for_timeout(5000)
		step("the connection can still be tried while it is off", "Connected" in alert_text(pg), alert_text(pg)[:160])
		snap(pg, "owner", "Desk: off, the connection can still be tried")

		# the way: straight to the astrology API instead of through the hub
		pg.locator('[data-fieldname="how"] select').first.select_option("Straight to the astrology API")
		pg.wait_for_timeout(600)
		step("choosing the straight way hides the hub's API name", not pg.locator('[data-fieldname="api_name"]').first.is_visible(), "")
		pg.locator('[data-fieldname="enabled"] input[type=checkbox]').first.check()
		pg.keyboard.press("Control+s")
		pg.wait_for_timeout(3000)
		step("it saves with the straight way chosen, the address and the key", saved().startswith(f"1|http://127.0.0.1:{PORT}|{GOOD_KEY}|") and way() == "Straight to the astrology API", saved() + " / " + way())
		pg.locator('[data-fieldname="check_connection"] button').first.click()
		pg.wait_for_timeout(5000)
		step("the check asks the astrology API itself and says so", "Connected to the astrology API" in alert_text(pg) and "e2e-stand-in" in alert_text(pg), alert_text(pg)[:160])
		snap(pg, "owner", "Desk: straight to the astrology API, connected")
		pg.reload()
		pg.wait_for_timeout(3000)
		step("the page says charts are available straight to the astrology API", "straight to the astrology API" in pg.inner_text("body"), "")
		pg.locator('[data-fieldname="api_key"] input').first.fill(WRONG_KEY)
		pg.keyboard.press("Control+s")
		pg.wait_for_timeout(3000)
		pg.locator('[data-fieldname="check_connection"] button').first.click()
		pg.wait_for_timeout(5000)
		step("straight, a key the service does not accept is reported in plain words", "did not accept AstroHQ's API key" in alert_text(pg), alert_text(pg)[:160])

	desk("owner", OWNER, look)


def stage_others(who, email, caption):
	def look(pg):
		pg.goto(B + "/app/astrology-api-settings", wait_until="networkidle")
		pg.wait_for_timeout(3000)
		text = pg.inner_text("body")
		step(f"{who} is not given the page that holds the key", GOOD_KEY not in text and "Where It Is" not in text and ("not permitted" in text.lower() or "insufficient" in text.lower() or "no permission" in text.lower()), text[:140].replace("\n", " | "))
		snap(pg, who, caption)

	desk(who, email, look)


if __name__ == "__main__":
	if "clean" in sys.argv:
		clean()
	else:
		start_hub()
		setup()
		try:
			stage_owner()
			stage_others("accounts", ACCOUNTS, "Desk: the accounts team is not given Astrology API Settings")
			stage_others("business", BUSINESS, "Desk: a Business Team user is not given Astrology API Settings")
		finally:
			J.save(state)
			clean()
		print("SHOTS", [(s["file"], s["caption"]) for s in state["shots"]])
		report()
