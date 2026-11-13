# The AI guides (many guides to an area)

An **area** is one agent in the agent factory with its own rules, tools and knowledge (`pandit_ji`: astrology, Rudraksha, gemstones and poojas; `numerologist`; `dream_guide`). Many **guides** can serve one area: each is an **AI Guide Persona** record in Desk (name, who it suits, languages, what it leans toward, how it speaks, its greeting and its picture). Nothing in code names a guide.

- **The persons are the factory's** (`raftor_agents_factory/personas/`: 50 characters, their schema, the portraits folder `images/`, the voice builder). AgentsHQ serves them to apps (`raftor_agentshq.personas`); AstroHQ never imports the factory. A person brings its character, voice, way of working, boundaries and portrait. AstroHQ attaches the skill it can do for the person's discipline, may give another name (`pack/guides.json` "names"), and decides if it is on. Install and migrate make each guide that is missing (`ai_profiles.run()`, by `profile_id`) and never touch one that exists, so what staff edit in Desk stays. A portrait added to the factory's `images/` (named by profile_id) becomes the guide's picture at the next migrate, unless one was attached in Desk. Each guide is also made a Provider (the card on Seek guidance, always online, labelled AI, `ai_guide_page` = `ask/guide?persona=<key>`). Switching a guide off in Desk puts its Provider on Paused.
- **One chat page** for all of them: `/ask/guide?persona=kavya`. The App Chat Card passes the name in the address to the chat method (`agent_chat.info`) and names it in the person's profile (`profile.persona`) on every message.
- **The voice:** AgentsHQ reads the name from the session's last queued message and asks AstroHQ (hook `agent_person.persona_voice`) for the guide's words; they travel as the chat's personality override. The name comes from the browser, so AstroHQ checks it is an enabled guide of that very area before giving any words. The area's boundaries, rules and tools are never changed by a voice. Language and tone in a voice take precedence over the area's English default (a line in each area's personality).
- **Honest by design:** every guide is labelled AI on its card and chat header, no guide claims credentials or years of experience, and a picture made by an AI tool is labelled (`ai_image`).
- **Pictures:** attach one in Desk; until then a plain lettered picture is made for the guide.
- **Adding the 101st guide** is one record in Desk; a new area needs its own agent (rules, tools, knowledge) first.

## Skills

A **skill** is an AI Guide Skill record (`ai_skills.json`, seeded once, then Desk): a discipline a guide can have. It names the **area** whose agent does it, the knowledge **shelves** it reads, and whether it is **on**.

| Skill | Area | On | Shelves |
|---|---|---|---|
| Numerology | numerologist | yes | numerology, consult |
| Dream interpretation | dream_guide | yes | dreams, consult |
| Vedic astrology | pandit_ji | yes | consult, services |
| Gemstones / Rudraksha / Poojas | pandit_ji | yes | gemstones / rudraksha / pooja, services |
| KP astrology | pandit_ji | no | needs a KP chart tool and KP knowledge |
| Tarot | tarot | no (built; off until its keys are made) | tarot, consult |

- **The tarot guide** (area `tarot`; blueprint and personality in the factory's astrohq domain) conducts a reading in the Academy's methodology, "Conducting a Session": the person chooses their cards or the guide deals them, as the conversation suits, one card at a time with the three tools of `docs/tarot.md`. The methodology comes with the tools (`how_to_conduct`), so the ceremony is the Academy's, not worded in the guide. It is built and **off**: to switch it on, (1) make its keys to the tool server (the agent user `tarot-guide-agent@agents.astrohq.in` is made on migrate) and set `TAROT_FAC_KEY` and `TAROT_FAC_SECRET` where the other guides' keys are set, (2) switch on its Blueprint Reference `tarot` (made switched off), (3) switch on the Tarot skill, then (4) switch on its guides in Desk (switching a skill on does not turn guides on).
- A guide has up to **three** skills, all of its own area; its area follows from them. It is shown and answers only while all its skills are on (switching a skill off pauses its guides, switching it on does not turn guides on).
- **Shelves:** a chat reads the shelves of the guide's skills together, never beyond the area's blueprint (the ceiling, as a tools override is). AgentsHQ asks the app (hook `agent_person.persona_shelves`) and hands the runner `rag_categories`. A guide with no skills reads the blueprint's shelves.
- **Minimum score:** a blueprint's `rag.min_score` (blank = as before) drops pieces that match weakly. The site's three guides use 0.25 (measured on the live store: off-topic messages 0.19 or less, real questions 0.28 or more). Measure again when the library grows a lot.
- **Profile import:** `bench --site <site> execute raftor_astrohq.ai_profiles.run --kwargs '{"preview": 1}'` shows what an import would do; without `preview` it makes the missing guides. A profile that does not fit the schema is reported and skipped. `pack/guides.json` ("held") names persons made **switched off** and why (a guide whose calculation the engine lacks: Pythagorean, Lo Shu, mobile numbers, two-person compatibility, system comparison).
- **The voice** is built by the factory's person from the fields kept on the guide in Desk: traits, mindset, how it communicates, signature line (also its greeting), way of working, shape of an answer and boundaries (added to the area's, never replacing them). The language comes from the profile's voice direction (`ai_profiles.languages`).
- **Not built yet:** routing between skills when a guide has two or more (today they are simply searched together, capped at the blueprint's top 3); a KP guide; pictures (the pack's briefs are kept on each guide in Desk).
