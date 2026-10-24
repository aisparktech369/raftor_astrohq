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

They are found on the Home page (a band at the top of Seek guidance), on the Guidance page, in the menu (Explore > Free reports) and on `/services/free-reports`, which also lists a signed-in person's own reports. The Home band and the menu link are this site's own data (`sites/<site>/site_pages/home_free.py`, kept beside `home.py` and `menu.py`), not the app's.

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

## The arranger (`arrange.py`, `layouts/`, `engine_words.json`)

Every mode of the astrology API answers in JSON, and almost all of it is a table. The arranger lays any answer out as pages: **it calculates nothing.** A *layout* (a small JSON file in
`layouts/`) says which part of the answer goes where, under which heading; the arranger does the rest. A new mode, or another order, is a new file and no code.

| Layout | Made from | Pages (sample) | What is in it |
|---|---|---|---|
| `basic` | SUPER_BASIC, CORE_BASIC | 2 / 4 | birth, planets, D1 and D9, Vimshottari with the running period marked; with CORE_BASIC also houses, planet strength (shadbala), 14 more divisional charts |
| `standard` | CORE_STANDARD | 6 | + planets with their chara karakas, special lagnas, shadow points, planets together, ashtakavarga, arudhas, doshas, sphutas, sahams |
| `advanced` | CORE_ADVANCED | 8 | + birth star, yogas, the panchang of the birth day with its times |
| `match` | MATCH_CALC | 1 | the two people, the eight kootas and their total, doshas, other checks |
| `dasha` | DASHA_CALC | 35 | every dasha system asked for, each under its own name, the running period marked (name the systems in `birth_data.requested_dasha_systems`) |
| `annual` | ANNUAL_CALC | 1 | Mudda and Patyayini dasha: **one fixed year after birth** (the API takes no year) |
| `transit` | TRANSIT_CALC | 1 | the Tajaka chart and sahams of the birth moment (**no date is taken**: it is not the sky of today) |
| `panchang` | PANCHANGA | 1 | tithi, nakshatra, yoga, karana with when each begins and ends |
| `kp` | KP_SYSTEM | 3 | ruling planets, planets and cusps with sign, star, sub and sub-sub lords, significators, aspects |

CORE_ADVANCED holds everything of the three modes under it, so one call can feed `basic`, `standard` and `advanced` (a layout simply shows less). CORE_STANDARD has **no
`planetary_positions`**: its planets come from `planets.info`, its signs from the houses (`arrange.where`).

