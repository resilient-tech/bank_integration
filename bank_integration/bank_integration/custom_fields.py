# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def make_custom_fields():
    party_fields = [
        {
            'fieldname': 'bank',
            'label': 'Bank',
            'fieldtype': 'Link',
            'options': 'Bank',
            'insert_after': 'bank_details_section',
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
        },
    ]

    custom_fields = {
        'Supplier': [
            {
                'fieldname': 'bank_details_section',
                'label': 'Bank Details',
                'fieldtype': 'Section Break',
                'insert_after': 'accounts',
            }
        ] + party_fields,
        'Customer': [
            {
                'fieldname': 'bank_details_section',
                'label': 'Bank Details',
                'fieldtype': 'Section Break',
                'insert_after': 'payment_terms',
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
            },
            {
                'fieldname': 'party_bank',
                'label': "Party's Bank",
                'fieldtype': 'Link',
                'options': 'Bank',
                'depends_on': "eval:doc.pay_now",
                'insert_after': 'pay_now',
                'print_hide': 1,
            },
            {
                'fieldname': 'party_bank_ac_no',
                'label': "Party's Bank Account No",
                'fieldtype': 'Data',
                'depends_on': "eval:doc.pay_now",
                'insert_after': 'party_bank',
                'print_hide': 1,
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
            },
            {
                'fieldname': 'transfer_type',
                'label': 'Bank Transfer Type',
                'fieldtype': 'Select',
                'options': '\nTransfer within the bank\nTransfer to other bank (NEFT)',
                'depends_on': "eval:doc.pay_now",
                'insert_after': 'payment_desc',
                'print_hide': 1,
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
            },
            {
                'fieldname': 'paid_from_bank',
                'fieldtype': 'Data',
                'hidden': 1,
                'insert_after': 'paid_from',
                'print_hide': 1,
            }
        ]
    }

    create_custom_fields(custom_fields)