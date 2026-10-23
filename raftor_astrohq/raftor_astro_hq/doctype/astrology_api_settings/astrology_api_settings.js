// Astrology API Settings: where the hub is, AstroHQ's key at the hub, and a check that the hub accepts it and the engine answers.
frappe.ui.form.on("Astrology API Settings", {
	refresh(frm) {
		const ready = frm.doc.enabled && frm.doc.hub_address;
		frm.dashboard.add_comment(
			ready ? __("Charts are available: AstroHQ asks the astrology engine through the hub.") : __("Charts are not available: AstroHQ does not ask the astrology engine anything."),
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
