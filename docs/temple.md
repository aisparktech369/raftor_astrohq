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

**Counted for the stats:** a finished round is counted on the meter `temple_pooja` (always free, in every plan of `plans.json`).

**Adding another pooja (Shodashopchar):** make a Pooja Kind with its steps in Desk. The card shows the first pooja that is on; choosing between several is not built yet. The five offerings the card can draw are the effect names above; a new kind of offering needs the card to learn its picture (a variant of the card, not a new card).

**Known limits:** one deity for each person (the data allows more); an old photo's file is left on the site when it is replaced.
