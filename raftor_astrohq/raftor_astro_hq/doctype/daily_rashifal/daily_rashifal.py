from frappe.model.document import Document


class DailyRashifal(Document):
	def before_insert(self):
		self.key = f"{self.for_date}-{int(self.rashi_no):02d}"
