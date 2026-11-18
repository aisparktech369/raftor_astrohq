"""The AI never sees a real name, and the person never sees a stand-in: the whole turn, from the record the guide is given to the notes it writes back
(AgentsHQ pseudonyms.py with this app's person.names)."""
import json
from unittest.mock import patch

import frappe

from raftor_astrohq import person
from raftor_astrohq.tests.helpers import AstroTestCase
from raftor_astrohq.tests.test_person import _user


class TestChatPrivacy(AstroTestCase):
	def setUp(self):
		super().setUp()
		frappe.local._pseudonym_maps = {}
		frappe.local._agentshq_settings = {}
		self.user = _user()
		person.write(self.user, {"notes": [{"about": "Rhenna (daughter)", "kind": "worry", "point": "Stressed about exams"}], "people": [{"name": "Rhenna", "relationship": "daughter", "date_of_birth": "2015-03-03", "place_of_birth": "Pune"}]}, "g", "s")
		self.session = frappe.get_doc({"doctype": "Conversation Session", "user": self.user, "platform": "Internal", "session_type": "AI"}).insert(ignore_permissions=True).name
		self.addCleanup(lambda: setattr(frappe.local, "_pseudonym_maps", {}))

	def _stand_in(self, real):
		from raftor_agentshq import pseudonyms

		return pseudonyms.forward(self.user, real)

	def test_the_names_given_are_the_profiles_names(self):
		got = {r["name"] for r in person.names(self.user)}
		self.assertIn("Rhenna", got)
		self.assertTrue(all(sum(c.isdigit() for c in n) < 5 for n in got))

	def test_what_the_guide_is_given_has_no_real_name_and_no_birth_date_or_place(self):
		from raftor_agentshq.api import conversation

		out = conversation.get_session_overrides(self.session)
		blob = json.dumps({k: out.get(k) for k in ("person", "memory", "chat_summary", "earlier_chats")}, ensure_ascii=False)
		self.assertNotIn("Rhenna", blob)
		self.assertIn(self._stand_in("Rhenna"), blob)
		for secret in ("2015", "Pune", "3 Mar"):
			self.assertNotIn(secret, blob)

	def test_the_reply_is_shown_with_the_real_name(self):
		from raftor_agentshq.api import queue

		said = f"{self._stand_in('Rhenna')} will do well."
		with patch("raftor_agentshq.mailbox.remember", return_value=1), patch("frappe.publish_realtime"), patch("frappe.enqueue"):
			queue.deliver_response(self.session, said, suggestions=json.dumps([f"Tell me about {self._stand_in('Rhenna')}"]))
			sent = frappe.publish_realtime.call_args.kwargs["message"]
		self.assertEqual(sent["response"], "Rhenna will do well.")
		self.assertEqual(sent["suggestions"], ["Tell me about Rhenna"])

	def test_notes_the_guide_writes_are_kept_under_the_real_name(self):
		from raftor_agentshq.api import conversation

		fake = self._stand_in("Rhenna")
		conversation.save_memory(self.session, json.dumps({"notes": [{"about": f"{fake} (daughter)", "kind": "worry", "point": f"{fake} fears maths"}], "summary": f"{fake} is stressed"}))
		points = frappe.get_all("Profile Note", filters={"user": self.user, "is_current": 1}, pluck="point")
		self.assertIn("Rhenna fears maths", points)
		self.assertFalse([p for p in points if fake in p])
		self.assertIn(fake, frappe.db.get_value("Conversation Session", self.session, "summary"))  # the summary stays under stand-ins

	def test_a_tool_asked_about_the_stand_in_finds_the_real_profile(self):
		out = person.member(self.user, self._stand_in("Rhenna"), "")
		self.assertTrue(out["found"])
		self.assertEqual(out["name"], "Rhenna")

	def test_the_message_on_its_way_to_the_runner_has_no_real_name_or_number(self):
		from raftor_agentshq.api import queue

		item = frappe._dict(session_id=self.session, blueprint_id="pandit_ji", payload=json.dumps({"text": "Rhenna is 11, call 9876543210"}))
		out = json.loads(queue._for_the_model(item))
		self.assertNotIn("Rhenna", out["text"])
		self.assertNotIn("9876543210", out["text"])
		self.assertIn("11", out["text"])
