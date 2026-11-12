# Numerology

A page at `/services/numerology`, open to anyone, drawn by websitehq's **Number Reveal Card** (full screen on a phone). There is no report to wait for: a name and a date of birth go in and the answer is there in a second or two.

- **Ask:** the name (English letters, as the engine counts them) and the date of birth. Nothing else: no time, no place. What is wrong is said by field (`numerology_page.reveal`).
- **The numbers:** worked out by the astrology engine (birth number from the day, name number from the letters, the year number, the zodiac period). A language model never counts. The page shows each number as a medallion, with how it was found (for example `14: 1 + 4 = 5`, the letters of the name and their values) and what it is said to mean (the engine's own reading).
- **Topics:** Self (the engine's own reading), Love, Career, Money, Health, Family. The last five are the app's own plain lines for each number from 1 to 9 (`numerology_topics.py`), plus the engine's text on what goes with the number and how to use it. Free for everyone.
- **The reading of the numbers together:** written by the hub's text-to-text (`hub.py`, the same settings as the daily rashifal) for someone signed in, once per asking, and kept as a **Numerology Reading**. A visitor sees it locked, with the way to sign in; after signing in they return to the same numbers (the token is in the address) and it is written then. The writer is told to use only the numbers, never to forecast and to give no medical, legal or money advice.
- **Consult now** follows the reading and opens Seek guidance showing the numerologists (AI and human).
- **Where it is shown:** the "Numerology" box of the free reports row. The old numerology report (a PDF made from the free report form) is no longer offered; its code and item are still there, switched off, and are not used by this page.
