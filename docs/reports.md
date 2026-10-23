# The kundli report and the match making report

Two reports a customer buys from the shop and receives as a PDF. They are made by AstroHQ from the birth details the customer gives, using the astrology API
(`docs/astrology-api.md`) for the calculation and a list of places (GeoNames) for the latitude, longitude and time zone. Nobody makes them by hand.

| | Kundli report | Match making report |
|---|---|---|
| Asks for | one person: name, date, **time** and place of birth | two people (boy and girl): the same four things for each |
| Gives | birth details, panchang of the day, the lagna chart and the navamsa chart (North Indian diamonds), the planets, the Vimshottari dasha with the running period marked | the eight kootas (Varna, Vashya, Tara, Yoni, Graha Maitri, Gana, Bhakoot, Nadi) out of 36 with the total, and each person's Mars (manglik) |
| Pages | 2 | 1 |
| Item code | `ASTROHQ-REPORT-KUNDLI` | `ASTROHQ-REPORT-MATCH` |

The words on the pages are English. The name must be written in English letters (the form says so): the PDF fonts on the server have no Indian script and would print boxes.

## Putting them on sale

Both ship **switched off** as ordinary shop items (made by `servicehq.servicecatalog.sync_standard_reports`, which runs on install and migrate and never changes a report
that already exists). Each has a comment in Desk saying what is left. The business team:

| Step | Where |
|---|---|
| 1. Set the price | Desk, Item Price: the row of the report in **Standard Selling**, field **Rate**. It ships as 1 so that nothing is sold at a forgotten price. **0 makes the report free**: the customer's order is placed with nothing to pay and the report is made at once. |
| 2. Switch it on | Desk, the Item: untick **Disabled**. Its page in the shop goes up by itself (and comes down when it is ticked again). |

While a report is switched off it is not in the shop, not found by search, has no page of its own, and cannot be put in a cart.

## What the customer does

```
the report's page  ->  "Get your report"  ->  the details  ->  the cart  ->  pay  ->  made and delivered
                                              checked here     (or free: order placed, made at once)
```

The details form says what is wrong, field by field, before anything is put in the cart:

| Written | Said |
|---|---|
| a name in another script | "Please write the name in English letters, for example Asha Rao." |
| a date in the future, or before 1800 | "The date of birth cannot be in the future." / "Reports are made for births from the year 1800." (the star files begin in 1800) |
| a place not in the list | "We could not find X. Check the spelling, write the town and its state (for example Pune, Maharashtra), or use the nearest bigger town." |
| a town that several places carry (Sirsa, Hyderabad, Rampur ...) | the places are listed and the customer is asked to add the state. A wrong guess would be a wrong chart, so it is never guessed. |
| no time of birth | required: the lagna and the dasha change with it |

When the order is paid the system makes the report from the details kept on the order line, saves it as a private file, records it as a Service Proof, and makes the
Delivery Note and the invoice. The customer sees **Ready** and **View report** under *Poojas and reports* on their Sessions page, and the file on the order page.
Only the customer and the business team can open the file.

## How a report is made (`reports.py`, `report_pdf.py`, `places.py`)

1. `places.lookup` turns the written place into latitude, longitude and the time zone **as it was on that day** (a 1972 summer birth in London is +1; a 1943 birth in
   India is +6:30).
2. `astrology.chart` asks the astrology API. **Only numbers are sent** (date, time, latitude, longitude, time zone offset, and the gender for the match): never the name or the place.
3. The pages are laid out as HTML (the charts are inline SVG, nothing the customer wrote is ever left unescaped) and turned into a PDF.
4. Each page carries the credit for the place data: "Place data: GeoNames (geonames.org), licensed CC BY 4.0."

## When a report cannot be made

The payment is never undone. The line stays undelivered and:

| What | How |
|---|---|
| The reason is written on the order | in plain words, once for the same reason ("Kundli report could not be made yet: Charts are switched off or not set up yet: see Astrology API Settings."). A failure the system did not expect gets a general sentence; the details go to the Error Log. |
| It is tried again | every hour (`servicehq.digital.deliver_waiting`, a scheduled job; **needs the scheduler**) for 30 days |
| The customer sees | **Being made**, with nothing to open |
| The business team sees it | on **Needs attention** (Team pages) after 5 minutes: the report, the customer, the order and the reason, with **Try again now**. That button works without the scheduler. Trying while it is still not possible says why. |

The usual reasons: the astrology API is switched off or not answering (Astrology API Settings), the list of places has not been built on this site, a place that was found
at the form is no longer found.

## Setting it up on a server

| Once | How |
|---|---|
| The astrology service | `docs/astrology-api.md` (the folder, the Procfile line, Astrology API Settings **on**, Check the Connection) |
| The list of places | `bench --site <site> execute raftor_astrohq.places.build` (about a minute, 14 MB down, 50 MB on disk; builds `private/places/places.sqlite`). Without it the form lets the details through and the maker waits with the reason above. |
| After an update | `bench --site <site> migrate` (puts the two items, the hourly retry and the Needs attention wording in place) |
| The scheduler | on, so that waiting reports are tried again by themselves |

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
- A limit on free reports: at price 0 any signed-in customer can order as many as they like, and each costs a second or two of the astrology service and the PDF maker. A report is made
  in the request that confirms the payment (the kundli takes about a second, the match two); if a gateway's webhook ever times out on it, make it a background job (the hourly retry already covers a miss).
- The astrologer's own chart screen (who may see whose chart).

## Checks

- Unit tests, on the engine's answers for two invented births (no service needed): `bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_kundli_reports`
  (the last class asks the real service and the real list, and is skipped where they are not set up); servicehq: `--app raftor_servicehq --module raftor_servicehq.tests.test_reports`;
  places: `raftor_astrohq.tests.test_places`.
- Browser, as a stranger, two customers and the business team (the two items are switched on at test prices and put back as they shipped; the gateway's confirmation is
  stood in for): `JOURNEY=reports_journey python3 apps/raftor_astrohq/e2e/reports_journey.py`. Done on 2026-10-23: 45 of 45 checks.
