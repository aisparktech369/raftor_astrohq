"""AstroHQ describes its onboarding; it does not code it.

Each step names a page (drawn by websitehq from page_definitions.py) and a check onboardinghq runs to know the step
is done. The journey is found by app first (AstroHQ), then by role, so these steps apply to every role of
this app until a role-specific journey is described.
"""
from raftor_onboardinghq.steps import register_step

APP_KEY = "AstroHQ"

JOURNEY = [
	{
		"step_key": "birth_details",
		"label": "Your birth details",
		"required": True,
		"step_type": "Form",
		"config": {"page": "/onboarding/birth-details", "entry": True},
		"completion_check": "raftor_astrohq.profiles.birth_details_complete",
	},
]


def register_journey() -> None:
	for order, step in enumerate(JOURNEY, start=1):
		register_step(APP_KEY, order=order, **step)


# The astrologer's steps. They are added to servicehq's general provider journey (it keeps its own steps) and
# fall between them by order number. servicehq spaces its steps 10, 20, 30...
PROVIDER_JOURNEY = "ServiceHQ Provider"
PROVIDER_STEPS = [
	{
		"step_key": "astro_details",
		"label": "Your astrologer details",
		"required": True,
		"step_type": "Form",
		"order": 15,
		"config": {"page": "/onboarding/astrologer-details"},
		"completion_check": "raftor_astrohq.astrologer.details_complete",
	},
	{
		"step_key": "astro_credentials",
		"label": "Your credentials",
		"required": True,
		"step_type": "Form",
		"order": 17,
		"config": {"page": "/onboarding/astrologer-credentials"},
		"completion_check": "raftor_astrohq.astrologer.credentials_complete",
	},
]


def register_provider_steps() -> None:
	for step in PROVIDER_STEPS:
		register_step(PROVIDER_JOURNEY, **step)
