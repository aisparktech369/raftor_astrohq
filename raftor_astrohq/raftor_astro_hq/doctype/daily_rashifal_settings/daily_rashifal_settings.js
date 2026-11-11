// Daily Rashifal Settings: the writer, and two buttons: write today's readings now, publish today's drafts.
frappe.ui.form.on("Daily Rashifal Settings", {
	async write_today(frm) {
		if (frm.is_dirty()) await frm.save();
		const { message } = await frm.call("write_today");
		frappe.show_alert({ message: message.message, indicator: message.ok ? "green" : "orange" }, 10);
	},
	async publish_drafts(frm) {
		const { message } = await frm.call("publish_drafts");
		frappe.show_alert({ message: message.message, indicator: "green" }, 7);
	},
});
