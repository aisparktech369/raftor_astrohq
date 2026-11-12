# Tarot

A page at `/services/tarot`, open to anyone, drawn by websitehq's **Tarot Draw Card**.

- **Draw:** anyone asks (an optional question) and three different major cards come out of the cabinet one after another (Past, Present, Future), each upright or reversed (one in four). Each card's meaning appears below as it lands. The draw is chosen in `tarot.py` (`secrets`), kept for a day under a secret token, and the token is put in the sign-in address, so coming back shows the same three.
- **The reading of the three together:** written by the hub's text-to-text (the same settings as the daily rashifal: Daily Rashifal Settings) for someone signed in, once per draw, and kept as a **Tarot Reading**. A visitor sees it locked, with the way to sign in; after signing in they return to the same draw and it is written then. The writer is told: reflection, never a forecast, no medical, legal or money advice.
- **Words and meanings** are the app's own: `tarot_deck.py` (22 major cards, number, name, a symbol by a name from websitehq's icon set, keywords, upright and reversed). The page holds no wording.
- **Where it is shown:** the "Tarot reading" box of the free reports row (vocabulary `reports_soon` with a `link`).

Open: the minor arcana (56 cards), Hindi words, and the cards' own artwork if the owner supplies it.
