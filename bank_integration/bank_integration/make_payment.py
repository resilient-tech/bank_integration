# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from bank_integration.bank_integration.api import get_bank_api

@frappe.whitelist()
def make_payment(from_account, to_account, transfer_type, amount, payment_desc,
docname, payment_uid, comm_type=None, comm_value=None):
    def emit_js(js):
        js = "if (cur_frm.payment_uid === '{0}') {{ {1} }}".format(payment_uid, js)
        frappe.emit_js(js, doctype="Payment Entry", docname=docname)

    bi_name = frappe.db.get_value('Bank Account', {'account': from_account}, 'name')
    bi = frappe.get_doc('Bank Integration Settings', bi_name)

    emit_js("frappe.msgprint('Logging in...');")

    bank = get_bank_api(bi.bank_name, bi.username, bi.bank_account_no)
    bank.login(bi.get_password())

    bank.check_login()

    emit_js("frappe.update_msgprint('Login Successful! Processing payment...');")

    if comm_value:
        comm_value = comm_value.replace(" ", "")

    bank.make_payment(to_account, transfer_type, amount, payment_desc, docname,
        payment_uid, comm_type, comm_value)

@frappe.whitelist()
def continue_payment_with_otp(otp, payment_uid):
    bank = frappe._bank_session[payment_uid]
    bank.continue_payment_with_otp(otp)

@frappe.whitelist()
def cancel_payment(payment_uid):
    bank = frappe._bank_session[payment_uid]
    bank.logout()
