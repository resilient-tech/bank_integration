frappe.ui.form.on("Bank Reconciliation Tool", {
    refresh: function(frm) {
        frm.add_custom_button(__("Sync Transactions"), () => {
                frappe.confirm(`Sync Transactions for <strong>${frm.doc.bank_account}</strong> using HDFC Netbanking Statement download?`, () => {
                frm._uid = frappe.utils.get_random(7);
                frappe.call({
                    method: "bank_integration.bank_integration.api.transactions.get_transactions",
                    args: { uid: frm._uid, from_account: frm.doc.bank_account ,from_date: frm.doc.bank_statement_from_date, to_date: frm.doc.bank_statement_to_date},
                });
                show_msg("Syncing Transactions&ensp; <i class='fa fa-refresh fa-spin'></i>")
            });
        })
        frm.add_custom_button(__("Auto Reconcile"), () => {
            frappe.confirm(`Are you sure that you want to Auto Reconcile all Bank Transactions ?`, () => {
                    frm._uid = frappe.utils.get_random(7);
                    frappe.call({
                        method: "bank_integration.bank_integration.api.auto_reconcile.reconcile_transactions",
                        args: { uid: frm._uid, bank_account: frm.doc.bank_account },
                    });
                frappe.msgprint("Reconciling Transactions&ensp; <i class='fa fa-refresh fa-spin'></i>")
                }
            );

        });
        frm.page.hide_menu();
    },

    onload: function(frm){
        frm.toggle_reqd(["bank_statement_to_date","bank_statement_from_date","bank_account"],1)
        let today = frappe.datetime.get_today();
        let yesterday = frappe.datetime.add_days(today, -1);
        frm.set_value("bank_statement_to_date",yesterday);

        bi.listenForOtp(frm);
        frappe.realtime.on("show_alert", (data)=>show_msg(data.message))
        frappe.realtime.on("bi_action",(data)=>{
            if(data.uid != frm._uid) return;
            if(data.action=="show_message"){
                show_msg(data.message);
            }
        })
        frappe.realtime.on("sync_transactions", function (data) {
            if (data.uid != frm._uid) return;
            frappe.msgprint(
                `Synced <strong>${data.count}</strong> Transaction${(data.count == 1) ? "" : "s"} from <strong>${data.after_date}</strong>.`
            )
            if (data.count) {
                frm.set_value("bank_statement_closing_balance", data.closing_balance);
            }
            frm.save();
            frm.trigger("make_reconciliation_tool");
        });
        frappe.realtime.on("auto_reconcile", function (data) {
            if (data.uid != frm._uid) return;
            frappe.update_msgprint(`Reconciled <strong>${data.count}</strong> Transaction${(data.count == 1) ? "" : "s"}.`)
            frm.trigger("make_reconciliation_tool");
        });

        
    },
    bank_statement_from_date: function(frm) {
        validate_date(frm, "bank_statement_from_date");
    },
    bank_statement_to_date: function(frm) {
        validate_date(frm, "bank_statement_to_date");
    }
})


function show_msg(message){
    frappe.show_alert({
        message,
        indicator:"green"}, 5);
}

function validate_date(frm, changed_field) {
    const date = frm.doc[changed_field];
    if (!date) return; 

    const today = frappe.datetime.get_today();
    const from_date = frm.doc.bank_statement_from_date;
    const to_date = frm.doc.bank_statement_to_date;

    if (date && date >= today) {
        frm.set_value(changed_field, "");
        const label = changed_field === "bank_statement_from_date" ? __("From Date") : __("To Date");
        frappe.msgprint(`${label} ${__("must be before today.")}`)
        return;
    }

    if (from_date && to_date && from_date > to_date) {
        frm.set_value(changed_field, "");
        frappe.msgprint(
            changed_field === "bank_statement_from_date"
                ? __("From Date cannot be greater than To Date.")
                : __("To Date cannot be less than From Date.")
        );
        return;
    }

    if (from_date && to_date) {
        frm.trigger("make_reconciliation_tool");
    }
}