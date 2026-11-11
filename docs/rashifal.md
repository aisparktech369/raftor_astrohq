# Daily rashifal (built 11 Nov 2026, after the owner's "Ok"; dev only)

Twelve cards at the top of the Consult page, above the free reports: a sign's mark, name and date; a tap turns the card over to bars, not sentences: how love, money, work and health lean (35 to 95, from the sky), a one-word mood, the lucky colour (a swatch) and number. The sentences the writer makes are kept on the record (and could be shown elsewhere) but are not on the card. Free, no sign-in.

## How a reading is made (rashifal.py)

1. **The sky.** The astrology service says where the nine planets stand at sunrise (CORE_BASIC for a moment; sunrise from the Panchang's town, Delhi when none is set, six in the morning when the Panchang cannot say).
2. **The facts and the bars of a sign** (worked out here, no AI; a bar is the share of the planets that speak for that part of life that stand in a good house, `score`): the house each planet is in counted from the sign; whether that is a good house for it by the traditional rule of transits from the Moon sign (`GOOD`); from them how love, money, work and health lean (positive, mixed, careful); the lucky colour and number (those of the first planet in a good house); the sign's element and ruler.
3. **The words.** The hub's `text-to-text` puts the facts in plain English and Hindi, told to use nothing else; its answer is checked (JSON, every part there, Hindi really in Devanagari, English not, length cut, markup stripped) before it is kept. A sign that fails is skipped and retried by the next run.
4. **Kept** as a Daily Rashifal record: Draft until staff publish it (Daily Rashifal Settings "Publish at once" publishes as it is written). Only Published readings are shown, the newest day not older than yesterday.

Scheduled at 04:00 and again at 06:00 (site time, IST): the second run writes only what the first missed. Desk: Daily Rashifal Settings has the hub address, hub site, hub key, and two buttons (write today's now, publish today's drafts).

## Where it plugs in

* servicehq `consult_page` asks every app for bands to put on top (hook `servicehq_consult_bands`, a list of functions that give sections); AstroHQ's is `rashifal.band`.
* websitehq Feature Card has a layout **Flip** (a premium dark card: a gold ring turning round the sign's mark, twinkling stars, a light sweep, bars that fill as it turns; all of it still under reduced motion) (library preset "Flip Card"; `rfhq_flip_card.js`, styles at the end of `rfhq_templates.css`). The sign's mark is in `number` (the `icon` field is an icon name and drops anything else). Both faces share one grid cell, so the card is as tall as the taller face; without the script both faces show one under the other; with reduced motion the faces swap with no turning.

## Limits to know

* One reading per sign for the whole country, from the sky at sunrise. The Moon changes sign during a day, so it is the day as it looks from sunrise.
* The facts are the same for signs whose planets stand alike, so their readings can read alike (a day when Aries, Leo and Pisces all lean careful). A richer rule set would separate them.
* Written by a program from traditional rules, not by an astrologer: have one read a few days against a printed rashifal before publishing. The writer is told never to promise, predict harm, or give medical, legal or money advice.
* Hindi needs a Devanagari font on the device (all phones have one; a bare server may not).

## Tests

`tests/test_rashifal.py` (houses, leans, the check on the writer's answer, a day written once, a failure retried, only Published shown) and servicehq `test_consult_page.py` (a band comes first).
