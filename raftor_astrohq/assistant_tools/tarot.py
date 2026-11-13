"""The tools that let a guide conduct a tarot session in a chat: start_tarot_session, deal_tarot_card and get_tarot_session.

The draw is the page's (tarot_session.py takes it one card at a time): the deck is shuffled once by the server, every word of a card and of a spread is the Academy's, and the guide never names or invents a card:
each card it speaks of came out of deal_tarot_card. Whether the person chooses their cards or the guide deals them is the guide's call from the conversation (a number the person gives goes in `pick`).
The person is never named by the model: the server puts the signed-in person into `user` (the blueprint's guardrails.session_user_tools), so a guide can only open the session of the person it is talking to.
"""
from typing import Any, Dict

from frappe_assistant_core.core.base_tool import BaseTool

USER = {"type": "string", "description": "Set by the system. Leave it out."}


class StartTarotSession(BaseTool):
	def __init__(self):
		super().__init__()
		self.name = "start_tarot_session"
		self.description = (
			"Begin a tarot session for the signed-in person: the server shuffles the whole deck once and it lies face down. Use it when the person wants a tarot reading. Choose the `spread` from what they want: "
			"one-card-draw (a quick answer, or a thought for the day), three-card-spread (a situation, a choice or a short period: past, present, outcome), yes-or-no (one yes-or-no question, one card), "
			"five-card-spread (a deeper look at one situation). If you are not sure which fits, call it without a spread and it lists the spreads with what each is for. Put their question in `question` in their own words, "
			"and a `topic` if they named one. Then conduct the session with deal_tarot_card. The answer carries `how_to_conduct`, the Academy's methodology for conducting a session (opening, choosing the cards, turning them over, "
			"the reading, going deeper, closing, care): follow it, including whether the person chooses their cards or you deal them. "
			"Never name, invent or hint at a card yourself: every card you speak of must come from deal_tarot_card."
		)
		self.requires_permission = None
		self.annotations = {"module": "astrohq.tarot", "tags": ["write"], "tier": "T2"}
		self.inputSchema = {
			"type": "object",
			"properties": {
				"spread": {"type": "string", "enum": ["one-card-draw", "three-card-spread", "yes-or-no", "five-card-spread"], "description": "The spread. Leave it out to be given the list."},
				"question": {"type": "string", "description": "What the person wants to explore, in their own words (kept short)."},
				"topic": {"type": "string", "enum": ["love", "career", "money", "health", "family", "self", "general"], "description": "The area of life, if they named one."},
				"user": USER,
			},
		}

	def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
		from raftor_astrohq import tarot_session

		return tarot_session.start(arguments.get("user"), arguments.get("spread"), arguments.get("question"), arguments.get("topic"))


class DealTarotCard(BaseTool):
	def __init__(self):
		super().__init__()
		self.name = "deal_tarot_card"
		self.description = (
			"Turn over ONE card into the next place of the person's tarot spread, and get what the Academy says of it in that place (what it shows, what it means, upright or reversed). "
			"Decide from the conversation how the card is chosen. If the person wants to take part (they say they want to choose, or they are relaxed and engaged), ask them for a number from 1 to the `face_down` count "
			"and pass it as `pick`; if they want a quick answer or have no preference, leave `pick` out and the top card is dealt for them. Call it once for each place, in order. After each card say, in a sentence or two, "
			"what it says in its place, then turn over the next, unless the person asked to see them all at once. When every place is full the answer carries `reading_guide`: give your reading of the cards together, in your own words, "
			"as something to reflect on, never a forecast. If something is still unclear you may turn over up to two more cards with `clarifier` true. The draw is random and made by the server: never promise what will come "
			"and never choose a card for the person yourself."
		)
		self.requires_permission = None
		self.annotations = {"module": "astrohq.tarot", "tags": ["write"], "tier": "T2"}
		self.inputSchema = {
			"type": "object",
			"properties": {
				"pick": {"type": "integer", "minimum": 1, "description": "The number the person chose among the cards still face down (1 to `face_down`). Leave it out to deal the top card."},
				"clarifier": {"type": "boolean", "description": "True to turn over one more card after the spread is full, for something unclear (up to two)."},
				"session": {"type": "string", "description": "Leave it out: the person's latest tarot session is meant."},
				"user": USER,
			},
		}

	def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
		from raftor_astrohq import tarot_session

		return tarot_session.deal(arguments.get("user"), arguments.get("pick"), bool(arguments.get("clarifier")), arguments.get("session"))


class GetTarotSession(BaseTool):
	def __init__(self):
		super().__init__()
		self.name = "get_tarot_session"
		self.description = (
			"Open the person's latest tarot session of the last day, to continue from it: their question, the spread, the cards turned over with what the Academy says of each, the places still empty, "
			"and (once the spread is full) how to read it. Use it whenever the person comes back to their cards, asks about one of them, or wants to go deeper ('what about the second card?', 'what does it say about work?'), "
			"before you answer, so that you speak only of the cards that really came out. If there is none, offer to begin a session."
		)
		self.requires_permission = None
		self.annotations = {"module": "astrohq.tarot", "tags": ["read"], "tier": "T2"}
		self.inputSchema = {
			"type": "object",
			"properties": {
				"session": {"type": "string", "description": "Leave it out: the person's latest tarot session is meant."},
				"user": USER,
			},
		}

	def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
		from raftor_astrohq import tarot_session

		return tarot_session.state(arguments.get("user"), arguments.get("session"))
