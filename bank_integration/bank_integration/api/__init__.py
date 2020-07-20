# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.utils import cint

from bank_integration.bank_integration.api.hdfc_bank_api import HDFCBankAPI

api_map = {
    "HDFC Bank": HDFCBankAPI,
}

def get_bank_api(bank_name, *args, **kwargs):
    return api_map.get(bank_name)(*args, **kwargs)

@frappe.whitelist()
def continue_with_otp(otp, bank_name, uid, doctype=None, docname=None, logged_in=0):
    logged_in = cint(logged_in)

    bank = get_bank_api(bank_name, uid=uid, doctype=doctype, docname=docname, logged_in=logged_in, resume=True)

    if not logged_in:
        bank.continue_login(otp)
    else:
        bank.continue_payment(otp)

@frappe.whitelist()
def continue_with_answers(answers, bank_name, uid, doctype=None, docname=None, logged_in=0):
    logged_in = cint(logged_in)
    answers = frappe._dict(json.loads(answers))

    bank = get_bank_api(bank_name, uid=uid, doctype=doctype, docname=docname, logged_in=logged_in, resume=True)

    if not logged_in:
        bank.continue_login(answers=answers)
    else:
        bank.continue_payment(answers=answers)

@frappe.whitelist()
def cancel_session(bank_name, uid, logged_in=0):
    logged_in = cint(logged_in)

    bank = get_bank_api(bank_name, uid=uid, logged_in=logged_in, resume=True)
    bank.logout()
