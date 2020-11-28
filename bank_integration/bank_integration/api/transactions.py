# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json

import frappe
from bank_integration.bank_integration.api import get_bank_api

from bank_integration.bank_integration.api.hdfc_bank_api import HDFCBankAPI


@frappe.whitelist()
def get_transactions(docname, uid, data):

    data = frappe._dict(json.loads(data))

    bi_name = "HDFC - HDFC Bank"
    bi_name = frappe.db.get_value(
        "Bank Account", {"account_name": data.from_account}, "name"
    )
    bi = frappe.get_doc("Bank Integration Settings", bi_name)
    data.from_account = bi.bank_account_no

    bank = get_bank_api(
        bi.bank_name,
        bi.username,
        bi.get_password(),
        doctype="Bank Account",
        docname=docname,
        uid=uid,
        data=data,
    )
