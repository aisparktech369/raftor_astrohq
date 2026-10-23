# The kundli report and the match making report

Two reports a customer asks for from the shop and receives as a PDF. **Both are free, always** (the owner's decision), so they are *given*, not sold: no cart, no order, no invoice
(`raftor_servicehq/docs/reports.md`, "Free reports"). They are made by AstroHQ from the birth details the customer gives, using the astrology API
(`docs/astrology-api.md`) for the calculation and a list of places (GeoNames) for the latitude, longitude and time zone. Nobody makes them by hand.

| | Kundli report | Match making report |
|---|---|---|
| Asks for | one person: name, date, **time** and place of birth | two people (boy and girl): the same four things for each |
| Gives | birth details, panchang of the day, the lagna chart and the navamsa chart (North Indian diamonds), the planets, the Vimshottari dasha with the running period marked | the eight kootas (Varna, Vashya, Tara, Yoni, Graha Maitri, Gana, Bhakoot, Nadi) out of 36 with the total, and each person's Mars (manglik) |
| Pages | 2 | 1 |
| Item code | `ASTROHQ-REPORT-KUNDLI` | `ASTROHQ-REPORT-MATCH` |

The words on the pages are English. The name must be written in English letters (the form says so): the PDF fonts on the server have no Indian script and would print boxes.

## Decided

All by the owner, 2026-10-23, and all built:

- **Both reports are free, always** (the leaders' portals give them free). Their price is 0 and there is no first-one-free rule.
- **Free digital reports skip the order cycle**: it is the chance to enrol the person in the portal, and anything free should engage the customer. A report that is given paid for later would keep the order route
  (price it in Desk and it goes that way again, nothing else changes).
- **Signing in first holds friction** while people fill in their details, so the sign-up pairs with the details and the verification, on one page.
- **The mobile number is the login id** (in India it is the major one), so the free report's sign-up asks for the mobile number only, and a **password is asked as the last step before the report is read**.
  Existing accounts and the other ways to sign in stay as they are.
- **The mobile code is stubbed to `12345678` until SMS and WhatsApp are set up** ("I will setup whatsapp and sms later"). Nothing is sent; it opens a customer's account, never a staff one; it is allowed
  only where the site config says so (`allow_mobile_code_stub`, or developer mode) and switched on in Website HQ Settings. The go-live list (`raftor_servicehq/docs/mvp.md`) says what to do before real customers.
- Consultancy is linked, not merged: reports stay on /services and consultancy on /consult (the owner's route rule). The next steps after a report link to it.

What AstroHQ adds to the free way (the `"free"` of each report in `vocabulary.py`; the mechanics are servicehq's):

| | Kundli report | Match making report |
|---|---|---|
| Asks besides the details | **This kundli is for**: me, my husband or wife, my child, my mother or father, my brother or sister, someone else (the birth profile's relationships, so an admin who edits them changes this) | nothing |
| Keeps | the details as a **birth profile**: "You" when it is for the person (never overwriting the one they have), the family member's otherwise with the person's confirmation that they may keep it; the same person is not kept twice | nothing: a match is between two people, so none is kept on its own |
| Names the new account | after the person, only when the kundli is their own | not |
| Says who it is for | "For Asha Rao" | "For Vikram Mehta and Priya Shah" |
| Fills the form | for someone signed in who has their own profile with a known time of birth | not |

The line beside the button says what is kept ("We keep these details in your birth profile so you do not have to write them again. If this is for someone else, you confirm that you may."). **The wording is for the lawyer to confirm** (the
DPDP Act wants a clear action by the person; it is the button, with the line beside it, not a ticked box).

## Putting them on sale

Both ship **switched off** as ordinary shop items (made by `servicehq.servicecatalog.sync_standard_reports`, which runs on install and migrate and never changes a report
that already exists), **at price 0** (the vocabulary says `"price": 0`). Each has a comment in Desk saying what is left. The business team:

| Step | Where |
|---|---|
| 1. Read the page | Desk, the Item and its Website Item. The price is 0 (Item Price, **Standard Selling**, field **Rate**): leave it, and the report is given. A price above 0 would sell it through the cart instead. |
| 2. Switch it on | Desk, the Item: untick **Disabled**. Its page in the shop goes up by itself (and comes down when it is ticked again). **On this site the owner switched both on on 23 Oct 2026** ("make it available"); a new site gets them switched off. |

While a report is switched off it is not in the shop, not found by search, has no page of its own, and cannot be put in a cart.

## What the customer does

```
the report's page -> "Get your free report" -> ONE page: the details + mobile number -> "Send me the code" -> the code (same page)
   -> the account exists and the report is made -> "Choose a password" (can be skipped) -> the report (View report) and what next
```

Someone already signed in skips the number and the code: the details, and the report is made. The details form says what is wrong, field by field, before anything is made (all at once, not one at a time):

| Written | Said |
|---|---|
| a name in another script | "Please write the name in English letters, for example Asha Rao." |
| a date in the future, or before 1800 | "The date of birth cannot be in the future." / "Reports are made for births from the year 1800." (the star files begin in 1800) |
| a place not in the list | "We could not find X. Check the spelling, write the town and its state (for example Pune, Maharashtra), or use the nearest bigger town." |
| a town that several places carry (Sirsa, Hyderabad, Rampur ...) | the places are listed and the customer is asked to add the state. A wrong guess would be a wrong chart, so it is never guessed. |
| no time of birth | required: the lagna and the dasha change with it |

The report is made from the details at once (the kundli takes about a second, the match two), saved as a private file on a small record (**Free Report**), and recorded as a Service Proof. The customer sees
it on their report page (**Ready**, **View report**, and *What would you like next?*) and among *Poojas and reports* on their Sessions page. Only the customer and the business team can open the file.

*What would you like next?* (from what exists): ask about the report, with the words of the free first session while the person has not had it ("Free first session · 10 min", **Talk free**, **Book free**);
another kundli (for someone in the family); the match making report.

## How a report is made (`reports.py`, `report_pdf.py`, `places.py`)

1. `places.lookup` turns the written place into latitude, longitude and the time zone **as it was on that day** (a 1972 summer birth in London is +1; a 1943 birth in
   India is +6:30).
2. `astrology.chart` asks the astrology API. **Only numbers are sent** (date, time, latitude, longitude, time zone offset, and the gender for the match): never the name or the place.
3. The pages are laid out as HTML (the charts are inline SVG, nothing the customer wrote is ever left unescaped) and turned into a PDF.
4. Each page carries the credit for the place data: "Place data: GeoNames (geonames.org), licensed CC BY 4.0."

## When a report cannot be made

The record stays **Being made** (a paid report's payment is never undone) and:

| What | How |
|---|---|
| The reason is written on the record | in plain words ("Charts are switched off or not set up yet: see Astrology API Settings."). A failure the system did not expect gets a general sentence; the details go to the Error Log. |
| It is tried again | every hour (`servicehq.free_reports.make_waiting`, and `digital.deliver_waiting` for a paid one; scheduled jobs; **need the scheduler**) for 30 days |
| The customer sees | **Being made**, "it is taking a little longer than usual", with nothing to open (never the technical reason) |
| The business team sees it | on **Needs attention** (Team pages) after 5 minutes: "Free, not made", the person, the record and the reason, with **Try again now**. That button works without the scheduler. Trying while it is still not possible says why. |

The usual reasons: the astrology API is switched off or not answering (Astrology API Settings), the list of places has not been built on this site, a place that was found
at the form is no longer found.

## Setting it up on a server

| Once | How |
|---|---|
| The astrology service | `docs/astrology-api.md` (the folder, the Procfile line, Astrology API Settings **on**, Check the Connection) |
| The list of places | `bench --site <site> execute raftor_astrohq.places.build` (about a minute, 14 MB down, 50 MB on disk; builds `private/places/places.sqlite`). Without it the form lets the details through and the maker waits with the reason above. |
| After an update | `bench --site <site> migrate` (puts the two items, the Free Report record and its Workflow, the two pages, the hourly retry and the Needs attention wording in place) |
| The scheduler | on, so that waiting reports are tried again by themselves |
| The mobile code | for now the stub (`allow_mobile_code_stub` in the site config, Website HQ Settings > Mobile code stub, and **Default Country Code** +91); before real customers an SMS provider (in India with DLT registration of the sender ID and message) or the WhatsApp Business account |
| Sign-up | Website HQ Settings, **Allow new accounts with OTP**, on (a visitor's code is their sign-up) |

## What the numbers rest on

The calculation is done by the astrology API (PyJHora 4.6.0 and the Swiss Ephemeris) and was checked against an independent Swiss Ephemeris calculation (hub
`tests/test_astrology_engine.py`). The **Ashtakoota** needed more: PyJHora's own was compared with the published rules over all 11,664 pairs of nakshatra padas and
found wrong for about four couples in ten. The API (1.1.1) now works four points out itself and takes four from the library; every one is tested against the published rules
(hub `tests/test_astrology_ashtakoota.py`):

| Koota | Out of | From | Note |
|---|---|---|---|
| Varna | 1 | the API's own | the library had the earth and air signs the wrong way round |
| Vashya | 2 | the API's own | the table is the one **Astroyogi** prints (OnlineJyotish prints the same except five of 25 cells); half of Sagittarius and Capricorn found from the Moon's degree |
| Tara | 3 | the API's own | the library gave its points to the inauspicious remainders 3, 5 and 7 |
| Yoni | 4 | the library | table checked: symmetric, enemies 0 |
| Graha Maitri | 5 | the library | all 49 cells checked against the natural friendships of the planets |
| Gana | 6 | the library | classes of the 27 nakshatras checked; the table is the one with Deva boy and Manushya girl 5, Manushya boy and Deva girl 6 |
| Bhakoot | 7 | the API's own | one cell of the library's table was wrong |
| Nadi | 8 | the library | all 11,664 pairs checked |

**For the business team's astrologers to confirm before selling:** the Vashya table and the Gana table (sources differ), and that Janma (the 1st) is not counted as
inauspicious in Tara. **Manglik** is counted when Mars is in the 2nd, 4th, 7th, 8th or 12th house from the lagna (the 1st is not counted); the page says so and says that astrologers
also read it from the Moon and Venus. The library's "exceptions" to manglik are 17 loose conditions that nearly everyone meets, so the report does not use them.
The score is a guide, and the page says a full match is read with the charts and by an astrologer.

## Licences

- Place data: GeoNames, CC BY 4.0 (printed on every page).
- The astrology engine uses PyJHora and Swiss Ephemeris, both AGPL. Customers who receive these reports are users of the engine through AstroHQ, so the source offer applies
  to them as to the astrologers (the hub's README, "Licences"): give the engine's `ASTROLOGY_SOURCE_URL` before selling, and have a lawyer confirm.

## Not built

- Other languages and scripts (names, pages); a report from an unknown time of birth (no lagna, so none is made); places outside the GeoNames list (500 people and more).
- More in the kundli (other divisional charts, yogas, remedies); a free kundli summary as a lighter report than the full one (price 0 on the full one works today).
- "Report ready" messages (notifications are the last topic). The report is made in the request that confirms the code, so it is normally ready before the person looks; make it a background job if the astrology
  service ever becomes slow.
- The astrologer seeing the customer's report for their booking, if the customer agrees (needs the chart screen and the owner's rule on who sees whose chart).
- The astrologer's own chart screen (who may see whose chart).

## Checks

- Unit tests, on the engine's answers for two invented births (no service needed): `bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_kundli_reports`
  (the last class asks the real service and the real list, and is skipped where they are not set up); servicehq: `--app raftor_servicehq --module raftor_servicehq.tests.test_reports`;
  places: `raftor_astrohq.tests.test_places`.
- The free way: `raftor_servicehq/tests/test_free_reports.py` (67), `raftor_astrohq/tests/test_free_report_hooks.py` (14) and the sign-in's own `raftor_websitehq` tests (`test_auth_mobile_stub`, `test_auth_password`).
- Browser, a stranger from the product page to the report, then the same person signing back in with the number and the password, a report for a child, the limit, a report that cannot be made and the business team:
  `python3 apps/raftor_astrohq/e2e/free_reports_journey.py` (the two items are switched on and put back as they shipped).
- Browser, the paid way as a stranger, two customers and the business team (the items are priced for the run and put back as they shipped; the gateway's confirmation is stood in for):
  `JOURNEY=reports_journey python3 apps/raftor_astrohq/e2e/reports_journey.py`.
