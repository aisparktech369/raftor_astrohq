"""What AstroHQ's plans count, in the plans' own words (servicehq's plans.py makes the plans, counts, and says what is said at a limit; the plans themselves are plans.json).

    AI_MINUTES      the time a person talks with the AI astrologers: AgentsHQ asks `allowance` before it queues a message and calls `turn_done` when a turn is complete
    PEOPLE          the people a person may keep in their profiles: `family_room`, `family_words`
"""
import frappe

from raftor_servicehq import plans

AI_MINUTES = "ai_minutes"
PEOPLE = "family_profiles"
UNLIMITED = 1000


def allowance(user: str, guide: str = "") -> dict:
	"""Whether the AI astrologers may answer this person now: {"ok": True} or {"ok": False, "message", "cards"}."""
	from raftor_astrohq import ai_minutes

	return ai_minutes.allowance(user)  # the plan's free minutes first, then the minutes the person bought


def turn_done(user: str, guide: str = "", persona: str = "") -> None:
	"""An answer was given: the time since the person last talked counts against their plan, unless they had paused (plans.use_time), as points: the minutes times the guide's multiplier."""
	from raftor_astrohq import ai_minutes

	ai_minutes.turn_done(user, persona)


def family_room(user: str) -> int:
	"""How many more people the person's profiles may hold on their plan (a plan that says nothing of it holds any number)."""
	quota = plans.quota_of(user, PEOPLE) if not plans._staff(user) else None
	if quota is None:
		return UNLIMITED
	return max(0, int(quota) - frappe.db.count("Astro Birth Profile", {"parent": user, "parenttype": "User"}))


def family_words(user: str) -> str:
	return plans.words_for(user, PEOPLE)
