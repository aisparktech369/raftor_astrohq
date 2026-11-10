# The AI plans: Free, Seeker, Needy (built 2026-11-10)

Three monthly plans for the AI guides. The owner's words: free users, seekers are occasional, needy are heavy users; monthly only; a variety of limits. India is a land of free seekers, so Free stays free and good.

| Plan | Price a month | Replies a month / a day | People | Reports a month | Notes a guide reads |
|---|---|---|---|---|---|
| Free | none | 100 / 15 | 3 | 20 | 15 |
| Seeker | Rs 149 | 300 / 40 | 6 | 40 | 40 |
| Needy | Rs 399 | 1,000 / 100 | 15 | 100 | 100 |

The numbers are rows of **AI Plan** (Desk). They are the business team's to change; the table is what ships (`plans.DEFAULT_PLANS`), and a row that exists is never put back.

## Where each piece lives

| Piece | File |
|---|---|
| The plans, the limits, what a person has used, the words a guide says when a limit is reached | `plans.py` (doctypes AI Plan, AI Plan Member, AI Usage, AI Plan Settings) |
| Taking a plan with monthly auto-pay, renewing, stopping, changing (PaymentHQ mandates, sandbox only so far) | `plan_billing.py` |
| The plans page's boxes: made from the AI Plans for websitehq's Service Card | `plan_site.py` |
| The pages' endpoints: the line "You are on ..." (`strip`), the confirm card (`choose_card`), the person's own page (`plan_cards`), `start`, `stop` | `plans_api.py` |
| The pages | `page_definitions.py`: `plans`, `plans/choose`, `my/ai-plan` |

## The pages

| Address | For | What |
|---|---|---|
| `/plans` | everyone | three boxes (Service Card): name, price, what is in it, a button. A signed-in person sees the plan they are on above the boxes. |
| `/plans/choose?plan=Seeker` | signed in | the plan they chose, what it costs, one button that sends them to PaymentHQ to agree to monthly auto-pay. Says "your plan" when it is theirs, and what changing costs when they have another. |
| `/my/ai-plan` | signed in | their plan, what they have used, change or stop renewing. |

The Free button goes to the guide (`/ask/pandit-ji`); the paid buttons go to `/plans/choose`. A paid plan is theirs when the first payment arrives (`plan_billing.paid`).

## How the boxes are made

The Service Card draws an ERPNext **Subscription Plan** with a **Subscription Plan Details** (its website words, features and button). `plan_site.sync` makes both from each AI Plan on every save of the plan and on every migrate. The AI Plan is the only place numbers are written.

- What the business team writes on the Details in Desk (button words, badge, featured, the note under the price, whole amounts) is set once and then left alone. The price, tagline, order, show/hide and the list of features follow the AI Plan every time.
- A plan switched off in AI Plan leaves the page. The page lists the enabled plans when it is built (migrate); a plan added later shows its box after the next migrate.
- A price of 0 reads the site's word (Website HQ Settings, Word for a Price of 0: "Free"); a plan's "Show Whole Amounts Without Decimals" gives Rs 149, not Rs 149.00. Both are as before when not asked for.

## Pitfalls

- Subscription Plan belongs to servicehq's own plan engine too (custom fields, a validation that a limited plan needs Monthly Units, a public list at `/services/plans` for plans ticked "Show on Pricing Page"). The AI plan records are never public there, and carry the replies as their units so the validation passes. Nobody subscribes to them.
- websitehq has an older generic page `/rfhq/plans` that lists every Subscription Plan Details ticked "Show on website", so it lists these plans too. It is not in any menu here (its Portal Settings entry is off) and its addresses name the app; leave it.
- A page group's name cannot have a hyphen (`ai-plans` was refused); the group is `plans`.
- Making an Item commits, so a test makes it before anything it must roll back (see `websitehq/tests/test_service_card.py`).
- Deleting a Subscription Plan Details by SQL leaves its feature rows; a plan with the same name picks them up.

## Not built yet

- Real Razorpay auto-pay (PaymentHQ sandbox only); GST wording on the page (waits for the accountant); a usage line inside the chat; the tarot guide's limits.
