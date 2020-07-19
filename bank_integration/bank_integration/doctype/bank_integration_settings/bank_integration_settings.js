// Copyright (c) 2018, Resilient Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bank Integration Settings', {
	onload(frm) {
		bi.listenForOtp(frm);
	},
	validate(frm) {
		if (frm.doc.disabled) return;
		frm._uid = frappe.utils.get_random(7);
		frm.call('check_credentials', {uid: frm._uid});
	}
});
