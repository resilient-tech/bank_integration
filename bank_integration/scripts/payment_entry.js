// Copyright (c) 2018, Resilient Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Payment Entry", {
    setup: function (frm) {
        frappe.realtime.on("bi_action", function (data) {

            switch (data.action) {
                case "show_message":
                    if(frm && frm._uid == data.uid){
                        frappe.update_msgprint(data.message);
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
                case "payment_success":
                    if (data.uid != frm._uid || frm.success_action_started) {
                        return;
                    }

                    frm.success_action_started = true;
                    frappe.update_msgprint("Payment successful!");
                    setTimeout(function () {
                        frappe.hide_msgprint();
                        frm.doc.reference_no = data.ref_no;
                        frm.reload_doc().then(()=>{
                            if (frm.doc.comm_email) {
                                let email_dialog = new frappe.views.CommunicationComposer({
                                    doc: frm.doc,
                                    frm: frm,
                                    subject: `Online Payment Processed (${frm.doc.name})`,
                                    recipients: frm.doc.comm_email,
                                    attach_document_print: true,
                                    message: `Hello,<br><br>
                                    A payment for ${fmt_money(frm.doc.paid_amount)} with Reference No. ${frm.doc.reference_no} has been made to your account on ${frappe.datetime.get_today()}. Enclosed is the payment note, with details of your invoices against which the said payment is made.<br><br>
                                    Feel free to get in touch with us if you have any queries or concerns.<br><br>
                                    Thank you for doing business with us. We look forward to your continued patronage in the future.<br><br>`,
                                });
                                
                            } else {
                                setup_sms(frm);
                                if (frm.sms_link) frm.sms_link.click();
                            }
                            delete frm.success_action_started;
                        })
                    }, 1000);
                    break;
            }
        });
    },

    onload: function (frm) {
        
        bi.listenForOtp(frm);
        bi.listenForQuestions(frm);

        $('input[data-fieldname="payment_desc"]').keypress(function (e) {
            var regex = new RegExp("^[a-zA-Z0-9 ]+$");
            var str = String.fromCharCode(!e.charCode ? e.which : e.charCode);
            if (regex.test(str)) {
                return true;
            }

            e.preventDefault();
            return false;
        });

    },

    payment_type: function (frm) {
        check_bank_integration(frm);
    },

    paid_from: function (frm) {
        check_bank_integration(frm);
    },

    party: function (frm) {
        set_bank_name_and_ac(frm);
        get_contact_data(frm);
    },

    pay_now: function (frm) {
        if (!frm.doc.paid_from_bank) {
            check_bank_integration(frm);
        }

        if (frm.doc.payment_type != "Pay") {
            return;
        }

        set_bank_name_and_ac(frm);
        get_contact_data(frm);

        if (frm.doc.pay_now) {
            frm.set_value("reference_no", "-");
            frm.set_value("reference_date", frappe.datetime.get_today());

            frm.toggle_reqd(
                ["party_bank_ac_no", "payment_desc", "transfer_type"],
                1,
            );
        } else {
            reset_fields(frm, "reference_no", "reference_date");
            frm.toggle_reqd(
                ["party_bank_ac_no", "payment_desc", "transfer_type"],
                0,
            );
        }
    },

    party_bank: async function (frm) {
        await set_transfer_type(frm);
    },

    paid_amount: async function (frm) {
        await set_transfer_type(frm);
    },

    payment_desc: function (frm) {
        frm.set_value(
            "payment_desc",
            frm.doc.payment_desc.replace(/[^a-zA-Z0-9 ]/gi, ""),
        );
    },

    transfer_type: function(frm){
        if (frm.doc.transfer_type && frm.doc.transfer_type.includes('Transfer to other bank')){
            frm.toggle_reqd('comm_type', 1);
            if(!frm.doc.comm_type){
                frm.set_value('comm_type', 'Email');
            }
        } else {
            frm.toggle_reqd("comm_type", 0);
            reset_fields(frm, "comm_type");
        }
    },

    comm_type: function (frm) {
        if (frm.doc.comm_type) {
            if (frm.doc.comm_type == "Email") {
                frm.toggle_reqd("comm_email", 1);
                frm.toggle_reqd("comm_mobile", 0);
            } else if (frm.doc.comm_type == "Mobile") {
                frm.toggle_reqd("comm_mobile", 1);
                frm.toggle_reqd("comm_email", 0);
            }
        } else {
            frm.toggle_reqd(["comm_email", "comm_mobile"], 0);
        }
    },

    validate: function (frm) {
        if (frm.doc.docstatus === 0) {
            if (frm.get_docfield("pay_now").hidden_due_to_dependency) {
                frm.set_value("pay_now", 0);
            } else if (frm.doc.pay_now && !frm.doc.online_payment_status) {
                frm.doc.online_payment_status = "Unpaid";
            }
        }
    },
    before_submit: function (frm) {
        if (frm.doc.pay_now && frm.doc.online_payment_status != "Paid") {
            frappe.throw({
                title: __("Warning"),
                message: __("Payment not made !"),
                indicator: "orange",
            });
        }
    },

    refresh: async function (frm) {
        if (frm.doc.docstatus === 0) {
            frm.fields_dict.payment_desc.$input[0].maxLength = 20;
            frm.fields_dict.comm_mobile.$input[0].maxLength = 10;
        }

        if (frm.doc.docstatus === 0 && !frm.doc.__unsaved) {
            if (frm.doc.pay_now && frm.doc.online_payment_status == "Unpaid") {

                await set_transfer_type(frm);

                frm.add_custom_button(__("Make Online Payment"), function () {
                    frappe.confirm(
                        `Are you sure you want to proceed with the following details? <br>
                    <br> Party's Bank Account No: <strong>${frm.doc.party_bank_ac_no}</strong>
                    <br> Transfer Type: <strong>${frm.doc.transfer_type}</strong>
                    <br> Amount Payable: <strong>${fmt_money(frm.doc.paid_amount)}</strong>
                    <br> Description: <strong>${frm.doc.payment_desc}</strong>`,
                        function () {
                            frm._uid = frappe.utils.get_random(7);

                            frappe.call({
                                method: "bank_integration.bank_integration.api.payments.make_payment",
                                args: {
                                    docname: frm.doc.name,
                                    uid: frm._uid,
                                },
                            });
                        },
                    );
                });
            }
        }

        setup_sms(frm);
    },
});

