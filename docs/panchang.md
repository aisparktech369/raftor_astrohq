# Today's panchang and chaugharia (built 24 Oct 2026, after the owner's "Yes")

**Status: the engine, the data and limits, the Panchang page and the glass card over a banner are built and tested. Nothing is switched on at Home; the page and the card are quiet until the owner names a town in Settings, and the card is on no page until the owner says.**

The owner asked (24 Oct 2026): today's panchang over the Home banner "like showing weather in overlay, transparent, very intuitive", the numbers from **our own astrology API**; chaugharia added, panchang first and chaugharia second but prominent; the page to go to **any date and any town**, with the next 7 days; a small muhurat button kept.

## What is built

| # | Piece | Where | State |
|---|---|---|---|
| 1 | The day's numbers (opcode `PANCHANGA_DAY`, hub engine 1.3.0): the tithi, nakshatra (with pada), yoga and karana with when each begins and ends and what follows, sunrise and sunset, moonrise, moonset and how much of the moon is lit, Rahu Kaal, Gulika, Yamaganda, Abhijit, and the chaugharia (eight by day, eight by night, good or avoid) | hub `astro_pipeline/engine/panchang_day.py`, `deploy/astrology-lambda/README.md` | built, tested; local branch `astrology-lambda`, **not pushed** |
| 2 | A day at a town, kept once, with limits, and a town found by its first letters or by where the visitor is | `panchang.py`, `places.py` | built, tested |
| 3 | The Panchang page: the bar (day and town) and the panes | `panchang_panes.py`, `views/panchang.json`, websitehq Report View | built, tested in a browser (desktop and phone) |
| 4 | The glass pill and card over a banner | websitehq's Pop-over section + library cards; AstroHQ answers only field values (`panchang.widget_cards`, `panchang_widget.py`) | built, tested in a browser (desktop and phone) on a throwaway page |
| 5 | Switched on at Home | `sites/astrohq.local/site_pages/home.py` (one section just before the banner's, see below) | **only when the owner says** |

## What a visitor sees on /panchang

The bar: ‹ the day › (the browser's own calendar, "Today" when away from today), the town (a search of names, "Use my location"). Under it, in this order, which is also the order on a phone:

1. **Panchang**: tithi, nakshatra, yoga, karana and the weekday, each with when it ends and what comes next; beside it the moon as it is lit ("Waxing · 94% lit") and sunrise, sunset, moonrise, moonset. The day's tithi and nakshatra are the ones at sunrise, and the page says so.
2. **Chaugharia**: the day's eight and the night's eight, good (Amrit, Shubh, Labh, Chal) or avoid (Udveg, Rog, Kaal); the one running now is marked on today's page, and on a phone the table that holds it comes first.
3. **Times to know**: Rahu Kaal, Gulika, Yamaganda (avoid) and Abhijit muhurat (good), the one on now marked.
4. **The next 7 days**: a tile for each (tithi, nakshatra), the day shown marked; folded on a phone.
5. **A muhurat**: "Ask a Pandit ji for a muhurat" with one button, only when the service is on and an approved Pandit ji offers it.

Any day from 1 Jan 1800 to 31 Dec 2399 (the years the engine was checked over); an address outside them is taken to the nearest end. The town and the day are in the address (`/panchang?date=2026-11-08&place=1275339`), so a page can be shared; the town chosen is also kept in the visitor's browser and used when the page is opened without one.

## Settings (Desk: Astrology API Settings, "Today's Panchang")

| Setting | What it does | Default |
|---|---|---|
| Place for the Panchang | The town shown to a visitor who has chosen none ("Delhi, India"). **Blank = the Panchang is off** (the page shows nothing) | blank |
| Service the Muhurat Button Leads To | The service of a Pandit ji for a muhurat. The button shows only when it is switched on and an approved Pandit ji offers it | blank |
| Topic Sent With the Muhurat Button | What the booking says it is about | Auspicious date |
| New Days Worked Out In A Minute, At Most | The safety limit on days and towns the engine has not worked out yet; over it a visitor is asked to try again in a moment (what is kept is always shown) | 60 |
| Requests A Visitor May Make In A Minute | Per visitor, for the page and the town search | 40 |

## How it is made safe and cheap

- **Our own engine only.** AstroHQ imports no astrology library (the AGPL rule; `test_astrology.py` scans for it). It asks the astrology service for `PANCHANGA_DAY` with the date, latitude, longitude and time zone of the town; the other birth fields are ignored.
- **A day at a town is worked out once** and kept (compressed, in the cache): 8 days for the default town, 1 day for any other; the default town's day and the week after it are worked out shortly after midnight (scheduler, `panchang.warm`) so the first visitor waits for nothing. "Kept Answers Are Good From" in the same settings throws away what was worked out before a date.
- **A visitor cannot make the engine do unlimited work**: a limit on new days a minute, a limit per visitor, and a town is only ever one the list knows (a number from the list, never free text).
- **What the engine writes is never markup**: every word is escaped and the page's markup is cleaned by websitehq (`report_html`), which keeps only tags, attributes and classes it knows.
- **The town list** is GeoNames' (CC BY): `places.suggest` ranks a name written whole first, then the bigger towns; another name of a place ("Bombay") counts as its name from four letters, so that a short nickname of a small place does not come before Mumbai.
- **Not a promise of the sky.** The numbers are the engine's (Lahiri, true positions, the sun rising at the centre of the disc with no refraction, the library's convention); the page does not claim more. The hub's tests check the engine against independent calculations; an astrologer should still read one day against a printed panchang before this goes live (see "The owner's").

## Tests

- hub: `cd services/astrology/src && PYTHONPATH=. ../venv/bin/python -m unittest raftor_apimanager.tests.test_astrology_panchang_day`
- astrohq: `raftor_astrohq.tests.test_panchang` (the day kept once, limits, the town, the running part, the page's markup, the moon's picture, the town search), `test_places`, `test_report_view` (the board's look)
- websitehq: `test_report_toolbar`, `test_feed`, `test_report_html`
- a browser: `python3 apps/raftor_astrohq/e2e/panchang_journey.py` (38 checks on a desktop and a phone; it names a town for the run and puts the setting back)
- breaking the code on purpose, one way at a time, and watching the tests fail each time, was done for the engine, the data layer, the panes, the town search and the bar's checks.

## The owner's

| To decide or give | Why |
|---|---|
| The town the page shows first (Delhi in the pictures) | blank = off; the page is quiet until it is named |
| Whether "Chal" is good or neutral | the library says good; many printed chaugharia say neutral |
| The muhurat service (price, minutes, switch on) and a Pandit ji for it | the button shows only then; SVC-07174 "Muhurat" and SVC-07175 "Shadi date" exist as drafts |
| When to put the pill over the Home banner | built next; switched on only on the owner's word |
| Deploying hub 1.2.0 and 1.3.0 to the live server | the live server still runs the older engine; never push the hub's `main` without the owner (a push deploys) |
| A check by an astrologer against a printed panchang for a day or two | the numbers are the engine's, not an authority |

## The card over a banner: websitehq's pieces, AstroHQ's data

AstroHQ writes no markup and no look. It answers a list of items, each naming a card of websitehq's library and giving that card's own fields; websitehq draws them in the site's Glass (`SIGNIN_AND_PAGE_KIT.md`, "Pop-over").

| What the visitor sees | Library card | Fields AstroHQ gives |
|---|---|---|
| the pill (stays on view): moon, tithi running now, "Chaugharia: Shubh · good" | Pill Card | `icon` (one of the eight moon emoji, from how much is lit), `title`, `body`, `tone` |
| the tithi, with the day, the town, when it ends and what follows | Feature Card, layout Icon Left | `icon`, `tag`, `title`, `body` |
| the chaugharia as a bar of its eight parts, the one running marked, what comes next | Parts Bar | `steps`, `tones`, `current`, `heading`, `heading_note`, the two ends, `note` |
| nakshatra, sun, Rahu Kaal, Abhijit (as they stand now: starts in, on now, over) | Stat Card | `label`, `value`, `description`, `tone` |
| yoga, karana | Fact Card | `label`, `value`, `description` |
| "Important work? Ask a Pandit ji for a muhurat" (only when it can be asked for) | Focus Card | `tag`, `title`, `body`, `link_url`, `link_label` |

It is about this moment: the tithi, nakshatra, yoga and karana **running now** (the page shows the ones at sunrise, as a printed panchang does), found in the answer of the day that holds the moment and the day after, so that it is right across midnight and sunrise. The town is the one the visitor kept on the Panchang page (`rfhq:lookup:place`), else the default town; the card says which, and its link goes to the Panchang page, where the town and the day are changed. The card asks again every 60 seconds while the page is on screen.

To put it on Home (only when the owner says): in `home.py`, one more section placed just before the banner's section:
`section("panchang", content_source="App Records", records_source="raftor_astrohq.panchang.widget_cards", records_card="Stat Card", records_args="{}", records_kept="place", records_refresh=60, columns="2", popover="Top Right", surface="Glass", section_padding="None", gap="Small", records_links=json.dumps([{"label": "The full panchang, night chaugharia and the next 7 days →", "href": "/panchang", "kind": "secondary", "where": "bottom"}]))`
Tests: `test_panchang` (`TestTheCardOverTheBanner`, `TestTheMoonMark`); browser: `python3 apps/raftor_astrohq/e2e/panchang_widget_journey.py` (builds a throwaway page, names a town for the run, removes both).
