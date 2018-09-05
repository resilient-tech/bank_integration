# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from .hdfc_bank_api import HDFCBankAPI

api_map = {
    "HDFC Bank": HDFCBankAPI,
}

def get_bank_api(bank_name, username, account_no):
    return api_map.get(bank_name)(username, account_no)