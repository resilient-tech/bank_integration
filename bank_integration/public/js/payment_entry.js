// Copyright (c) 2018, Resilient Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on('Payment Entry', {
	onload: function(frm) {
        frappe.realtime.on("get_otp", function(data){
            if (data.payment_uid != frm.payment_uid) {
                return;
            }

            frappe.hide_msgprint();
            var otp_dialog = frappe.prompt(
                {fieldtype: 'Data', label: 'One Time Password',
                 fieldname: 'otp', reqd: 1,
                 description: `A one time password has been sent to your Mobile
                 Number <strong>${data.mobile_no}</strong> for further authentication.`},
            function(data){
                frappe.call({
                    method: "bank_integration.bank_integration.make_payment.continue_payment_with_otp",
                    args: {otp: data.otp, payment_uid: frm.payment_uid},
                });
            }, 'Enter OTP');
            otp_dialog.set_secondary_action(function(){
                frappe.call({
                    method: "bank_integration.bank_integration.make_payment.cancel_payment",
                    args: {payment_uid: frm.payment_uid}
                });
            });
        });

        $('input[data-fieldname="payment_desc"]').keypress(function (e) {
            var regex = new RegExp("^[a-zA-Z0-9 ]+$");
            var str = String.fromCharCode(!e.charCode ? e.which : e.charCode);
            if (regex.test(str)) {
                return true;
            }

            e.preventDefault();
            return false;
        });

        frappe.realtime.on('payment_success', function(data){
            if (data.payment_uid != frm.payment_uid) {
                return;
            }

            frappe.update_msgprint('Payment successful!');
            setTimeout(function() {
                frappe.hide_msgprint();
                frm.doc.remarks = '';
                frm.doc.online_payment_status = 'Paid';
                frm.doc.reference_no = data.ref_no;
                frm.refresh();
                frm.save().then(function(){
                    frm.savesubmit();
                });
            }, 1000);
        });
    },

    payment_type: function(frm){
        check_bank_integration(frm);
    },

    paid_from: function(frm) {
        check_bank_integration(frm);
    },

    party: function(frm) {
        set_bank_name_and_ac(frm);
    },

    pay_now: function(frm) {
        if (!frm.doc.paid_from_bank) {
            check_bank_integration(frm);
        }

        if (frm.doc.payment_type != 'Pay'){
            return;
        }
        set_bank_name_and_ac(frm);
        if (frm.doc.pay_now) {
            // Set reference details
            frm.set_value('reference_no', '-');
            frm.set_value('reference_date', frappe.datetime.get_today());

            // Set mandatory
            frm.toggle_reqd(['party_bank_ac_no', 'payment_desc', 'transfer_type'], 1)
        } else {
            reset_fields(frm, 'reference_no', 'reference_date');
            frm.toggle_reqd(['party_bank_ac_no', 'payment_desc', 'transfer_type'], 0)
        }
    },

    party_bank: function(frm){
        set_transfer_type(frm);
    },

    payment_desc: function(frm){
        frm.set_value('payment_desc', frm.doc.payment_desc.replace(/[^a-zA-Z0-9 ]/gi, ''));
    },

    transfer_type: function(frm){
        if (frm.doc.transfer_type == 'Transfer to other bank (NEFT)'){
            frm.toggle_reqd('comm_type', 1);
            frm.set_value('comm_type', 'Email');
        } else {
            frm.toggle_reqd('comm_type', 0);
            reset_fields(frm, 'comm_type');
        }
    },

    comm_type: function(frm) {
        if(frm.doc.comm_type){
            get_contact_data(frm);
            if (frm.doc.comm_type == 'Email'){
                frm.toggle_reqd('comm_email', 1);
                frm.toggle_reqd('comm_mobile', 0);
            } else if (frm.doc.comm_type == 'Mobile'){
                frm.toggle_reqd('comm_mobile', 1);
                frm.toggle_reqd('comm_email', 0);
            }
        } else {
            frm.toggle_reqd(['comm_email', 'comm_mobile'], 0);
        }
    },

    validate: function(frm) {
        if (frm.doc.docstatus === 0){
            if (frm.get_docfield('pay_now').hidden_due_to_dependency){
                frm.set_value('pay_now', 0);
            } else if (frm.doc.pay_now && !frm.doc.online_payment_status) {
                frm.doc.online_payment_status = 'Unpaid';
            }
        }
    },

    refresh: function(frm) {
        frm.fields_dict.payment_desc.$input[0].maxLength = 20;
        frm.fields_dict.comm_mobile.$input[0].maxLength = 10;

        if (frm.doc.docstatus === 0 && !frm.doc.__unsaved){
            if (frm.doc.pay_now && frm.doc.online_payment_status == 'Unpaid'){
                var comm_value = '';
                if (frm.doc.comm_type == 'Email') {
                    comm_value = frm.doc.comm_email;
                } else if (frm.doc.comm_type == 'Mobile') {
                    comm_value = frm.doc.comm_mobile;
                }

                frm.add_custom_button(__('Make Online Payment'), function() {
                    frappe.confirm(`Are you sure you want to proceed with the following details? <br>
                    <br> Party's Bank Account No: <strong>${frm.doc.party_bank_ac_no}</strong>
                    <br> Transfer Type: <strong>${frm.doc.transfer_type}</strong>
                    <br> Amount Payable: <strong>${frm.doc.paid_amount}</strong>
                    <br> Description: <strong>${frm.doc.payment_desc}</strong>`,
                    function() {
                        frm.payment_uid = frappe.utils.get_random(7);

                        frappe.call({
                            method: "bank_integration.bank_integration.make_payment.make_payment",
                            args: {from_account: frm.doc.paid_from, to_account: frm.doc.party_bank_ac_no,
                                transfer_type: frm.doc.transfer_type, amount: frm.doc.paid_amount,
                                payment_desc: frm.doc.payment_desc, docname: frm.doc.name,
                                comm_type: frm.doc.comm_type, comm_value: comm_value,
                                payment_uid: frm.payment_uid},
                        });
                    });
                });

            }
        }
    }

});

