# The AI guides (many guides to an area)

An **area** is one agent in the agent factory with its own rules, tools and knowledge (`pandit_ji`: astrology, Rudraksha, gemstones and poojas; `numerologist`; `dream_guide`). Many **guides** can serve one area: each is an **AI Guide Persona** record in Desk (name, who it suits, languages, what it leans toward, how it speaks, its greeting and its picture). Nothing in code names a guide.

- **None ship with the app** (`ai_personas.json` is an empty list; the owner is making his own). Guides are made in Desk; a seed file would be read once on install and then never put back. Each guide is also made a Provider (the card on Seek guidance, always online, labelled AI, `ai_guide_page` = `ask/guide?persona=<key>`). Switching a guide off in Desk puts its Provider on Paused.
- **One chat page** for all of them: `/ask/guide?persona=kavya`. The App Chat Card passes the name in the address to the chat method (`agent_chat.info`) and names it in the person's profile (`profile.persona`) on every message.
- **The voice:** AgentsHQ reads the name from the session's last queued message and asks AstroHQ (hook `agent_person.persona_voice`) for the guide's words; they travel as the chat's personality override. The name comes from the browser, so AstroHQ checks it is an enabled guide of that very area before giving any words. The area's boundaries, rules and tools are never changed by a voice. Language and tone in a voice take precedence over the area's English default (a line in each area's personality).
- **Honest by design:** every guide is labelled AI on its card and chat header, no guide claims credentials or years of experience, and a picture made by an AI tool is labelled (`ai_image`).
- **Pictures:** attach one in Desk; until then a plain lettered picture is made for the guide.
- **Adding the 101st guide** is one record in Desk; a new area needs its own agent (rules, tools, knowledge) first.
