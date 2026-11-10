# AstroHQ's plans: Free, Seeker, Needy (built 2026-11-10, reshaped the same day)

Three monthly plans for the people of AstroHQ. The owner's words: free users, seekers are occasional, needy are heavy users; monthly only; a variety of limits. It is not an "AI plan": the plan covers the guides, the profiles, the reports and the notes. India is a land of free seekers, so Free stays free and good.

| Plan | Price a month | Replies a month / a day | People | Reports a month | Notes a guide reads |
|---|---|---|---|---|---|
| Free | none | 100 / 15 | 3 | 20 | 15 |
| Seeker | Rs 149 | 300 / 40 | 6 | 40 | 40 |
| Needy | Rs 399 | 1,000 / 100 | 15 | 100 | 100 |

## They are AstroHQ's own

servicehq has a plan engine of its own for its services (ERPNext Subscription Plans with units) and knows nothing of these plans. So nothing about them is written into servicehq's or ERPNext's plan records; the other apps only ask AstroHQ through generic hooks.

| Piece | Where |
|---|---|
| The standard plans and the words a guide says at a limit | `plans.json`, made by `plans.ensure_plans()` on a fresh install and on migrate when missing (the same way as `ai_guides.json`); a row that exists is never put back |
| The plans, the limits, what a person has used | `plans.py`; doctypes **Astro Plan**, **Astro Plan Member**, **Astro Plan Usage**, **Astro Plan Settings** (Desk, module Raftor Astro HQ) |
| Taking a plan with monthly auto-pay, renewing, stopping, changing (PaymentHQ mandates; sandbox only so far) | `plan_billing.py` |
| The endpoints of the pages | `plans_api.py`: `boxes`, `choose_card`, `my_plan`, `start`, `stop` |
| The pages | `page_definitions.py`: `plans`, `plans/choose`, `my/astro-plan` |
| "May this guide answer?" and "count this reply" | AgentsHQ asks AstroHQ (hook `agent_person`); it has no plan words in it |
| The website's free-report limit | servicehq asks AstroHQ (hook `free_reports_allowance`) |
| The look of a box | websitehq's Service Card |

## The pages

| Address | For | What |
|---|---|---|
| `/plans` | everyone | a box for each plan (Service Card): name, price, what is in it, a button. A signed-in person's own plan is marked "Your plan" and its button leads to what they have used. |
| `/plans/choose?plan=Seeker` | signed in | the plan they chose, what it costs, one button that sends them to PaymentHQ to agree to monthly auto-pay. Says "your plan" when it is theirs, and what changing costs when they have another. |
| `/my/astro-plan` | signed in | their plan, what they have used, change it or stop renewing. |

The Free button goes to the guide; a paid button goes to `/plans/choose`. A paid plan is theirs when the first payment arrives (`plan_billing.paid`).

## How the boxes get their words

`plans_api.boxes` answers one item for each enabled plan, and websitehq draws each with the Service Card (`website_hq/feed.py`: the app gives values, never markup). The words are fields of the Astro Plan, so the business team changes them in Desk: tagline, button, button address, note under the price, badge. The lines of what is in a plan come from its limits (`plans.limit_lines`), so a number is written once. A plan switched off in Desk has no box.

The Service Card can draw a plan two ways: from an ERPNext Subscription Plan (`plan_name`), or from values an app gives (`title`, `price`, `feature_lines`, `button_label`, `button_url` ...). Both blank draws nothing.

## Pitfalls

- The page group is `plans`: a group's name cannot have a hyphen.
- servicehq's own "Plan" entry in the left menu (service subscriptions) is still there beside "Your plan".
- websitehq's older `/rfhq/plans` lists Subscription Plans ticked "Show on website". These plans are not among them (not written there any more).
- A doctype JSON that is changed by hand needs its `modified` stamp changed too, or migrate skips it.
- Deleting a parent by SQL leaves its child rows.

## Not built yet

- Real Razorpay auto-pay (PaymentHQ sandbox only); GST wording on the page (waits for the accountant); a usage line inside the chat; the tarot guide's limits.
