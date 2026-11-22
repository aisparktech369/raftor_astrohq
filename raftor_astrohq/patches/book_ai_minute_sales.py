"""The AI minutes already bought and paid for get their Sales Order and settled Sales Invoice (ai_minutes.book), so they show in the customer's orders and the money is a sale. Once per payment: safe to run again."""
import frappe

from raftor_astrohq import ai_minutes


def execute():
	frappe.reload_doc("raftor_astro_hq", "doctype", "ai_minute_settings")
	for payment in frappe.get_all("AI Minute Credit", filters={"payment": ["is", "set"]}, pluck="payment", order_by="bought_on"):
		try:
			ai_minutes.book(payment)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"AI minutes sale for {payment}")
