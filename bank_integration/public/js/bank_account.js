frappe.ui.form.on('Bank Account', {
	refresh: function (frm) {
		frm.add_custom_button(__('Fetch Trasactions'), function () {
			frm.trigger("fetch_transactions");
		});
	},

	fetch_transactions: function (frm) {
		var d = new frappe.ui.Dialog({
			title: __('Fetch Transactions'),
			fields: [
				{
					"label": "From Date",
					"fieldname": "from_date",
					"fieldtype": "Date",
					"reqd": 1
				},
				{
					"label": "Account",
					"fieldname": "from_account",
					"fieldtype": "Data",
					"default": frm.doc.account_name,
					"reqd": 1,
					"read_only": 1
				}
			],
			primary_action: function () {
				let data = d.get_values();
				frm._uid = frappe.utils.get_random(7);
				let payment_data = {
					from_account: data.from_account,
					from_date: data.from_date
				}

				frappe.call({
					method: "bank_integration.bank_integration.api.transactions.get_transactions",
					args: { docname: frm.doc.name, uid: frm._uid, data: payment_data },
					callback: function (r) {
						d.hide();
					}
				});
			},
			primary_action_label: __('Confirm')
		});
		d.show();
	}
});


// merge_account: function(frm) {
// 		var d = new frappe.ui.Dialog({
// 			title: __('Merge with Existing Account'),
// 			fields: [
// 				{
// 					"label" : "Name",
// 					"fieldname": "name",
// 					"fieldtype": "Data",
// 					"reqd": 1,
// 					"default": frm.doc.name
// 				}
// 			],
// 			primary_action: function() {
// 				var data = d.get_values();
// 				frappe.call({
// 					method: "erpnext.accounts.doctype.account.account.merge_account",
// 					args: {
// 						old: frm.doc.name,
// 						new: data.name,
// 						is_group: frm.doc.is_group,
// 						root_type: frm.doc.root_type,
// 						company: frm.doc.company
// 					},
// 					callback: function(r) {
// 						if(!r.exc) {
// 							if(r.message) {
// 								frappe.set_route("Form", "Account", r.message);
// 							}
// 							d.hide();
// 						}
// 					}
// 				});
// 			},
// 			primary_action_label: __('Merge')
// 		});
// 		d.show();
// 	},