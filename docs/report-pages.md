# Reports as web pages and branded PDFs (design, 2026-10-23)

**Status: built in the order below up to the astrologer's page (owner's yes, 23 Oct 2026; details and checks in `reports.md`): the arranger, the brand for documents, the kept answers, the reports made from a layout with the checked-sections rule, the panes and the customer's web page, the drishti in the hub (engine 1.2.0), the astrologer's wide page. Not yet: one tap for more (4) and the layouts as records in Desk (6).** The owner asked (23 Oct 2026): "design this available functionality to integrate for
optimum utilisation and features... we can keep them free... platform agnostic, web based feature alongwith branded pdf report"; then, after the second ask below: "Build it".

## The idea in four lines

1. A person gives their birth details **once** (the free report's one-page form, already built).
2. The system asks the astrology API **once per person and mode** and keeps the answer, private to that person.
3. Every report is **a layout over the kept answer** (`layouts/*.json`): the same data is a **web page** (phone first, any browser, the PWA shell) and a **branded PDF**.
4. All free. Each report ends with the same next steps (the free first session, another report for the family, the other free reports), and an astrologer the person books can open the report.

The pictures that went with this (a web page on a phone and on a desktop, the branded PDF's first page) were made from the real arranged answers with the site's own logo and theme colours.

## Pieces

| # | Piece | Today | To build | Where |
|---|---|---|---|---|
| 1 | **Brand for documents** | the PDF says the site's name in small type, in a fixed purple | one function reads the site's name, logo, colours and font names from Website Settings and the Website Theme; PDFs (and later receipts and statements) use it; blank = as before | websitehq `brand.py` (it owns the theme), used by `report_pdf` |
| 2 | **Kept answers** | none: every report asks the API again | a private record per (person, birth numbers, mode, engine version) holding the API's answer (a private file); asked only when missing | astrohq `Astro Answer` |
| 3 | **Reports from layouts** | the arranger and 9 layouts, as pictures | each customer-facing report = a vocabulary entry (title, blurb, modes, layout) made into an Item **switched off at price 0**, one generic maker for all | astrohq `vocabulary.py`, `reports.py` |
| 4 | **The web page** | `my/report` shows a card with the file | the same page shows the arranged report: summary cards, tabs, the tables, a Download PDF button, next steps; wide tables scroll inside their box, the page never scrolls sideways; the running period is marked **today** | websitehq section "Report Body" fed by an astrohq method; servicehq page `my/report` |
| 5 | **The PDF** | kundli and match | any layout, in the brand, a dated copy ("made for you on ..."); cover with logo, name and birth details; footer with the brand and the page number | `arrange.html` + brand |
| 6 | **One tap for more** | "Get it free" opens the form again | the person's saved details make the next report at once, from the kept answer (no API call) | servicehq `next_steps`, `free_reports.cards` |
| 7 | **The astrologer's page** | none | one wide page of panes (below) for the customer of a booking: **all sections**, the unchecked ones marked Draft; only with the customer's consent line | servicehq `proof.can_view`, a card in the astrologer's booking; astrohq panes |
| 8 | **Team control in Desk** | layouts are files | a Report Layout record per layout, synced from the files on migrate (like page definitions), so the team changes what a report shows and ticks a section **reviewed** | astrohq doctype |

## How it fits what exists

- **Number of API calls.** CORE_ADVANCED (0.6 s, 727 KB) holds everything of SUPER_BASIC, CORE_BASIC and CORE_STANDARD and the panchang; so **three calls per person** feed seven of the ten modes:
  CORE_ADVANCED, DASHA_CALC (1.8 s with the default systems) and KP_SYSTEM (0.01 s). MATCH_CALC is one call per pair. The hub meters calls per key, so the kept answer is also the saving. Sample timings: SUPER_BASIC 0.7 s, PANCHANGA 0.03 s,
  CORE_BASIC 0.33 s, CORE_STANDARD 0.38 s, ANNUAL 0.32 s, TRANSIT 0.31 s, MATCH 0.67 s.
- **The Free Report record** (servicehq) stays the person's list of reports and the owner of the file; it gets a pointer to the kept answers its report was made from. A report made earlier is never changed: its PDF is the copy of that day.
- **The web page is alive, the PDF is dated.** The page marks the period running *today* from the kept answer; the PDF marks it as on the day it was made.
- **No library in AstroHQ.** The arranger imports no astrology library (the AGPL rule; `test_astrology.py` checks it). The credit and the source link of the engine go into the footer of the PDF and the page (`ASTROLOGY_SOURCE_URL`, the owner's and the lawyer's).
- **Platform agnostic.** The web page is plain HTML any browser opens, also inside the PWA shell and in the browsers of chat apps; the PDF opens anywhere and is shared like any file. Nothing in the layout engine knows astrology: the words (`engine_words.json`, the formatters) are astrology's;
  when a second vertical needs it the engine moves from AstroHQ to the platform with only those words left behind (decide then, not now).

## Guardrails

| Guardrail | How |
|---|---|
| **Only checked sections reach customers** | a section of a layout carries `reviewed`; a customer's page and PDF show reviewed sections only; an astrologer (and staff) see all, the others marked Draft; a setting shows all on a demo. Start with what the live kundli already says. The yogas stay Draft until checked (two of six I tried by hand are wrong). |
| **Privacy** | birth details are personal: the kept answer, the file and the page belong to the person; an astrologer sees them only for their own booking and the customer's consent line; **no public share links** (the person shares the PDF themselves). |
| **The API is one at a time** | the existing Being made > Ready workflow, the hourly retry and Needs attention stay; a report from a kept answer never waits. |
| **Daily limit** | counts reports that needed the API; one from a kept answer is free of it (to confirm). |
| **The logo** | the site's logo moves (an animated SVG); a PDF needs a still one: a second logo field for documents, drawn once. |
| **Fonts** | the brand's fonts (DM Sans, Fraunces) are web fonts; the PDF engine cannot load them, so PDFs use a serif and a sans until the font files are installed on the server and named in the style. |
| **Nothing hard-coded** | name, logo, colours, footer lines, the report titles and which sections show all come from the site's data and the layout files. |

## Build order (each step: screens, role permissions, tests, a browser check, docs, a local commit; items stay OFF)

1. Brand for documents (piece 1) with a test on the theme's contrast; the kundli and match PDFs take it (blank = as before).
2. Kept answers and the generic maker (pieces 2, 3) with the first reports as OFF items: the owner's choice of names and of which sections are reviewed.
3. The web page (piece 4), checked on a phone and a desktop in the PWA shell; the PDF button (piece 5).
4. One tap for more (piece 6).
5. The panes and the condensed web view (below), then the astrologer's page (piece 7).
6. The layouts in Desk (piece 8).

Later, and not part of this: **Year ahead** and **Transit today** need the hub's API to take a year and a date (today ANNUAL_CALC has one fixed year and TRANSIT_CALC takes no date); "report ready" messages (notifications are last); Hindi.

## Which reports (to decide with the owner; names are the owner's)

| Report for the customer | From | Pages | Note |
|---|---|---|---|
| Kundli | SUPER_BASIC (in the kept CORE_ADVANCED) | 2 | what is live today |
| Detailed kundli | CORE_ADVANCED | 8 | the reviewed sections only |
| Match making | MATCH_CALC | 1 | live today |
| Dasha periods | DASHA_CALC | up to 35 | Vimshottari first, the other systems after; or for astrologers only |
| KP chart | KP_SYSTEM | 3 | |
| Panchang of the birth day | PANCHANGA | 1 | |
| Yearly, Tajaka | ANNUAL_CALC, TRANSIT_CALC | 1 + 1 | wait for the API to take a date |

## The astrologer's page and the condensed view (second ask, 23 Oct 2026)

The owner sent a screenshot of Parashara's Light (one wide screen of panes: the birth chart, six divisional charts, the dasha list, the planets, shad bala, karakas, "today from lagna") and said:
condense the web views (a lot of information, use the space wisely); show drishti as a matrix with each planet as a row and a column and the drishti where they meet; "we need an astrologer page, one wider page view like this".
Pictures of both were made from the real answers for the sample birth (`final-astrologer-page`, `final-condensed-desktop`, `final-condensed-phone`).

**One block, many pages.** A *pane* is a titled box that shows one part of the answer (a chart, a table, bars, a matrix, a list). A *view* is a grid of panes, written as data like the layouts
(`views/*.json`: pane, column, row, how wide). The astrologer's page is the view "Birth chart" at 1920 px (four columns, four rows, about 1100 px tall: no scrolling on a full-HD screen) with the other views as tabs
(Dashas, Strength, Transits, KP, Yogas (draft), and "+ New view" for the astrologer's own); the customer's condensed view is the same panes in three columns; on a phone the same panes in one column,
two open and the rest shut with **one line of what they say** ("Drishti: Ma→Mo 58, Sa→Ve 56").

| Pane | Made from | API call |
|---|---|---|
| Birth chart, wide, with each planet's degree; facts beside it (lagna, Moon sign, star, tithi, yoga and karana, weekday, running period, ayanamsa, manglik, kala sarpa) | CORE_ADVANCED (`planetary_positions`, `lagna`, `panchanga`, `dosha`) | the kept answer |
| Divisional charts (D9, D10, D7, D24, D60, D4; the astrologer picks any of the 16 from the pane's list) | `divisional_charts` | the kept answer |
| Planets: degree, sign and its lord, house, nakshatra and pada, star, sub and sub-sub lord (KP), D9 sign | `planetary_positions` + KP_SYSTEM `planets` | + KP_SYSTEM |
| Vimshottari: the running line, the sub-periods, the next main periods; levels 1 to 6 chosen in the pane | `dasha_sequences` (`dasha_levels` 3 asked) | the kept answer |
| **Drishti matrix** (below) | **not in the API today** | needs the hub |
| Shad bala: bars of total rupas, green when the planet has what it needs | `shadbala.components` | the kept answer |
| Karakas (AK to DK), special lagnas, arudhas | `planets.info`, `arudha` | the kept answer |
| Today from lagna: today's planets in the person's houses; any date can be picked | **a chart asked for that date** (the same API, a "birth" at that moment), each planet's sign placed by the person's lagna | + one SUPER_BASIC call per date |
| Houses (two columns), panchang strip, yogas (Draft) | `houses`, `panchanga`, `yogas` | the kept answer |

**Drishti as a matrix.** Each planet is a row (looking) and a column (looked at); where they meet is the drishti in virupas (60 is a full aspect; the special aspects of Mars, Jupiter and Saturn are in it), shaded darker for stronger,
the diagonal empty; a second block of 12 more columns (the houses) is the same table with `include_houses`. PyJHora has it (`strength.planet_aspect_relationship_table`, rows aspecting, columns aspected) but **no mode of the API returns it**
(KP_SYSTEM has the western aspects, SHADBALA only each planet's net Drik bala), although the engine's own list of what a mode holds (`opcode_matrix.py`) already names "House & Aspect Logic" as **mandatory** for CORE_STANDARD and CORE_ADVANCED: it was promised and never filled. A small change in the hub's engine (our code, version 1.2.0) adds `drishti` to CORE_STANDARD and CORE_ADVANCED; the picture's numbers were asked from the library directly
for the sample birth, never through AstroHQ. Checked by hand: Mars (Leo) on the Moon (Pisces) is its 8th aspect, 58 virupas; Rahu and Ketu 60 on each other.

**Today's sky needs no new API.** A chart for 23 Oct 2026 at the birth place gives each planet's sign that day; the person's lagna turns the sign into a house. (This corrects the earlier note that "transit today" needed the hub to take a date: only the Tajaka
**annual chart** (the year ahead, from the solar return) does. TRANSIT_CALC and ANNUAL_CALC stay as they are.)

**Condensing rules** (so every pane says more in less): dense by default and expandable (a shut pane keeps one line); tables in 12 px with 1 to 2 px of padding, no wide gaps (extra columns use the width: sign lord, D9 sign, KP lords); two tables side by side before one below the other;
houses in two columns of six; sign names in three letters on a phone, full names on a desktop; degrees without minutes in a small chart, with them in the wide one; planets tinted as readers know them (benefics green, blue and gold, malefics red); charts the shape of their room
(a wide rectangle where the pane is wide); a wide table scrolls **inside** its pane, never the page; touch targets 44 px on a phone.

**Who may see it.** The astrologer's page is for the customer of the astrologer's own booking and only with the customer's consent line; staff in Desk; nobody else. The same panes with only `reviewed` sections are the customer's view. The page asks for the kept answers of that person
(three calls once, the date's chart when the pane is opened).

**To decide:** the first view's panes; whether an astrologer may save views of their own (a pane list is a small record per person); the hub's `drishti` (1.2.0) and its tests; the default dasha level (3).

## Notes from the pictures

- A heading and its table must not be parted at a page end: a heading is the table's caption, a note its last row (`reports.md`).
- On a phone the page must not scroll sideways: the page's column is `minmax(0, 1fr)` and each wide table scrolls inside its own box.
- A class name the page uses (`grid`) must not clash with the arranger's: the arranger's classes are to be prefixed when it goes on the site.
