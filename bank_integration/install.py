# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property, setup_custom_perms

def after_install():
    make_custom_fields()
    make_property_setters()
    make_role_and_permissions()

def make_custom_fields():
    create_custom_fields(custom_fields)
    frappe.db.commit()

def make_property_setters():
    frappe.make_property_setter({
        'doctype': 'Employee',
        'fieldname': 'bank_ac_no',
        'property': 'permlevel',
        'value': 7,
        'property_type': 'Int'
    })
    frappe.db.commit()

def make_role_and_permissions():
    role_name = 'Bank Payments Manager'
    try:
        role = frappe.new_doc('Role')
        role.update({
            'role_name': role_name,
            'desk_access': 1
        })
        role.save()
    except frappe.DuplicateEntryError:
        pass

    frappe.reload_doc('bank_integration', 'doctype', 'bank_integration_settings')
    setup_custom_perms('Bank Integration Settings')

    for doctype in ['Employee', 'Customer', 'Supplier', 'Payment Entry']:
        add_permission(doctype, role_name, 7)
        update_permission_property(doctype, role_name, 7, 'write', 1)

    frappe.db.commit()


party_fields = [
    {
        'fieldname': 'bank',
        'label': 'Bank',
        'fieldtype': 'Link',
        'options': 'Bank',
        'insert_after': 'bank_details_section',
        'permlevel': 7
    },
    {
        'fieldname': 'bank_details_cb',
        'fieldtype': 'Column Break',
        'insert_after': 'bank',
    },

    {
        'fieldname': 'bank_ac_no',
        'label': 'Bank Account No',
        'fieldtype': 'Data',
        'insert_after': 'bank_details_cb',
        'permlevel': 7
    },
]

custom_fields = {
    'Supplier': [
        {
            'fieldname': 'bank_details_section',
            'label': 'Bank Details',
            'fieldtype': 'Section Break',
            'insert_after': 'accounts',
            'permlevel': 7
        }
    ] + party_fields,
    'Customer': [
        {
            'fieldname': 'bank_details_section',
            'label': 'Bank Details',
            'fieldtype': 'Section Break',
            'insert_after': 'payment_terms',
            'permlevel': 7
        }
    ] + party_fields,
    'Payment Entry': [
        {
            'fieldname': 'bank_payment_section',
            'label': 'Online Bank Payment',
            'fieldtype': 'Section Break',
            'depends_on': "eval:(doc.payment_type=='Pay' \
                && doc.mode_of_payment!='Cash' && doc.paid_from \
                && doc.party)",
            'insert_after': 'contact_email',
            'permlevel': 7
        },
        {
            'fieldname': 'pay_now',
            'label': 'Make Payment Now',
            'fieldtype': 'Check',
            'depends_on': "eval:(doc.payment_type=='Pay' \
                && doc.mode_of_payment!='Cash' && doc.paid_from \
                && doc.party)",
            'insert_after': 'bank_payment_section',
            'print_hide': 1,
            'permlevel': 7
        },
        {
            'fieldname': 'party_bank',
            'label': "Party's Bank",
            'fieldtype': 'Link',
            'options': 'Bank',
            'depends_on': "eval:doc.pay_now",
            'insert_after': 'pay_now',
            'print_hide': 1,
            'permlevel': 7
        },
        {
            'fieldname': 'party_bank_ac_no',
            'label': "Party's Bank Account No",
            'fieldtype': 'Data',
            'depends_on': "eval:doc.pay_now",
            'insert_after': 'party_bank',
            'print_hide': 1,
            'permlevel': 7
        },
        {
            'fieldname': 'online_payment_status',
            'label': "Payment Status",
            'fieldtype': 'Select',
            'options': '\nUnpaid\nPaid',
            'depends_on': "eval:(doc.pay_now && doc.creation)",
            'insert_after': 'party_bank_ac_no',
            'print_hide': 1,
            'read_only': 1,
            'permlevel': 7
        },
        {
            'fieldname': 'bank_payment_cb',
            'fieldtype': 'Column Break',
            'insert_after': 'online_payment_status',
        },
        {
            'fieldname': 'payment_desc',
            'label': 'Payment Description',
            'fieldtype': 'Data',
            'depends_on': "eval:doc.pay_now",
            'insert_after': 'bank_payment_cb',
            'print_hide': 1,
            'permlevel': 7
        },
        {
            'fieldname': 'transfer_type',
            'label': 'Bank Transfer Type',
            'fieldtype': 'Select',
            'options': '\nTransfer within the bank\nTransfer to other bank (NEFT)',
            'depends_on': "eval:doc.pay_now",
            'insert_after': 'payment_desc',
            'print_hide': 1,
            'permlevel': 7
        },
        {
            'fieldname': 'comm_type',
            'label': 'Communication Type',
            'fieldtype': 'Select',
            'options': '\nEmail\nMobile',
            'depends_on': "eval:(doc.pay_now \
                && doc.transfer_type=='Transfer to other bank (NEFT)')",
            'insert_after': 'transfer_type',
            'print_hide': 1,
            'permlevel': 7
        },
        {
            'fieldname': 'comm_email',
            'label': 'Email Address',
            'fieldtype': 'Data',
            'depends_on': "eval:(doc.pay_now \
                && doc.transfer_type=='Transfer to other bank (NEFT)' \
                && doc.comm_type=='Email')",
            'insert_after': 'comm_type',
            'print_hide': 1,
            'permlevel': 7
        },
        {
            'fieldname': 'comm_mobile',
            'label': 'Mobile Number',
            'fieldtype': 'Data',
            'depends_on': "eval:(doc.pay_now \
                && doc.transfer_type=='Transfer to other bank (NEFT)' \
                && doc.comm_type=='Mobile')",
            'insert_after': 'comm_email',
            'print_hide': 1,
            'permlevel': 7
        },
        {
            'fieldname': 'paid_from_bank',
            'fieldtype': 'Data',
            'hidden': 1,
            'insert_after': 'paid_from',
            'print_hide': 1,
            'permlevel': 7
        }
    ],
    'Employee': [
        {
            'fieldname': 'bank',
            'label': 'Bank',
            'fieldtype': 'Link',
            'options': 'Bank',
            'insert_after': 'bank_name',
            'permlevel': 7
        }
    ],
    'Bank Transaction': [
        {
            'fieldname': 'transaction_hash',
            'label': 'Transaction Hash',
            'fieldtype': 'Data',
            'hidden': 1,
            'print_hide': 1,
            'read_only': 1,
            'insert_after': 'date',
            'permlevel': 7
        },
        {
            'fieldname': 'closing_balance',
            'label': 'Closing Balance',
            'fieldtype': 'Currency',
            'in_list_view': 1,
            'insert_after': 'currency',
            'permlevel': 7
        }
    ]
}