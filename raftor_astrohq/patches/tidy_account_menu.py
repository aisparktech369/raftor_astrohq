"""Tidies the account menu (Portal Settings) once: our own pages first, the provider's link in the vertical's word, the procurement pages that
ERPNext shows to the Supplier role hidden (a provider is a Supplier in the books, but never uses them; payouts will bring their own pages), and the
old second "Birth profiles" row removed. Rows stay plain rows afterwards: anything an admin changes later is theirs."""
import frappe
from frappe import _

FIRST = ["/my/bookings", "/my/registrations", "/my/subscriptions", "/my/plan", "/my/schedule", "/my/recommendations", "/my/birth-profiles",
         "/provider", "/team"]
HIDE = ["/rfq", "/supplier-quotations", "/purchase-orders", "/purchase-invoices"]  # ERPNext's procurement pages for the Supplier role
STALE = ["/birth-profiles"]  # the address before the page moved under /my


def execute():
    from raftor_servicehq import kinds

    settings = frappe.get_doc("Portal Settings", "Portal Settings")
    settings.menu = [row for row in settings.menu if row.route not in STALE]
    for row in settings.menu:
        if row.route in HIDE:
            row.enabled = 0
        if row.route == "/provider":
            row.title = _("Your {0} page").format(kinds.words(kinds.default_vertical(), kinds.CONSULTATION)["provider"])
    rank = {route: n for n, route in enumerate(FIRST)}
    settings.menu = sorted(settings.menu, key=lambda row: rank.get(row.route, len(FIRST)))  # a stable sort: the others keep their order
    for n, row in enumerate(settings.menu, start=1):
        row.idx = n
    settings.save(ignore_permissions=True)
