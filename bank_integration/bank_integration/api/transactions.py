# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from bank_integration.bank_integration.api import get_bank_api

from bank_integration.bank_integration.api.hdfc_bank_api import HDFCBankAPI


@frappe.whitelist()
def get_transactions(uid, from_account):
    bi = frappe.get_doc("Bank Integration Settings", from_account)
    account_name = frappe.get_value("Bank Account", from_account, "account_name")
    data = frappe._dict(
        {
            "bank_account": from_account,
            "from_account": account_name,
            "from_account_no": bi.bank_account_no,
        }
    )

    bank = get_bank_api(
        bi.bank_name,
        bi.username,
        bi.get_password(),
        doctype="Bank Account",
        uid=uid,
        data=data,
    )
