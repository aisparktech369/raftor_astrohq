# My reminders (built 11 Nov 2026, after the owner's "My reminder page.... U get it"; dev only)

A signed-in person says which days they follow and is told before each one. Page `/my/reminders` (in the account menu) lists them (Pause or turn on, Delete) and `/my/reminders/new` adds one.

A reminder names any of: a **tithi** (Pratipada to Chaturdashi, Purnima, Amavasya) with a **fortnight** (Shukla, Krishna or Both), a **weekday**, a **special day** (Ravi Pushya, Guru Pushya, Sarvartha Siddhi, Amrit Siddhi), and when to tell them: the evening before, the morning of, or both. It holds on a day when **everything it names holds** (Ashtami on a Tuesday). Up to 20 a person; the same one twice is refused.

## How it runs (reminders.py)
* The day's facts come from the Panchang's engine answer at the Panchang's town (`panchang.day`): the tithi at sunrise with when it begins and ends, the weekday, the nakshatra (it counts for a special day when it holds at sunrise or begins before the next sunrise). No AI.
* Scheduled at 19:00 (tomorrow's days, "evening before") and 05:30 (today's, "morning of"), site time.
* Sent through ServiceHQ's `messages.send` to Notification HQ, event `astro.reminder`: the email, and its in-app twin (the bell). SMS and WhatsApp when switched on there. The words are a Notification in Desk ("Reminder: a day you follow"), editable.
* Once per reminder, day and time of day (`Astro Reminder Sent`), so a repeated run sends nothing new. A paused reminder or a disabled person is skipped.

## Limits to know
* One town for all (the Panchang's), not each person's own.
* Tithis are kept by the tithi at sunrise. Traditions differ for some vrats (Pradosh is the evening's Trayodashi, Ekadashi can be kept on the next day): an astrologer should confirm. The special days' rules are the commonly printed ones.

Fixed on the way: `vocabulary.pack_services()` read every JSON in `pack/` as a list of services, including `guides.json` (a dictionary), which broke the service sync on migrate; it now reads list files only.

Tests: `tests/test_reminders.py`.
