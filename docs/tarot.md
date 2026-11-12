# Tarot

A page at `/services/tarot`, open to anyone, drawn by websitehq's **Tarot Draw Card**.

- **Draw:** anyone asks (an optional question) and three different major cards come out of the cabinet one after another (Past, Present, Future), each upright or reversed (one in four). Each card's meaning appears below as it lands. The draw is chosen in `tarot.py` (`secrets`), kept for a day under a secret token, and the token is put in the sign-in address, so coming back shows the same three.
- **The reading of the three together:** written by the hub's text-to-text (the same settings as the daily rashifal: Daily Rashifal Settings) for someone signed in, once per draw, and kept as a **Tarot Reading**. A visitor sees it locked, with the way to sign in; after signing in they return to the same draw and it is written then. The writer is told: reflection, never a forecast, no medical, legal or money advice.
- **Words and meanings** are the app's own: `tarot_deck.py` (22 major cards, number, name, a symbol by a name from websitehq's icon set, keywords, upright and reversed). The page holds no wording.
- **Where it is shown:** the "Tarot reading" box of the free reports row (vocabulary `reports_soon` with a `link`).

Open: the minor arcana (56 cards), Hindi words, and the cards' own artwork if the owner supplies it.

## Card pictures

Put the pictures of the cards in `raftor_astrohq/public/tarot/` (they are served as `/assets/raftor_astrohq/tarot/<file>`). Where a picture is present the page shows it full size on the card, with the card's name over it; where it is not, the card is drawn from its symbol. Nothing else needs changing.

- **Name:** `<number>-<card name>.webp`, the number with two digits and the name in lower case with dashes: `00-the-fool.webp`, `01-the-magician.webp`, `02-the-high-priestess.webp`, `03-the-empress.webp`, `04-the-emperor.webp`, `05-the-hierophant.webp`, `06-the-lovers.webp`, `07-the-chariot.webp`, `08-strength.webp`, `09-the-hermit.webp`, `10-wheel-of-fortune.webp`, `11-justice.webp`, `12-the-hanged-man.webp`, `13-death.webp`, `14-temperance.webp`, `15-the-devil.webp`, `16-the-tower.webp`, `17-the-star.webp`, `18-the-moon.webp`, `19-the-sun.webp`, `20-judgement.webp`, `21-the-world.webp`. (`.jpg` and `.png` also work.)
- **The back of the cards:** `back.webp`.
- **Size:** 7 to 12 in shape (for example 700 x 1200 pixels), at most about 150 KB each. Upright pictures: a card that comes out reversed is turned by the page.
- Leave the bottom fifth free of detail: the card's name is written there.
- After adding files run `bench build` so that the new files are served.