function check_bank_integration(frm){
    if(frm.doc.payment_type == 'Pay' && frm.doc.paid_from) {
        frappe.db.get_value('Bank Account', {'account': frm.doc.paid_from}, ['name', 'bank'])
        .then((r) => {
            if(r.message){
                frm.set_value('paid_from_bank', r.message.bank ? r.message.bank : '');
                if (frm.doc.paid_from_bank) {
                    set_transfer_type(frm);
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
    frm.set_value('pay_now', 0);
    frm.get_docfield('pay_now').read_only = 1;
    frm.refresh_field('pay_now');
}

function set_bank_name_and_ac(frm) {
    if($.inArray(frm.doc.party_type, ['Supplier', 'Customer', 'Employee']) != -1 &&
        frm.doc.party && frm.doc.pay_now) {
            frappe.db.get_value(frm.doc.party_type, frm.doc.party, ['bank', 'bank_ac_no'])
            .then((r) => {
                frm.set_value('party_bank', r.message.bank ? r.message.bank : '');
                frm.set_value('party_bank_ac_no', r.message.bank_ac_no ? r.message.bank_ac_no : '');
            });
    } else {
        reset_fields(frm, 'party_bank', 'party_bank_ac_no');
    }
}

function set_transfer_type(frm) {
    if(frm.doc.paid_from_bank && frm.doc.party_bank) {
        if(frm.doc.paid_from_bank == frm.doc.party_bank){
            frm.set_value('transfer_type', 'Transfer within the bank');
        } else {
            frm.set_value('transfer_type', 'Transfer to other bank (NEFT)');
        }
    } else {
        reset_fields(frm, 'transfer_type');
    }
}

function get_contact_data(frm) {
    if(frm.doc.party && frm.doc.comm_type &&
    $.inArray(frm.doc.party_type, ['Supplier', 'Customer', 'Employee']) != -1){
        frappe.call({
			method: "bank_integration.bank_integration.get_contact_data.get_contact_data",
            args: {party_type: frm.doc.party_type, party: frm.doc.party,
                comm_type: frm.doc.comm_type},
			callback: function(r){
				if (r.message) {
                    if (frm.doc.comm_type == 'Email'){
                        frm.set_value('comm_email', r.message);
                    } else if (frm.doc.comm_type == 'Mobile'){
                        frm.set_value('comm_mobile', r.message.replace(/\s/g,'').slice(-10));
                    }
                }
			},
		});
    } else {
        reset_fields(frm, 'comm_email', 'comm_mobile');
    }
}

function reset_fields() {
    var frm = arguments[0];
    for(var i=1; i<arguments.length; i++) {
        frm.set_value(arguments[i], '')
    }
}