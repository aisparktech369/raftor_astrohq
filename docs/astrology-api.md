# The astrology API in AstroHQ

AstroHQ does not calculate charts. It asks the **hub's `astrology` API**, and the hub passes the request on to the astrology engine
(inside the hub, or on AWS Lambda: see the hub's `deploy/astrology-lambda/README.md`).

```
AstroHQ  --(API key, https)-->  the hub (API Registry: astrology)  -->  the engine (Lambda or in the hub)
```

What exists today is the **plumbing**: the settings page, the client code and the checks. No screen shows a chart to anyone yet (see
"Not built yet").

## To switch it on

| Where | What |
|---|---|
| The hub, Desk | Give AstroHQ a place in the hub: a Customer (for example "AstroHQ") with a Subscription on the **Internal** plan (no limit on calls). Issue it an API key. The key is shown once. |
| The hub, Desk, API Registry, `astrology` | Approved and Active. If the engine runs on Lambda, set it to REST as the hub's README says. |
| AstroHQ, Desk, **Astrology API Settings** (System Manager only) | Hub Address (`https://...`), API Key, leave the name `astrology`, tick **Charts Are Available**, Save. |
| Same page | Press **Check the Connection**. It asks the hub whether it accepts the key (this counts no call), then has the engine make one sample chart. The page keeps what the hub said and when. |

The check can be pressed before charts are switched on.

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
| `AstrologyUnavailable` | charts are off or not set up; the hub or engine did not answer; the key was refused (401), the plan does not include the API (403), the API's name is wrong (404), or the calls are used up (429) | the message says which; fix the settings, the key or the plan, or try again later |

## Privacy and the licence boundary

- Only the calculation numbers leave AstroHQ. The hub logs that a call happened (which key, which operation, how long), not the birth details,
  and the engine on Lambda logs the same and stores nothing. AstroHQ keeps no copy of a chart.
- The engine uses PyJHora and Swiss Ephemeris, both **AGPL**. AstroHQ stays a separate program that only asks over the web: **never
  `import jhora` or `import swisseph` in AstroHQ.** `tests/test_astrology.py` fails if anyone does.

## Not built yet

- **Places.** A birth profile holds the place as text only. A chart needs latitude, longitude and the time zone offset, so a place has to be
  turned into those (a place list or a lookup, and the time zone rule for that date), and the profile or the screen has to keep them.
- **The astrologer's chart screen.** Who may see whose chart (the astrologer of a booking, the person themselves), what is shown, and
  where. `astrology.chart` checks nobody; the test `test_nothing_that_makes_a_chart_can_be_called_from_the_web` keeps it off the web until a
  screen does the checking.
- **Source offer.** The people who use the engine through AstroHQ are owed a link to its source (the hub's README, "Licences").

## Checks

- Unit tests: `bench --site astrohq.local run-tests --app raftor_astrohq --module raftor_astrohq.tests.test_astrology`
- Browser (the owner, an accounts user and a Business Team user, against a stand-in hub): `JOURNEY=astrology_check python3 e2e/astrology_settings_check.py`
- Against the real hub: done on 2026-10-23 with a throwaway key on the local hub (check of the connection, CORE_BASIC, PANCHANGA, MATCH_CALC, a
  profile-made birth, a refused month, a wrong key, an unknown API name); the key and everything it made were removed afterwards.
