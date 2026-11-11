"""The words AstroHQ asks Notification HQ to keep (created once, then an admin edits them in Desk; the email gets an in-app twin, which is the bell)."""


def definitions() -> list[dict]:
	return [{"name": "Reminder: a day you follow (email)", "event": "astro.reminder", "channel": "Email", "subject": "{{ title }}",
			 "message": "Hello {{ name }}, {{ text }}\n\nThe panchang for the day: {{ link }}\n\nYou asked for this reminder. You can change or stop it in My reminders."}]
