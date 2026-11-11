"""The digital temple (temple.py): a person's own private photo of a deity, and the pooja performed before it one offering after another, in the order the Pooja Kind gives."""
import os
import uuid
from unittest.mock import patch

import frappe
from PIL import Image

from raftor_astrohq import install, page_definitions, temple
from raftor_astrohq.tests.helpers import AstroTestCase, make_user


def _photo(user: str, ending: str = "png", image: bool = True, private: int = 1) -> str:
	"""A file the person uploaded: written under the site's files and recorded for them, the way an upload leaves it (made without the storage hooks)."""
	name = f"temple-{uuid.uuid4().hex[:8]}.{ending}"
	folder = frappe.get_site_path("private" if private else "public", "files")
	path = os.path.join(folder, name)
	if image:
		Image.new("RGB", (8, 8), (200, 120, 40)).save(path, format="PNG")
	else:
		open(path, "wb").write(b"not a picture")
	url = ("/private" if private else "") + "/files/" + name
	record = frappe.get_doc({"doctype": "File", "file_url": url, "file_name": name, "is_private": private, "file_size": os.path.getsize(path)})
	record.db_insert()
	frappe.db.set_value("File", record.name, "owner", user, update_modified=False)
	TestTemple.made.append((path, url))
	return url


class TestTemple(AstroTestCase):
	made = []

	def setUp(self):
		super().setUp()
		install.seed_pooja()
		self.user = make_user().name
		self.gallery()
		frappe.set_user(self.user)

	def tearDown(self):
		frappe.set_user("Administrator")
		for path, url in TestTemple.made:
			frappe.db.delete("File", {"file_url": url})
			if os.path.exists(path):
				os.remove(path)
		TestTemple.made = []
		super().tearDown()

	def gallery(self):
		"""A small gallery of the tests' own (the real one is the owner's to fill): two pictures and two live darshans, one the temple's own channel and one a relay."""
		frappe.set_user("Administrator")
		for key, extra in (("t-ganesh", {"title": "Ganesh ji", "deity": "Ganesh", "image": "/files/t-ganesh.jpg", "credit": "A. Photographer", "licence": "CC0"}),
						   ("t-lakshmi", {"title": "Maa Lakshmi", "deity": "Lakshmi", "image": "/files/t-lakshmi.jpg", "credit": "B. Photographer", "licence": "CC BY 4.0"}),
						   ("t-live", {"title": "Somnath, live", "deity": "Shiva", "live_channel": "UCT1egsvA08YcdMLiEu1DTRg", "channel_name": "Somnath Temple - Official Channel", "official": 1, "licence": "Live stream from YouTube"}),
						   ("t-relay", {"title": "Mahakal, live", "deity": "Shiva", "live_channel": "UCQE_hlxeDSuw4YpuAkDmrMg", "channel_name": "divyadarshan", "official": 0, "licence": "Live stream from YouTube"})):
			if not frappe.db.exists("Mandir Image", key):
				frappe.get_doc({"doctype": "Mandir Image", "image_key": key, "enabled": 1, "sequence": 10, **extra}).insert(ignore_permissions=True)

	def with_photo(self):
		return temple.set_photo(_photo(self.user))

	def make(self, *steps):
		"""The person makes these offerings, leaving the sandal first when it is asked."""
		out = None
		for step in steps:
			if step == "gandha" and not temple._tilaks(temple._session(self.user, temple._deity(self.user), temple._kind())):
				temple.place_tilak(50, 42)
			out = temple.offer(step)
		return out

	def test_the_pooja_comes_with_its_five_offerings_as_data_in_order(self):
		kind = frappe.get_doc("Pooja Kind", "Panchopchar")
		self.assertEqual([(s.step_key, s.effect, s.action) for s in kind.steps], [("gandha", "sandal", "apply"), ("pushpa", "flower", "none"), ("deep", "lamp", "circle"), ("dhoop", "incense", "circle"), ("naivedya", "food", "carry")])  # the lamp first: the incense is lit from it
		self.assertEqual([s.turns for s in kind.steps if s.action == "circle"], [3, 3])
		self.assertTrue(all(s.mantra and s.meaning and s.devanagari for s in kind.steps))

	def test_seeding_again_never_puts_back_what_staff_changed(self):
		frappe.db.set_value("Pooja Step", {"parent": "Panchopchar", "step_key": "gandha"}, "label", "Chandan")
		install.seed_pooja()
		self.assertEqual(frappe.db.get_value("Pooja Step", {"parent": "Panchopchar", "step_key": "gandha"}, "label"), "Chandan")

	def test_a_step_key_may_not_repeat(self):
		frappe.set_user("Administrator")
		kind = frappe.get_doc("Pooja Kind", "Panchopchar")
		kind.steps[1].step_key = kind.steps[0].step_key
		self.assertRaises(frappe.ValidationError, kind.save)

	def test_without_a_photo_every_step_is_locked_and_the_card_asks_for_one(self):
		out = temple.view()
		self.assertEqual(out["photo"], "")
		self.assertEqual([s["state"] for s in out["steps"]], ["locked"] * 5)
		self.assertFalse(out["finished"])
		with self.assertRaises(frappe.ValidationError):
			temple.offer("gandha")
		self.assertFalse(frappe.db.exists("Pooja Session", {"user": self.user}))

	def test_a_guest_has_no_temple(self):
		frappe.set_user("Guest")
		for call in (temple.view, lambda: temple.offer("gandha"), lambda: temple.set_photo("/private/files/x.png"), lambda: temple.place_tilak(1, 1)):
			with self.assertRaises(frappe.PermissionError):
				call()

	def test_the_first_photo_makes_the_deity_and_the_first_step_opens(self):
		out = self.with_photo()
		self.assertTrue(out["photo"].startswith("/private/files/"))
		self.assertEqual([s["state"] for s in out["steps"]], ["next", "locked", "locked", "locked", "locked"])
		self.assertEqual((out["card"]["title"], out["tilaks"]), ("Next · Gandha", []))
		self.assertEqual([(s["action"], s["turns"]) for s in out["steps"]][:3], [("apply", 3), ("none", 3), ("circle", 3)])
		self.assertTrue(all(out["words"]["prompts"][a] for a in ("apply", "circle", "carry")))
		deity = frappe.get_all("Temple Deity", filters={"user": self.user}, fields=["name", "is_main", "photo"])
		self.assertEqual(len(deity), 1)
		self.assertEqual(frappe.db.get_value("File", {"file_url": out["photo"]}, "attached_to_name"), deity[0].name)

	def test_only_a_photo_the_person_uploaded_privately_is_taken(self):
		other = make_user().name
		for url, who in ((_photo(other), self.user), (_photo(self.user, private=0), self.user), (_photo(self.user, ending="png", image=False), self.user), (_photo(self.user, ending="gif"), self.user), ("/private/files/none.png", self.user)):
			frappe.set_user(who)
			with self.assertRaises(frappe.ValidationError):
				temple.set_photo(url)
		self.assertFalse(frappe.db.exists("Temple Deity", {"user": self.user}))

	def test_a_later_photo_replaces_the_first_and_begins_the_round_again(self):
		self.with_photo()
		self.make("gandha", "pushpa")
		out = temple.set_photo(_photo(self.user))
		self.assertEqual((out["done"], out["tilaks"]), (0, []))
		self.assertEqual(frappe.db.count("Temple Deity", {"user": self.user}), 1)

	def test_the_offerings_are_made_in_order_and_one_further_on_is_refused(self):
		self.with_photo()
		with self.assertRaises(frappe.ValidationError):
			temple.offer("pushpa")
		with self.assertRaises(frappe.ValidationError):
			temple.offer("no-such-step")
		with self.assertRaises(frappe.ValidationError):
			temple.offer("gandha")  # no sandal left yet
		out = self.make("gandha")
		self.assertEqual((out["done"], out["played"]), (1, "sandal"))
		self.assertEqual([s["state"] for s in out["steps"]], ["done", "next", "locked", "locked", "locked"])
		self.assertEqual(out["card"]["mantra"], "Pushpam samarpayami")

	def test_an_offering_already_made_can_be_shown_again_without_moving_on(self):
		self.with_photo()
		self.make("gandha", "pushpa")
		out = temple.offer("gandha")
		self.assertEqual((out["done"], out["played"]), (2, "sandal"))

	def test_the_last_offering_finishes_the_round_and_counts_it_once(self):
		self.with_photo()
		with patch("raftor_servicehq.plans.use") as counted:
			self.make("gandha", "pushpa", "deep", "dhoop")
			self.assertFalse(counted.called)
			out = temple.offer("naivedya")
			temple.offer("naivedya")
		counted.assert_called_once_with(self.user, temple.METER)
		self.assertEqual((out["finished"], out["rounds"], out["done"]), (True, 1, 5))
		self.assertEqual(out["card"]["title"], "Panchopchar complete")
		self.assertEqual(frappe.db.get_value("Pooja Session", {"user": self.user}, "status"), "Completed")

	def test_again_begins_a_new_round_and_keeps_the_count(self):
		self.with_photo()
		self.make("gandha", "pushpa", "deep", "dhoop", "naivedya")
		out = temple.again()
		self.assertEqual((out["done"], out["finished"], out["rounds"], out["tilaks"]), (0, False, 1, []))
		self.assertEqual(out["steps"][0]["state"], "next")

	def test_each_mark_of_sandal_is_kept_where_it_was_left_and_there_may_be_several(self):
		self.with_photo()
		temple.place_tilak(31, 140)
		out = temple.place_tilak(70, 20)
		self.assertEqual(out["tilaks"], [{"x": 31, "y": 100}, {"x": 70, "y": 20}])  # kept on the photo, however far off
		self.assertEqual(temple.view()["tilaks"], out["tilaks"])
		for _ in range(temple.TILAKS_MAX):
			try:
				temple.place_tilak(5, 5)
			except frappe.ValidationError:
				break
		self.assertEqual(len(temple.view()["tilaks"]), temple.TILAKS_MAX)

	def test_nobody_can_reach_another_persons_temple(self):
		self.with_photo()
		mine = frappe.db.get_value("Temple Deity", {"user": self.user}, "name")
		frappe.set_user(make_user().name)
		self.assertEqual(temple.view(deity=mine)["photo"], "")
		with self.assertRaises(frappe.ValidationError):
			temple.offer("gandha", deity=mine)
		with self.assertRaises(frappe.ValidationError):
			temple.place_tilak(5, 5, deity=mine)

	def test_a_new_day_begins_a_new_round(self):
		self.with_photo()
		self.make("gandha")
		frappe.db.set_value("Pooja Session", {"user": self.user}, "session_date", frappe.utils.add_days(frappe.utils.today(), -1))
		self.assertEqual(temple.view()["done"], 0)

	def test_the_card_is_given_its_doors_words_sounds_and_the_way_out(self):
		out = self.with_photo()
		for word in ("enter", "ring_bell", "sound_on", "sound_off", "close_doors", "leave", "title"):
			self.assertTrue(out["words"][word], word)
		self.assertEqual((out["immersive"], out["leave_url"]), (True, "/"))
		self.assertEqual(out["sounds"], {"open": "", "bell": "", "done": "", "aarti": ""})  # none given yet: the card makes its own
		self.assertEqual({s["sound"] for s in out["steps"]}, {""})

	def test_a_recording_staff_attach_reaches_the_card(self):
		frappe.set_user("Administrator")
		kind = frappe.get_doc("Pooja Kind", "Panchopchar")
		kind.sound_open, kind.steps[0].sound = "/files/shankh.mp3", "/files/gandha.mp3"
		kind.save()
		frappe.set_user(self.user)
		out = self.with_photo()
		self.assertEqual(out["sounds"]["open"], "/files/shankh.mp3")
		self.assertEqual(out["steps"][0]["sound"], "/files/gandha.mp3")

	def test_a_person_picks_a_mandir_from_the_gallery_and_it_is_theirs_and_open_now(self):
		gallery = temple.view()["gallery"]
		pictures = [g for g in gallery if not g["live"]]
		self.assertEqual(len(pictures), 2)
		self.assertEqual(pictures[0]["credit"], "Photo: A. Photographer · CC0")  # who made it, and under what licence
		out = temple.choose_mandir(pictures[0]["id"])
		self.assertEqual(out["photo"], pictures[0]["image"])
		self.assertEqual([m["current"] for m in out["mandirs"]], [True])
		self.assertEqual(temple.choose_mandir(pictures[0]["id"])["mandirs"][0]["id"], out["mandirs"][0]["id"])  # again: it only opens it
		self.assertEqual(out["steps"][0]["state"], "next")

	def test_with_an_empty_gallery_the_person_is_asked_for_their_own_photo(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("Mandir Image", {"enabled": 1}, "enabled", 0)
		frappe.set_user(self.user)
		out = temple.view()
		self.assertEqual((out["gallery"], out["words"]["choose"]), ([], "Add your mandir photo"))

	def test_a_gallery_picture_that_is_switched_off_is_not_offered(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("Mandir Image", "t-ganesh", "enabled", 0)
		frappe.set_user(self.user)
		self.assertNotIn("t-ganesh", [g["id"] for g in temple.view()["gallery"]])
		with self.assertRaises(frappe.ValidationError):
			temple.choose_mandir("t-ganesh")

	def test_the_seeded_gallery_has_no_picture_without_a_licence_and_the_live_ones_wait_switched_off(self):
		import json
		from pathlib import Path

		rows = json.loads((Path(install.__file__).parent / "mandirs.json").read_text(encoding="utf-8"))["images"]
		for row in rows:
			self.assertTrue(row.get("live_channel") or str(row.get("licence", "")).startswith(("CC0", "CC BY", "Public domain")), row["key"])
			if row.get("live_channel"):
				self.assertEqual(row["enabled"], 0, row["key"])  # live darshan is postponed

	def test_a_person_keeps_several_mandirs_opens_one_and_puts_one_away(self):
		first = temple.choose_mandir("t-ganesh")
		second = temple.choose_mandir("t-lakshmi")
		own = temple.set_photo(_photo(self.user), new=1)
		ids = [m["id"] for m in own["mandirs"]]
		self.assertEqual(len(ids), 3)
		self.assertEqual([m["current"] for m in own["mandirs"]], [False, False, True])
		self.assertEqual(temple.switch_mandir(ids[0])["deity"], ids[0])
		self.assertEqual(temple.view()["deity"], ids[0])
		self.assertEqual(temple.remove_mandir(ids[1])["mandirs"][0]["id"], ids[0])
		self.assertEqual(len(temple.view()["mandirs"]), 2)

	def test_a_mandir_of_another_person_cannot_be_opened_or_removed_and_the_number_is_limited(self):
		mine = temple.choose_mandir("t-ganesh")["deity"]
		frappe.set_user(make_user().name)
		for call in (lambda: temple.switch_mandir(mine), lambda: temple.remove_mandir(mine)):
			with self.assertRaises(frappe.ValidationError):
				call()
		with self.assertRaises(frappe.ValidationError):
			temple.choose_mandir("no-such-mandir")
		keys = frappe.get_all("Mandir Image", filters={"enabled": 1}, pluck="image_key")
		with patch.object(temple, "MANDIRS_MAX", 2):
			temple.choose_mandir(keys[0]); temple.choose_mandir(keys[1])
			with self.assertRaises(frappe.ValidationError):
				temple.choose_mandir(keys[2])

	def test_the_donate_button_is_only_the_mandirs_own_https_page(self):
		self.assertIsNone(temple.choose_mandir("t-ganesh")["donate"])
		frappe.set_user("Administrator")
		frappe.db.set_value("Mandir Image", "t-ganesh", "donate_url", "https://example.org/donate")
		frappe.set_user(self.user)
		out = temple.choose_mandir("t-ganesh")
		self.assertEqual(out["donate"], {"label": "Donate to Ganesh ji", "url": "https://example.org/donate"})

	def test_a_live_darshan_is_a_mandir_whose_picture_is_the_temples_own_stream(self):
		live = [g for g in temple.view()["gallery"] if g["live"]]
		self.assertGreaterEqual(len(live), 2)
		out = temple.choose_mandir("t-live")
		self.assertEqual(out["photo"], "")
		self.assertRegex(out["live"]["url"], r"^https://www\.youtube-nocookie\.com/embed/live_stream\?channel=UC[\w-]{22}&")
		self.assertEqual(out["live"]["credit"], "Live from Somnath Temple - Official Channel")  # the temple's own channel
		self.assertEqual(out["credit"], out["live"]["credit"])
		self.assertRegex(out["live"]["watch"], r"^https://www\.youtube\.com/channel/UC[\w-]{22}/live$")  # a way out to the stream if it does not play inside the page
		frappe.set_user("Administrator")
		frappe.db.set_value("Mandir Image", "t-live", "live_video", "MZexuq9xqS0")
		frappe.set_user(self.user)
		self.assertEqual(temple.choose_mandir("t-live")["live"]["watch"], "https://www.youtube.com/watch?v=MZexuq9xqS0")  # a particular live video, when one is named
		self.assertEqual(out["steps"][0]["state"], "next")  # the offerings can be made over the stream
		self.assertEqual(temple.place_tilak(40, 40)["tilaks"], [{"x": 40, "y": 40}])
		self.assertEqual(self.make("gandha")["done"], 1)
		self.assertTrue(temple.choose_mandir("t-relay")["live"]["credit"].startswith("Relayed from "))  # someone else's relay says so

	def test_a_channel_that_is_not_a_channel_id_plays_nothing(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("Mandir Image", "t-live", "live_channel", "UC\"><script>alert(1)</script>")
		frappe.set_user(self.user)
		out = temple.choose_mandir("t-live")
		self.assertIsNone(out["live"])
		self.assertEqual(out["steps"][0]["state"], "locked")

	def test_the_page_names_the_card_and_methods_that_exist(self):
		page = page_definitions.temple_page()
		self.assertTrue(page["login_required"])
		card = page["sections"][0]["cards"][0]
		self.assertEqual(card["type"], "Offering Stage Card")
		for method in card["values"].values():
			func = frappe.get_attr(method)
			self.assertIn(func, frappe.whitelisted)
		self.assertIn(page, page_definitions.definitions())
