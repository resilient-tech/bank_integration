frappe.ui.form.on('Bank Account', {
	refresh: function (frm) {
		frm.add_custom_button(__('Fetch Trasactions'), function () {
			frappe.confirm(`Are you sure you want to proceed? <br>`,
				function () {
					frm._uid = frappe.utils.get_random(7);
					let payment_data = {
						from_account: frm.doc.account_name,
					}

					frappe.call({
						method: "bank_integration.bank_integration.api.transactions.get_transactions",
						args: { docname: frm.doc.name, uid: frm._uid, data: payment_data },
					});
				});

		});
	}
});
