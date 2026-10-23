# The astrology API in AstroHQ

AstroHQ does not calculate charts. It asks **the astrology API**, a program of its own (the hub's astrology engine), in one of two ways, chosen on
the page **Astrology API Settings**:

```
Straight to the astrology API (the MVP):  AstroHQ --(key)--> the astrology service on this server (127.0.0.1:8795)
                                          AstroHQ --(key, https)--> an AWS Lambda function with the same contract (later)
Through the hub:                          AstroHQ --(key, https)--> the hub (API Registry: astrology) --> the engine (Lambda or in the hub)
```

What exists today is the **plumbing**: the service on this server, the settings page, the client code and the checks. No screen shows a chart to
anyone yet (see "Not built yet").

## The MVP way: the service on this server

It lives beside the bench, in `services/astrology` (not inside any Frappe app, on purpose: its libraries are AGPL, see below).

| What | Where |
|---|---|
| The program | `services/astrology/src`, a clone of the hub's repository, branch `astrology-lambda` (the hub's `deploy/astrology-lambda/README.md` says how it works). Update with `git -C src pull`, then restart. |
| Its own Python | `services/astrology/venv`: PyJHora 4.6.0 and the packages pinned in `requirements.txt`, and the star-position files (checked by SHA-256) |
| Its key | `services/astrology/engine.env`: `ASTROLOGY_API_KEYS` and the port 8795. Readable by the owner only. The same key is in Astrology API Settings. |
| Starting it | the line `astrology: services/astrology/run.sh` in the bench's `Procfile`: `bench start` runs it. `run.sh` starts it again within 3 seconds if it ever stops, so its trouble never stops the bench, and it does not start a second copy when one already answers. |
| Who can reach it | only programs on this server: it listens on `127.0.0.1` and has no TLS. Never open its port to the internet. |
| Its log | `logs/astrology.log` (one line per request: an id, the operation, the outcome, the milliseconds; never a birth detail) |
| Its speed | one request at a time (the library keeps settings in module-level state); a chart takes under a second |

To check it by hand:
`services/astrology/venv/bin/python services/astrology/src/deploy/astrology-lambda/smoke_test.py --url http://127.0.0.1:8795/ --key "$(grep ^ASTROLOGY_API_KEYS services/astrology/engine.env | cut -d= -f2)"`

On the live server the same folder is set up again (steps 1 to 6 of "One server, no AWS" in the hub's README) and the Procfile line goes into the
live bench's Procfile.

## To switch it on

| Where | What |
|---|---|
| AstroHQ, Desk, **Astrology API Settings** (System Manager only) | **How AstroHQ Reaches It**: *Straight to the astrology API*. **Address**: `http://127.0.0.1:8795`. **API Key**: the one in `engine.env`. Tick **Charts Are Available**. Save. |
| Same page | Press **Check the Connection**. It asks the service who it is and whether it is ready, then has the engine make one sample chart. The page keeps what it said and when. |

The check can be pressed before charts are switched on. To go through the hub instead, choose *Through the hub*, give the hub's address, the key the
hub issued to AstroHQ (on the hub: a Customer such as "AstroHQ" with a Subscription on the **Internal** plan, which has no limit on calls) and the API's
name in the hub's API Registry (`astrology`, Approved and Active; set to REST if the engine runs on Lambda).

## What can be asked

`astrology.chart(birth, opcode)` returns the engine's answer for these operations. The sizes and what each holds are in the hub's README.

| Operation | Gives |
|---|---|
| `SUPER_BASIC`, `CORE_BASIC`, `CORE_STANDARD`, `CORE_ADVANCED` | the chart: lagna, planets (sign, degree, house, nakshatra, pada, retrograde), houses, divisional charts, dasha; more in each |
| `MATCH_CALC` (give `partner=`) | Ashtakoota score out of 36 and the manglik and pitru dosha of each person |
| `DASHA_CALC`, `ANNUAL_CALC`, `TRANSIT_CALC` | dasha systems, the yearly chart, transits |
| `PANCHANGA` | tithi, nakshatra, yoga, karana, weekday and its lord, sunrise, sunset, lagna |
| `KP_SYSTEM` | KP planets, cusps, lords, significators |

A chart is made from **numbers only**: year, month, day, hour, minute, second, latitude, longitude and the time zone offset (hours east of
Greenwich on that date and place; +5.5 for India, +1 for London in summer 1972). Nothing else is sent: not the name, not the place's name.
`astrology.birth_data(profile_row, latitude, longitude, timezone_offset)` makes those numbers from an Astro Birth Profile row, and says in
words when the time of birth is not known (no lagna or houses without it).

```python
from raftor_astrohq import astrology
born = astrology.birth_data(row, latitude=18.5204, longitude=73.8567, timezone_offset=5.5)
data = astrology.chart(born, "CORE_BASIC")
```

## When it does not work

`chart` raises one of two errors. Both are Frappe validation errors, so a web caller gets the message.

| Error | Means | What to do |
|---|---|---|
| `AstrologyRefused` | the birth details or the operation were not accepted; the message says which | put the details right; asking again as it was will not help |
| `AstrologyUnavailable` | charts are off or not set up; the service or hub did not answer; the key was refused (401); through the hub, the plan does not include the API (403) or the API's name is wrong (404); the service is not ready (503); or the calls are used up (429) | the message says which; fix the settings, the key or the plan, start the service (`services/astrology/run.sh`), or try again later |

## Privacy and the licence boundary

- Only the calculation numbers leave AstroHQ. The service logs that a call happened, not the birth details, and keeps nothing; the hub, when used,
  logs which key called which operation and how long it took. AstroHQ keeps no copy of a chart.
- The engine uses PyJHora and Swiss Ephemeris, both **AGPL**. AstroHQ stays a separate program that only asks over the web: **never
  `import jhora` or `import swisseph` in AstroHQ**, and the service has its own folder and Python environment, not the bench's. A test fails if
  anyone imports them in AstroHQ.

## Not built yet

- **Places.** A birth profile holds the place as text only. A chart needs latitude, longitude and the time zone offset, so a place has to be
  turned into those (a place list or a lookup, and the time zone rule for that date), and the profile or the screen has to keep them.
- **The astrologer's chart screen and the report offerings.** Who may see whose chart (the astrologer of a booking, the person themselves),
  what is shown, and where; and the kundli and matching reports a customer can buy. `astrology.chart` checks nobody; the test
  `test_nothing_that_makes_a_chart_can_be_called_from_the_web` keeps it off the web until a screen does the checking.
- **Source offer.** The people who use the engine through AstroHQ are owed a link to its source (the hub's README, "Licences").

## Checks

- Unit tests: `bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_astrology`
- Browser (the owner, an accounts user and a Business Team user, against a stand-in that answers both ways; it refuses to run while the page is
  switched on, so it can never wipe a real setting): `JOURNEY=astrology_check python3 e2e/astrology_settings_check.py`
- Against the real hub: done on 2026-10-23 with a throwaway key on the local hub. Against the real service on this server: done the same day.
