frappe.ui.form.on("Bank Reconciliation Tool", {
    refresh: function(frm) {
        frm.add_custom_button(__("Sync Transactions"), () => {
            frappe.confirm(`Sync Transactions for <strong>${frm.doc.bank_account}</strong> ?`, () => {
                frm.doc.uid = frappe.utils.get_random(7);
                frappe.call({
                    method: "bank_integration.bank_integration.api.transactions.get_transactions",
                    args: { uid: frm.doc.uid, from_account: frm.doc.bank_account },
                });
                frappe.msgprint("Syncing Transactions&ensp; <i class='fa fa-refresh fa-spin'></i>")
                frappe.realtime.on("sync_transactions", function (data) {
                    if (data.uid != frm.doc.uid) return;
                    frappe.update_msgprint(
                        `Synced <strong>${data.count}</strong> Transaction${(data.count == 1) ? "" : "s"} from <strong>${data.after_date}</strong>.`
                    )
                    frm.set_value("bank_statement_closing_balance", data.closing_balance);
                    frm.save();
                    frm.trigger("make_reconciliation_tool");
                });
            });
        })
        frm.add_custom_button(__("Auto Reconcile"), () => {
            frappe.confirm(`Are you sure that you want to Auto Reconcile all Bank Transactions ?`, () => {
                    frm.doc.uid = frappe.utils.get_random(7);
                    frappe.call({
                        method: "bank_integration.bank_integration.api.auto_reconcile.reconcile_transactions",
                        args: { uid: frm.doc.uid, bank_account: frm.doc.bank_account },
                    });
                frappe.msgprint("Reconciling Transactions&ensp; <i class='fa fa-refresh fa-spin'></i>")
                }
            );
            frappe.realtime.on("auto_reconcile", function (data) {
                if (data.uid != frm.doc.uid) return;
                frappe.update_msgprint(`Reconciled <strong>${data.count}</strong> Transaction${(data.count == 1) ? "" : "s"}.`)
                frm.trigger("make_reconciliation_tool");
            });
        });
        frm.page.hide_menu();
    }
})
