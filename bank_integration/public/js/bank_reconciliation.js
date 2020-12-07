modifyMethod("erpnext.accounts.bankReconciliation", "make", function () {
    frappe.db.get_single_value('Global Defaults', 'default_company').then(function (default_company) {
        $("input[data-fieldname='company']").val(default_company)
    })
    $("input[data-fieldname='company']").focus()
});

modifyMethod("erpnext.accounts.bankReconciliation", "add_actions", function () {
    let me = cur_page.page
    me.bank_account = $("input[data-fieldname='bank_account']").val()

    frappe.db.get_value('Bank Integration Settings', me.bank_account, 'disabled').then(function (data) {
        me.page.add_inner_button(__('Sync Transactions'), function () {
            frappe.confirm(`Sync Transactions for <strong>${me.bank_account}</strong> ?`,
                function () {
                    me.uid = frappe.utils.get_random(7);
                    frappe.call({
                        method: "bank_integration.bank_integration.api.transactions.get_transactions",
                        args: { uid: me.uid, from_account: me.bank_account },
                    });
                    frappe.msgprint("Syncing Transactions&ensp; <i class='fa fa-refresh fa-spin'></i>")
                    $("span[data-label='Reconcile this account']").parent().click()
                });
        });
        $(`button[data-label='${encodeURIComponent(__('Sync Transactions'))}']`).parent().hide()
        if (data.message.disabled == 0) {
           $(`button[data-label='${encodeURIComponent(__('Sync Transactions'))}']`).parent().show()

        }
        else {
            $(`button[data-label='${encodeURIComponent(__('Sync Transactions'))}']`).parent().hide()
        }
        frappe.realtime.on("sync_transactions", function (data) {
            $("button[data-label='Refresh']").click()
            if (data.uid != me.uid) {
                return;
            }
            frappe.update_msgprint(`Synced <strong>${data.count}</strong> Transaction${(data.count == 1) ? "" : "s"} from <strong>${data.after_date}</strong>.`)
        });
    });
});


modifyMethod("erpnext.accounts.bankReconciliation", "make_reconciliation_tool", function () {
    me = cur_page.page
    me.bank_account = $("input[data-fieldname='bank_account']").val()

    me.page.add_inner_button(__('Auto Reconcile'), function () {
        frappe.confirm(`Are you sure that you want to Auto Reconcile all Bank Transactions ?`,
            function () {
                me.uid = frappe.utils.get_random(7);
                frappe.call({
                    method: "bank_integration.bank_integration.api.auto_reconcile.reconcile_transactions",
                    args: { uid: me.uid, bank_account: me.bank_account },
                });
            frappe.msgprint("Reconciling Transactions&ensp; <i class='fa fa-refresh fa-spin'></i>")
            }
        );
    });

    frappe.realtime.on("auto_reconcile", function (data) {
        $("button[data-label='Refresh']").click()
        if (data.uid != me.uid) {
            return;
        }
        frappe.update_msgprint(`Reconciled <strong>${data.count}</strong> Transaction${(data.count == 1) ? "" : "s"}.`)
    });
});
