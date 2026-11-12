# The days a person of astrohq follows (the domain side of servicehq's day reminders)

servicehq does the reminding (see its `docs/day-reminders.md`: the records, the pages `/my/reminders`, the schedule, the message). astrohq only says what a day is, through the hook `servicehq_day_reminders` (`day_reminders.py`, `definition`).

## What a person can choose
Any of: **tithis** (Pratipada to Chaturdashi, Purnima, Amavasya) with a **fortnight** (Shukla, Krishna or Both), **weekdays**, **special days** (Ravi Pushya, Guru Pushya, Sarvartha Siddhi, Amrit Siddhi). A reminder holds on a day when **any** of the things it names holds; the message says which one the day is. Purnima and Amavasya need no fortnight.

## How a day is known (`day_reminders.py`)
* `facts(date)`: the Panchang's engine answer for the day at the Panchang's town (`panchang.day`): the tithi at sunrise with when it begins and ends, the weekday, the nakshatra (it counts for a special day when it holds at sunrise or begins before the next sunrise). No AI.
* `follows`, `title_of`, `text_for`, `link`, `clean`: the rule, in words, and what the person chose, checked.

## Limits to know
* One town for all (the Panchang's), not each person's own.
* Tithis are kept by the tithi at sunrise. Traditions differ for some vrats (Pradosh is the evening's Trayodashi, Ekadashi can be kept on the next day): an astrologer should confirm. The special days' rules are the commonly printed ones.

## History
The first version lived in astrohq (Astro Reminder, its own pages and schedule). The patches `move_reminders_to_servicehq` (the records, the old message) and `hand_reminder_pages_to_servicehq` (the pages change hands) moved it; a site that never had reminders has nothing to move.

Tests: `tests/test_day_reminders.py` (the days, the words, what a person may choose).