**A layout** is `{"title", "intro", "note", "hide": [keys never shown], "sections": [...], "rest": false}`; `"extends": "basic"` with `"append": [...]` builds on another. A section is one of
`lines` (a few facts by template), `facts` (by key), `times` (what the library wrote as "Revati ... 02:05:50 from 00:19:48 (+1) ends"), `places` (what it wrote as "♉︎Taurus 24° 6’ 21" (Atma Karaka)"),
`table`, `pivot`, `matrix`, `charts`, `dasha`, `dashas`, `yogas`, `auto` (whatever is there, as it comes: every record a row, nothing left as raw JSON) and `text`. The top of `arrange.py` says what each takes.
A section with nothing to show is left out with its heading.

**The engine's words.** The library spells names its own way (Tamil: Revathi, Sadhayam, Dhasami, Soubhagya): `engine_words.json` turns them into ours (Revati, Shatabhisha, Dashami, Saubhagya), whole
words only. The library writes a time before midnight as how far it is from midnight with "(-1)" after it (a tithi that began at 17:08 the day before comes as "06:51:18 (-1)"): `arrange.clock`
turns it back. Its "% balance" is **left out** (it works it out from the wrong start for that tithi). Also left out: the longevity estimate, the match's verdicts (feasibility, harmony, risk), what a yoga is said to give,
the engine's own verification block, and the placeholders for dasha systems the mode did not make.

**For a PDF** (wkhtmltopdf, an old WebKit): no CSS variables, no flex or grid; `page-break-inside: avoid` on a `div` is not honoured but on a *table* it is. So a heading is written as the `<caption>` of the table under it
(a page can never end between them), a note is the table's last row, and a part of several tables is put in a table of one cell (`arrange.keep`). The chart drawing writes its title inside its own picture
(it used to sit below the picture and was cut off, in the kundli report too).

**Not checked by an astrologer yet** (the layout shows what the engine gave, no value is changed): planet strength, special lagnas, shadow points, sphutas, sahams, ashtakavarga, arudhas, the Tajaka chart, every dasha
system but Vimshottari, KP lords and significators, the 14 divisional charts but D1 and D9. **The yogas are not reliable:** of six checked by hand two are wrong (Sareera Soukhya needs the lagna lord, Jupiter and Venus in kendras,
Bhaga Chumbana the 7th lord in the 4th with Venus; Jupiter is in the 12th). Match: both people show Manglik and Pitru dosha "Yes" in the sample.

**Tests:** `raftor_astrohq/tests/test_arrange.py` (38; the ten layouts on the engine's own answers for one invented birth, `tests/fixtures/engine_answers_all_modes.json.gz`) and the chart drawing in `test_kundli_reports.py`;
13 deliberate breakages were each caught. The pictures: lay each mode out with `arrange.html(answer, layout, subject=..., today=...)` and `frappe.utils.pdf.get_pdf`.

## What a report wears (the site's brand)

A report's PDF is drawn in the site's own brand, read when it is made from the places the web pages read it (websitehq `brand.document_brand()`): the colours and the two fonts of the active **Website Theme**,
the name in **Website Settings**, and a **still logo** kept in **Website HQ Settings, Logo for Documents** (a PDF cannot play the moving logo of the site; the picture is carried inside the PDF as a data address, so no
network or login is needed; PNG, JPG, GIF or WEBP, up to 400 KB). `report_pdf.site_look()` turns it into a *look*; the kundli, the match making report and every arranged page are drawn in it: the logo over a rule
in the accent colour, the headings, table heads, lines and charts in the theme's colours, the headings in the theme's heading font where the PDF engine has one (else a serif). A main colour that would not read on white (under 4.5 to 1) gives way to the ink.
**A site with no theme, or no logo, gets what it always had** (the name in small type, the plain purple). Nothing is typed in the code: change the theme or the logo in Desk and the next report wears it.

## Reports made from a layout, and what is kept (`answers.py`, `reports.arranged_report`)

Four more reports ship with the kundli and the match making report, each **switched off, at price 0, its page down** (the team switches them on; the names are plain words to change in Desk):
**Detailed kundli report** (layout `advanced`), **Dasha periods report** (`dasha`), **KP chart report** (`kp`), **Panchang of your birth day** (`panchang`). They ask what the kundli asks, say whose it is and keep the details
the same way (`vocabulary.person_free`). Their maker, `reports.arranged_report`, finds the layout and the mode in the vocabulary entry, asks the engine (or reads what is kept), lays the answer out by the layout in the site's brand and makes the PDF, titled
by the report (the layout's own title is not used).

**What a customer sees: only what an astrologer has checked.** A section of a layout says `"reviewed": true` (a `dashas` section names the systems: `"reviewed": ["vimshottari"]`). A customer's PDF has those only; a
page that shows all (an astrologer's, the team's, or a customer's when **Astrology API Settings, Show Sections Nobody Has Checked To Customers** is ticked, for a demonstration) marks the others **Draft** beside their heading.
Today the four sections the live kundli has already are checked (Birth, Planets, Charts, Vimshottari dasha): so the detailed report reads like the kundli until astrologers check more, one section at a time, in the layout file.
A report none of whose sections is checked cannot be given ("Nothing in this report has been checked by an astrologer yet": the engine is not even asked).

**What is kept.** The engine's answer for a person's birth in a mode is kept in a private `Astro Answer` record (only a System Manager can open it) under a fingerprint of the person, the mode and the numbers sent: so the
second report from the same birth, a page and a PDF cost no new call (a second detailed report took 0.4 s instead of 1.3 s; three calls per person feed seven of the ten modes). It is gzip-packed (about a tenth of its size), goes with the person (a User's deletion removes it),
is never shared between two people with the same birth, and is asked for again when it was made before **Astrology API Settings, Kept Answers Are Good From** (put today's date there after the engine has been updated).
The sky of another moment (today's planets) is kept for a day in the cache, for anyone, since it is about no person.

## The web page of a report, and the astrologer's page (`panes.py`, `report_view.py`, `views/`)

The same kept answers also make a page of **panes** (design: `report-pages.md`). A *pane* shows one part of an answer in a titled box: `chart` (the lagna chart, with facts beside it in the wide board), `varga` (any divisional chart), `planets`, `dasha`
(Vimshottari, the running period marked, the next ones), `drishti` (the matrix: each planet a row and a column, where they meet the strength in virupas, darker is stronger), `shadbala` (bars), `karakas` (with the special lagnas and arudhas), `houses`, `facts`
(birth, star, tithi, yoga, karana, manglik) and `today` (today's planets in the person's houses). A pane is a function in `panes.py` that answers `{body, summary}` or nothing when the answer has no data for it: it is then left out. The summary is the one line a pane shows when it is folded on a phone.

A *view* is a small JSON file in `views/` that places panes on a board: `board` ("lite" is three columns, "wide" four), `modes` (the engine modes it is made from), and for each pane `at` [column, row, columns wide, rows tall], `reviewed` and `shut`. Two views ship:

| View | For | Board | Panes |
|---|---|---|---|
| `customer` ("Your chart") | the person who asked for a report | lite, 3 columns | chart, planets, at a glance, Vimshottari and D9 checked; drishti, shad bala, houses, karakas, today are Draft |
| `astrologer` ("Birth chart wide") | the astrologer of a booking | wide, 4 columns, about 1100 px tall | chart and D1 facts, D9, D10, D7, D24, D60, D4, planets, Vimshottari, drishti, shad bala, karakas, today, houses |

**The customer sees only the checked panes** (the same rule as the PDF, `reports.shown()`); the astrologer sees all, the unchecked ones marked **Draft**. A pane that is folded on a phone says its one line; on a desktop every pane is open. A pane that cannot be drawn is left out
and logged; it never takes the page down.

**Where it is.** The customer's page is servicehq's `my/report` (a section `Report View` fed by `free_reports.report_view`, which answers only the person's own report, and only once it is Ready; the vertical's entry in the vocabulary says which view: `"view": "raftor_astrohq.report_view.customer_view"`).
The astrologer's page is **`provider/chart?booking=<booking>`** (role Service Provider only; anyone else goes to the join page). It is a *wide* page (websitehq: no left menu, no page container, the whole window): a strip across the top (the person's name, who
they are to the customer, the birth line, **Back to your bookings** and **See <name>'s chart** for each other person the customer shares) and under it the board of panes, four columns on a big screen (about 1050 px tall at 1920 px wide), three on a laptop, one on a phone with
the chart, the planets and the running period open and the other panes folded to one line. The astrologer reaches it from **View chart** on the booking in their bookings list (servicehq asks the vertical for `booking_actions`; the action is there only when the booking
is the astrologer's own and the customer shares a birth profile). One endpoint answers the whole page (`report_view.chart_view`).

**Who may open a customer's chart** (`report_view.chart_view`; nothing else is ever checked on the page itself):

| Rule | How |
|---|---|
| Only the astrologer of that booking, and the team | any other signed-in person gets the same "That was not found." as for a booking that does not exist |
| Only a booking that is Requested, Confirmed or Delivered | not a declined, cancelled, missed or expired one |
| Only a birth profile the customer shares | their own ("Themselves"), and a family member's only when the customer ticked **Permission Given** for it; the other people the customer shares are links in the strip at the top of the page |
| A birth time is needed | without it the page says so in words (no chart can be drawn), and the strip is still there to go to another person |
| What is kept | the engine's answers are kept for the customer, never for the astrologer, and go with the customer |

**Safe to put on a page.** An app may send a block of markup only by a method it lists in the hook `rfhq_trusted_html_sources` (astrohq lists the chart page, servicehq the report page), and websitehq's `report_html.clean` keeps an allowlist of tags and attributes before it reaches the page:
layout and table tags, `details` and `summary`, a link to a page of this site (a path: never one with a scheme or `//`) and the tags of a small inline drawing; classes that begin `rv-`; colours that are numbers, hex, or `var(--rv-...)`; never a script, form, frame, image from an address,
`style` (except the colour variables on the root) or `url()`.
The colours come from the site's theme (the report view reads them as variables), so a site's brand shows without a line of code here.

**The drishti** is the hub's (engine 1.2.0, CORE_STANDARD and CORE_ADVANCED carry `drishti`): `astrohq` imports no astrology library. Until the running engine is 1.2.0 the pane is simply not shown; after the engine is updated put today's date in
**Astrology API Settings, Kept Answers Are Good From**, so that a person's earlier kept answer is asked for again and carries it.

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
found wrong for about four couples in ten. The API (1.1.1, and 1.2.0 after it) works four points out itself and takes four from the library; every one is tested against the published rules
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
- One tap for the next report from the answers already kept; the layouts as records in Desk (a team member ticking a section checked there instead of in the file); web pages for the dasha, KP, panchang and match reports (only the kundli and the detailed report have a page of panes today);
  the Tajaka chart of the year ahead (needs the hub to take a year). Remedies.
- "Report ready" messages (notifications are the last topic). The report is made in the request that confirms the code, so it is normally ready before the person looks; make it a background job if the astrology
  service ever becomes slow.
- Views of the astrologer's own (a saved list of panes per astrologer), and a tab bar of more views (Dashas, Strength, KP, Yogas); today there is one wide view.

## Checks

- Unit tests, on the engine's answers for two invented births (no service needed): `bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_kundli_reports`
  (the last class asks the real service and the real list, and is skipped where they are not set up); servicehq: `--app raftor_servicehq --module raftor_servicehq.tests.test_reports`;
  places: `raftor_astrohq.tests.test_places`.
- The panes, the web page and the astrologer's page: `raftor_astrohq/tests/test_report_view.py` (27), `test_astrologer_chart.py` (15), `raftor_websitehq` `test_report_html` (what may reach a page), `test_feed` and `test_page_sync` (the wide page); servicehq `test_booking_api` (the "View chart" action). Each was also broken on purpose, one way at a time (who may open a chart, what a customer is shown, the link rule, the wide page, the sub-lord columns): every break was caught.
- The free way: `raftor_servicehq/tests/test_free_reports.py` (79), `raftor_astrohq/tests/test_free_report_hooks.py` (14) and the sign-in's own `raftor_websitehq` tests (`test_auth_mobile_stub`, `test_auth_password`).
- Browser, a stranger from the product page to the report, then the same person signing back in with the number and the password, a report for a child, the limit, a report that cannot be made and the business team:
  `python3 apps/raftor_astrohq/e2e/free_reports_journey.py` (the two items are switched on and put back as they shipped).
- Browser, the paid way as a stranger, two customers and the business team (the items are priced for the run and put back as they shipped; the gateway's confirmation is stood in for):
  `JOURNEY=reports_journey python3 apps/raftor_astrohq/e2e/reports_journey.py`.