function setup_sms(frm) {
    if (frm.sms_setup_done) return;

    if (
        frm.doc.docstatus === 1 &&
        !in_list(["Cancelled", "Closed"], frm.doc.status) &&
        frm.doc.payment_type === "Pay"
    ) {
        frm.sms_setup_done = true;
        frm.sms_link = frm.page.add_menu_item("Send SMS", function () {
            var d = new frappe.ui.Dialog({
                title: "Send SMS",
                width: 400,
                fields: [
                    {
                        fieldname: "number",
                        fieldtype: "Data",
                        label: "Mobile Number",
                        reqd: 1,
                    },
                    {
                        fieldname: "message",
                        fieldtype: "Text",
                        label: "Message",
                        reqd: 1,
                    },
                    { fieldname: "send", fieldtype: "Button", label: "Send" },
                ],
            });

            d.fields_dict.send.input.onclick = function () {
                var btn = d.fields_dict.send.input;
                var v = d.get_values();

                if (v) {
                    $(btn).set_working();
                    frappe.call({
                        method: "frappe.core.doctype.sms_settings.sms_settings.send_sms",
                        args: {
                            receiver_list: [v.number],
                            msg: v.message,
                        },
                        callback: function (r) {
                            $(btn).done_working();
                            if (r.exc) {
                                frappe.msgprint(r.exc);
                                return;
                            }
                            d.hide();
                        },
                    });
                }
            };

            let paid_to_message = "you";
            if (frm.doc.pay_now) {
                paid_to_message =
                    `your ${frm.doc.party_bank.trim()} a/c ending **` +
                    frm.doc.party_bank_ac_no.slice(-4);
            }

            let allocation = [];
            for (let i of frm.doc.references) {
                if (i.reference_doctype === "Purchase Invoice" && i.bill_no) {
                    allocation.push(
                        i.bill_no +
                            ` (${i.allocated_amount} ${frm.doc.paid_to_account_currency})`,
                    );
                }
            }

            let allocation_message = "";
            if (allocation.length) {
                allocation_message = ` against Bill No${allocation.length > 1 ? "s" : ""}. ${allocation.join(", ")}`;
                if (
                    allocation.length === 1 &&
                    allocation_message.endsWith(")")
                ) {
                    allocation_message = allocation_message.slice(
                        0,
                        allocation_message.lastIndexOf(" ("),
                    );
                }
            }

            let mode = frm.doc.mode_of_payment || "Bank Transfer";
            mode = mode.replace("Wire Transfer", "Bank Transfer");

            let ref_message = ".";
            if (frm.doc.reference_no && frm.doc.reference_no.replace("-", "")) {
                ref_message = ` (Ref. No. ${frm.doc.reference_no})`;
            }

            let mobile_no = frm.doc.comm_mobile;
            if (!mobile_no && frm.doc.contact_person) {
                frappe.call({
                    method: "frappe.core.doctype.sms_settings.sms_settings.get_contact_number",
                    args: {
                        contact_name: frm.doc.contact_person,
                        ref_doctype: frm.doc.party_type,
                        ref_name: frm.doc.party,
                    },
                    callback: function (r) {
                        if (r.exc) {
                            frappe.msgprint(r.exc);
                            return;
                        }
                        mobile_no = r.message;
                    },
                });
            }

            d.set_values({
                number: mobile_no,
                message:
                    `An amount of ${frm.doc.paid_amount.toFixed(2)}` +
                    ` ${frm.doc.paid_to_account_currency} has been paid to ` +
                    paid_to_message +
                    allocation_message +
                    ` via ${mode}${ref_message}` +
                    `\n\n- ${frm.doc.company}`,
            });

            d.show();
        })
    }
}

