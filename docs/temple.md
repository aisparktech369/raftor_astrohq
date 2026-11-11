# The digital temple

A person's own photo of the deity they worship, and the pooja performed before it, one offering after another. The page is `/my/temple` (signed in).

**Who does what**

| Part | Where | What it holds |
|---|---|---|
| Pooja Kind and Pooja Step | AstroHQ (data, `pooja.json`, seeded once) | The pooja's name and its steps in order: name, Devanagari, mantra line, meaning, and the offering the card draws (`sandal`, `flower`, `incense`, `lamp`, `food`). Staff correct or add one in Desk; a pooja staff have edited is never put back. |
| Temple Deity | AstroHQ | The person's photo (a private file, readable only by them) and where they put the sandal tilak. |
| Pooja Session | AstroHQ | One round of a pooja before a deity for one day: the steps made so far and how many rounds were finished. |
| `temple.py` | AstroHQ | `view`, `offer`, `again`, `set_photo`, `place_tilak`: every word on the card and every rule (a step out of order is refused; a file must be the person's own private photo and a real image under 8 MB). |
| Offering Stage Card | websitehq | Draws what `view` answers. Holds no wording and no rules. |

**The offerings are made by hand** (Pooja Step.action, and `turns` for a circle):

| Action | What the person does | Done when |
|---|---|---|
| `none` | One tap (the flowers) | At once |
| `apply` | Taps each deity's forehead; a mark of sandal stays on the photo for the round (several deities may be on one photo) | The person taps Done (at least one mark is needed, and the server asks for it) |
| `circle` | Moves the lamp or the incense in a circle, clockwise, round the guide ring; the lamp's light moves over the photo and the incense leaves a trail of smoke | After the set turns |
| `carry` | Drags a sweet from the thali to the deity's mouth, once for each deity | The person taps Done |

Each also has a "Do it for me" button, for a person who cannot use the screen that way. The lamp comes before the incense (the incense is lit from the lamp).

**Mandirs (the gallery and the person's own).** A person keeps up to 12 mandirs (`MANDIRS_MAX`), opens one for the day from "My mandirs", and can pick from the gallery or upload their own. The gallery is the doctype **Mandir Image** (Desk): picture, deity, mandir, credit, licence, where it came from, and the mandir's own donation page (the Donate button only opens that page, in a new tab; no money passes through us). Seeded once from `mandirs.json` with the pictures in `public/mandirs/`; a gallery staff have edited is never put back. **The interim set is generic and every picture is CC0, CC BY, CC BY-SA or public domain (from Wikimedia Commons), with its credit shown on the temple and in the gallery; the owner is collecting the final pictures himself, so replace or switch off any of them in Desk.** Famous mandirs (Tirupati Balaji, Vaishno Devi) are not in the set: their official pictures need the shrine's permission.

**Live darshan.** A Mandir Image with a YouTube channel id (24 characters starting UC) is a live darshan: the temple screen plays whatever that channel is streaming now, through YouTube's own player (youtube-nocookie.com, muted so the temple's own sounds are heard; a button hears the stream), and the offerings are drawn over it. The channel's name is shown under it: "Live from X" when the record says it is the temple's own channel, "Relayed from X" otherwise; aarti times are shown with it. A channel id that is not a channel id plays nothing (checked before it reaches the page). Seeded: Somnath and Tirumala Tirupati (SVBC TTD) on their own channels; Mahakaleshwar and Kashi Vishwanath through other channels' relays, until the temples' own channels are known. Nothing is copied: if a channel stops allowing embedding, or a temple asks, switch the record off in Desk.

**Counted for the stats:** a finished round is counted on the meter `temple_pooja` (always free, in every plan of `plans.json`).

**Adding another pooja (Shodashopchar):** make a Pooja Kind with its steps in Desk. The card shows the first pooja that is on; choosing between several is not built yet. The five offerings the card can draw are the effect names above; a new kind of offering needs the card to learn its picture (a variant of the card, not a new card).

**Known limits:** one deity for each person (the data allows more); an old photo's file is left on the site when it is replaced.
