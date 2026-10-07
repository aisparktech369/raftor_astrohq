"""AstroHQ's brand and navigation on a site: the name, the line under it, the colours, the logo, the menus and the home page.

They are written into the site's own settings (Website Settings, System Settings, a Website Theme, the PWA app, Portal Settings) once,
and only where the site still has Frappe's or ERPNext's defaults, so whatever the business team changes in Desk afterwards stays.
The words in the menus come from astrohq's vocabulary (what astrohq calls providers, a havan, a daily pooja) and the addresses from
the page groups, so nothing about a page is typed here twice."""
import frappe

BRAND = {
    "name": "AstroHQ",
    "tagline": "Headquarter for all Astro needs",
    "primary": "#3b2f80",   # deep indigo
    "dark": "#1a1a2e",      # night sky (the PWA's colour)
    "accent": "#e8a33d",    # saffron
    "font": "Inter",
}
THEME = "AstroHQ"
LOGO_FILE = "astrohq-logo.svg"
FRAPPE_DEFAULT_NAMES = ("", None, "Frappe", "ERPNext")
DEFAULT_TOP_BAR = [("Products", "/all-products")]
DEFAULT_PWA_NAV = [("Shop", "/all-products"), ("Cart", "/cart"), ("Account", "/me")]
# Portal menu rows the platform does not use for its customers (ERPNext's project and support pages), and websitehq's older plan pages,
# which the plan pages of servicehq replace. Switched off, not deleted: an admin can switch any back on.
UNUSED_PORTAL_ROUTES = ("/project", "/timesheets", "/material-requests", "/issues", "/newsletters", "/rfhq/plans", "/rfhq/my-subscription", "/birth-profiles")


def _logo_svg(on_dark: bool = False) -> str:
    """The wordmark. On a dark bar (the site header) the name is white; on a light page (sign-in) it is the night colour."""
    b = BRAND
    ink, mark = ("#ffffff", b["accent"]) if on_dark else (b["dark"], b["primary"])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="48" viewBox="0 0 200 48" role="img" aria-label="{b["name"]}">'
            f'<circle cx="24" cy="24" r="20" fill="{b["dark"]}"/>'
            f'<path d="M30 12a13 13 0 1 0 0 24a10 10 0 1 1 0-24z" fill="{b["accent"]}"/>'
            f'<path d="M17 15l1.6 3.4 3.7.5-2.7 2.6.6 3.7-3.2-1.8-3.3 1.8.7-3.7-2.7-2.6 3.7-.5z" fill="#fff"/>'
            f'<text x="54" y="31" font-family="{b["font"]}, Arial, sans-serif" font-size="22" font-weight="800" fill="{ink}">Astro'
            f'<tspan fill="{mark}">HQ</tspan></text></svg>')


def _icon_svg() -> str:
    b = BRAND
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 48 48"><circle cx="24" cy="24" r="22" fill="{b["dark"]}"/>'
            f'<path d="M30 11a13 13 0 1 0 0 26a10.5 10.5 0 1 1 0-26z" fill="{b["accent"]}"/></svg>')


def _file(name: str, content: str) -> str:
    url = frappe.db.get_value("File", {"file_name": name, "is_private": 0}, "file_url")
    if url:
        return url
    doc = frappe.get_doc({"doctype": "File", "file_name": name, "is_private": 0, "content": content}).insert(ignore_permissions=True)
    return doc.file_url


def _words():
    from raftor_servicehq import kinds

    vertical = "astrohq"
    return {kind: kinds.words(vertical, kind) for kind in kinds.KINDS}


def _top_bar():
    from raftor_servicehq import kinds
    from raftor_websitehq.website_hq.page_groups import page_url

    w = _words()
    return [
        {"label": w[kinds.CONSULTATION]["providers"].capitalize(), "url": page_url("services", "book")},
        {"label": "Online now", "url": page_url("services", "online")},
        {"label": w[kinds.EVENT]["services"].capitalize(), "url": page_url("services", "events")},
        {"label": w[kinds.SUBSCRIPTION]["service"].capitalize(), "url": page_url("services", "subscriptions")},
        {"label": "Plans", "url": page_url("services", "plans")},
        {"label": "Shop", "url": "/all-products"},
    ]


def _footer_items():
    from raftor_websitehq.website_hq.page_groups import page_url

    return [
        {"label": "Book", "url": page_url("services", "book")},
        {"label": "What is on", "url": page_url("services", "events")},
        {"label": "Plans", "url": page_url("services", "plans")},
        {"label": "Shop", "url": "/all-products"},
        {"label": "My account", "url": page_url("my")},
        {"label": "Become an astrologer", "url": "/login?intent=provider"},
    ]


