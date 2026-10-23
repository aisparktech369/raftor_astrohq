// Astrology API Settings: how AstroHQ reaches the astrology API (through the hub, or straight), where it is, AstroHQ's key, and a check that the key is accepted and the engine answers.
frappe.ui.form.on("Astrology API Settings", {
	refresh(frm) {
		const ready = frm.doc.enabled && frm.doc.hub_address;
		const way = frm.doc.how === "Straight to the astrology API" ? __("straight to the astrology API") : __("through the hub");
		frm.dashboard.add_comment(
			ready ? __("Charts are available: AstroHQ asks the astrology engine {0}.", [way]) : __("Charts are not available: AstroHQ does not ask the astrology engine anything."),
			ready ? "green" : "orange",
			true
		);
	},
	async check_connection(frm) {
		if (frm.is_dirty()) await frm.save();
		const { message: result } = await frm.call("check_connection");
		frappe.show_alert({ message: result.message, indicator: result.ok ? "green" : "red" }, 10);
		frm.reload_doc();
	},
});
