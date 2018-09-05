# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from .api import get_bank_api

@frappe.whitelist()
def make_payment(from_account, to_account, transfer_type, amount, payment_desc, 
docname, comm_type=None, comm_value=None):
    bi_name = frappe.db.get_value('Bank Account', {'account': from_account}, 'name')
    bi = frappe.get_doc('Bank Integration', bi_name)

    frappe.emit_js("frappe.msgprint('Logging in...');")

    bank = get_bank_api(bi.bank_name, bi.username, bi.bank_account_no)
    bank.login(bi.get_password())

    bank.check_login()

    frappe.emit_js("frappe.update_msgprint('Login Successful! Processing payment...');")

    bank.make_payment(to_account, transfer_type, amount, payment_desc, docname, comm_type, comm_value)

@frappe.whitelist()
def continue_payment_with_otp(otp):
    bank = frappe._bank_session    
    bank.continue_payment_with_otp(otp)

@frappe.whitelist()
def cancel_payment():
    bank = frappe._bank_session    
    bank.logout()