def _color(name: str, value: str) -> str:
    """A Website Theme names its colours as Color records."""
    if not frappe.db.exists("Color", name):
        doc = frappe.get_doc({"doctype": "Color", "color": value})
        doc.name = name
        doc.flags.name_set = True
        doc.insert(ignore_permissions=True)
    return name


def ensure_theme() -> str:
    if not frappe.db.exists("Website Theme", THEME):
        theme = frappe.new_doc("Website Theme")
        theme.update({"theme": THEME, "primary_color": _color("AstroHQ Indigo", BRAND["primary"]), "dark_color": _color("AstroHQ Night", BRAND["dark"]),
                      "text_color": _color("AstroHQ Ink", "#1f2333"), "background_color": _color("AstroHQ White", "#ffffff"),
                      "google_font": BRAND["font"], "button_rounded_corners": 1})
        theme.insert(ignore_permissions=True)
    return THEME


def apply() -> dict:
    """Puts the brand and the menus on this site where it still has the defaults. Returns what it changed."""
    from raftor_websitehq.website_hq.page_groups import page_url

    done = {}
    logo = _file(LOGO_FILE, _logo_svg())
    logo_on_dark = _file("astrohq-logo-light.svg", _logo_svg(on_dark=True))
    icon = _file("astrohq-icon.svg", _icon_svg())

    ws = frappe.get_single("Website Settings")
    if ws.app_name in FRAPPE_DEFAULT_NAMES:
        ws.app_name = BRAND["name"]; done["app_name"] = 1
    for field, value in (("title_prefix", BRAND["name"]), ("app_logo", logo), ("favicon", icon), ("copyright", BRAND["name"]),
                         ("footer_powered", f'{BRAND["name"]} · {BRAND["tagline"]}'), ("home_page", page_url("services").strip("/"))):
        if not ws.get(field):
            ws.set(field, value); done[field] = 1
    if not ws.brand_html:
        ws.brand_html = f'<img src="{logo_on_dark}" alt="{BRAND["name"]}" style="height:32px">'; done["brand_html"] = 1
    if [(r.label, r.url) for r in ws.top_bar_items] in ([], DEFAULT_TOP_BAR):
        ws.set("top_bar_items", []); [ws.append("top_bar_items", row) for row in _top_bar()]; done["top_bar_items"] = 1
    if not ws.footer_items:
        [ws.append("footer_items", row) for row in _footer_items()]; done["footer_items"] = 1
    if ws.website_theme in (None, "", "Standard"):
        ws.website_theme = ensure_theme(); done["website_theme"] = 1
    ws.save(ignore_permissions=True)

    if frappe.db.get_single_value("System Settings", "app_name") in FRAPPE_DEFAULT_NAMES:
        frappe.db.set_single_value("System Settings", "app_name", BRAND["name"]); done["system_app_name"] = 1
    if frappe.db.get_single_value("System Settings", "login_with_email_link"):
        frappe.db.set_single_value("System Settings", "login_with_email_link", 0); done["email_link_off"] = 1  # sign-in is code, PIN or password

    if frappe.db.exists("DocType", "PWA App"):
        for name in frappe.get_all("PWA App", pluck="name"):
            app = frappe.get_doc("PWA App", name)
            if [(r.label, r.url) for r in app.nav_items] in ([], DEFAULT_PWA_NAV):
                app.set("nav_items", [])
                for label, url, icon_name, guest in (("Home", "/", "home", 1), ("Book", page_url("services", "book"), "star", 1),
                                                     ("Account", page_url("my"), "user", 1), ("Shop", "/all-products", "shopping-bag", 1), ("Cart", "/cart", "shopping-cart", 1)):
                    app.append("nav_items", {"label": label, "url": url, "icon": icon_name, "guest_ok": guest})
                app.save(ignore_permissions=True); done["pwa_nav"] = 1

    portal = frappe.get_single("Portal Settings")

    portal.sync_menu()  # the menu rows the apps ship (hooks standard_portal_menu_items) are added if missing

    portal = frappe.get_single("Portal Settings")
    changed = False
    for row in portal.menu:
        if row.route in UNUSED_PORTAL_ROUTES and row.enabled:
            row.enabled = 0; changed = True
    if changed:
        portal.save(ignore_permissions=True); done["portal_menu"] = 1
    frappe.clear_cache()
    return done
