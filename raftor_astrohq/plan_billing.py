"""Taking a plan, and keeping it from month to month: Seeker and Needy are paid by PaymentHQ's auto-pay.

    start(user, plan)        the person chooses a plan: PaymentHQ makes the agreement and the first month's payment, and the person is sent to agree to auto-pay
    paid(payment)            (hook paymenthq_on_paid) the first payment arrived: the plan is theirs from today for a month; a later one arrived: the next month begins
    payment_not_taken(...)   (hooks paymenthq_on_failed, _expired, _cancelled) the first payment did not happen: nothing was taken
    request_renewals()       (daily) a few days before a month ends, next month's payment is asked from the agreement; PaymentHQ tells the person at once and takes it after its notice period
    check_agreements()       (daily) an agreement that has ended (stopped at the bank, refused too often) stops the plan renewing
    stop(user)               the person stops renewing: the plan stays to the end of the month they have paid for
    end_lapsed()             (daily) a plan whose month ended without a renewal is marked Ended

Payment is not this app's: it asks PaymentHQ through servicehq's payments_port, and is told what happened. The plans are monthly only; the price of a month is the plan's `monthly_price` (GST included).
A month runs from the day the plan began to the day before the same day next month (the 12th to the 11th); a person who changes plan begins again on the day the new plan's first payment arrives, and the old agreement is stopped.
The next month's payment is asked a few days early, so a month paid for early only moves 'paid through' on; the month the person's replies are counted in does not change until it ends.
"""
import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, flt, getdate, today

from raftor_astrohq import plans

AGREEMENT_DAYS = 3 * 365  # how long an auto-pay agreement runs (a person starts a new one if it ends)
ASK_AHEAD_DAYS = 3        # next month's payment is asked this many days before the month ends (PaymentHQ gives notice before it takes it)
MEMBER = "AI Plan Member"


def _port():
	from raftor_servicehq import payments_port

	return payments_port


def paid_through(anchor, months: int):
	"""The last day paid for when `months` months of a plan that began on `anchor` are paid: counted from the anchor each time (see plans.month_window)."""
	return add_days(getdate(add_months(getdate(anchor), months)), -1)


def _plan_to_take(plan: str):
	row = frappe.db.get_value("AI Plan", plan, ["plan_name", "monthly_price", "enabled"], as_dict=True)
	if not row or not cint(row.enabled) or flt(row.monthly_price) <= 0:
		frappe.throw(_("That plan cannot be taken."))
	return row


def start(user: str, plan: str) -> dict:
	"""The person chooses a paid plan. Answers {"redirect": where to agree to auto-pay}. The plan is theirs only when the first payment arrives."""
	row = _plan_to_take(plan)
	current = plans.membership(user)
	if current and current.plan == plan and cint(frappe.db.get_value(MEMBER, user, "renews")):
		frappe.throw(_("You already have the {0} plan.").format(plan))
	price = flt(row.monthly_price, 2)
	if not frappe.db.exists(MEMBER, user):  # PaymentHQ's payment is for this record, so it has to be there first
		frappe.get_doc({"doctype": MEMBER, "user": user, "plan": plan, "status": "Waiting", "source": "Payment", "renews": 0}).insert(ignore_permissions=True)
	agreement = _port().agreement_start(user, price, price, add_days(today(), AGREEMENT_DAYS), MEMBER, user, _("{0} plan, each month").format(plan)[:140], first_for=(MEMBER, user), return_to=plans.PLANS_PAGE)
	frappe.db.set_value(MEMBER, user, {"pending_plan": plan, "pending_agreement": agreement["mandate"]})
	return {"redirect": agreement["url"]}


def _activate(member, plan: str, agreement: str) -> None:
	"""The first payment of a plan arrived: it is the person's from today for a month, and renews."""
	old = member.agreement
	begin = getdate(today())
	member.update({"plan": plan, "status": "Active", "period_start": begin, "months_paid": 1, "period_end": paid_through(begin, 1), "source": "Payment", "agreement": agreement, "renews": 1,
				   "pending_plan": None, "pending_agreement": None, "charge_asked_for": None})
	member.save(ignore_permissions=True)
	if old and old != agreement:  # a change of plan: the old agreement is not wanted any more
		try:
			_port().agreement_stop(old, "system", _("The plan was changed"))
		except Exception:
			frappe.log_error(title="plan change: old agreement not stopped")


