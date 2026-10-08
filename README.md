### Raftor Astro HQ

The astrology vertical. It describes; it does not draw or validate generically.

* **Birth profiles** - a table on the existing User (*Astro Birth Profile* rows): the account holder is the row
  marked "You", family members are the others (no limit). Rules in `profiles.py` run for the website and for
  every User save. Time of birth is text on purpose (Frappe fills empty Time fields with "now").
* **Website** - `api.py` has the signed-in endpoints (own rows only); `page_definitions.py` describes the pages as data for
  websitehq to build: `/onboarding/birth-details`, `/onboarding/birth-details/done`, `/my/birth-profiles`,
  `/my/birth-profiles/new`, `/my/birth-profiles/edit?id=`. "Birth profiles" is listed on the My account page. The old addresses forward.
* **Journey** - `journey.py` registers the onboarding step with onboardinghq (`config.page` plus a completion
  check), so `/login?intent=astrohq` brings a new person to the form and an unfinished one back to it.
* No CSS, JS or HTML here: the look belongs to websitehq.

## Astrologer (a provider specialised by astrohq)
servicehq owns the general **Provider** and its journey ("ServiceHQ Provider"). astrohq adds to it and never changes it:
- its own table **Astrologer Profile** (one row per Provider: expertise, languages, years, credentials) and child **Astrologer Credential**
- two steps added to the provider journey by order number (`journey.py`): *Your astrologer details* and *Your credentials*
- pages `/onboarding/astrologer-details`, `/onboarding/astrologer-credentials` (page definitions, `page_definitions.py`), endpoints in `astrologer_api.py`, rules in `astrologer.py`
- verification is done by staff (Verify button on the Onboarding Application in Desk). Credentials file upload comes later with a page-kit upload block.
# raftor_astrohq
