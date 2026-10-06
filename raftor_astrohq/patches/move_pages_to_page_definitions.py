"""astrohq's pages are page definitions now, at new addresses (/onboarding/birth-details, /onboarding/astrologer-details, ...). The
onboarding steps name their page in their config, so they are registered again (the registration updates a step in place)."""


def execute():
    from raftor_astrohq.journey import register_journey, register_provider_steps

    register_journey()
    register_provider_steps()
