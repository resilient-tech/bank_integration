# -*- coding: utf-8 -*-
# Copyright (c) 2018, Resilient Tech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from bank_integration.bank_integration.custom_fields import make_custom_fields

def execute():
    make_custom_fields()
