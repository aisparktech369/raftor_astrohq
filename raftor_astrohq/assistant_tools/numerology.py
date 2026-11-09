"""The tool that lets the numerology guide work out a number: calculate_numerology.

The sums are the engine's (astrology.numerology, Cheiro's rules): the guide never adds numbers or counts letters itself. It only reads; the answer holds no birth time and no place.
"""

from typing import Any, Dict

from frappe_assistant_core.core.base_tool import BaseTool


class CalculateNumerology(BaseTool):
	def __init__(self):
		super().__init__()
		self.name = "calculate_numerology"
		self.description = (
			"Work out numerology by Cheiro's rules, by code: give a day of the month for the birth number (its profile and the compound's meaning), a day and a month for the zodiac period too, "
			"and a name in Latin letters for the name number word by word. Every addition is returned in steps. Use it for every number: never add numbers or count letters yourself."
		)
		self.requires_permission = None
		self.annotations = {"module": "astrohq.numerology", "tags": ["read", "calculate"], "tier": "T2"}
		self.inputSchema = {
			"type": "object",
			"properties": {
				"day": {"type": "integer", "minimum": 1, "maximum": 31, "description": "The day of the month the person was born (1-31)"},
				"month": {"type": "integer", "minimum": 1, "maximum": 12, "description": "The month of birth (1-12), only for the zodiac period"},
				"name": {"type": "string", "description": "The name in Latin letters, in the spelling the person chose, for example 'John Smith'"},
			},
		}

	def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
		from raftor_astrohq import astrology

		try:
			return {"found": True, **astrology.numerology(arguments.get("day"), arguments.get("month"), arguments.get("name"))}
		except astrology.AstrologyRefused as error:
			return {"found": False, "message": str(error)}
		except astrology.AstrologyUnavailable:
			return {"found": False, "message": "The numerology calculator is not available right now. Say so, and offer a live numerologist."}