def paid(payment) -> None:
	"""PaymentHQ says a payment for a plan arrived (hook paymenthq_on_paid). Safe to run twice."""
	user = payment.purpose_name
	if not frappe.db.exists(MEMBER, user):
		return
	member = frappe.get_doc(MEMBER, user)
	key = payment.get("request_key") or ""
	if member.pending_agreement and payment.get("mandate") == member.pending_agreement and not key:
		_activate(member, member.pending_plan, member.pending_agreement)
	elif key.startswith(f"{user}|") and payment.get("mandate") == member.agreement:
		begin = getdate(key.split("|", 1)[1])
		if getdate(add_months(getdate(member.period_start), cint(member.months_paid))) == begin:  # the month this payment was asked for is the next one not yet paid: heard for the first time
			member.months_paid = cint(member.months_paid) + 1
			member.period_end = paid_through(member.period_start, member.months_paid)
			member.status = "Active"
			member.save(ignore_permissions=True)


def payment_not_taken(payment) -> None:
	"""PaymentHQ says a payment for a plan failed, lapsed or was withdrawn. If it was the first one, the plan was never taken. A month's renewal that is not paid simply is not extended."""
	user = payment.purpose_name
	if not frappe.db.exists(MEMBER, user):
		return
	member = frappe.get_doc(MEMBER, user)
	if member.pending_agreement and payment.get("mandate") == member.pending_agreement and not payment.get("request_key"):
		member.pending_plan, member.pending_agreement = None, None
		if member.status == "Waiting":
			member.status = "Ended"
		member.save(ignore_permissions=True)


def request_renewals(now=None) -> int:
	"""Daily: the payment for the next month of each plan that is about to end and renews is asked from its agreement. Returns how many were asked."""
	base, asked = getdate(now or today()), 0
	for row in frappe.get_all(MEMBER, filters={"status": "Active", "renews": 1, "agreement": ["is", "set"], "period_end": ["between", [base, add_days(base, ASK_AHEAD_DAYS)]]},
							  fields=["name", "plan", "period_end", "agreement", "charge_asked_for"], limit=500):
		begin = add_days(row.period_end, 1)
		if row.charge_asked_for and getdate(row.charge_asked_for) == getdate(begin):
			continue
		price = flt(frappe.db.get_value("AI Plan", row.plan, "monthly_price"), 2)
		if price <= 0 or not frappe.db.get_value("AI Plan", row.plan, "enabled"):
			continue
		frappe.db.savepoint("renewal")
		try:
			_port().request(row.name, price, MEMBER, row.name, _("{0} plan, from {1}").format(row.plan, frappe.utils.formatdate(begin))[:140], method="Auto-pay", mandate=row.agreement, key=f"{row.name}|{begin}")
			frappe.db.set_value(MEMBER, row.name, "charge_asked_for", begin)
			asked += 1
		except Exception:
			frappe.db.rollback(save_point="renewal")
			frappe.log_error(frappe.get_traceback(), f"Renewal for {row.name} could not be asked")
	return asked


def check_agreements() -> int:
	"""Daily: a plan whose auto-pay agreement has ended stops renewing. Returns how many."""
	stopped = 0
	for row in frappe.get_all(MEMBER, filters={"status": "Active", "renews": 1, "agreement": ["is", "set"]}, fields=["name", "agreement"]):
		if _port().agreement_state(row.agreement) != "Active":
			frappe.db.set_value(MEMBER, row.name, "renews", 0)
			stopped += 1
	return stopped


def stop(user: str) -> dict:
	"""The person stops renewing. The plan stays to the end of the month they have paid for. Answers {"message"}."""
	member = frappe.db.get_value(MEMBER, user, ["status", "agreement", "period_end", "plan"], as_dict=True)
	if not member or member.status != "Active" or not member.agreement or not cint(frappe.db.get_value(MEMBER, user, "renews")):
		frappe.throw(_("You have no plan to stop."))
	_port().agreement_stop(member.agreement, "customer", _("The person stopped renewing"))
	frappe.db.set_value(MEMBER, user, {"renews": 0, "charge_asked_for": None})
	return {"message": _("Your {0} plan will not renew. It stays until {1}.").format(member.plan, frappe.utils.formatdate(member.period_end, "d MMMM"))}


def end_lapsed() -> int:
	"""Daily: a plan whose month ended is marked Ended (the person has the free plan until they take one again). Returns how many."""
	ended = 0
	for row in frappe.get_all(MEMBER, filters={"status": "Active", "period_end": ["<", getdate(today())]}, pluck="name"):
		frappe.db.set_value(MEMBER, row, "status", "Ended")
		ended += 1
	return ended


def daily() -> None:
	"""The scheduled job: agreements are checked, the next month asked for, and lapsed plans ended."""
	check_agreements()
	request_renewals()
	end_lapsed()