function check_bank_integration(frm){
    if(frm.doc.payment_type == 'Pay' && frm.doc.paid_from) {
        frappe.db.get_value('Bank Account', {'account': frm.doc.paid_from}, ['name', 'bank'])
        .then(async (r) => {
            if(r.message){
                frm.set_value('paid_from_bank', r.message.bank ? r.message.bank : '');
                if (frm.doc.paid_from_bank) {
                    await set_transfer_type(frm);
                }

                frappe.db.get_value('Bank Integration Settings', {name: r.message.name, disabled: false}, 'name').then((r) => {
                    if (!r.message) {
                        disable_pay_now(frm);
                    } else {
                        frm.get_docfield('pay_now').read_only = 0;
                        frm.refresh_field('pay_now');
                    }
                });

            } else {
                reset_fields(frm, 'paid_from_bank');
                disable_pay_now(frm);
            }
        });
    }
}

function disable_pay_now(frm) {
    frm.set_value("pay_now", 0);
    frm.get_docfield("pay_now").read_only = 1;
    frm.refresh_field("pay_now");
}

function set_bank_name_and_ac(frm) {
    if (
        $.inArray(frm.doc.party_type, ["Supplier", "Customer", "Employee"]) !=
            -1 &&
        frm.doc.party &&
        frm.doc.pay_now
    ) {
        frappe.db
            .get_value(frm.doc.party_type, frm.doc.party, [
                "bank",
                "bank_ac_no",
            ])
            .then((r) => {
                frm.set_value(
                    "party_bank",
                    r.message.bank ? r.message.bank : "",
                );
                frm.set_value(
                    "party_bank_ac_no",
                    r.message.bank_ac_no ? r.message.bank_ac_no : "",
                );
            });
    } else {
        reset_fields(frm, "party_bank", "party_bank_ac_no");
    }
}

async function set_transfer_type(frm) {
    if (!frm.doc.paid_from_bank || !frm.doc.party_bank) {
        return reset_fields(frm, "transfer_type");
    }

    if (frm.doc.paid_from_bank === frm.doc.party_bank) {
        frm.set_df_property("transfer_type", "options", "Transfer within the bank");
        await frm.set_value("transfer_type", "Transfer within the bank");
        return;
    }

    let options = [
        "Transfer to other bank (NEFT)",
        "Transfer to other bank (IMPS)",
        ...(frm.doc.paid_amount >= 200000 ? ["Transfer to other bank (RTGS)"] : []),
    ];
    frm.set_df_property("transfer_type", "options", options.join("\n"));

    if (!options.includes(frm.doc.transfer_type)) {
        await frm.set_value("transfer_type", "Transfer to other bank (NEFT)");
    }
    frm.refresh_field("transfer_type");
}

function get_contact_data(frm) {
    if (
        frm.doc.party &&
        $.inArray(frm.doc.party_type, ["Supplier", "Customer", "Employee"]) !=
            -1
    ) {
        frappe.call({
            method: "bank_integration.bank_integration.get_contact_data.get_contact_data",
            args: {
                party_type: frm.doc.party_type,
                party: frm.doc.party,
                comm_type: frm.doc.comm_type,
            },
            callback: function (r) {
                if (r.message) {
                    if (r.message.email) {
                        frm.set_value("comm_email", r.message.email.trim());
                    }
                    if (r.message.mobile) {
                        frm.set_value(
                            "comm_mobile",
                            r.message.mobile.replace(/\s/g, "").slice(-10),
                        );
                    }
                }
            },
        });
    } else {
        reset_fields(frm, "comm_email", "comm_mobile");
    }
}

function reset_fields(frm, ...fields) {
    for (let field of fields) {
        frm.set_value(field, "");
    }
}
