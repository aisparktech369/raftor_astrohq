"""Puts AstroHQ's brand and navigation on an existing site (only where it still has the defaults; see branding.py)."""


def execute():
    from raftor_astrohq.branding import apply

    apply()
