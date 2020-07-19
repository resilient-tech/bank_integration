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
def continue_with_otp(otp, bank_name, uid, resume_info, doctype=None, docname=None, data=None, logged_in=0):
    logged_in = cint(logged_in)
    if data:
        data = frappe._dict(json.loads(data))

    bank = get_bank_api(bank_name, uid=uid, doctype=doctype, docname=docname, resume_info=json.loads(resume_info),
        data=data, logged_in=logged_in)

    if not logged_in:
        bank.continue_login(otp)
    else:
        bank.continue_payment(otp)

@frappe.whitelist()
def cancel_session(bank_name, resume_info, logged_in=0):
    logged_in = cint(logged_in)

    bank = get_bank_api(bank_name, resume_info=json.loads(resume_info), logged_in=logged_in)
    bank.logout()
