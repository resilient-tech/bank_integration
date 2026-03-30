frappe.listview_settings["Payment Entry"] = {
    add_fields: [
        "party_name",
        "transfer_type",
        "payment_type",
        "payment_desc",
        "online_payment_status",
        "party_bank_ac_no",
        "party_bank",
        "pay_now",
        "paid_from",
        "paid_amount",
    ],
    onload(listview) {


        frappe.realtime.on("bi_action", function (data) {
            switch (data.action) {
                case "bulk_payment_completed":
                    if(listview && listview._uid == data.uid){
                        setTimeout(() => {
                            frappe.hide_msgprint();
                            listview.refresh();
                            listview.clear_checked_items();
                        }, 4000);
                    }
                    break;
                case "show_message":
                    if(listview && listview._uid == data.uid){
                        frappe.update_msgprint(data.message);
                    }
                    break;
                case "reload_doc":
                    if(listview && listview._uid == data.uid){
				    		frappe.hide_msgprint()
                            listview.refresh();
                    }
                    break;
                case "payment_success_bulk":
                    if (!listview || listview._uid !== data.uid) return;
                        frappe.update_msgprint(`Payment completed for the following Payment Entry:<br>
                        <strong>Payment Entry ID:</strong> ${data.docname}<br>
                        <strong>Party's Name:</strong> ${data.party_name}<br>
                        <strong>Amount:</strong> ${fmt_money(data.paid_amount)}<br>
                        <strong>Payment Reference No.:</strong> ${data.ref_no}<br>
                        <strong>Payment Proof:</strong> You can find the payment proof attached within this Payment Entry document.<br><br>
                        ${data.is_last ? "All payments are completed." : "Proceeding to next payment..."}<br>`);
                    break;
                }
        });         
        bi.listenForOtp(listview, true);
        listview.page.add_action_item("Process Bulk Payments", async () => {
            const selected_docs = listview.get_checked_items();

            if (!selected_docs.length) {
                frappe.msgprint("Please select at least one Payment Entry.");
                return;
            }
            let ineligible_docs = [];
            const eligible_docs = selected_docs.filter((d) => {
                if (
                    cint(d.docstatus) === 1 ||
                    cint(d.docstatus) === 2 ||
                    d.payment_type !== "Pay" ||
                    cint(d.pay_now) !== 1 ||
                    d.online_payment_status !== "Unpaid"
                ) {
                    ineligible_docs.push(d.name);
                    return false;
                }
                return (
                    cint(d.docstatus) === 0 &&
                    d.payment_type === "Pay" &&
                    cint(d.pay_now) === 1 &&
                    d.online_payment_status === "Unpaid"
                );
            });

            if (ineligible_docs.length) {
                frappe.msgprint(
                    `The following Payment Entries are ineligible for payment processing<br>Please select only unpaid draft Payment Entries with Pay Now enabled.<br><br><strong>- ${ineligible_docs.join("<br>- ")}</strong>`,
                );
                return;
            }

            if (!eligible_docs.length) {
                frappe.msgprint(
                    "No eligible rows found. Select unpaid draft Payment entries with Pay Now enabled.",
                );
                return;
            }

            if (eligible_docs.length > 500) {
                frappe.msgprint(
                    "You can process a maximum of 500 Payment Entries at once. Please select fewer entries and try again.",
                );
                return;
            }

            let confirm_msg = `Are you sure you want to proceed with ${eligible_docs.length > 1 ? "these" : "this"} ${eligible_docs.length} payments?<br><br>`;
            eligible_docs.map((d, idx) => {
                let msg = `Party's Bank Account No: <strong>${d.party_bank_ac_no}</strong>
                    <br> Party's Name: <strong>${d.party_name}</strong>
                    <br> Transfer Type: <strong>${d.transfer_type}</strong>
                    <br> Amount Payable: <strong>${fmt_money(d.paid_amount)}</strong>
                    <br> Description: <strong>${d.payment_desc}</strong>
                    ${idx != eligible_docs.length - 1 ? "<hr>" : ""}`;
                confirm_msg += msg;
            });

            listview._uid = frappe.utils.get_random(7);
            frappe.confirm(confirm_msg, async () => {
                const docname_list = eligible_docs.map((d) => {
                    return d.name;
                });

                await frappe.call({
                    method: "bank_integration.bank_integration.api.payments.make_bulk_payment",
                    args: { docname_list, uid: listview._uid },
                });
            });
        });

    },
};
