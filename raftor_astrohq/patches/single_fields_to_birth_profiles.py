"""Birth details used to be two single fields on the User (time, place) next to Frappe's Birth Date.
They are now rows of the Birth Profiles table. Copies any existing details into a "You" row (only when
the person has no profiles yet and has enough to make a valid row), then removes the old fields."""
import frappe

OLD_FIELDS = ("astro_time_of_birth", "astro_place_of_birth")


def copy_to_you_rows() -> int:
	from raftor_astrohq import profiles

	if not all(frappe.db.has_column("User", f) for f in OLD_FIELDS):
		return 0
	copied = 0
	for u in frappe.db.sql("select name, full_name, birth_date, astro_time_of_birth, astro_place_of_birth from `tabUser` "
						   "where astro_place_of_birth is not null and astro_place_of_birth <> '' and birth_date is not null", as_dict=True):
		if frappe.db.exists("Astro Birth Profile", {"parent": u.name, "parenttype": "User"}):
			continue
		doc = frappe.get_doc("User", u.name)
		doc.append(profiles.TABLE, {
			"relationship": profiles.SELF, "full_name": u.full_name or u.name, "date_of_birth": u.birth_date,
			"time_of_birth": u.astro_time_of_birth or "", "time_unknown": 0, "place_of_birth": u.astro_place_of_birth,
		})
		doc.flags.ignore_validate = True  # moving data across, not judging it; the web form asks for what is missing
		doc.save(ignore_permissions=True)
		copied += 1
	return copied


def execute():
	from raftor_astrohq.profiles import ensure_fields

	ensure_fields()
	copy_to_you_rows()
	for field in OLD_FIELDS:
		name = frappe.db.get_value("Custom Field", {"dt": "User", "fieldname": field}, "name")
		if name:
			frappe.delete_doc("Custom Field", name, force=True, ignore_permissions=True)
