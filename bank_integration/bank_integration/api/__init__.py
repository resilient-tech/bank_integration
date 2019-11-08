# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from bank_integration.bank_integration.api.hdfc_bank_api import HDFCBankAPI

api_map = {
    "HDFC Bank": HDFCBankAPI,
}

def get_bank_api(bank_name=None, api_name=None):
    if api_name:
        return globals()[api_name]()

    elif bank_name:
        return api_map.get(bank_name)()
