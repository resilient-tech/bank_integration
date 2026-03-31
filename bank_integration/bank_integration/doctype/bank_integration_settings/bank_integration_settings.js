// Copyright (c) 2018, Resilient Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bank Integration Settings', {
	setup(frm) {
		frappe.realtime.on("bi_action", function(data){
			switch(data.action){
				case "show_message":
                    if(frm && frm._uid == data.uid){
                        frappe.update_msgprint(data.message);
                    }
                    break;
				case "login_success":
					if(frm && frm._uid == data.uid){
						setTimeout(() => {
							frappe.hide_msgprint();
						}, 2000);
					}
					break;
				case "reload_doc":
					
                    if(frm && frm._uid == data.uid){
                        if (frm.docname == data.docname) {
							frappe.hide_msgprint()
                            frm.reload_doc();
                        }
                    }
                    break;
			}
		});
	},
	onload(frm) {
		bi.listenForOtp(frm);
		bi.listenForQuestions(frm);
	},
	async validate(frm) {
		frm._uid = frappe.utils.get_random(7);
		let bank_integrations = await frappe.db.get_list(
			"Bank Integration Settings",
			{
				fields: ["name"],
				filters: {
            		bank_account_no: frm.doc.bank_account_no,
            		name: ["!=", frm.doc.name],
        		}
			}
		);
		if (bank_integrations.length > 0) {
			if (bank_integrations[0].name !== frm.doc.name) {
				frm.reload_doc();
				frappe.throw(__("Only one Bank Integration for a bank account can exist."));
			}
		}
		if(!frm.doc.disabled){
			frm.call("check_credentials", { uid: frm._uid });
		}
	}
});
