"""The tool that lets a guide open one person from the signed-in person's own profiles: get_family_member.

"My daughter" or "Tara" is found among the profiles the person has saved (their own, and their family's, including those a guide added from earlier chats). What comes back is the profile, the short summary kept
from the chats, the dated notes, and the numerology headline of the birth date when it is known. The person is never named by the model: the server puts the signed-in person into `user` (the agent's
guardrails.session_user_tools), so a guide can only open the record of the person it is talking to.
"""
from typing import Any, Dict

from frappe_assistant_core.core.base_tool import BaseTool


class GetFamilyMember(BaseTool):
	def __init__(self):
		super().__init__()
		self.name = "get_family_member"
		self.description = (
			"Open one person from the signed-in person's own saved profiles: themself ('me'), or a family member by name ('Tara') or by relation ('my daughter'). Returns their details, the short summary and the dated notes "
			"kept from earlier chats, and the numerology headline of their birth date. Use it as soon as the person speaks of someone by name or relation, before asking them anything the profile may already answer. "
			"If nothing matches, it lists the profiles that exist."
		)
		self.requires_permission = None
		self.annotations = {"module": "astrohq.people", "tags": ["read"], "tier": "T2"}
		self.inputSchema = {
			"type": "object",
			"properties": {
				"who": {"type": "string", "description": "The name or the relation, as the person said it: 'Tara', 'my daughter', 'me'."},
				"user": {"type": "string", "description": "Set by the system. Leave it out."},
			},
			"required": ["who"],
		}

	def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
		from raftor_astrohq import person

		user = (arguments.get("user") or "").strip()
		if not user or user == "Guest":
			return {"found": False, "message": "Nobody is signed in, so there is no profile to open."}
		return person.member(user, str(arguments.get("who") or ""))
